from __future__ import annotations

import zipfile
from pathlib import Path

from src.catalog import Catalog, DEMO_CEFR_LEVELS
from src.event_store import LocalEventStore
from src.research_export import build_research_export
from src.session_service import SessionService


def test_research_export_contains_raw_and_derived_data_without_code_hash(
    tmp_path: Path,
):
    catalog = Catalog.from_json(
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json",
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )
    store = LocalEventStore(tmp_path / "data")
    store.register_participant(
        "p1",
        "Anna Rossi",
        "never-export-this-hash",
        name_lookup_hash="never-export-this-name-lookup",
    )
    service = SessionService(catalog, store, "test", "demo")
    descriptor = catalog.all()[0]
    state = service.start_session("p1", "Anna Rossi", [descriptor])
    state = service.submit_answer(state, descriptor["correct_level"])
    service.advance(state)

    archive = build_research_export(
        store.list_participants(), store.list_events(), catalog
    )

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert {
            "participants.csv",
            "sessions.csv",
            "descriptor_history.csv",
            "attempts.csv",
            "integrity.csv",
            "events.jsonl",
            "manifest.json",
        }.issubset(names)
        participants = bundle.read("participants.csv").decode("utf-8-sig")
        assert "Anna Rossi" in participants
        assert "never-export-this-hash" not in participants
        assert "never-export-this-name-lookup" not in participants
        assert bundle.read("events.jsonl")
