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
