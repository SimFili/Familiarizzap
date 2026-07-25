from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.catalog import Catalog
from src.event_store import EventStoreError, LocalEventStore
from src.session_service import SessionService


def sample_catalog() -> Catalog:
    path = (
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json"
    )
    return Catalog.from_json(path)


def make_service(tmp_path: Path):
    catalog = sample_catalog()
    store = LocalEventStore(tmp_path)
    service = SessionService(catalog, store, "test", "demo")
    descriptors = catalog.for_scale(
        "Strategie linguistico-comunicative",
        "Interazione",
        "Gestione dell’interazione",
        "Alternarsi nei turni di parola",
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
