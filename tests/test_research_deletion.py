from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import app
from src.event_store import LocalEventStore


def _authorized_state(monkeypatch) -> dict:
    monkeypatch.setattr(
        app,
        "SETTINGS",
        replace(app.SETTINGS, researcher_access_key="research-secret"),
    )
    return app._authorized_research_state()


def _questionnaire_event() -> dict:
    return {
        "event_id": "questionnaire",
        "event_type": "questionnaire_submitted",
        "occurred_at": "2026-11-17T10:00:00+00:00",
        "session_id": "questionnaire-p1-pilot",
        "participant_id_hash": "p1",
    }


def test_research_authorization_state_cannot_be_replaced_by_a_boolean(
    monkeypatch,
):
    state = _authorized_state(monkeypatch)

    assert app._research_authorized(state)
    assert not app._research_authorized({"authorized": True})
    assert not app._research_authorized({**state, "proof": "altered"})


def test_researcher_previews_and_confirms_questionnaire_deletion(
    tmp_path: Path, monkeypatch
):
    state = _authorized_state(monkeypatch)
    store = LocalEventStore(tmp_path)
    store.register_participant("p1", "Anna")
    store.append_events([_questionnaire_event()])
    monkeypatch.setattr(app, "STORE", store)

    preview, summary, confirmation, _ = app.preview_research_deletion(
        state, "p1", "questionnaire"
    )
    assert preview["questionnaire_count"] == 1
    assert "Anna" in summary
    assert confirmation == ""

    wrong = app.delete_research_data(state, preview, "elimina")
    assert "esattamente" in wrong[0]
    assert len(store.list_events("p1")) == 1

    completed = app.delete_research_data(state, preview, "ELIMINA")
    assert "Cancellazione completata" in completed[0]
    assert store.list_events("p1") == []
    assert store.get_participant("p1") is not None


def test_duplicate_research_participant_names_are_disambiguated():
    choices = app._research_participant_choices(
        [
            {"participant_id": "abcdefgh-one", "display_name": "Anna"},
            {"participant_id": "abcdefgh-two", "display_name": "ANNA"},
            {"participant_id": "unique", "display_name": "Bruno"},
        ]
    )

    assert choices[0] == ("Anna · ID abcdefgh-one", "abcdefgh-one")
    assert choices[1] == ("ANNA · ID abcdefgh-two", "abcdefgh-two")
    assert choices[2] == ("Bruno", "unique")
