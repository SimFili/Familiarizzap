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
from src.guided_track import (
    CANONICAL_LEVELS,
    GUIDED_DESCRIPTOR_IDS,
    GUIDED_STAGES,
    guided_general_descriptors,
)


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
    assert basis == "guide_validated"
    assert "punti salienti" in first
    assert "B1" not in first and "B1" not in second
    assert "di nuovo B2" in second
    assert "discorso lungo" in second
    assert first != second
    assert "Esatto: B1" in final
    assert "B2" in second
    assert "punti salienti" in final
    assert "Confronta con" not in final
    assert "A2" not in final and "B2" not in final
    assert "Non ancora." not in first + second + final


def test_src_8_correct_feedback_explains_only_the_target_descriptor():
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
    assert "significato generale" in corrected
    assert "informazioni specifiche" in corrected
    assert "Confronta con" not in corrected
    assert set(re.findall(
        r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", corrected
    )) == {"B1+"}


def test_each_draft_guide_is_bound_to_a_real_descriptor_and_contrast():
    catalog = {item["descriptor_id"]: item for item in full_catalog()}
    bank = json.loads(GUIDE_DATA_PATH.read_text(encoding="utf-8"))
    assert bank["review_status"] == "mixed_validated_pending_and_draft"
    assert bank["pilot_validation_status"] == "guided_track_partial_validation"
    assert bank["pilot_validation_date"] == "2026-10-25"
    assert sum(
        item.get("validation_status") == "validated_for_guided_pilot"
        for item in bank["items"]
    ) == 13
    assert sum(
        item.get("validation_status") == "pending_targeted_review"
        for item in bank["items"]
    ) == 3
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
            assert set(guide["first_hints"]).issubset(guide["contrasts"])
            assert len(set(guide["first_hints"].values())) == len(guide["first_hints"])
            assert all(hint.endswith("?") for hint in guide["first_hints"].values())
        if guide.get("validation_status") in {
            "validated_for_guided_pilot",
            "pending_targeted_review",
        }:
            assert set(guide["first_hints"]) == {
                "A1", "A2", "B1", "B2"
            } - {guide["level"]}
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
            expected_basis = (
                "guide_validated"
                if guide.get("validation_status")
                == "validated_for_guided_pilot"
                else "guide_draft"
            )
            assert first_basis == second_basis == expected_basis
            assert first != second
            assert "Non ancora." not in first + second
            assert guide["level"] not in re.findall(
                r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)",
                first + second,
            )
            assert len(first) <= MAX_FEEDBACK_LENGTH
            assert len(second) <= MAX_FEEDBACK_LENGTH
            assert guide["contrasts"][selected_level]["text"] in second


def test_all_848_guided_feedback_states_are_safe_and_complete(monkeypatch):
    monkeypatch.setattr(feedback_module, "DRAFT_GUIDES_ENABLED", False)
    catalog = {item["descriptor_id"]: item for item in full_catalog()}
    phase_by_id = {
        descriptor_id: stage.phase
        for stage in GUIDED_STAGES
        for descriptor_id in stage.descriptor_ids
    }
    forbidden = re.compile(
        r"Non ancora|si limita|catalogo sorgente|Quale azione e quali condizioni|"
        r"\bLì\b|\bparlato\b",
        re.IGNORECASE,
    )
    checked = 0

    def verify(
        message: str,
        basis: str,
        expected_basis: str,
        *,
        correct: bool = False,
    ) -> None:
        nonlocal checked
        checked += 1
        assert basis == expected_basis
        assert len(message) <= MAX_FEEDBACK_LENGTH
        assert "…" not in message
        assert not forbidden.search(message)
        if correct:
            assert "Confronta con" not in message
            assert "Hai scelto" not in message

    for descriptor_id in GUIDED_DESCRIPTOR_IDS:
        descriptor = catalog[descriptor_id]
        phase = phase_by_id[descriptor_id]
        correct_level = descriptor["correct_level"]
        expected_basis = (
            "guide_validated"
            if DESCRIPTOR_GUIDES[descriptor_id].get("validation_status")
            == "validated_for_guided_pilot"
            else "guide_draft"
        )
        wrong_levels = [
            level for level in CANONICAL_LEVELS if level != correct_level
        ]

        message, basis = compose_feedback(
            descriptor,
            phase=phase,
            selected_level=correct_level,
            attempt_number=1,
            previous_attempts=[],
            completed_records=[],
        )
        verify(message, basis, expected_basis, correct=True)
        message, basis = compose_feedback(
            descriptor,
            phase=phase,
            selected_level=correct_level,
            attempt_number=1,
            previous_attempts=[],
            completed_records=[],
            prior_exposure_count=1,
        )
        verify(message, basis, expected_basis, correct=True)

        for first_wrong in wrong_levels:
            message, basis = compose_feedback(
                descriptor,
                phase=phase,
                selected_level=first_wrong,
                attempt_number=1,
                previous_attempts=[],
                completed_records=[],
            )
            verify(message, basis, expected_basis)
            message, basis = compose_feedback(
                descriptor,
                phase=phase,
                selected_level=correct_level,
                attempt_number=2,
                previous_attempts=[first_wrong],
                completed_records=[],
            )
            verify(message, basis, expected_basis, correct=True)

            for second_wrong in wrong_levels:
                message, basis = compose_feedback(
                    descriptor,
                    phase=phase,
                    selected_level=second_wrong,
                    attempt_number=2,
                    previous_attempts=[first_wrong],
                    completed_records=[],
                )
                verify(message, basis, expected_basis)
                message, basis = compose_feedback(
                    descriptor,
                    phase=phase,
                    selected_level=correct_level,
                    attempt_number=3,
                    previous_attempts=[first_wrong, second_wrong],
                    completed_records=[],
                )
                verify(message, basis, expected_basis, correct=True)

                for final_wrong in wrong_levels:
                    message, basis = compose_feedback(
                        descriptor,
                        phase=phase,
                        selected_level=final_wrong,
                        attempt_number=3,
                        previous_attempts=[first_wrong, second_wrong],
                        completed_records=[],
                    )
                    verify(message, basis, expected_basis)

    assert checked == 848


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
    assert basis == "guide_validated"
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
    assert basis == "guide_validated"
    assert "restano molto brevi" in first_low
    assert "Su quali temi" in first_high
    assert first_low != first_high
    assert "B1" not in re.findall(
        r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", first_low + first_high
    )


def test_correct_feedback_does_not_revisit_a_previous_wrong_choice():
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
    assert basis == "guide_validated"
    assert "Esatto: B1" in corrected
    assert "sequenza lineare" in corrected
    assert "Confronta con" not in corrected
    assert "A2" not in corrected

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
    assert "sostenute con elementi ed esempi" in wrong_final
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
    assert basis not in {"guide_draft", "guide_validated"}


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
    assert message.startswith("Che cosa è in grado di fare?")
    assert "deve fare la persona" not in message
    assert "ampiezza del compito" not in message


def test_active_feedback_describes_capabilities_instead_of_obligations():
    guides = json.loads(GUIDE_DATA_PATH.read_text(encoding="utf-8"))["items"]
    editorial_texts = []
    for guide in guides:
        editorial_texts.extend((guide["focus"], guide["reason"]))
        editorial_texts.extend(guide.get("first_hints", {}).values())
        editorial_texts.extend(
            contrast["text"] for contrast in guide["contrasts"].values()
        )
    for descriptor in full_catalog():
        editorial_texts.extend(
            text for key in ("rationale", "hint_1", "hint_2")
            if (text := descriptor.get(key, ""))
            and "feedback provvisorio" not in text.casefold()
        )
    for text in editorial_texts:
        assert "la soglia" not in text.casefold(), text
        assert not re.search(
            r"\b(?:deve|richiede|richiedono|richiesto|richiesta|si chiede|si chiedono)\b",
            text,
            re.IGNORECASE,
        ), text


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
        assert "Confronta con" not in message
        assert "Hai scelto" not in message
        corrected, _ = compose_feedback(
            descriptor,
            phase="orientation",
            selected_level=level,
            attempt_number=2,
            previous_attempts=[wrong],
            completed_records=[],
        )
        assert len(corrected) <= MAX_FEEDBACK_LENGTH
        assert "Confronta con" not in corrected
        assert "Hai scelto" not in corrected
