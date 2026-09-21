"""Short feedback grounded in prevalidated descriptor text.

Only descriptor-level matches from the active prevalidation nuclei are included.
The other descriptors get a reflective prompt, never an invented CEFR rule.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any


FEEDBACK_VERSION = "1"
MAX_FEEDBACK_LENGTH = 180
FEEDBACK_DATA_PATH = Path(__file__).resolve().parents[1] / "data/feedback.prevalidated.json"
LOGGER = logging.getLogger(__name__)


def _load_feedback_bank(path: Path) -> dict[str, tuple[str, str, str]]:
    """Fail closed: invalid or missing data cannot present a mismatched cue."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or (
            data.get("schema_version") != 1
            or data.get("review_status") != "ai_prevalidated_pending_human_review"
            or not isinstance(data.get("items"), list)
        ):
            raise ValueError("metadata non valida")
        cues: dict[str, tuple[str, str, str]] = {}
        for item in data["items"]:
            descriptor_id = item["descriptor_id"]
            level = item["level"]
            digest = item["descriptor_sha256"]
            cue = item["cue"]
            if (
                not isinstance(descriptor_id, str)
                or not re.fullmatch(r"SRC-\d+", descriptor_id)
                or descriptor_id in cues
                or level not in {"A1", "A2", "A2+", "B1", "B1+", "B2"}
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(cue, str)
                or not 10 <= len(cue) <= 140
                or not cue.endswith(".")
                or "<" in cue or ">" in cue
                or re.search(r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", cue)
            ):
                raise ValueError(f"indizio non valido: {descriptor_id}")
            cues[descriptor_id] = (level, digest, cue)
        return cues
    except (OSError, ValueError, TypeError, KeyError) as exc:
        LOGGER.warning("Feedback prevalidati non caricati: %s", exc)
        return {}


PREVALIDATED_CUES = _load_feedback_bank(FEEDBACK_DATA_PATH)


def _short_sentence(value: str, limit: int) -> str:
    """Prefer a complete short sentence to an abruptly cut explanation."""
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    first = re.split(r"(?<=[.!?])\s+", value, maxsplit=1)[0]
    if len(first) <= limit:
        return first
    words = value.split()
    kept: list[str] = []
    for word in words:
        if len(" ".join(kept + [word])) > limit - 1:
            break
        kept.append(word)
    return " ".join(kept).rstrip(" ,;:") + "…"


def _editorial_text(descriptor: dict[str, Any], attempt: int, finished: bool) -> str:
    if finished:
        raw = str(descriptor.get("rationale", ""))
        if "catalogo sorgente" in raw.casefold():
            return ""
        raw = re.sub(r"^Il livello corretto è [^.!?]+[.!?]\s*", "", raw)
        return _short_sentence(raw, MAX_FEEDBACK_LENGTH - 18) if raw else ""
    raw = str(descriptor.get(f"hint_{attempt}", ""))
    if not raw or "confronta il descrittore con i livelli vicini" in raw.casefold():
        return ""
    # Some legacy hints contain level labels. A hint must not disclose the
    # answer (or suggest a different level) while a retry is still possible.
    if re.search(r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", raw):
        return ""
    return _short_sentence(raw, MAX_FEEDBACK_LENGTH - 15)


PHASE_PROMPTS = {
    "orientation": "Che cosa deve fare la persona? Guarda anche le condizioni del compito.",
    "canonical_variation": "Che cosa cambia rispetto agli esempi precedenti: azione, autonomia o condizioni?",
    "introduce_a2_plus": "Quale dettaglio distingue questo compito dai livelli vicini?",
    "introduce_b1_plus": "Quale dettaglio distingue questo compito dai livelli vicini?",
    "deepening": "Rileggi l'intero compito, non una sola parola.",
    "consolidation": "Quale indizio ti aveva aiutato negli incontri precedenti?",
    "maintenance": "Ricontrolla il compito e le condizioni prima di scegliere.",
}


def compose_feedback(
    descriptor: dict[str, Any],
    *,
    phase: str,
    selected_level: str,
    attempt_number: int,
    previous_attempts: list[str],
    completed_records: list[dict[str, Any]],
    prior_exposure_count: int = 0,
) -> tuple[str, str]:
    """Return (message, basis) without disclosing the answer on a wrong try."""
    correct = str(descriptor["correct_level"])
    finished = selected_level == correct or attempt_number == 3
    prevalidated = PREVALIDATED_CUES.get(str(descriptor.get("descriptor_id", "")))
    descriptor_hash = hashlib.sha256(
        str(descriptor.get("descriptor_text", "")).encode("utf-8")
    ).hexdigest()
    cue = (
        prevalidated[2]
        if prevalidated
        and prevalidated[0] == correct
        and prevalidated[1] == descriptor_hash
        else ""
    )
    editorial = _editorial_text(descriptor, attempt_number, finished) if not cue else ""
    basis = "prevalidated" if cue else "editorial" if editorial else "reflection"
    detail = cue or editorial

    if not finished:
        if attempt_number == 1:
            if detail:
                lead = "Non ancora. " if phase != "consolidation" else "Da rivedere. "
                message = lead + detail
            else:
                message = "Non ancora. " + PHASE_PROMPTS.get(
                    phase, PHASE_PROMPTS["orientation"]
                )
        elif detail:
            lead = (
                f"Hai scelto ancora {selected_level}. "
                if selected_level in previous_attempts
                else f"Anche {selected_level} non va. "
            )
            message = lead + detail
        else:
            message = "Ancora no. Confronta il compito e le condizioni del testo con le opzioni rimaste."
        return _short_sentence(message, MAX_FEEDBACK_LENGTH), basis

    if selected_level == correct:
        if attempt_number > 1:
            lead = f"Sì, {correct}, dopo {previous_attempts[0]}. "
        elif prior_exposure_count or any(
            record.get("correct_level") == correct for record in completed_records
        ):
            lead = f"Sì, {correct} al primo tentativo questa volta. "
        else:
            lead = f"Sì, {correct}. "
    else:
        lead = f"Il livello è {correct}. "

    if detail:
        message = lead + detail
    else:
        message = lead + "Per ragionarci: quali azioni e condizioni lo distinguono dalle altre opzioni?"
    return _short_sentence(message, MAX_FEEDBACK_LENGTH), basis
