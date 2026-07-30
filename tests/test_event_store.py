from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.event_store import EventStoreError, LocalEventStore


def test_participant_code_hash_is_preserved_until_explicit_reset(
    tmp_path: Path,
):
    store = LocalEventStore(tmp_path)
    first = store.register_participant("p1", "Anna Rossi", "hash-one")
    second = store.register_participant("p1", "ANNA ROSSI")

    assert first["access_code_hash"] == "hash-one"
    assert second["access_code_hash"] == "hash-one"

    reset = store.set_access_code("p1", "hash-two")
    assert reset["access_code_hash"] == "hash-two"
    assert reset["access_code_updated_at"]


def test_existing_event_file_is_never_overwritten(tmp_path: Path):
    store = LocalEventStore(tmp_path)
    original = {
        "event_id": "fixed",
        "event_type": "test",
        "occurred_at": "2026-07-30T10:00:00+00:00",
        "session_id": "session",
        "participant_id_hash": "p1",
        "value": "original",
    }
    changed_retry = {**original, "value": "changed"}

    store.append_events([original])
    store.append_events([changed_retry])

    events = store.list_events("p1")
    assert len(events) == 1
    assert events[0]["value"] == "original"
    event_path = next((tmp_path / "events").rglob("*.json"))
    assert json.loads(event_path.read_text(encoding="utf-8"))["value"] == "original"


def test_corrupted_event_is_reported_instead_of_silently_dropped(
    tmp_path: Path,
):
    target = tmp_path / "events" / "2026" / "07" / "30" / "session"
    target.mkdir(parents=True)
    (target / "broken.json").write_text("{", encoding="utf-8")
    store = LocalEventStore(tmp_path)

    with pytest.raises(EventStoreError, match="Evento illeggibile"):
        store.list_events()
