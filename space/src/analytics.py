from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .catalog import Catalog, CatalogError


ROME = ZoneInfo("Europe/Rome")

OUTCOME_LABELS = {
    "first": "✓ 1° tentativo",
    "second": "✓ 2° tentativo",
    "third": "✓ 3° tentativo",
    "unresolved": "Da rivedere",
    "unseen": "Non ancora incontrato",
}

FOCUS_OUTCOMES = {"second", "third", "unresolved"}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def exact_timestamp(value: str | None) -> str:
    parsed = parse_timestamp(value)
    if not parsed:
        return "—"
    local = parsed.astimezone(ROME)
    return (
        f"{local:%d/%m/%Y %H:%M:%S} {local.tzname()} "
        f"({parsed:%Y-%m-%d %H:%M:%S} UTC)"
    )


def relative_timestamp(
    value: str | None, *, now: datetime | None = None
) -> str:
    parsed = parse_timestamp(value)
    if not parsed:
        return "data non disponibile"
    local = parsed.astimezone(ROME)
    reference = (now or datetime.now(timezone.utc)).astimezone(ROME)
    if local > reference:
        return f"il {local:%d/%m/%Y}"
    day_delta = (reference.date() - local.date()).days
    elapsed_seconds = max((reference - local).total_seconds(), 0)
    if day_delta == 0:
        minutes = int(elapsed_seconds // 60)
        if minutes < 2:
            return "pochi minuti fa"
        if minutes < 60:
            return f"circa {minutes} minuti fa"
        hours = max(round(elapsed_seconds / 3600), 1)
        return f"circa {hours} {'ora' if hours == 1 else 'ore'} fa"
    if day_delta == 1:
        return "ieri"
    if day_delta < 30:
        return f"{day_delta} giorni fa"
    return f"il {local:%d/%m/%Y}"


def outcome_key(record: dict[str, Any] | None) -> str:
    if not record:
        return "unseen"
    attempt = record.get("resolved_on_attempt")
    if attempt == 1:
        return "first"
    if attempt == 2:
        return "second"
    if attempt == 3:
        return "third"
    return "unresolved"


def outcome_label(record: dict[str, Any] | None) -> str:
    return OUTCOME_LABELS[outcome_key(record)]


def group_sessions(
    events: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("event_type") in {
            "consent_recorded",
            "participant_accessed",
        }:
            continue
        session_id = str(event.get("session_id", ""))
        if session_id:
            grouped[session_id].append(event)
    for session_events in grouped.values():
        session_events.sort(key=lambda item: item.get("occurred_at", ""))
    return dict(grouped)


def descriptor_history(
    events: Iterable[dict[str, Any]], catalog: Catalog
) -> list[dict[str, Any]]:
    grouped = group_sessions(events)
    records: list[dict[str, Any]] = []
    for session_id, session_events in grouped.items():
        start = first_event(session_events, "session_started") or {}
        answers_by_descriptor: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in session_events:
            if event.get("event_type") == "answer_submitted":
                answers_by_descriptor[str(event.get("descriptor_id", ""))].append(
                    event
                )
        for answers in answers_by_descriptor.values():
            answers.sort(key=lambda item: int(item.get("attempt_number", 0)))

        for completed in (
            event
            for event in session_events
            if event.get("event_type") == "descriptor_completed"
        ):
            descriptor_id = str(completed.get("descriptor_id", ""))
            answers = answers_by_descriptor.get(descriptor_id, [])
            descriptor = _catalog_item(catalog, descriptor_id)
            attempts = list(completed.get("attempts") or [])
            if not attempts:
                attempts = [
                    str(answer.get("selected_level", "")) for answer in answers
                ]
            correct_level = (
                completed.get("correct_level")
                or descriptor.get("correct_level")
                or (answers[-1].get("correct_level") if answers else "")
            )
            record = {
                "participant_id": completed.get("participant_id_hash", ""),
                "session_id": session_id,
                "descriptor_id": descriptor_id,
                "schema": start.get("schema") or descriptor.get("schema", ""),
                "modality": start.get("modality")
                or descriptor.get("modality", ""),
                "activity": start.get("activity")
                or descriptor.get("activity", ""),
                "scale": start.get("scale") or descriptor.get("scale", ""),
                "level": correct_level,
                "descriptor_text": descriptor.get("descriptor_text")
                or completed.get("descriptor_text", ""),
                "attempts": attempts,
                "attempts_text": " → ".join(attempts) if attempts else "—",
                "resolved": bool(completed.get("resolved")),
                "resolved_on_attempt": completed.get("resolved_on_attempt"),
                "rationale": completed.get("rationale")
                or descriptor.get("rationale", ""),
                "occurred_at": completed.get("occurred_at", ""),
                "outcome": outcome_key(completed),
                "outcome_label": outcome_label(completed),
                "content_revision": completed.get("content_revision")
                or start.get("content_revision", ""),
                "app_version": completed.get("app_version")
                or start.get("app_version", ""),
                "response_time_ms": sum(
                    int(answer.get("response_time_ms") or 0) for answer in answers
                )
                if any(
                    answer.get("response_time_ms") is not None
                    for answer in answers
                )
                else None,
                "first_response_distance": _first_non_null(
                    [
                        *[
                            answer.get("error_distance")
                            for answer in answers[:1]
                        ],
                        completed.get("first_response_distance"),
                    ]
                ),
            }
            records.append(record)
    records.sort(key=lambda item: item["occurred_at"])
    exposures: Counter[str] = Counter()
    for record in records:
        exposures[record["descriptor_id"]] += 1
        record["exposure_number"] = exposures[record["descriptor_id"]]
    return records


def session_records(
    events: Iterable[dict[str, Any]], catalog: Catalog
) -> list[dict[str, Any]]:
    histories = descriptor_history(events, catalog)
    history_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in histories:
        history_by_session[record["session_id"]].append(record)

    rows: list[dict[str, Any]] = []
    for session_id, session_events in group_sessions(events).items():
        start = first_event(session_events, "session_started")
        if not start:
            continue
        completed_event = first_event(session_events, "session_completed")
        descriptor_records = history_by_session.get(session_id, [])
        counts = Counter(record["outcome"] for record in descriptor_records)
        total = len(descriptor_records)
        last_timestamp = max(
            (event.get("occurred_at", "") for event in session_events),
            default=start.get("occurred_at", ""),
        )
        rows.append(
            {
                "session_id": session_id,
                "schema": start.get("schema", ""),
                "modality": start.get("modality", ""),
                "activity": start.get("activity", ""),
                "scale": start.get("scale", ""),
                "started_at": start.get("occurred_at", ""),
                "completed_at": (
                    completed_event.get("occurred_at", "")
                    if completed_event
                    else ""
                ),
                "last_activity_at": last_timestamp,
                "status": "completed" if completed_event else "in_progress",
                "status_label": "Completata" if completed_event else "In corso",
                "descriptors_completed": total,
                "descriptors_planned": len(start.get("descriptor_order", [])),
                "first": counts["first"],
                "second": counts["second"],
                "third": counts["third"],
                "unresolved": counts["unresolved"],
                "first_attempt_rate": (counts["first"] / total * 100)
                if total
                else 0.0,
                "duration_seconds": _duration_seconds(
                    start.get("occurred_at"),
                    (
                        completed_event.get("occurred_at")
                        if completed_event
                        else last_timestamp
                    ),
                ),
                "content_revision": start.get("content_revision", ""),
                "app_version": start.get("app_version", ""),
            }
        )
    return sorted(rows, key=lambda item: item["started_at"], reverse=True)


def scale_map(
    catalog: Catalog,
    events: Iterable[dict[str, Any]],
    path: tuple[str, str, str, str],
    *,
    session_id: str | None = None,
    outcome_filter: str = "all",
) -> list[dict[str, Any]]:
    schema, modality, activity, scale = path
    descriptors = catalog.for_scale(schema, modality, activity, scale)
    histories = [
        record
        for record in descriptor_history(events, catalog)
        if (
            record["schema"],
            record["modality"],
            record["activity"],
            record["scale"],
        )
        == path
        and (session_id is None or record["session_id"] == session_id)
    ]
    by_descriptor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in histories:
        by_descriptor[record["descriptor_id"]].append(record)

    order = {level: index for index, level in enumerate(catalog.level_order)}
    rows: list[dict[str, Any]] = []
    for source_order, descriptor in enumerate(descriptors):
        history = by_descriptor.get(descriptor["descriptor_id"], [])
        latest = history[-1] if history else None
        status = latest["outcome"] if latest else "unseen"
        if not _matches_filter(status, outcome_filter):
            continue
        rows.append(
            {
                "descriptor_id": descriptor["descriptor_id"],
                "level": descriptor["correct_level"],
                "text": descriptor["descriptor_text"],
                "status": status,
                "status_label": OUTCOME_LABELS[status],
                "when": (
                    relative_timestamp(latest["occurred_at"]) if latest else ""
                ),
                "attempts": latest["attempts_text"] if latest else "—",
                "source_order": source_order,
                "level_order": order.get(descriptor["correct_level"], -1),
            }
        )
    return sorted(
        rows,
        key=lambda item: (-item["level_order"], item["source_order"]),
    )


def descriptor_details(
    descriptor_id: str,
    events: Iterable[dict[str, Any]],
    catalog: Catalog,
    *,
    session_id: str | None = None,
    user_facing_time: bool = True,
) -> dict[str, Any]:
    descriptor = _catalog_item(catalog, descriptor_id)
    history = [
        record
        for record in descriptor_history(events, catalog)
        if record["descriptor_id"] == descriptor_id
        and (session_id is None or record["session_id"] == session_id)
    ]
    return {
        "descriptor": descriptor,
        "history": history,
        "latest": history[-1] if history else None,
        "time_formatter": relative_timestamp
        if user_facing_time
        else exact_timestamp,
    }


def participant_overview(
    events: Iterable[dict[str, Any]], catalog: Catalog
) -> dict[str, Any]:
    events_list = list(events)
    sessions = session_records(events_list, catalog)
    histories = descriptor_history(events_list, catalog)
    latest_by_descriptor: dict[str, dict[str, Any]] = {}
    for record in histories:
        latest_by_descriptor[record["descriptor_id"]] = record
    latest_counts = Counter(
        record["outcome"] for record in latest_by_descriptor.values()
    )
    first_count = latest_counts["first"]
    encountered = len(latest_by_descriptor)
    all_descriptors = len(catalog.all())
    return {
        "sessions_started": len(sessions),
        "sessions_completed": sum(
            session["status"] == "completed" for session in sessions
        ),
        "sessions_in_progress": sum(
            session["status"] == "in_progress" for session in sessions
        ),
        "descriptors_encountered": encountered,
        "descriptors_available": all_descriptors,
        "latest_first_count": first_count,
        "latest_first_rate": (
            first_count / encountered * 100 if encountered else 0.0
        ),
        "last_activity_at": max(
            (event.get("occurred_at", "") for event in events_list),
            default="",
        ),
        "outcome_counts": latest_counts,
    }


def integrity_report(
    events: Iterable[dict[str, Any]],
    participants: Iterable[dict[str, Any]] = (),
) -> list[dict[str, str]]:
    events_list = list(events)
    issues: list[dict[str, str]] = []
    ids: Counter[str] = Counter(
        str(event.get("event_id", "")) for event in events_list
    )
    for event_id, count in ids.items():
        if not event_id:
            issues.append(
                {"severity": "errore", "scope": "evento", "message": "ID mancante"}
            )
        elif count > 1:
            issues.append(
                {
                    "severity": "errore",
                    "scope": event_id,
                    "message": f"ID evento duplicato ({count} occorrenze)",
                }
            )

    participant_ids = {
        str(participant.get("participant_id", "")) for participant in participants
    }
    for event in events_list:
        participant = str(event.get("participant_id_hash", ""))
        if not participant:
            issues.append(
                {
                    "severity": "errore",
                    "scope": str(event.get("event_id", "")),
                    "message": "Identificativo partecipante mancante",
                }
            )
        elif participant_ids and participant not in participant_ids:
            issues.append(
                {
                    "severity": "avviso",
                    "scope": str(event.get("event_id", "")),
                    "message": "Evento senza registro partecipante corrispondente",
                }
            )
        if not parse_timestamp(event.get("occurred_at")):
            issues.append(
                {
                    "severity": "errore",
                    "scope": str(event.get("event_id", "")),
                    "message": "Timestamp non valido o mancante",
                }
            )

    for session_id, session_events in group_sessions(events_list).items():
        starts = [
            event
            for event in session_events
            if event.get("event_type") == "session_started"
        ]
        completions = [
            event
            for event in session_events
            if event.get("event_type") == "session_completed"
        ]
        if len(starts) != 1:
            issues.append(
                {
                    "severity": "errore",
                    "scope": session_id,
                    "message": f"Eventi di avvio sessione: {len(starts)}",
                }
            )
        if len(completions) > 1:
            issues.append(
                {
                    "severity": "errore",
                    "scope": session_id,
                    "message": "Più eventi di completamento sessione",
                }
            )
        attempt_keys: Counter[tuple[str, int]] = Counter()
        for event in session_events:
            if event.get("event_type") == "answer_submitted":
                key = (
                    str(event.get("descriptor_id", "")),
                    int(event.get("attempt_number") or 0),
                )
                attempt_keys[key] += 1
        for (descriptor_id, attempt), count in attempt_keys.items():
            if count > 1:
                issues.append(
                    {
                        "severity": "errore",
                        "scope": session_id,
                        "message": (
                            f"Tentativo duplicato: {descriptor_id}, "
                            f"tentativo {attempt}"
                        ),
                    }
                )
    return issues


def first_event(
    events: Iterable[dict[str, Any]], event_type: str
) -> dict[str, Any] | None:
    return next(
        (event for event in events if event.get("event_type") == event_type),
        None,
    )


def _catalog_item(catalog: Catalog, descriptor_id: str) -> dict[str, Any]:
    try:
        return catalog.get(descriptor_id)
    except CatalogError:
        return {"descriptor_id": descriptor_id}


def _matches_filter(status: str, outcome_filter: str) -> bool:
    if outcome_filter in {"", "all"}:
        return True
    if outcome_filter == "focus":
        return status in FOCUS_OUTCOMES
    return status == outcome_filter


def _duration_seconds(start: str | None, end: str | None) -> int | None:
    parsed_start = parse_timestamp(start)
    parsed_end = parse_timestamp(end)
    if not parsed_start or not parsed_end:
        return None
    return max(round((parsed_end - parsed_start).total_seconds()), 0)


def _first_non_null(values: Iterable[Any]) -> Any:
    return next((value for value in values if value is not None), None)
