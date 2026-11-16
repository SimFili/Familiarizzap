from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src import data_maintenance


class FakeApi:
    def __init__(self, files: list[str]):
        self.files = set(files)
        self.commits: list[list[str]] = []

    def repo_info(self, **_kwargs):
        return SimpleNamespace(private=True)

    def list_repo_files(self, **_kwargs):
        return sorted(self.files)

    def create_commit(self, *, operations, **_kwargs):
        paths = [operation.path_in_repo for operation in operations]
        self.commits.append(paths)
        self.files.difference_update(paths)


def _write_json(root: Path, relative_path: str, value: dict) -> str:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")
    return relative_path


def test_cleanup_deletes_full_profile_and_only_selected_questionnaire(
    tmp_path, monkeypatch
):
    records = {
        "participants/alice.json": {
            "participant_id": "alice",
            "display_name": "Alice",
        },
        "participants/bob.json": {
            "participant_id": "bob",
            "display_name": "Bob",
        },
        "participants/carla.json": {
            "participant_id": "carla",
            "display_name": "Carla",
        },
        "events/2026/01/01/s1/alice-answer.json": {
            "participant_id_hash": "alice",
            "event_type": "answer_submitted",
        },
        "events/2026/01/01/s1/alice-questionnaire.json": {
            "participant_id_hash": "alice",
            "event_type": "questionnaire_submitted",
        },
        "events/2026/01/01/s2/bob-answer.json": {
            "participant_id_hash": "bob",
            "event_type": "answer_submitted",
        },
        "events/2026/01/01/s2/bob-questionnaire.json": {
            "participant_id_hash": "bob",
            "event_type": "questionnaire_submitted",
        },
        "events/2026/01/01/s3/carla-answer.json": {
            "participant_id_hash": "carla",
            "event_type": "answer_submitted",
        },
    }
    for path, record in records.items():
        _write_json(tmp_path, path, record)
    api = FakeApi(list(records))
    monkeypatch.setattr(data_maintenance, "HfApi", lambda token: api)
    monkeypatch.setattr(
        data_maintenance,
        "hf_hub_download",
        lambda *, filename, **_kwargs: str(tmp_path / filename),
    )
    monkeypatch.setenv(
        "DATA_CLEANUP_PAYLOAD",
        json.dumps(
            {
                "version": 1,
                "apply": True,
                "request_key": "secret-request",
                "report_key": "report-secret",
                "full_profiles": ["Alice"],
                "questionnaire_only": ["Bob"],
            }
        ),
    )

    result = json.loads(
        data_maintenance.run_data_cleanup(
            "secret-request",
            repo_id="owner/private-events",
            token="private-token",
        )
    )

    assert result["ok"] is True
    assert result["total_delete_paths"] == 4
    assert "participants/alice.json" not in api.files
    assert "events/2026/01/01/s1/alice-answer.json" not in api.files
    assert "events/2026/01/01/s1/alice-questionnaire.json" not in api.files
    assert "events/2026/01/01/s2/bob-questionnaire.json" not in api.files
    assert "participants/bob.json" in api.files
    assert "events/2026/01/01/s2/bob-answer.json" in api.files
    assert "participants/carla.json" in api.files
    assert "events/2026/01/01/s3/carla-answer.json" in api.files


def test_cleanup_stops_if_a_target_is_missing(tmp_path, monkeypatch):
    record_path = _write_json(
        tmp_path,
        "participants/alice.json",
        {"participant_id": "alice", "display_name": "Alice"},
    )
    api = FakeApi([record_path])
    monkeypatch.setattr(data_maintenance, "HfApi", lambda token: api)
    monkeypatch.setattr(
        data_maintenance,
        "hf_hub_download",
        lambda *, filename, **_kwargs: str(tmp_path / filename),
    )
    monkeypatch.setenv(
        "DATA_CLEANUP_PAYLOAD",
        json.dumps(
            {
                "version": 1,
                "apply": True,
                "request_key": "secret-request",
                "report_key": "report-secret",
                "full_profiles": ["Missing"],
                "questionnaire_only": [],
            }
        ),
    )

    result = json.loads(
        data_maintenance.run_data_cleanup(
            "secret-request",
            repo_id="owner/private-events",
            token="private-token",
        )
    )

    assert result["ok"] is False
    assert result["error"] == "ambiguous_or_missing"
    assert api.commits == []
