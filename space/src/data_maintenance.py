from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from huggingface_hub import CommitOperationDelete, HfApi, hf_hub_download


MAX_DELETE_OPERATIONS = 10


def _normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _anonymous_label(name: str, report_key: str) -> str:
    return hmac.new(
        report_key.encode("utf-8"),
        _normalize_name(name).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]


def _read_repo_json(
    repo_id: str,
    path: str,
    token: str,
) -> tuple[str, dict[str, Any]]:
    local_path = hf_hub_download(
        repo_id=repo_id,
        filename=path,
        repo_type="dataset",
        token=token,
    )
    return path, json.loads(Path(local_path).read_text(encoding="utf-8"))


def run_data_cleanup(
    request_key: str,
    *,
    repo_id: str,
    token: str,
) -> str:
    """Apply one secret-scoped maintenance request to the private Dataset.

    The response contains anonymous labels only.  The temporary request secret
    is installed and removed by the GitHub maintenance workflow.
    """
    raw_payload = os.environ.get("DATA_CLEANUP_PAYLOAD", "")
    if not raw_payload or not repo_id or not token:
        return json.dumps({"ok": False, "error": "maintenance_disabled"})

    payload = json.loads(raw_payload)
    expected_key = str(payload.get("request_key", ""))
    if not expected_key or not hmac.compare_digest(request_key or "", expected_key):
        return json.dumps({"ok": False, "error": "not_authorized"})
    if payload.get("version") != 1 or not payload.get("report_key"):
        return json.dumps({"ok": False, "error": "invalid_payload"})

    report_key = str(payload["report_key"])
    apply_changes = payload.get("apply") is True
    resume_changes = apply_changes and payload.get("resume") is True
    full_names = [str(value) for value in payload.get("full_profiles", [])]
    questionnaire_names = [
        str(value) for value in payload.get("questionnaire_only", [])
    ]
    normalized_full = {_normalize_name(value): value for value in full_names}
    normalized_questionnaire = {
        _normalize_name(value): value for value in questionnaire_names
    }
    if (
        len(normalized_full) != len(full_names)
        or len(normalized_questionnaire) != len(questionnaire_names)
        or normalized_full.keys() & normalized_questionnaire.keys()
    ):
        return json.dumps({"ok": False, "error": "invalid_targets"})

    api = HfApi(token=token)
    repo_info = api.repo_info(repo_id=repo_id, repo_type="dataset")
    if getattr(repo_info, "private", None) is not True:
        return json.dumps({"ok": False, "error": "dataset_not_private"})
    repo_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    participant_paths = sorted(
        path
        for path in repo_files
        if path.startswith("participants/") and path.endswith(".json")
    )
    event_paths = sorted(
        path
        for path in repo_files
        if path.startswith("events/") and path.endswith(".json")
    )

    with ThreadPoolExecutor(max_workers=min(16, max(1, len(participant_paths)))) as pool:
        participant_pairs = list(
            pool.map(
                lambda path: _read_repo_json(repo_id, path, token),
                participant_paths,
            )
        )
    participants_by_name: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for path, participant in participant_pairs:
        normalized = _normalize_name(str(participant.get("display_name", "")))
        participants_by_name[normalized].append((path, participant))

    target_names = list(normalized_full) + list(normalized_questionnaire)
    target_report = []
    for normalized in target_names:
        source_name = normalized_full.get(normalized) or normalized_questionnaire[normalized]
        target_report.append(
            {
                "label": _anonymous_label(source_name, report_key),
                "participant_records": len(participants_by_name.get(normalized, [])),
            }
        )
    ambiguous = []
    for normalized in normalized_full:
        count = len(participants_by_name.get(normalized, []))
        if count > 1 or (count == 0 and not resume_changes):
            ambiguous.append(normalized)
    for normalized in normalized_questionnaire:
        if len(participants_by_name.get(normalized, [])) != 1:
            ambiguous.append(normalized)
    if ambiguous:
        return json.dumps(
            {
                "ok": False,
                "error": "ambiguous_or_missing",
                "mode": "apply" if apply_changes else "dry_run",
                "targets": target_report,
            },
            sort_keys=True,
        )

    full_ids = {
        str(records[0][1]["participant_id"])
        for name in normalized_full
        if (records := participants_by_name.get(name))
    }
    questionnaire_ids = {
        str(participants_by_name[name][0][1]["participant_id"])
        for name in normalized_questionnaire
    }
    all_target_ids = full_ids | questionnaire_ids
    full_event_paths: dict[str, list[str]] = defaultdict(list)
    questionnaire_event_paths: dict[str, list[str]] = defaultdict(list)

    def inspect_event(path: str) -> tuple[str, str, str]:
        event_path, event = _read_repo_json(repo_id, path, token)
        return (
            event_path,
            str(event.get("participant_id_hash", "")),
            str(event.get("event_type", "")),
        )

    with ThreadPoolExecutor(max_workers=min(20, max(1, len(event_paths)))) as pool:
        for path, participant_id, event_type in pool.map(inspect_event, event_paths):
            if participant_id not in all_target_ids:
                continue
            if participant_id in full_ids:
                full_event_paths[participant_id].append(path)
            elif event_type == "questionnaire_submitted":
                questionnaire_event_paths[participant_id].append(path)

    delete_paths: set[str] = set()
    details = []
    for normalized, source_name in normalized_full.items():
        participant_records = participants_by_name.get(normalized, [])
        if not participant_records:
            details.append(
                {
                    "label": _anonymous_label(source_name, report_key),
                    "operation": "full",
                    "events": 0,
                    "participant_files": 0,
                }
            )
            continue
        participant_path, participant = participant_records[0]
        participant_id = str(participant["participant_id"])
        paths = full_event_paths[participant_id]
        delete_paths.add(participant_path)
        delete_paths.update(paths)
        details.append(
            {
                "label": _anonymous_label(source_name, report_key),
                "operation": "full",
                "events": len(paths),
                "participant_files": 1,
            }
        )
    for normalized, source_name in normalized_questionnaire.items():
        _, participant = participants_by_name[normalized][0]
        participant_id = str(participant["participant_id"])
        paths = questionnaire_event_paths[participant_id]
        delete_paths.update(paths)
        details.append(
            {
                "label": _anonymous_label(source_name, report_key),
                "operation": "questionnaire",
                "events": len(paths),
                "participant_files": 0,
            }
        )

    result = {
        "ok": True,
        "mode": "apply" if apply_changes else "dry_run",
        "targets": target_report,
        "details": details,
        "total_delete_paths": len(delete_paths),
    }
    if not apply_changes:
        return json.dumps(result, sort_keys=True)

    paths = sorted(delete_paths)[:MAX_DELETE_OPERATIONS]
    if paths:
        api.create_commit(
            repo_id=repo_id,
            repo_type="dataset",
            operations=[CommitOperationDelete(path_in_repo=path) for path in paths],
            commit_message="Rimuove un gruppo di dati di pre-test selezionati",
        )
    remaining_files = set(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    result["remaining_delete_paths"] = len(delete_paths & remaining_files)
    result["deleted_in_batch"] = len(paths)
    result["complete"] = result["remaining_delete_paths"] == 0
    return json.dumps(result, sort_keys=True)
