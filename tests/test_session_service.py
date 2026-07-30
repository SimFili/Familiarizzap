from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.catalog import Catalog, DEMO_CEFR_LEVELS
from src.event_store import EventStoreError, LocalEventStore
from src.session_service import SessionService


def sample_catalog() -> Catalog:
    path = (
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json"
    )
    return Catalog.from_json(
        path,
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )


def make_service(tmp_path: Path):
    catalog = sample_catalog()
    store = LocalEventStore(tmp_path)
    service = SessionService(catalog, store, "test", "demo")
    descriptors = catalog.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    return catalog, store, service, descriptors


def wrong_level(service: SessionService, state: dict) -> str:
    correct = service.current_descriptor(state)["correct_level"]
    return next(
        level for level in service.available_levels(state) if level != correct
    )


def test_correct_answer_closes_descriptor_and_records_once(tmp_path: Path):
    _, store, service, descriptors = make_service(tmp_path)
    state = service.start_session("participant", "Nome Privato", descriptors)
    correct = service.current_descriptor(state)["correct_level"]

    updated = service.submit_answer(state, correct)

    assert updated["descriptor_finished"] is True
    assert updated["completed_records"][0]["resolved_on_attempt"] == 1
    event_types = [
        event["event_type"] for event in store.list_events("participant")
    ]
    assert event_types.count("answer_submitted") == 1
    assert event_types.count("descriptor_completed") == 1


def test_three_attempts_reveal_solution_and_retry_is_idempotent(tmp_path: Path):
    _, store, service, descriptors = make_service(tmp_path)
    state = service.start_session("participant", "Nome Privato", descriptors)
    wrong = wrong_level(service, state)

    first = service.submit_answer(state, wrong)
    repeated_first = service.submit_answer(state, wrong)
    assert first["attempts"] == repeated_first["attempts"] == [wrong]
    assert len(
        [
            event
            for event in store.list_events("participant")
            if event["event_type"] == "answer_submitted"
        ]
    ) == 1

    second = service.submit_answer(first, wrong)
    third = service.submit_answer(second, wrong)
    assert third["descriptor_finished"] is True
    assert third["completed_records"][0]["resolved"] is False
    assert len(third["attempts"]) == 3


def test_resume_restores_attempts_without_display_name_in_events(
    tmp_path: Path,
):
    _, store, service, descriptors = make_service(tmp_path)
    state = service.start_session("participant", "Nome Privato", descriptors)
    updated = service.submit_answer(state, wrong_level(service, state))

    restored = service.restore_session(
        "participant", "Nome Privato", state["session_id"]
    )

    assert restored["attempts"] == updated["attempts"]
    serialized_events = json.dumps(
        store.list_events("participant"), ensure_ascii=False
    )
    assert "Nome Privato" not in serialized_events


def test_failed_write_does_not_consume_attempt(tmp_path: Path, monkeypatch):
    _, store, service, descriptors = make_service(tmp_path)
    state = service.start_session("participant", "Nome Privato", descriptors)
    wrong = wrong_level(service, state)

    def fail(_events):
        raise EventStoreError("offline")

    monkeypatch.setattr(store, "append_events", fail)
    with pytest.raises(EventStoreError):
        service.submit_answer(state, wrong)

    assert state["attempts"] == []
    assert state["descriptor_finished"] is False


def test_longitudinal_events_preserve_snapshot_distance_and_timing(
    tmp_path: Path,
):
    _, store, service, descriptors = make_service(tmp_path)
    state = service.start_session("participant", "Nome Privato", descriptors[:1])
    wrong = wrong_level(service, state)

    first = service.submit_answer(state, wrong)
    correct = service.current_descriptor(first)["correct_level"]
    completed = service.submit_answer(first, correct)
    finished = service.advance(completed)

    assert finished["session_finished"] is True
    events = store.list_events("participant")
    presented = next(
        event for event in events if event["event_type"] == "descriptor_presented"
    )
    first_answer = next(
        event
        for event in events
        if event["event_type"] == "answer_submitted"
        and event["attempt_number"] == 1
    )
    completion = next(
        event for event in events if event["event_type"] == "descriptor_completed"
    )
    session_completion = next(
        event for event in events if event["event_type"] == "session_completed"
    )

    assert presented["schema_version"] == "2.0"
    assert presented["descriptor_text"]
    assert presented["content_version"]
    assert presented["exposure_number"] == 1
    assert first_answer["error_distance"] >= 1
    assert first_answer["response_time_ms"] >= 0
    assert completion["first_response_distance"] == first_answer["error_distance"]
    assert completion["resolved_on_attempt"] == 2
    assert session_completion["first_attempt_rate"] == 0
    assert session_completion["duration_seconds"] >= 0


def test_repeated_descriptor_gets_incremented_exposure_number(tmp_path: Path):
    _, store, service, descriptors = make_service(tmp_path)
    first = service.start_session("participant", "Nome Privato", descriptors[:1])
    correct = service.current_descriptor(first)["correct_level"]
    first = service.submit_answer(first, correct)
    service.advance(first)

    second = service.start_session("participant", "Nome Privato", descriptors[:1])
    second_presented = [
        event
        for event in store.list_events("participant")
        if event["event_type"] == "descriptor_presented"
        and event["session_id"] == second["session_id"]
    ][0]

    assert second_presented["exposure_number"] == 2


def test_access_events_are_append_only_and_do_not_contain_name(tmp_path: Path):
    _, store, service, _ = make_service(tmp_path)

    service.record_participant_access("participant", "name_and_personal_code")
    service.record_access_code_event("participant", "access_code_reset")

    events = store.list_events("participant")
    assert [event["event_type"] for event in events] == [
        "participant_accessed",
        "access_code_reset",
    ]
    assert "Nome Privato" not in json.dumps(events, ensure_ascii=False)
