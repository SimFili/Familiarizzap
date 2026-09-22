from __future__ import annotations

import html
import json
from pathlib import Path

import pytest

import app
import src.feedback as feedback_module
from src.catalog import Catalog, PILOT_CEFR_LEVELS
from src.event_store import LocalEventStore
from src.feedback import DESCRIPTOR_GUIDES, compose_feedback
from src.guided_track import (
    CANONICAL_LEVELS,
    GUIDED_STAGES,
    guided_general_descriptors,
    guided_progress,
    stage_descriptors,
)
from src.session_service import SessionService


CATALOG_PATH = Path(__file__).resolve().parents[1] / "space/data/catalog.full.json"


def guided_catalog() -> Catalog:
    rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return Catalog(
        [*rows, *guided_general_descriptors()],
        allowed_statuses=("approved", "guided_draft"),
        allowed_levels=PILOT_CEFR_LEVELS,
    )


def test_four_stages_use_four_distinct_canonical_descriptors_and_checked_guides():
    catalog = guided_catalog()
    assert [stage.title for stage in GUIDED_STAGES] == [
        "Scala generale QCER",
        "Comprensione orale generale",
        "Produzione orale generale",
        "Interazione orale generale",
    ]
    assert len({item for stage in GUIDED_STAGES for item in stage.descriptor_ids}) == 16
    for stage in GUIDED_STAGES:
        rows = stage_descriptors(catalog, DESCRIPTOR_GUIDES, stage)
        assert len(rows) == 4
        assert tuple(row["correct_level"] for row in rows) == CANONICAL_LEVELS
        assert all(row["descriptor_id"] in stage.descriptor_ids for row in rows)
    assert all(row["status"] == "guided_draft" for row in guided_general_descriptors())


def test_guided_stage_is_four_questions_with_only_canonical_answer_levels(tmp_path: Path):
    catalog = guided_catalog()
    store = LocalEventStore(tmp_path)
    service = SessionService(catalog, store, "test", "demo")
    stage = GUIDED_STAGES[0]
    state = service.start_session(
        "participant",
        "Test",
        stage_descriptors(catalog, DESCRIPTOR_GUIDES, stage),
        include_plus_levels=False,
        selected_descriptor_ids=list(stage.descriptor_ids),
        progression_phase=stage.phase,
        answer_levels_override=list(CANONICAL_LEVELS),
    )
    assert len(state["descriptor_ids"]) == 4
    assert set(state["descriptor_ids"]) == set(stage.descriptor_ids)
    assert tuple(state["available_levels"]) == CANONICAL_LEVELS
    progress = guided_progress(store.list_events("participant"))
    assert progress["next_index"] == 0
    assert progress["resume_session_id"] == state["session_id"]
    restored = service.restore_session("participant", "Test", state["session_id"])
    assert restored["descriptor_ids"] == state["descriptor_ids"]


def test_progress_requires_actual_matching_completed_session():
    first = GUIDED_STAGES[0]
    started = {
        "event_type": "session_started",
        "session_id": "general-1",
        "progression_phase": first.phase,
        "schema": first.path[0],
        "modality": first.path[1],
        "activity": first.path[2],
        "scale": first.path[3],
        "descriptor_order": list(first.descriptor_ids),
        "answer_levels": list(CANONICAL_LEVELS),
        "occurred_at": "2026-09-21T10:00:00Z",
    }
    unrelated = dict(started, session_id="other", progression_phase="free")
    events = [unrelated, dict(event_type="session_completed", session_id="other")]
    assert guided_progress(events)["next_index"] == 0
    events.append(started)
    assert guided_progress(events)["resume_session_id"] == "general-1"
    events.append(dict(event_type="session_completed", session_id="general-1"))
    progress = guided_progress(events)
    assert progress["completed_indices"] == frozenset({0})
    assert progress["next_index"] == 1
    assert progress["resume_session_id"] is None


def test_tailored_guides_are_active_only_in_guided_route_by_default(monkeypatch):
    monkeypatch.setattr(feedback_module, "DRAFT_GUIDES_ENABLED", False)
    descriptor = stage_descriptors(guided_catalog(), DESCRIPTOR_GUIDES, GUIDED_STAGES[1])[2]
    guided_text, guided_basis = compose_feedback(
        descriptor,
        phase=GUIDED_STAGES[1].phase,
        selected_level="B2",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    free_text, free_basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B2",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert guided_basis == "guide_draft"
    assert guided_text != free_text
    assert free_basis != "guide_draft"
    assert "B1" not in guided_text


def test_all_guided_feedback_paths_exclude_suspended_plus_levels(monkeypatch):
    monkeypatch.setattr(feedback_module, "DRAFT_GUIDES_ENABLED", False)
    catalog = guided_catalog()

    for stage in GUIDED_STAGES:
        for descriptor in stage_descriptors(catalog, DESCRIPTOR_GUIDES, stage):
            correct = descriptor["correct_level"]
            wrong_choices = [level for level in CANONICAL_LEVELS if level != correct]
            correct_first, basis = compose_feedback(
                descriptor,
                phase=stage.phase,
                selected_level=correct,
                attempt_number=1,
                previous_attempts=[],
                completed_records=[],
            )
            assert basis == "guide_draft"
            assert "A2+" not in correct_first and "B1+" not in correct_first

            for first_wrong in wrong_choices:
                first, basis = compose_feedback(
                    descriptor,
                    phase=stage.phase,
                    selected_level=first_wrong,
                    attempt_number=1,
                    previous_attempts=[],
                    completed_records=[],
                )
                assert basis == "guide_draft"
                assert "A2+" not in first and "B1+" not in first

                for second_wrong in wrong_choices:
                    second, second_basis = compose_feedback(
                        descriptor,
                        phase=stage.phase,
                        selected_level=second_wrong,
                        attempt_number=2,
                        previous_attempts=[first_wrong],
                        completed_records=[],
                    )
                    finished, finished_basis = compose_feedback(
                        descriptor,
                        phase=stage.phase,
                        selected_level=correct,
                        attempt_number=3,
                        previous_attempts=[first_wrong, second_wrong],
                        completed_records=[],
                    )
                    assert second_basis == finished_basis == "guide_draft"
                    assert all(
                        "A2+" not in message and "B1+" not in message
                        for message in (second, finished)
                    )


def test_app_can_pause_resume_and_finish_all_guided_stages(tmp_path: Path, monkeypatch):
    store = LocalEventStore(tmp_path)
    service = SessionService(app.CATALOG, store, "test", "demo")
    monkeypatch.setattr(app, "STORE", store)
    monkeypatch.setattr(app, "SESSIONS", service)
    participant_id = "guided-integration"
    state = {"participant_id": participant_id, "display_name": "Test", "session": None}

    first_result = app.start_guided_stage(state)
    first_session = first_result[0]["session"]
    assert first_session["progression_phase"] == GUIDED_STAGES[0].phase
    paused = app.pause_session_and_choose_scale(first_result[0])
    assert paused[1]["visible"] is True  # Back to the catalog, not an empty scale page.
    assert paused[2]["visible"] is False
    assert "Percorso consigliato" in paused[10]
    assert any(
        value == first_session["session_id"]
        for _, value in app._resume_dropdown(participant_id).choices
    )
    resumed = app.start_guided_stage(paused[0])
    assert resumed[0]["session"]["session_id"] == first_session["session_id"]

    for index, stage in enumerate(GUIDED_STAGES):
        started = resumed if index == 0 else app.start_guided_stage(state)
        session = started[0]["session"]
        assert session["progression_phase"] == stage.phase
        assert set(session["descriptor_ids"]) == set(stage.descriptor_ids)
        assert tuple(session["available_levels"]) == CANONICAL_LEVELS
        for _ in range(4):
            correct = service.current_descriptor(session)["correct_level"]
            session = service.submit_answer(session, correct)
            session = service.advance(session)
        assert session["session_finished"] is True
        assert stage.reflection_prompt in html.unescape(app._summary_components(session)[0])
        state["session"] = session
        if index < 3:
            assert GUIDED_STAGES[index + 1].title in app.guided_next_button_view(state).value

    assert guided_progress(store.list_events(participant_id))["next_index"] is None
    completed_status, next_button = app.guided_intro_view(state)
    assert "non devi completare il catalogo" in completed_status.casefold()
    assert next_button.visible is False
    personal = app._personal_view(participant_id)
    assert any(
        "Scala generale QCER" in label for label, _ in personal[1].choices
    )
