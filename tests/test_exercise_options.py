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


def test_progress_map_reveals_levels_only_after_descriptor_completion():
    descriptors = app.CATALOG.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    session = app.SESSIONS.start_session(
        "progress-participant", "Anna", descriptors
    )

    initial = app._exercise_progress_data(session)

    assert initial["steps"][0]["kind"] == "current"
    assert initial["steps"][0]["level"] == ""
    assert all(step["level"] == "" for step in initial["steps"])

    correct_level = app.SESSIONS.current_descriptor(session)["correct_level"]
    completed = app.SESSIONS.submit_answer(session, correct_level)
    after_answer = app._exercise_progress_data(completed)

    assert after_answer["steps"][0]["kind"] == "done"
    assert after_answer["steps"][0]["level"] == correct_level
    assert after_answer["steps"][0]["badge"] == "1"
    assert after_answer["steps"][0]["status"] == "progress-first"

    advanced = app.SESSIONS.advance(completed)
    after_advance = app._exercise_progress_data(advanced)

    assert after_advance["steps"][0]["kind"] == "done"
    assert after_advance["steps"][1]["kind"] == "current"
    assert after_advance["steps"][1]["level"] == ""


def test_progress_map_marks_solution_shown_after_three_failed_attempts():
    descriptors = app.CATALOG.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    session = app.SESSIONS.start_session(
        "unresolved-progress", "Anna", descriptors
    )
    correct = app.SESSIONS.current_descriptor(session)["correct_level"]
    wrong = next(
        level for level in app.SESSIONS.available_levels(session)
        if level != correct
    )
    for _ in range(3):
        session = app.SESSIONS.submit_answer(session, wrong)

    step = app._exercise_progress_data(session)["steps"][0]

    assert step["level"] == correct
    assert step["badge"] == "!"
    assert step["status"] == "progress-unresolved"


def test_submit_answer_returns_the_updated_progress_map():
    descriptors = app.CATALOG.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )
    session = app.SESSIONS.start_session(
        "progress-output", "Anna", descriptors
    )
    correct_level = app.SESSIONS.current_descriptor(session)["correct_level"]

    result = app.submit_answer({"session": session}, correct_level)

    progress = result[1]
    assert progress["steps"][0]["kind"] == "done"
    assert progress["steps"][0]["level"] == correct_level
    assert progress["steps"][0]["badge"] == "1"


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
    assert result[1]["visible"] is False
    assert result[2]["visible"] is True
    assert result[3]["visible"] is False
    assert result[8].value == "Comprensione orale"
    assert result[9].value == "Comprensione orale generale"
    assert "messa in pausa" in result[10]
    assert result[11].value == session["session_id"]
    restored = app.SESSIONS.restore_session(
        "pause-participant", "Anna", session["session_id"]
    )
    assert restored["session_id"] == session["session_id"]


def test_exit_confirmation_can_be_opened_and_cancelled():
    opened = app.open_exercise_exit_confirmation()
    cancelled = app.cancel_exercise_exit()

    assert opened["visible"] is True
    assert cancelled["visible"] is False
