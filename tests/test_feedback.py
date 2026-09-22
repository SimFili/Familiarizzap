from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

import pytest

import src.feedback as feedback_module
from src.feedback import (
    DESCRIPTOR_GUIDES,
    FEEDBACK_DATA_PATH,
    GUIDE_DATA_PATH,
    MAX_FEEDBACK_LENGTH,
    PREVALIDATED_CUES,
    _load_feedback_bank,
    compose_feedback,
)
from src.guided_track import guided_general_descriptors


CATALOG_PATH = Path(__file__).resolve().parents[1] / "space/data/catalog.full.json"


@pytest.fixture(autouse=True)
def enable_draft_guides_for_local_feedback_tests(monkeypatch):
    monkeypatch.setattr(feedback_module, "DRAFT_GUIDES_ENABLED", True)


def full_catalog() -> list[dict]:
    return (
        json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        + guided_general_descriptors()
    )


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


def test_draft_guide_changes_content_between_attempts_and_explains_answer():
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
    assert basis == "guide_draft"
    assert "punti salienti" in first
    assert "B1" not in first and "B1" not in second
    assert "di nuovo B2" in second
    assert "discorso lungo" in second
    assert first != second
    assert "Esatto: B1" in final
    assert "B2" in second
    assert "A2" in final and "B2" in final
    assert "punti salienti" in final
    assert "Non ancora." not in first + second + final


def test_src_8_comparison_is_local_to_its_b1_neighbour():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-8"
    )
    assert "in una varietà piuttosto familiare" in descriptor["descriptor_text"]
    corrected, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1+",
        attempt_number=2,
        previous_attempts=["B1"],
        completed_records=[],
    )
    assert basis == "guide_draft"
    assert "B1 della stessa scala" in corrected
    assert "mette l'accento principalmente sui punti salienti" in corrected


def test_each_draft_guide_is_bound_to_a_real_descriptor_and_contrast():
    catalog = {item["descriptor_id"]: item for item in full_catalog()}
    bank = json.loads(GUIDE_DATA_PATH.read_text(encoding="utf-8"))
    assert bank["review_status"] == "draft_pending_human_review"
    assert len(DESCRIPTOR_GUIDES) == len(bank["items"]) == 21
    assert [item["descriptor_id"] for item in bank["suspended_items"]] == ["SRC-10"]
    assert "SRC-10" not in DESCRIPTOR_GUIDES
    for descriptor_id, guide in DESCRIPTOR_GUIDES.items():
        descriptor = catalog[descriptor_id]
        assert descriptor["scale"] in bank["scales"]
        assert descriptor["correct_level"] == guide["level"]
        assert hashlib.sha256(
            descriptor["descriptor_text"].encode("utf-8")
        ).hexdigest() == guide["descriptor_sha256"]
        assert all(
            part in descriptor["descriptor_text"]
            for part in guide["evidence"]
        )
        assert guide["focus"] != guide["reason"]
        scale_path = tuple(
            descriptor[field] for field in ("schema", "modality", "activity", "scale")
        )
        available_levels = {
            item["correct_level"]
            for item in catalog.values()
            if tuple(item[field] for field in ("schema", "modality", "activity", "scale"))
            == scale_path
        }
        assert set(guide["contrasts"]) == available_levels - {guide["level"]}
        if "first_hints" in guide:
            assert set(guide["first_hints"]) == set(guide["contrasts"])
            assert len(set(guide["first_hints"].values())) == len(guide["first_hints"])
            assert all(hint.endswith("?") for hint in guide["first_hints"].values())
        for selected_level, contrast in guide["contrasts"].items():
            reference = catalog[contrast["ref"]]
            assert tuple(
                reference[field] for field in ("schema", "modality", "activity", "scale")
            ) == scale_path
            assert reference["correct_level"] == selected_level
            assert contrast["text"]


def test_draft_guides_compare_each_wrong_level_without_repeating_a_hint():
    catalog = {item["descriptor_id"]: item for item in full_catalog()}
    for descriptor_id, guide in DESCRIPTOR_GUIDES.items():
        descriptor = catalog[descriptor_id]
        for selected_level in guide["contrasts"]:
            first, first_basis = compose_feedback(
                descriptor,
                phase="orientation",
                selected_level=selected_level,
                attempt_number=1,
                previous_attempts=[],
                completed_records=[],
            )
            second, second_basis = compose_feedback(
                descriptor,
                phase="orientation",
                selected_level=selected_level,
                attempt_number=2,
                previous_attempts=[selected_level],
                completed_records=[],
            )
            assert first_basis == second_basis == "guide_draft"
            assert first != second
            assert "Non ancora." not in first + second
            assert guide["level"] not in re.findall(
                r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)",
                first + second,
            )
            assert len(first) <= MAX_FEEDBACK_LENGTH
            assert len(second) <= MAX_FEEDBACK_LENGTH
            assert guide["contrasts"][selected_level]["text"] in second


def test_unreviewed_guides_are_not_active_by_default(monkeypatch):
    monkeypatch.setattr(feedback_module, "DRAFT_GUIDES_ENABLED", False)
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    )
    _, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B2",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis != "guide_draft"


def test_second_hint_uses_the_level_actually_chosen():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-9"
    )
    second, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1+",
        attempt_number=2,
        previous_attempts=["A2"],
        completed_records=[],
    )
    assert basis == "guide_draft"
    assert "Confronta con B1+" in second
    assert "informazioni specifiche" in second
    assert "discorso lungo" not in second
    assert "B1" not in re.findall(
        r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", second
    )


def test_first_hint_on_interaction_scale_responds_to_chosen_level():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-408"
    )
    first_low, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="A2",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    first_high, _ = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1+",
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis == "guide_draft"
    assert "scambi molto brevi" in first_low
    assert "situazioni meno frequenti" in first_high
    assert first_low != first_high
    assert "B1" not in re.findall(
        r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", first_low + first_high
    )


def test_final_feedback_revisits_a_real_wrong_choice_without_repeating_latest_hint():
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-230"
    )
    corrected, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B1",
        attempt_number=2,
        previous_attempts=["A2"],
        completed_records=[],
    )
    assert basis == "guide_draft"
    assert "Confronta con A2" in corrected
    assert "elenco" in corrected

    wrong_final, _ = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level="B2",
        attempt_number=3,
        previous_attempts=["A2", "A1"],
        completed_records=[],
    )
    assert "Il livello previsto è B1" in wrong_final
    assert "Confronta con B2" in wrong_final
    assert "sostenute con esempi" in wrong_final
    assert len(wrong_final) <= MAX_FEEDBACK_LENGTH


def test_guide_is_not_used_if_the_catalog_text_changes():
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
    assert basis != "guide_draft"


def test_cue_is_not_used_if_its_textual_evidence_is_wrong(monkeypatch):
    descriptor = next(
        item for item in full_catalog() if item["descriptor_id"] == "SRC-45"
    )
    level, digest, cue, _ = PREVALIDATED_CUES["SRC-45"]
    monkeypatch.setitem(
        PREVALIDATED_CUES,
        "SRC-45",
        (level, digest, cue, ("testo che non compare nel descrittore",)),
    )
    _, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level=descriptor["correct_level"],
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
    assert "questa volta al primo tentativo" in first
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


@pytest.mark.parametrize(
    "descriptor_id", ("SRC-87", "SRC-88", "SRC-90", "SRC-91", "SRC-94", "SRC-95")
)
def test_catalog_placeholder_is_not_presented_as_a_final_explanation(
    descriptor_id: str,
):
    descriptor = next(
        item for item in full_catalog()
        if item["descriptor_id"] == descriptor_id
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
    assert "motivazione dettagliata" not in message.casefold()
    assert "livello previsto dal catalogo" not in message.casefold()


def test_common_catalog_hint_is_not_mislabelled_as_specific_feedback():
    descriptor = next(
        item for item in full_catalog()
        if item["descriptor_id"] == "SRC-21"
    )
    wrong = next(
        level for level in ("A1", "A2", "B1", "B2")
        if level != descriptor["correct_level"]
    )
    message, basis = compose_feedback(
        descriptor,
        phase="orientation",
        selected_level=wrong,
        attempt_number=1,
        previous_attempts=[],
        completed_records=[],
    )
    assert basis == "reflection"
    assert "ampiezza del compito" not in message


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
            assert "Non ancora." not in message
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
