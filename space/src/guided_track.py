"""A small, source-bound starting route through the canonical CEFR levels."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


CANONICAL_LEVELS = ("A1", "A2", "B1", "B2")


@dataclass(frozen=True)
class GuidedStage:
    key: str
    title: str
    path: tuple[str, str, str, str]
    descriptor_ids: tuple[str, str, str, str]
    learning_goal: str
    reflection_prompt: str

    @property
    def phase(self) -> str:
        return f"guided_core_{self.key}"


GUIDED_STAGES = (
    GuidedStage(
        key="general",
        title="Scala generale QCER",
        path=(
            "Quadro generale QCER",
            "Orientamento",
            "Scala generale",
            "Scala generale QCER",
        ),
        descriptor_ids=(
            "QCER-GEN-A1", "QCER-GEN-A2", "QCER-GEN-B1", "QCER-GEN-B2"
        ),
        learning_goal=(
            "Prima orientati: individua che cosa la persona sa fare, "
            "su quali argomenti e con quale autonomia. Non cercare una parola magica."
        ),
        reflection_prompt=(
            "Quali differenze tra A2, B1 e B2 ti sembrano più utili da verificare "
            "nelle scale successive?"
        ),
    ),
    GuidedStage(
        key="comprehension",
        title="Comprensione orale generale",
        path=(
            "Attività linguistico-comunicative",
            "Ricezione",
            "Comprensione orale",
            "Comprensione orale generale",
        ),
        descriptor_ids=("SRC-13", "SRC-11", "SRC-9", "SRC-7"),
        learning_goal=(
            "Ora osserva la ricezione: dal dato concreto ai punti salienti, "
            "fino al discorso lungo. Considera sempre le condizioni indicate."
        ),
        reflection_prompt=(
            "Nel distinguere B1 da A2 e B2, quali dettagli del compito di "
            "comprensione hanno contato davvero?"
        ),
    ),
    GuidedStage(
        key="production",
        title="Produzione orale generale",
        path=(
            "Attività linguistico-comunicative",
            "Produzione",
            "Produzione orale",
            "Produzione orale generale",
        ),
        descriptor_ids=("SRC-232", "SRC-231", "SRC-230", "SRC-229"),
        learning_goal=(
            "Passa alla produzione: confronta quanto è articolato il testo "
            "e come le idee vengono collegate e sostenute."
        ),
        reflection_prompt=(
            "Che cosa distingue la sequenza lineare di B1 dall'elenco A2 "
            "e dalle idee sviluppate con esempi in B2?"
        ),
    ),
    GuidedStage(
        key="interaction",
        title="Interazione orale generale",
        path=(
            "Attività linguistico-comunicative",
            "Interazione",
            "Interazione orale",
            "Interazione orale generale",
        ),
        descriptor_ids=("SRC-411", "SRC-410", "SRC-408", "SRC-406"),
        learning_goal=(
            "Infine metti insieme azione e autonomia nell'interazione: "
            "quanto la persona riesce a sostenere lo scambio e con quali aiuti?"
        ),
        reflection_prompt=(
            "Quale passaggio distingue l'intervento su temi familiari "
            "dall'interazione spontanea e agevole?"
        ),
    ),
)

GUIDED_DESCRIPTOR_IDS = frozenset(
    descriptor_id
    for stage in GUIDED_STAGES
    for descriptor_id in stage.descriptor_ids
)


# Transcribed from the four relevant rows in the researcher-supplied image.
# They enter only the guided introduction, never the free-exploration taxonomy.
GENERAL_QCER_REFERENCE = (
    (
        "A1",
        "È in grado di comprendere e utilizzare espressioni familiari di uso "
        "quotidiano e formule molto comuni per soddisfare bisogni di tipo "
        "concreto. Sa presentare se stesso/a e altri ed è in grado di porre "
        "domande su dati personali e rispondere a domande analoghe (il luogo "
        "dove abita, le persone che conosce, le cose che possiede). È in grado "
        "di interagire in modo semplice purché l’interlocutore si esprima "
        "lentamente e chiaramente e sia disposto a collaborare.",
    ),
    (
        "A2",
        "È in grado di comprendere frasi isolate ed espressioni di uso "
        "frequente relative ad ambiti di immediata rilevanza (ad es. "
        "informazioni di base sulla persona e sulla famiglia, acquisti, "
        "geografia locale, lavoro). È in grado di comunicare in attività "
        "semplici e di routine che richiedono solo uno scambio di informazioni "
        "semplice e diretto su argomenti familiari e abituali. È in grado di "
        "descrivere in termini semplici aspetti del proprio vissuto e del "
        "proprio ambiente ed elementi che si riferiscono a bisogni immediati.",
    ),
    (
        "B1",
        "È in grado di comprendere i punti essenziali di messaggi chiari in "
        "lingua standard su argomenti familiari che affronta normalmente al "
        "lavoro, a scuola, nel tempo libero ecc. Se la cava in molte situazioni "
        "che si possono presentare viaggiando in una regione dove si parla la "
        "lingua in questione. Sa produrre testi semplici e coerenti su "
        "argomenti che gli siano familiari o siano di suo interesse. È in grado "
        "di descrivere esperienze e avvenimenti, sogni, speranze, ambizioni, "
        "di esporre brevemente ragioni e dare spiegazioni su opinioni e progetti.",
    ),
    (
        "B2",
        "È in grado di comprendere le idee fondamentali di testi complessi su "
        "argomenti sia concreti sia astratti, comprese le discussioni tecniche "
        "nel proprio settore di specializzazione. È in grado di interagire con "
        "relativa scioltezza e spontaneità, tanto che l’interazione con un "
        "parlante nativo si sviluppa senza eccessiva fatica e tensione. Sa "
        "produrre testi chiari e articolati su un’ampia gamma di argomenti e "
        "esprimere un’opinione su un argomento d’attualità, esponendo i pro e "
        "i contro delle diverse opzioni.",
    ),
)


def guided_general_descriptors() -> list[dict[str, Any]]:
    """Keep the image-based source distinct from the Excel-derived catalog."""
    stage = GUIDED_STAGES[0]
    rows: list[dict[str, Any]] = []
    for (level, text), descriptor_id in zip(
        GENERAL_QCER_REFERENCE, stage.descriptor_ids
    ):
        rows.append(
            {
                "descriptor_id": descriptor_id,
                "source_row_id": "",
                "schema": stage.path[0],
                "modality": stage.path[1],
                "activity": stage.path[2],
                "scale": stage.path[3],
                "source_schema": stage.path[0],
                "source_modality": stage.path[1],
                "source_activity": stage.path[2],
                "correct_level": level,
                "descriptor_text": text,
                "rationale": "",
                "hint_1": "",
                "hint_2": "",
                "language": "it",
                "source": (
                    "Consiglio d’Europa (2020), Quadro comune europeo di "
                    "riferimento per le lingue: apprendimento, insegnamento, "
                    "valutazione — Volume complementare, p. 187"
                ),
                "source_version": "2026-09-21",
                "license_or_permission": "Da verificare prima della pubblicazione pubblica",
                "content_version": "introduzione-guidata-qcer-2026-09-21",
                "status": "guided_draft",
                "active": True,
            }
        )
    return rows


def stage_descriptors(
    catalog: Any, guides: dict[str, dict[str, Any]], stage: GuidedStage
) -> list[dict[str, Any]]:
    """Fail closed if any chosen text or its tailored guide has drifted."""
    selected: list[dict[str, Any]] = []
    stage_ids_by_level = dict(zip(CANONICAL_LEVELS, stage.descriptor_ids))
    for level, descriptor_id in zip(CANONICAL_LEVELS, stage.descriptor_ids):
        descriptor = catalog.get(descriptor_id)
        guide = guides.get(descriptor_id)
        descriptor_path = tuple(
            str(descriptor[field])
            for field in ("schema", "modality", "activity", "scale")
        )
        digest = hashlib.sha256(
            str(descriptor["descriptor_text"]).encode("utf-8")
        ).hexdigest()
        if (
            not descriptor.get("active")
            or descriptor_path != stage.path
            or descriptor["correct_level"] != level
            or not guide
            or guide["level"] != level
            or guide["descriptor_sha256"] != digest
            or not all(part in descriptor["descriptor_text"] for part in guide["evidence"])
            or not (set(CANONICAL_LEVELS) - {level}).issubset(guide["contrasts"])
            or any(
                guide["contrasts"][other_level]["ref"]
                != stage_ids_by_level[other_level]
                for other_level in CANONICAL_LEVELS
                if other_level != level
            )
        ):
            raise ValueError(f"Tappa guidata non pronta: {descriptor_id}")
        selected.append(descriptor)
    return selected


def guided_progress(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the next stage and resumable session from persisted events."""
    starts: dict[str, dict[str, Any]] = {}
    completed_sessions: set[str] = set()
    for event in events:
        session_id = str(event.get("session_id", ""))
        if event.get("event_type") == "session_started":
            starts[session_id] = event
        elif event.get("event_type") == "session_completed":
            completed_sessions.add(session_id)

    completed_stages: set[int] = set()
    resumable: dict[int, tuple[str, str]] = {}
    for session_id, start in starts.items():
        for index, stage in enumerate(GUIDED_STAGES):
            if (
                start.get("progression_phase") != stage.phase
                or tuple(start.get(field) for field in ("schema", "modality", "activity", "scale"))
                != stage.path
                or set(start.get("descriptor_order", [])) != set(stage.descriptor_ids)
                or set(start.get("answer_levels", [])) != set(CANONICAL_LEVELS)
            ):
                continue
            if session_id in completed_sessions:
                completed_stages.add(index)
            else:
                occurred_at = str(start.get("occurred_at", ""))
                if index not in resumable or occurred_at > resumable[index][0]:
                    resumable[index] = (occurred_at, session_id)

    next_index = next(
        (index for index in range(len(GUIDED_STAGES)) if index not in completed_stages),
        None,
    )
    return {
        "completed_indices": frozenset(completed_stages),
        "next_index": next_index,
        "resume_session_id": resumable.get(next_index, ("", None))[1],
    }
