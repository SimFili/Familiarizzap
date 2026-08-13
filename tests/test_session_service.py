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


def test_access_event_is_append_only_and_does_not_contain_name(tmp_path: Path):
    _, store, service, _ = make_service(tmp_path)

    service.record_participant_access("participant", "name_only")

    events = store.list_events("participant")
    assert [event["event_type"] for event in events] == ["participant_accessed"]
    assert "Nome Privato" not in json.dumps(events, ensure_ascii=False)


def test_level_counts_are_stored_for_the_selected_scale(tmp_path: Path):
    _, store, service, descriptors = make_service(tmp_path)

    state = service.start_session("participant", "Nome Privato", descriptors)
    expected = {
        level: sum(item["correct_level"] == level for item in descriptors)
        for level in service.available_levels(state)
    }

    assert service.level_counts(state) == expected
    start = next(
        event
        for event in store.list_events("participant")
        if event["event_type"] == "session_started"
    )


def finish_correctly(service: SessionService, state: dict) -> dict:
    while not state["session_finished"]:
        correct = service.current_descriptor(state)["correct_level"]
        state = service.submit_answer(state, correct)
        state = service.advance(state)
    return state
    assert start["level_counts"] == expected


def test_plus_levels_can_be_excluded_and_remain_excluded_after_resume(
    tmp_path: Path,
):
    _, store, service, descriptors = make_service(tmp_path)

    state = service.start_session(
        "participant",
        "Nome Privato",
        descriptors,
        include_plus_levels=False,
    )

    assert "A2+" not in service.available_levels(state)
    assert "B1+" not in service.available_levels(state)
    assert all(
        service.catalog.get(item_id)["correct_level"] not in {"A2+", "B1+"}
        for item_id in state["descriptor_ids"]
    )
    restored = service.restore_session(
        "participant", "Nome Privato", state["session_id"]
    )
    assert restored["include_plus_levels"] is False
    assert service.available_levels(restored) == service.available_levels(state)
    start = next(
        event
        for event in store.list_events("participant")
        if event["event_type"] == "session_started"
    )
    assert start["include_plus_levels"] is False


def test_block_session_selects_six_descriptors_balanced_across_levels(
    tmp_path: Path,
):
    _, store, service, descriptors = make_service(tmp_path)

    state = service.start_session(
        "participant",
        "Nome Privato",
        descriptors,
        session_size=6,
    )
    selected_levels = {
        service.catalog.get(item_id)["correct_level"]
        for item_id in state["descriptor_ids"]
    }

    assert len(state["descriptor_ids"]) == 6
    assert selected_levels == set(service.available_levels(state))
    assert state["session_mode"] == "block"
    assert state["scale_descriptor_count"] == len(descriptors)
    assert state["remaining_new_after_batch"] == len(descriptors) - 6

    start = next(
        event
        for event in store.list_events("participant")
        if event["event_type"] == "session_started"
    )
    assert start["session_mode"] == "block"
    assert start["descriptor_count"] == 6


def test_next_block_avoids_every_descriptor_already_presented(tmp_path: Path):
    _, _, service, descriptors = make_service(tmp_path)

    first = service.start_session(
        "participant", "Nome Privato", descriptors, session_size=6
    )
    second = service.start_session(
        "participant", "Nome Privato", descriptors, session_size=6
    )

    assert set(first["descriptor_ids"]).isdisjoint(second["descriptor_ids"])
    assert len(second["descriptor_ids"]) == len(descriptors) - 6
    assert second["remaining_new_after_batch"] == 0


def test_full_session_still_includes_every_eligible_descriptor(tmp_path: Path):
    _, _, service, descriptors = make_service(tmp_path)

    state = service.start_session(
        "participant", "Nome Privato", descriptors, session_size=None
    )

    assert set(state["descriptor_ids"]) == {
        item["descriptor_id"] for item in descriptors
    }
    assert state["session_mode"] == "full"


def test_progressive_path_introduces_variation_before_plus_levels(
    tmp_path: Path,
):
    _, _, service, descriptors = make_service(tmp_path)

    orientation = service.start_progressive_session(
        "progressive", "Nome Privato", descriptors
    )
    assert orientation["progression_phase"] == "orientation"
    assert service.available_levels(orientation) == ["A1", "A2", "B1", "B2"]
    assert {
        service.catalog.get(item_id)["correct_level"]
        for item_id in orientation["descriptor_ids"]
    } == {"A1", "A2", "B1", "B2"}
    finish_correctly(service, orientation)

    variation = service.start_progressive_session(
        "progressive", "Nome Privato", descriptors
    )
    assert variation["progression_phase"] == "canonical_variation"
    assert service.available_levels(variation) == ["A1", "A2", "B1", "B2"]
    variation_levels = {
        service.catalog.get(item_id)["correct_level"]
        for item_id in variation["descriptor_ids"]
    }
    assert {"A1", "B2"}.issubset(variation_levels)
    assert variation_levels.issubset({"A1", "A2", "B1", "B2"})
    assert 4 <= len(variation["descriptor_ids"]) <= 6
    finish_correctly(service, variation)

    a2_plus = service.start_progressive_session(
        "progressive", "Nome Privato", descriptors
    )
    assert a2_plus["progression_phase"] == "introduce_a2_plus"
    assert service.available_levels(a2_plus) == ["A1", "A2", "A2+", "B1", "B2"]
    a2_plus_levels = {
        service.catalog.get(item_id)["correct_level"]
        for item_id in a2_plus["descriptor_ids"]
    }
    assert {"A2", "A2+", "B1"}.issubset(a2_plus_levels)
    assert "B1+" not in a2_plus_levels
    assert 4 <= len(a2_plus["descriptor_ids"]) <= 6
    finish_correctly(service, a2_plus)

    b1_plus = service.start_progressive_session(
        "progressive", "Nome Privato", descriptors
    )
    assert b1_plus["progression_phase"] == "introduce_b1_plus"
    assert service.available_levels(b1_plus) == [
        "A1", "A2", "A2+", "B1", "B1+", "B2"
    ]
    b1_plus_levels = {
        service.catalog.get(item_id)["correct_level"]
        for item_id in b1_plus["descriptor_ids"]
    }
    assert {"B1", "B1+", "B2"}.issubset(b1_plus_levels)
    assert 4 <= len(b1_plus["descriptor_ids"]) <= 6


def test_every_progressive_flow_has_between_four_and_six_descriptors(
    tmp_path: Path,
):
    _, _, service, descriptors = make_service(tmp_path)

    for _ in range(10):
        state = service.start_progressive_session(
            "bounded", "Nome Privato", descriptors
        )
        assert 4 <= len(state["descriptor_ids"]) <= 6
        assert len(state["descriptor_ids"]) == len(set(state["descriptor_ids"]))
        finish_correctly(service, state)


def test_plus_level_is_used_only_to_reach_minimum_on_a_four_item_scale(
    tmp_path: Path,
):
    _, _, _, source = make_service(tmp_path)
    raw = []
    for index, level in enumerate(("A2", "B1", "B1+", "B2"), start=1):
        item = dict(source[index - 1])
        item["descriptor_id"] = f"short-{index}"
        item["correct_level"] = level
        item["scale"] = "Scala minima con livello più"
        raw.append(item)
    catalog = Catalog(
        raw,
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )
    service = SessionService(
        catalog, LocalEventStore(tmp_path / "short"), "test", "demo"
    )

    state = service.start_progressive_session("short", "Nome Privato", raw)

    assert len(state["descriptor_ids"]) == 4
    assert {
        catalog.get(item_id)["correct_level"]
        for item_id in state["descriptor_ids"]
    } == {"A2", "B1", "B1+", "B2"}


def test_first_attempt_answers_return_later_for_consolidation(tmp_path: Path):
    _, _, service, descriptors = make_service(tmp_path)

    for _ in range(4):
        state = service.start_progressive_session(
            "review", "Nome Privato", descriptors
        )
        finish_correctly(service, state)

    review = service.start_progressive_session(
        "review", "Nome Privato", descriptors
    )

    assert review["progression_phase"] == "consolidation"
    assert review["review_descriptor_ids"]
    assert set(review["review_descriptor_ids"]) == set(review["descriptor_ids"])
