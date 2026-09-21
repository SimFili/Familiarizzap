from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

from src.feedback import (
    FEEDBACK_DATA_PATH,
    MAX_FEEDBACK_LENGTH,
    PREVALIDATED_CUES,
    _load_feedback_bank,
    compose_feedback,
)


CATALOG_PATH = Path(__file__).resolve().parents[1] / "space/data/catalog.full.json"


def full_catalog() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_every_prevalidated_cue_matches_its_exact_descriptor_text_and_level():
    catalog = {item["descriptor_id"]: item for item in full_catalog()}
    bank = json.loads(FEEDBACK_DATA_PATH.read_text(encoding="utf-8"))
    assert bank["schema_version"] == 2
    assert bank["review_status"] == "ai_prevalidated_pending_human_review"
    assert len(PREVALIDATED_CUES) == len(bank["items"]) == 21
    for descriptor_id, (level, digest, sentence, evidence) in PREVALIDATED_CUES.items():
        assert catalog[descriptor_id]["correct_level"] == level
        assert hashlib.sha256(
            catalog[descriptor_id]["descriptor_text"].encode("utf-8")
        ).hexdigest() == digest
        assert evidence
        assert all(
            fragment in catalog[descriptor_id]["descriptor_text"]
            for fragment in evidence
        )
        assert sentence.endswith(".")
        assert "catalogo sorgente" not in sentence


def test_prevalidated_feedback_changes_with_attempt_and_session_history():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    )
    first, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B2",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    second, _ = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B2",
        attempt_number=2,
        previous_attempts=["B2"],
        completed_records=[],
    )
    final, _ = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1",
        attempt_number=3,
        previous_attempts=["B2", "B2"],
        completed_records=[],
    )
    assert basis == "prevalidated"
    assert "punti salienti" in first
    assert "B1" not in first and "B1" not in second
    assert "ancora B2" in second
    assert "Sì, B1, dopo B2" in final
    assert "punti salienti" in final


def test_cue_is_not_used_if_the_catalog_text_changes():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    ).copy()
    descriptor["descriptor_text"] += " Testo modificato."
    _, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis != "prevalidated"


def test_cue_is_not_used_if_its_textual_evidence_is_wrong(monkeypatch):
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    )
    level, digest, cue, _ = PREVALIDATED_CUES["SRC-9"]
    monkeypatch.setitem(
        PREVALIDATED_CUES,
        "SRC-9",
        (level, digest, cue, ("testo che non compare nel descrittore",)),
    )
    _, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis != "prevalidated"


def test_invalid_feedback_bank_fails_closed(tmp_path: Path):
    path = tmp_path / "feedback.json"
    path.write_text('{"schema_version": 2, "items": []}', encoding="utf-8")
    assert _load_feedback_bank(path) == {}
    assert _load_feedback_bank(tmp_path / "missing.json") == {}


def test_first_try_is_recognized_without_claiming_mastery():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    )
    first, _ = compose_feedback(
        descriptor,
        phase="consolidation",
        selected_level="B1",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[{"correct_level": "B1"}],
    )
    assert "al primo tentativo questa volta" in first
    assert "padroneggi" not in first


def test_generic_rationale_is_not_presented_as_an_explanation():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-21"
    )
    message, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level=descriptor["correct_level"],
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis == "reflection"
    assert "catalogo sorgente" not in message
    assert "quali azioni e condizioni" in message


def test_full_catalog_feedback_is_short_and_wrong_hints_hide_target():
    for descriptor in full_catalog():
        level = descriptor["correct_level"]
        wrong = next(candidate for candidate in ("A1", "A2", "B1", "B2") if candidate != level)
        for attempt in (1, 2):
            message, _ = compose_feedback(
                descriptor,
                phase="orientation",
                selected_level=wrong,
                attempt_number=attempt,
                previous_attempts=[wrong] if attempt == 2 else [],
                completed_records=[],
            )
            assert len(message) <= MAX_FEEDBACK_LENGTH
            assert "catalogo sorgente" not in message
            assert f"Il livello corretto è {level}" not in message
            mentioned_levels = re.findall(
                r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", message
            )
            assert set(mentioned_levels).issubset({wrong})
        message, _ = compose_feedback(
            descriptor,
            phase="orientation",
            selected_level=level,
            attempt_number=1,
            previous_attempts=[],
            completed_records=[],
        )
        assert len(message) <= MAX_FEEDBACK_LENGTH
