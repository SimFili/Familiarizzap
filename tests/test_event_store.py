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
        self.commits = []

    def repo_info(self, *, repo_id: str, repo_type: str):
        assert repo_id == "Sibucs/Familiarizzap-events"
        assert repo_type == "dataset"
        self.calls += 1
        if self.error:
            raise self.error
        return _FakeRepoInfo(self.private)

    def create_commit(self, **kwargs):
        self.commits.append(kwargs)


class _CachedStore(HuggingFaceEventStore):
    def __init__(self, files):
        super().__init__(
            "Sibucs/Familiarizzap-events", "secret", api=_FakeHfApi()
        )
        self.files = {path: dict(value) for path, value in files.items()}
        self.list_calls = 0
        self.download_calls = 0
        self.upload_calls = 0

    def _list_files(self, prefix):
        self.list_calls += 1
        return sorted(path for path in self.files if path.startswith(prefix))

    def _download_json(self, path):
        self.download_calls += 1
        value = self.files.get(path)
        return dict(value) if value is not None else None

    def _upload_participant(self, path, record, commit_message):
        del commit_message
        self.upload_calls += 1
        self.files[path] = dict(record)


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


def test_huggingface_event_reads_are_cached_after_first_archive_load():
    event = {
        "event_id": "e1",
        "occurred_at": "2026-07-30T10:00:00+00:00",
        "session_id": "s1",
        "participant_id_hash": "p1",
    }
    store = _CachedStore(
        {"events/2026/07/30/s1/e1.json": event}
    )

    assert store.list_events("p1") == [event]
    assert store.list_events("p1") == [event]
    assert store.list_calls == 1
    assert store.download_calls == 1


def test_huggingface_unchanged_participant_is_not_uploaded_again():
    participant = {
        "participant_id": "p1",
        "display_name": "Anna",
        "created_at": "2026-07-30T10:00:00+00:00",
        "updated_at": "2026-07-30T10:00:00+00:00",
        "status": "active",
        "merged_into": None,
        "name_lookup_hash": "lookup",
    }
    store = _CachedStore({"participants/p1.json": participant})

    first = store.register_participant("p1", "Anna", "lookup")
    second = store.register_participant("p1", "Anna", "lookup")

    assert first == participant
    assert second == participant
    assert store.download_calls == 1
    assert store.upload_calls == 0


def test_huggingface_event_append_lists_remote_paths_only_once():
    store = _CachedStore({})
    event = {
        "event_id": "e1",
        "occurred_at": "2026-07-30T10:00:00+00:00",
        "session_id": "s1",
        "participant_id_hash": "p1",
    }

    store.append_events([event])
    store.append_events([event])

    assert store.list_calls == 1
    assert len(store.api.commits) == 1
    assert store.list_events("p1") == [event]
    assert store.download_calls == 0


def test_huggingface_warmup_avoids_metadata_calls_on_first_write():
    store = _CachedStore({})
    event = {
        "event_id": "e1",
        "occurred_at": "2026-07-30T10:00:00+00:00",
        "session_id": "s1",
        "participant_id_hash": "p1",
    }

    store.warm_up()
    store.append_events([event])

    assert store.api.calls == 1
    assert store.list_calls == 1
    assert len(store.api.commits) == 1


def test_new_participant_does_not_download_other_participants_events():
    other_event = {
        "event_id": "other",
        "occurred_at": "2026-07-30T10:00:00+00:00",
        "session_id": "s-other",
        "participant_id_hash": "other",
    }
    store = _CachedStore(
        {"events/2026/07/30/s-other/other.json": other_event}
    )

    store.register_participant("new", "Nuova", "new")

    assert store.list_events("new") == []
    # One lookup confirms that the participant is new; the unrelated event is
    # never downloaded.
    assert store.download_calls == 1
