from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.event_store import (
    EventStoreError,
    HuggingFaceEventStore,
    LocalEventStore,
)


def test_participant_name_record_preserves_creation_and_lookup_hash(
    tmp_path: Path,
):
    store = LocalEventStore(tmp_path)
    first = store.register_participant(
        "p1", "Anna", name_lookup_hash="name-hash"
    )
    second = store.register_participant("p1", "ANNA")

    assert second["display_name"] == "ANNA"
    assert second["created_at"] == first["created_at"]
    assert second["name_lookup_hash"] == "name-hash"


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


class _FakeRepoInfo:
    def __init__(self, private: bool):
        self.private = private


class _FakeHfApi:
    def __init__(self, *, private: bool = True, error: Exception | None = None):
        self.private = private
        self.error = error
        self.calls = 0

    def repo_info(self, *, repo_id: str, repo_type: str):
        assert repo_id == "Sibucs/Familiarizzap-events"
        assert repo_type == "dataset"
        self.calls += 1
        if self.error:
            raise self.error
        return _FakeRepoInfo(self.private)


def test_huggingface_store_accepts_only_a_reachable_private_dataset():
    api = _FakeHfApi(private=True)
    store = HuggingFaceEventStore(
        "Sibucs/Familiarizzap-events", "secret", api=api
    )

    assert store.health_check() == (True, "")
    assert store.health_check() == (True, "")
    assert api.calls == 1


def test_huggingface_store_rejects_a_public_dataset():
    store = HuggingFaceEventStore(
        "Sibucs/Familiarizzap-events",
        "secret",
        api=_FakeHfApi(private=False),
    )

    healthy, message = store.health_check()

    assert healthy is False
    assert "deve essere privato" in message


def test_huggingface_store_reports_an_unreachable_dataset():
    store = HuggingFaceEventStore(
        "Sibucs/Familiarizzap-events",
        "secret",
        api=_FakeHfApi(error=RuntimeError("offline")),
    )

    healthy, message = store.health_check()

    assert healthy is False
    assert "non raggiungibile" in message
