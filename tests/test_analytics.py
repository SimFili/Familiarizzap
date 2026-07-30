from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.analytics import (
    descriptor_history,
    exact_timestamp,
    integrity_report,
    relative_timestamp,
    scale_map,
    session_records,
)
from src.catalog import Catalog, DEMO_CEFR_LEVELS
from src.event_store import LocalEventStore
from src.session_service import SessionService


def _catalog() -> Catalog:
    return Catalog.from_json(
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json",
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )


def _completed_session(tmp_path: Path):
    catalog = _catalog()
    store = LocalEventStore(tmp_path)
    store.register_participant("p1", "Anna Rossi", "code-hash")
    service = SessionService(catalog, store, "test-app", "test-content")
    descriptors = catalog.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione scritta",
        "Comprensione generale di un testo scritto",
    )[:1]
    state = service.start_session("p1", "Anna Rossi", descriptors)
    correct = service.current_descriptor(state)["correct_level"]
    state = service.submit_answer(state, correct)
    state = service.advance(state)
    return catalog, store, state


def test_relative_and_exact_time_have_distinct_audiences():
    timestamp = "2026-07-30T10:00:00+00:00"
    now = datetime(2026, 7, 30, 12, 5, tzinfo=timezone.utc)

    assert relative_timestamp(timestamp, now=now) == "circa 2 ore fa"
    exact = exact_timestamp(timestamp)
    assert "30/07/2026" in exact
    assert "UTC" in exact


def test_history_sessions_and_map_are_reconstructed_from_events(tmp_path: Path):
    catalog, store, state = _completed_session(tmp_path)
    events = store.list_events("p1")

    history = descriptor_history(events, catalog)
    sessions = session_records(events, catalog)
    rows = scale_map(
        catalog,
        events,
        (
            "Attività linguistico-comunicative",
            "Ricezione",
            "Comprensione scritta",
            "Comprensione generale di un testo scritto",
        ),
    )

    assert history[0]["outcome"] == "first"
    assert history[0]["exposure_number"] == 1
    assert sessions[0]["status"] == "completed"
    assert sessions[0]["first_attempt_rate"] == 100
    assert rows[0]["level_order"] >= rows[-1]["level_order"]
    assert sum(row["status"] == "first" for row in rows) == 1
    assert sum(row["status"] == "unseen" for row in rows) == 4
    assert state["session_finished"] is True


def test_integrity_check_accepts_a_consistent_archive(tmp_path: Path):
    _, store, _ = _completed_session(tmp_path)

    assert integrity_report(
        store.list_events(), store.list_participants()
    ) == []
