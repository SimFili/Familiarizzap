from __future__ import annotations

import pytest

from src.questionnaire import (
    QUESTIONNAIRE_VERSION,
    RATING_KEYS,
    QuestionnaireValidationError,
    questionnaire_is_submitted,
    validate_questionnaire,
)


def valid_payload() -> dict:
    return {
        "data_collection_consent": True,
        "q2_teaching_experience": "4-10 anni",
        "q3_teaching_contexts": ["Università"],
        "q3_teaching_context_other": "",
        **{key: 4 for key in RATING_KEYS},
        "q15_problems": "  Un problema   breve. ",
        "q16_positive_aspects": "Percorso chiaro.",
    }


def test_questionnaire_validation_keeps_only_the_declared_fields():
    payload = valid_payload()
    payload["unexpected"] = "do not store"

    result = validate_questionnaire(payload)

    assert result["q15_problems"] == "Un problema breve."
    assert result["q3_teaching_contexts"] == ["Università"]
    assert "unexpected" not in result


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("data_collection_consent", False, "consenso"),
        ("q2_teaching_experience", None, "anni"),
        ("q1_qcer_familiarity", None, "scala"),
    ],
)
def test_questionnaire_rejects_missing_required_answers(field, value, message):
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(QuestionnaireValidationError, match=message):
        validate_questionnaire(payload)


def test_other_teaching_context_can_be_written_freely():
    payload = valid_payload()
    payload["q3_teaching_contexts"] = []
    payload["q3_teaching_context_other"] = "Centro di formazione regionale"

    result = validate_questionnaire(payload)

    assert result["q3_teaching_context_other"] == (
        "Centro di formazione regionale"
    )


def test_submission_detection_is_version_specific():
    events = [
        {
            "event_type": "questionnaire_submitted",
            "questionnaire_version": QUESTIONNAIRE_VERSION,
        }
    ]

    assert questionnaire_is_submitted(events)
    assert not questionnaire_is_submitted(events, "future-version")
