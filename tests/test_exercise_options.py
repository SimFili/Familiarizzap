from __future__ import annotations

from collections import Counter

import app


def test_exercise_options_show_descriptor_count_but_submit_level_value(
    monkeypatch,
):
    descriptors = app.CATALOG.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    session = app.SESSIONS.start_session(
        "options-participant", "Anna", descriptors
    )

    level_radio = app._exercise_view(session)[3]
    expected = Counter(item["correct_level"] for item in descriptors)

    assert level_radio.choices == [
        (
            f"{level} · {expected[level]} "
            f"{'descrittore' if expected[level] == 1 else 'descrittori'}",
            level,
        )
        for level in app.SESSIONS.available_levels(session)
    ]


def test_pausing_exercise_returns_to_selected_scale_without_losing_session():
    descriptors = app.CATALOG.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    session = app.SESSIONS.start_session(
        "pause-participant", "Anna", descriptors
    )
    state = {
        **app._empty_ui_state(),
        "participant_id": "pause-participant",
        "display_name": "Anna",
        "session": session,
    }

    result = app.pause_session_and_choose_scale(state)

    assert result[0]["session"] is None
    assert result[1]["visible"] is True
    assert result[2]["visible"] is False
    assert result[7].value == "Comprensione orale"
    assert result[8].value == "Comprensione orale generale"
    assert "messa in pausa" in result[9]
    assert result[10].value == session["session_id"]
    restored = app.SESSIONS.restore_session(
        "pause-participant", "Anna", session["session_id"]
    )
    assert restored["session_id"] == session["session_id"]


def test_exit_confirmation_can_be_opened_and_cancelled():
    opened = app.open_exercise_exit_confirmation()
    cancelled = app.cancel_exercise_exit()

    assert opened["visible"] is True
    assert cancelled["visible"] is False
