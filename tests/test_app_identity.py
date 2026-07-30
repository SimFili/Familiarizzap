from __future__ import annotations

import gradio as gr
from pathlib import Path

import app
from src.event_store import EventStoreError, LocalEventStore


def test_new_code_is_still_shown_if_follow_up_event_write_fails(
    monkeypatch,
):
    class Store:
        registered = None

        def list_participants(self):
            return []

        def register_participant(
            self,
            participant,
            shown_name,
            access_code_hash=None,
            name_lookup_hash=None,
        ):
            self.registered = (
                participant,
                shown_name,
                access_code_hash,
                name_lookup_hash,
            )
            return {}

    class Sessions:
        def record_access_code_event(self, participant, event_type):
            raise EventStoreError("offline dopo il registro")

        def record_consent(self, participant, version):
            raise AssertionError("non deve essere raggiunto")

        def record_participant_access(self, participant, method):
            raise AssertionError("non deve essere raggiunto")

    store = Store()
    monkeypatch.setattr(app, "STORE", store)
    monkeypatch.setattr(app, "SESSIONS", Sessions())
    monkeypatch.setattr(
        app,
        "_personal_view",
        lambda participant: (
            "",
            gr.Dropdown(choices=[]),
            "",
            [],
            [],
            gr.Dropdown(choices=[]),
        ),
    )

    result = app.identify_participant(
        "Anna", "Rossi", "", False, True, app._empty_ui_state()
    )

    assert store.registered is not None
    assert result[1]["access_code"]
    assert result[1]["access_code"] in result[5]
    assert "va conservato" in result[-1]


def test_homonyms_can_have_distinct_random_participant_ids(
    tmp_path: Path, monkeypatch
):
    class Sessions:
        def record_access_code_event(self, participant, event_type):
            return None

        def record_consent(self, participant, version):
            return None

        def record_participant_access(self, participant, method):
            return None

    store = LocalEventStore(tmp_path)
    monkeypatch.setattr(app, "STORE", store)
    monkeypatch.setattr(app, "SESSIONS", Sessions())
    monkeypatch.setattr(
        app,
        "_personal_view",
        lambda participant: (
            "",
            gr.Dropdown(choices=[]),
            "",
            [],
            [],
            gr.Dropdown(choices=[]),
        ),
    )

    first = app.identify_participant(
        "Anna", "Rossi", "", False, True, app._empty_ui_state()
    )
    second = app.identify_participant(
        "Anna", "Rossi", "", True, True, app._empty_ui_state()
    )

    assert first[0]["participant_id"] != second[0]["participant_id"]
    participants = store.list_participants()
    assert len(participants) == 2
    assert len({item["name_lookup_hash"] for item in participants}) == 1
