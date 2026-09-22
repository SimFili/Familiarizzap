"""Short feedback grounded in prevalidated descriptor text.

Only descriptor-level matches from the active prevalidation nuclei are included.
The other descriptors get a reflective prompt, never an invented CEFR rule.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from .guided_track import GUIDED_DESCRIPTOR_IDS, GUIDED_STAGES


FEEDBACK_VERSION = "3"
MAX_FEEDBACK_LENGTH = 180
FEEDBACK_DATA_PATH = Path(__file__).resolve().parents[1] / "data/feedback.prevalidated.json"
GUIDE_DATA_PATH = Path(__file__).resolve().parents[1] / "data/feedback.descriptor_guides.json"
LOGGER = logging.getLogger(__name__)
GUIDE_ID_PATTERN = re.compile(r"(?:SRC-\d+|QCER-GEN-(?:A1|A2|B1|B2))")


def _load_feedback_bank(path: Path) -> dict[str, tuple[str, str, str, tuple[str, ...]]]:
    """Fail closed: invalid or missing data cannot present a mismatched cue."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or (
            data.get("schema_version") != 2
            or data.get("review_status") != "ai_prevalidated_pending_human_review"
            or not isinstance(data.get("items"), list)
        ):
            raise ValueError("metadata non valida")
        cues: dict[str, tuple[str, str, str, tuple[str, ...]]] = {}
        for item in data["items"]:
            descriptor_id = item["descriptor_id"]
            level = item["level"]
            digest = item["descriptor_sha256"]
            cue = item["cue"]
            evidence = item["evidence"]
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
                or not isinstance(evidence, list)
                or not 1 <= len(evidence) <= 4
                or any(
                    not isinstance(fragment, str)
                    or not 5 <= len(fragment) <= 100
                    for fragment in evidence
                )
            ):
                raise ValueError(f"indizio non valido: {descriptor_id}")
            cues[descriptor_id] = (level, digest, cue, tuple(evidence))
        return cues
    except (OSError, ValueError, TypeError, KeyError) as exc:
        LOGGER.warning("Feedback prevalidati non caricati: %s", exc)
        return {}


PREVALIDATED_CUES = _load_feedback_bank(FEEDBACK_DATA_PATH)
LEVEL_ORDER = ("A1", "A2", "A2+", "B1", "B1+", "B2")


def _load_descriptor_guides(path: Path) -> dict[str, dict[str, Any]]:
    """Load draft editorial contrasts, bound to the exact catalog text."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != 1
            or data.get("review_status") != "draft_pending_human_review"
            or not isinstance(data.get("items"), list)
        ):
            raise ValueError("metadata non valida")
        guides: dict[str, dict[str, Any]] = {}
        for item in data["items"]:
            descriptor_id = item["descriptor_id"]
            if (
                not isinstance(descriptor_id, str)
                or not GUIDE_ID_PATTERN.fullmatch(descriptor_id)
                or descriptor_id in guides
                or item["level"] not in {"A1", "A2", "A2+", "B1", "B1+", "B2"}
                or not isinstance(item["descriptor_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["descriptor_sha256"])
                or not isinstance(item["evidence"], list)
                or not 1 <= len(item["evidence"]) <= 4
                or any(not isinstance(part, str) or len(part) < 5 for part in item["evidence"])
                or any(
                    not isinstance(item[field], str)
                    or not item[field]
                    or len(item[field]) > 155
                    or "<" in item[field]
                    or ">" in item[field]
                    for field in ("focus", "reason")
                )
                or not isinstance(item["contrasts"], dict)
                or not item["contrasts"]
                or not set(item["contrasts"]).issubset(set(LEVEL_ORDER) - {item["level"]})
                or (
                    "first_hints" in item
                    and (
                        not isinstance(item["first_hints"], dict)
                        or set(item["first_hints"]) != set(item["contrasts"])
                        or any(
                            not isinstance(hint, str)
                            or not 20 <= len(hint) <= 155
                            or "<" in hint
                            or ">" in hint
                            or re.search(r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)", hint)
                            for hint in item["first_hints"].values()
                        )
                    )
                )
                or any(
                    not isinstance(contrast, dict)
                    or not isinstance(contrast.get("ref"), str)
                    or not GUIDE_ID_PATTERN.fullmatch(contrast["ref"])
                    or not isinstance(contrast.get("text"), str)
                    or not 15 <= len(contrast["text"]) <= 155
                    or "<" in contrast["text"]
                    or ">" in contrast["text"]
                    for contrast in item["contrasts"].values()
                )
                or re.search(
                    r"(?<!\w)(?:A1|A2\+?|B1\+?|B2)(?!\w)",
                    item["focus"],
                )
            ):
                raise ValueError(f"guida non valida: {descriptor_id}")
            guides[descriptor_id] = item
        return guides
    except (OSError, ValueError, TypeError, KeyError) as exc:
        LOGGER.warning("Guide editoriali non caricate: %s", exc)
        return {}


DESCRIPTOR_GUIDES = _load_descriptor_guides(GUIDE_DATA_PATH)
# Draft editorial content must not silently become pilot feedback.
DRAFT_GUIDES_ENABLED = os.getenv("FAMILIARIZZAPP_DRAFT_FEEDBACK", "") == "1"


def _matched_guide(descriptor: dict[str, Any]) -> dict[str, Any] | None:
    guide = DESCRIPTOR_GUIDES.get(str(descriptor.get("descriptor_id", "")))
    text = str(descriptor.get("descriptor_text", ""))
    if (
        guide
        and guide["level"] == descriptor.get("correct_level")
        and guide["descriptor_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
        and all(part in text for part in guide["evidence"])
    ):
        return guide
    return None


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
        if (
            "catalogo sorgente" in raw.casefold()
            or "motivazione dettagliata sarà aggiunta" in raw.casefold()
            or "soluzione corretta è il livello previsto dal catalogo" in raw.casefold()
        ):
            return ""
        raw = re.sub(r"^Il livello corretto è [^.!?]+[.!?]\s*", "", raw)
        return _short_sentence(raw, MAX_FEEDBACK_LENGTH - 18) if raw else ""
    raw = str(descriptor.get(f"hint_{attempt}", ""))
    if not raw or any(
        placeholder in raw.casefold()
        for placeholder in (
            "confronta il descrittore con i livelli vicini",
            "feedback provvisorio",
            "osserva l’ampiezza del compito, il tipo di contenuto",
        )
    ):
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
    guided_phase = phase in {stage.phase for stage in GUIDED_STAGES}
    guided_item = str(descriptor.get("descriptor_id", "")) in GUIDED_DESCRIPTOR_IDS
    guide = (
        _matched_guide(descriptor)
        if DRAFT_GUIDES_ENABLED or (guided_phase and guided_item)
        else None
    )
    if guide and not finished and attempt_number > 1 and selected_level not in guide["contrasts"]:
        guide = None
    if guide:
        if not finished:
            if attempt_number == 1:
                lead = f"Hai scelto {selected_level}. "
                if phase in {"consolidation", "maintenance"}:
                    lead += "Ripensa al contrasto già incontrato. "
                message = lead + guide.get("first_hints", {}).get(
                    selected_level, guide["focus"]
                )
            else:
                contrast = guide["contrasts"][selected_level]["text"]
                lead = (
                    f"Hai scelto di nuovo {selected_level}. "
                    if selected_level in previous_attempts
                    else f"Confronta con {selected_level}: "
                )
                message = lead + (
                    contrast
                    if selected_level in previous_attempts
                    else contrast[0].lower() + contrast[1:]
                )
            return _short_sentence(message, MAX_FEEDBACK_LENGTH), "guide_draft"

        if selected_level == correct:
            lead = f"Esatto: {correct}. "
            if attempt_number == 1 and (
                prior_exposure_count
                or any(record.get("correct_level") == correct for record in completed_records)
            ):
                lead = f"Esatto: {correct}, questa volta al primo tentativo. "
        else:
            lead = f"Il livello previsto è {correct}. "
        comparison_level = None
        if selected_level != correct and selected_level in guide["contrasts"]:
            # The final, unsuccessful choice has not received a comparison yet.
            comparison_level = selected_level
        elif selected_level == correct and previous_attempts:
            # After one error, revisit that choice. After two different errors,
            # revisit the first: the latest hint already compared the second.
            if attempt_number == 2 or (
                len(previous_attempts) > 1
                and previous_attempts[0] != previous_attempts[1]
            ):
                comparison_level = previous_attempts[0]
        if comparison_level in guide["contrasts"]:
            comparison = guide["contrasts"][comparison_level]["text"]
            reason = f"Confronta con {comparison_level}: {comparison[0].lower()}{comparison[1:]}"
        else:
            reason = guide["reason"]
        return _short_sentence(lead + reason, MAX_FEEDBACK_LENGTH), "guide_draft"

    prevalidated = PREVALIDATED_CUES.get(str(descriptor.get("descriptor_id", "")))
    descriptor_hash = hashlib.sha256(
        str(descriptor.get("descriptor_text", "")).encode("utf-8")
    ).hexdigest()
    cue = (
        prevalidated[2]
        if prevalidated
        and prevalidated[0] == correct
        and prevalidated[1] == descriptor_hash
        and all(
            fragment in str(descriptor.get("descriptor_text", ""))
            for fragment in prevalidated[3]
        )
        else ""
    )
    editorial = _editorial_text(descriptor, attempt_number, finished) if not cue else ""
    basis = "prevalidated" if cue else "editorial" if editorial else "reflection"
    detail = cue or editorial

    if not finished:
        if attempt_number == 1:
            if detail:
                message = "Rileggi la prestazione descritta: " + detail
            else:
                message = PHASE_PROMPTS.get(
                    phase, PHASE_PROMPTS["orientation"]
                )
        else:
            lead = (
                f"Hai scelto di nuovo {selected_level}. "
                if selected_level in previous_attempts
                else f"Hai scelto {selected_level}. "
            )
            message = lead + "Quale azione e quali condizioni distinguono il testo dalle opzioni rimaste?"
        return _short_sentence(message, MAX_FEEDBACK_LENGTH), basis

    if selected_level == correct:
        if attempt_number == 1 and (prior_exposure_count or any(
            record.get("correct_level") == correct for record in completed_records
        )):
            lead = f"Esatto: {correct}, questa volta al primo tentativo. "
        else:
            lead = f"Esatto: {correct}. "
    else:
        lead = f"Il livello previsto è {correct}. "

    if detail:
        message = lead + detail
    else:
        message = lead + "Per ragionarci: quali azioni e condizioni lo distinguono dalle altre opzioni?"
    return _short_sentence(message, MAX_FEEDBACK_LENGTH), basis
