"""Validated questionnaire used after the four-stage recommended route."""

from __future__ import annotations

from typing import Any, Iterable


QUESTIONNAIRE_VERSION = "pilot-2026-11-07"

TEACHING_EXPERIENCE_CHOICES = (
    "Meno di 1 anno",
    "1-3 anni",
    "4-10 anni",
    "Più di 10 anni",
)

TEACHING_CONTEXT_CHOICES = (
    "Corsi per adulti",
    "Scuola",
    "Università",
    "Formazione di interpreti",
    "Corsi privati o individuali",
    "Associazioni ed enti del terzo settore",
)

RATING_ITEMS = (
    (
        "q1_qcer_familiarity",
        "Prima di questa prova, quanto conoscevi il QCER e i suoi descrittori?",
        "1 = per nulla · 5 = molto bene",
    ),
    (
        "q4_faster_orientation",
        "Usare FamiliarizzApp mi permetterebbe di orientarmi più rapidamente "
        "tra i livelli del QCER.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q5_effective_recognition",
        "Usare FamiliarizzApp renderebbe più efficace il mio modo di "
        "riconoscere il livello di un descrittore.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q6_easier_qcer_work",
        "Usare FamiliarizzApp renderebbe più facile il mio lavoro con il QCER.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q7_difficult_to_learn",
        "Imparare a usare FamiliarizzApp è stato difficile per me.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q8_clear_interaction",
        "La mia interazione con FamiliarizzApp è stata chiara e comprensibile.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q9_easy_to_gain_familiarity",
        "Credo che per me sarebbe facile acquisire dimestichezza nell’uso di "
        "FamiliarizzApp.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q10_easy_overall",
        "Nel complesso, trovo FamiliarizzApp facile da usare.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q11_reuse_intention",
        "Ho intenzione di usare di nuovo FamiliarizzApp nei prossimi mesi.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q12_recommend_to_colleague",
        "Consiglierei FamiliarizzApp a un/a collega che insegna LIS.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q13_feedback_helpfulness",
        "I feedback ricevuti dopo un tentativo mi hanno aiutato a capire "
        "perché il livello era quello.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
    (
        "q14_recognition_confidence",
        "Dopo questa prova mi sento più sicuro/a nel riconoscere il livello "
        "QCER di un descrittore.",
        "1 = per nulla d’accordo · 5 = completamente d’accordo",
    ),
)

RATING_KEYS = tuple(item[0] for item in RATING_ITEMS)


class QuestionnaireValidationError(ValueError):
    """Raised when a required questionnaire response is missing or invalid."""


def questionnaire_is_submitted(
    events: Iterable[dict[str, Any]],
    version: str = QUESTIONNAIRE_VERSION,
) -> bool:
    return any(
        event.get("event_type") == "questionnaire_submitted"
        and event.get("questionnaire_version") == version
        for event in events
    )


def validate_questionnaire(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, serialisable response set or a friendly error."""
    if payload.get("data_collection_consent") is not True:
        raise QuestionnaireValidationError(
            "Per inviare il questionario devi confermare il consenso alla "
            "raccolta delle risposte."
        )

    experience = str(payload.get("q2_teaching_experience") or "").strip()
    if experience not in TEACHING_EXPERIENCE_CHOICES:
        raise QuestionnaireValidationError(
            "Indica da quanti anni insegni LIS."
        )

    raw_contexts = payload.get("q3_teaching_contexts") or []
    if not isinstance(raw_contexts, (list, tuple)):
        raw_contexts = []
    contexts = [str(value).strip() for value in raw_contexts if str(value).strip()]
    if any(value not in TEACHING_CONTEXT_CHOICES for value in contexts):
        raise QuestionnaireValidationError(
            "Una delle risposte sul contesto di insegnamento non è valida."
        )
    context_other = _clean_text(payload.get("q3_teaching_context_other"), 500)
    if not contexts and not context_other:
        raise QuestionnaireValidationError(
            "Indica almeno un contesto di insegnamento oppure compilane uno "
            "nel campo «Altro»."
        )

    normalised: dict[str, Any] = {
        "data_collection_consent": True,
        "q2_teaching_experience": experience,
        "q3_teaching_contexts": list(dict.fromkeys(contexts)),
        "q3_teaching_context_other": context_other,
    }
    for key in RATING_KEYS:
        value = payload.get(key)
        try:
            rating = int(value)
        except (TypeError, ValueError) as exc:
            raise QuestionnaireValidationError(
                "Rispondi a tutte le domande con scala da 1 a 5."
            ) from exc
        if rating not in {1, 2, 3, 4, 5}:
            raise QuestionnaireValidationError(
                "Le risposte su scala devono essere comprese tra 1 e 5."
            )
        normalised[key] = rating

    normalised["q15_problems"] = _clean_text(payload.get("q15_problems"), 4000)
    normalised["q16_positive_aspects"] = _clean_text(
        payload.get("q16_positive_aspects"), 4000
    )
    return normalised


def _clean_text(value: Any, maximum: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > maximum:
        raise QuestionnaireValidationError(
            f"Una risposta aperta supera il limite di {maximum} caratteri."
        )
    return text
