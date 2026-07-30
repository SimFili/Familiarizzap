from __future__ import annotations

import csv
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .analytics import descriptor_history, integrity_report, session_records
from .catalog import Catalog


def build_research_export(
    participants: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    catalog: Catalog,
) -> Path:
    participant_rows = list(participants)
    event_rows = list(events)
    participant_names = {
        str(row.get("participant_id", "")): row.get("display_name", "")
        for row in participant_rows
    }
    export_root = Path(tempfile.mkdtemp(prefix="familiarizzapp-export-"))
    generated = datetime.now(timezone.utc)
    archive = export_root / f"familiarizzapp-ricerca-{generated:%Y%m%d-%H%M%S}.zip"

    safe_participants = [
        {
            key: value
            for key, value in row.items()
            if key != "name_lookup_hash"
        }
        for row in participant_rows
    ]
    sessions: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    for participant in participant_rows:
        participant_id = str(participant.get("participant_id", ""))
        own_events = [
            event
            for event in event_rows
            if event.get("participant_id_hash") == participant_id
        ]
        for row in session_records(own_events, catalog):
            sessions.append(
                {
                    "participant_id": participant_id,
                    "display_name": participant.get("display_name", ""),
                    **row,
                }
            )
        for row in descriptor_history(own_events, catalog):
            histories.append(
                {
                    "display_name": participant.get("display_name", ""),
                    **row,
                }
            )

    attempts = []
    for event in event_rows:
        if event.get("event_type") != "answer_submitted":
            continue
        participant_id = str(event.get("participant_id_hash", ""))
        attempts.append(
            {
                "display_name": participant_names.get(participant_id, ""),
                **event,
            }
        )
    issues = integrity_report(event_rows, participant_rows)

    files: dict[str, bytes] = {
        "participants.csv": _csv_bytes(safe_participants),
        "sessions.csv": _csv_bytes(sessions),
        "descriptor_history.csv": _csv_bytes(histories),
        "attempts.csv": _csv_bytes(attempts),
        "integrity.csv": _csv_bytes(issues),
        "events.jsonl": _jsonl_bytes(event_rows),
        "manifest.json": json.dumps(
            {
                "generated_at_utc": generated.isoformat(),
                "participants": len(participant_rows),
                "events": len(event_rows),
                "sessions": len(sessions),
                "descriptor_completions": len(histories),
                "attempts": len(attempts),
                "integrity_issues": len(issues),
                "notes": (
                    "I timestamp originali sono in UTC. I nomi compaiono "
                    "soltanto nei file derivati riservati al ricercatore. "
                    "Gli hash dei codici percorso e le chiavi HMAC usate per "
                    "cercare i nomi non sono esportati."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return archive


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: _scalar(row.get(key))
                for key in fieldnames
            }
        )
    return buffer.getvalue().encode("utf-8-sig")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows
        )
        + ("\n" if rows else "")
    ).encode("utf-8")


def _scalar(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value
