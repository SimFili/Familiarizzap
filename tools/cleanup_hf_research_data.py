from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from huggingface_hub import CommitOperationDelete, HfApi, hf_hub_download


DATASET_REPO_ID = "Sibucs/Familiarizzap-events"
SPACE_REPO_ID = "Sibucs/Familiarizzap"
MAX_DELETE_OPERATIONS = 50


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def anonymous_label(name: str, report_key: str) -> str:
    return hmac.new(
        report_key.encode("utf-8"),
        normalize_name(name).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]


def load_payload() -> dict[str, Any]:
    raw = os.environ.get("DATA_CLEANUP_PAYLOAD", "")
    if not raw:
        raise RuntimeError("DATA_CLEANUP_PAYLOAD non configurato.")
    payload = json.loads(raw)
    if payload.get("version") != 1:
        raise RuntimeError("Versione del payload non supportata.")
    if not payload.get("report_key"):
        raise RuntimeError("report_key mancante.")
    return payload


def read_repo_json(path: str, token: str) -> tuple[str, dict[str, Any]]:
    local_path = hf_hub_download(
        repo_id=DATASET_REPO_ID,
        filename=path,
        repo_type="dataset",
        token=token,
    )
    return path, json.loads(Path(local_path).read_text(encoding="utf-8"))


def batched(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def main() -> int:
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        raise RuntimeError("HF_TOKEN non configurato.")
    payload = load_payload()
    report_key = str(payload["report_key"])
    apply_changes = payload.get("apply") is True
    full_names = [str(value) for value in payload.get("full_profiles", [])]
    questionnaire_names = [
        str(value) for value in payload.get("questionnaire_only", [])
    ]

    normalized_full = {normalize_name(value): value for value in full_names}
    normalized_questionnaire = {
        normalize_name(value): value for value in questionnaire_names
    }
    if len(normalized_full) != len(full_names):
        raise RuntimeError("Nomi duplicati tra i profili completi.")
    if len(normalized_questionnaire) != len(questionnaire_names):
        raise RuntimeError("Nomi duplicati tra i questionari.")
    if normalized_full.keys() & normalized_questionnaire.keys():
        raise RuntimeError("Uno stesso nome compare in entrambe le operazioni.")

    api = HfApi(token=token)
    repo_info = api.repo_info(repo_id=DATASET_REPO_ID, repo_type="dataset")
    if getattr(repo_info, "private", None) is not True:
        raise RuntimeError("Il Dataset di ricerca non risulta privato.")

    repo_files = api.list_repo_files(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
    )
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
            pool.map(lambda path: read_repo_json(path, token), participant_paths)
        )

    participants_by_name: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for path, participant in participant_pairs:
        participants_by_name[normalize_name(str(participant.get("display_name", "")))].append(
            (path, participant)
        )

    target_names = list(normalized_full) + list(normalized_questionnaire)
    ambiguous = {
        name: participants_by_name.get(name, [])
        for name in target_names
        if len(participants_by_name.get(name, [])) != 1
    }

    print(f"MODE={'APPLY' if apply_changes else 'DRY_RUN'}")
    for normalized_name_value in target_names:
        source_name = (
            normalized_full.get(normalized_name_value)
            or normalized_questionnaire[normalized_name_value]
        )
        label = anonymous_label(source_name, report_key)
        print(
            f"TARGET {label} participant_records="
            f"{len(participants_by_name.get(normalized_name_value, []))}"
        )

    if ambiguous:
        print(f"GUARDRAIL_STOP ambiguous_or_missing={len(ambiguous)}")
        return 2

    full_participant_ids = {
        str(participants_by_name[name][0][1]["participant_id"])
        for name in normalized_full
    }
    questionnaire_participant_ids = {
        str(participants_by_name[name][0][1]["participant_id"])
        for name in normalized_questionnaire
    }

    matching_event_paths: dict[str, list[str]] = defaultdict(list)
    questionnaire_event_paths: dict[str, list[str]] = defaultdict(list)

    def inspect_event(path: str) -> tuple[str, str, str]:
        event_path, event = read_repo_json(path, token)
        return (
            event_path,
            str(event.get("participant_id_hash", "")),
            str(event.get("event_type", "")),
        )

    with ThreadPoolExecutor(max_workers=min(20, max(1, len(event_paths)))) as pool:
        for path, participant_id, event_type in pool.map(inspect_event, event_paths):
            if participant_id in full_participant_ids:
                matching_event_paths[participant_id].append(path)
            elif (
                participant_id in questionnaire_participant_ids
                and event_type == "questionnaire_submitted"
            ):
                questionnaire_event_paths[participant_id].append(path)

    delete_paths: set[str] = set()
    for normalized_name_value, source_name in normalized_full.items():
        participant_path, participant = participants_by_name[normalized_name_value][0]
        participant_id = str(participant["participant_id"])
        event_count = len(matching_event_paths[participant_id])
        delete_paths.add(participant_path)
        delete_paths.update(matching_event_paths[participant_id])
        print(
            f"FULL {anonymous_label(source_name, report_key)} "
            f"events={event_count} participant_file=1"
        )

    for normalized_name_value, source_name in normalized_questionnaire.items():
        _, participant = participants_by_name[normalized_name_value][0]
        participant_id = str(participant["participant_id"])
        count = len(questionnaire_event_paths[participant_id])
        delete_paths.update(questionnaire_event_paths[participant_id])
        print(
            f"QUESTIONNAIRE {anonymous_label(source_name, report_key)} "
            f"events={count} participant_file=0"
        )

    print(f"TOTAL_DELETE_PATHS={len(delete_paths)}")
    if not apply_changes:
        print("DRY_RUN_COMPLETE")
        return 0

    sorted_paths = sorted(delete_paths)
    for batch_number, paths in enumerate(
        batched(sorted_paths, MAX_DELETE_OPERATIONS), start=1
    ):
        api.create_commit(
            repo_id=DATASET_REPO_ID,
            repo_type="dataset",
            operations=[CommitOperationDelete(path_in_repo=path) for path in paths],
            commit_message=f"Rimuove dati di pre-test selezionati ({batch_number})",
        )

    remaining_files = set(
        api.list_repo_files(repo_id=DATASET_REPO_ID, repo_type="dataset")
    )
    remaining_targets = sorted(delete_paths & remaining_files)
    if remaining_targets:
        raise RuntimeError(
            f"Verifica fallita: {len(remaining_targets)} file risultano ancora presenti."
        )

    print(f"APPLY_COMPLETE deleted_paths={len(delete_paths)}")
    try:
        api.restart_space(repo_id=SPACE_REPO_ID)
        print("SPACE_RESTART_REQUESTED=True")
    except Exception as exc:
        print(f"SPACE_RESTART_REQUESTED=False reason={type(exc).__name__}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
