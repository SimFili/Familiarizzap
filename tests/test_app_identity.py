from __future__ import annotations

from pathlib import Path

import gradio as gr

import app
from src.event_store import EventStoreError, LocalEventStore


def _empty_personal_view(participant: str):
    del participant
    return (
        "",
        gr.Dropdown(choices=[]),
        "",
        [],
        [],
        gr.Dropdown(choices=[]),
    )


def test_name_only_access_is_registered_and_remembered(
    tmp_path: Path, monkeypatch
):
    class Sessions:
        def record_consent(self, participant, version):
            return None

        def record_participant_access(self, participant, method):
            assert method == "name_only"

    store = LocalEventStore(tmp_path)
    monkeypatch.setattr(app, "STORE", store)
    monkeypatch.setattr(app, "SESSIONS", Sessions())
    monkeypatch.setattr(app, "_personal_view", _empty_personal_view)

    result = app.identify_participant(
        "  Anna  ", True, app._empty_ui_state()
    )

    assert result[0]["display_name"] == "Anna"
    assert result[1] == {"name": "Anna"}
    assert result[-1] == ""
    participants = store.list_participants()
    assert len(participants) == 1
    assert participants[0]["display_name"] == "Anna"


def test_same_normalized_name_recovers_the_same_profile(
    tmp_path: Path, monkeypatch
):
    class Sessions:
        def record_consent(self, participant, version):
            return None

        def record_participant_access(self, participant, method):
            return None

    store = LocalEventStore(tmp_path)
    monkeypatch.setattr(app, "STORE", store)
    monkeypatch.setattr(app, "SESSIONS", Sessions())
    monkeypatch.setattr(app, "_personal_view", _empty_personal_view)

    first = app.identify_participant(
        "Anna", True, app._empty_ui_state()
    )
    second = app.identify_participant(
        "  ANNA ", True, app._empty_ui_state()
    )

    assert first[0]["participant_id"] == second[0]["participant_id"]
    assert len(store.list_participants()) == 1


def test_practice_access_does_not_build_the_personal_map(
    tmp_path: Path, monkeypatch
):
    class Sessions:
        def record_consent(self, participant, version):
            return None

        def record_participant_access(self, participant, method):
            return None

        def incomplete_sessions(self, participant):
            return []

    def unexpected_personal_view(*args, **kwargs):
        raise AssertionError("La mappa non deve essere costruita nella home.")

    monkeypatch.setattr(app, "STORE", LocalEventStore(tmp_path))
    monkeypatch.setattr(app, "SESSIONS", Sessions())
    monkeypatch.setattr(app, "_personal_view", unexpected_personal_view)

    result = app.identify_for_practice(
        "Anna", True, app._empty_ui_state()
    )

    assert result[0]["display_name"] == "Anna"
    assert len(result) == 7
    assert result[-1] == ""


def test_storage_error_keeps_the_name_form_visible(monkeypatch):
    class Store:
        def register_participant(self, *args, **kwargs):
            raise EventStoreError("archivio non disponibile")

    monkeypatch.setattr(app, "STORE", Store())

    result = app.identify_participant(
        "Anna", True, app._empty_ui_state()
    )

    assert result[1] == {"name": ""}
    assert "archivio non disponibile" in result[-1]
