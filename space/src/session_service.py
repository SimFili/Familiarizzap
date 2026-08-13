from __future__ import annotations

import copy
import random
import secrets
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .catalog import Catalog
from .event_store import EventStore


EVENT_NAMESPACE = uuid.UUID("a302ad37-79ac-4ce0-96f6-1721259d980d")
CANONICAL_LEVELS = ("A1", "A2", "B1", "B2")


class SessionError(RuntimeError):
    """Raised when a session transition is not allowed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(
        self,
        catalog: Catalog,
        event_store: EventStore,
        app_version: str,
        content_revision: str,
    ):
        self.catalog = catalog
        self.event_store = event_store
        self.app_version = app_version
        self.content_revision = content_revision

    def record_consent(
        self, participant_id: str, consent_version: str
    ) -> None:
        session_id = f"consent-{participant_id}"
        event_id = str(
            uuid.uuid5(
                EVENT_NAMESPACE,
                f"{session_id}:{consent_version}",
            )
        )
        self.event_store.append_events(
            [
                self._base_event(
                    event_id=event_id,
                    event_type="consent_recorded",
                    session_id=session_id,
                    participant_id=participant_id,
                    consent_version=consent_version,
                )
            ]
        )

    def record_participant_access(
        self, participant_id: str, access_method: str
    ) -> None:
        access_id = str(uuid.uuid4())
        self.event_store.append_events(
            [
                self._base_event(
                    event_id=access_id,
                    event_type="participant_accessed",
                    session_id=f"access-{access_id}",
                    participant_id=participant_id,
                    access_method=access_method,
                )
            ]
        )

    def start_session(
        self,
        participant_id: str,
        display_name: str,
        descriptors: list[dict[str, Any]],
        *,
        include_plus_levels: bool = True,
        session_size: int | None = None,
        selected_descriptor_ids: list[str] | None = None,
        progression_phase: str = "",
        progression_label: str = "",
        progression_note: str = "",
        review_descriptor_ids: list[str] | None = None,
        answer_levels_override: list[str] | None = None,
        remaining_new_override: int | None = None,
    ) -> dict[str, Any]:
        if not include_plus_levels:
            descriptors = [
                item
                for item in descriptors
                if item["correct_level"] not in {"A2+", "B1+"}
            ]
        if not descriptors:
            raise SessionError(
                "La scala selezionata non contiene descrittori con i livelli "
                "scelti. Riattiva A2+ e B1+."
            )
        all_events = self.event_store.list_events(participant_id)
        exposure_counts: dict[str, int] = defaultdict(int)
        encounter_counts: dict[str, int] = defaultdict(int)
        prior_sessions: set[str] = set()
        for event in all_events:
            if event.get("event_type") == "descriptor_completed":
                exposure_counts[str(event.get("descriptor_id", ""))] += 1
            if event.get("event_type") == "descriptor_presented":
                encounter_counts[str(event.get("descriptor_id", ""))] += 1
            if event.get("event_type") == "session_started":
                prior_sessions.add(str(event.get("session_id", "")))
                if event.get("session_mode") == "block":
                    for item_id in event.get("descriptor_order", []):
                        encounter_counts[str(item_id)] += 1

        seed = secrets.randbits(63)
        randomizer = random.Random(seed)
        eligible_descriptors = list(descriptors)
        unseen_descriptors = [
            item
            for item in eligible_descriptors
            if encounter_counts[item["descriptor_id"]] == 0
        ]
        requested_size = (
            max(int(session_size), 1) if session_size is not None else None
        )
        selected_id_set = set(selected_descriptor_ids or [])
        if selected_descriptor_ids is not None:
            selected_descriptors = [
                item
                for item in eligible_descriptors
                if item["descriptor_id"] in selected_id_set
            ]
            if len(selected_descriptors) != len(selected_id_set):
                raise SessionError("Il percorso contiene descrittori non disponibili.")
            session_mode = "progressive"
        elif requested_size is None:
            selected_descriptors = eligible_descriptors
            session_mode = "full"
        else:
            selection_pool = unseen_descriptors or eligible_descriptors
            selected_descriptors = self._balanced_selection(
                selection_pool,
                min(requested_size, len(selection_pool)),
                randomizer,
                encounter_counts,
            )
            session_mode = "block"

        descriptor_ids = [
            item["descriptor_id"] for item in selected_descriptors
        ]
        randomizer.shuffle(descriptor_ids)
        remaining_new_after_batch = max(
            len(unseen_descriptors)
            - sum(
                encounter_counts[item_id] == 0 for item_id in descriptor_ids
            ),
            0,
        )
        if remaining_new_override is not None:
            remaining_new_after_batch = max(int(remaining_new_override), 0)
        session_id = str(uuid.uuid4())
        first = self.catalog.get(descriptor_ids[0])
        scale_descriptors = self.catalog.for_scale(
            first["schema"],
            first["modality"],
            first["activity"],
            first["scale"],
        )
        if not include_plus_levels:
            scale_descriptors = [
                item
                for item in scale_descriptors
                if item["correct_level"] not in {"A2+", "B1+"}
            ]
        answer_levels = self.catalog.levels_for(
            [item["descriptor_id"] for item in scale_descriptors]
        )
        if answer_levels_override is not None:
            allowed_answers = set(answer_levels_override)
            answer_levels = [
                level for level in answer_levels if level in allowed_answers
            ]
        if not answer_levels:
            raise SessionError("Il percorso non contiene livelli di risposta validi.")
        level_counts = Counter(
            item["correct_level"] for item in eligible_descriptors
        )
        now = utc_now()
        state = {
            "participant_id": participant_id,
            "display_name": display_name,
            "session_id": session_id,
            "schema": first["schema"],
            "modality": first["modality"],
            "activity": first["activity"],
            "scale": first["scale"],
            "seed": seed,
            "descriptor_ids": descriptor_ids,
            "available_levels": answer_levels,
            "level_counts": dict(level_counts),
            "include_plus_levels": include_plus_levels,
            "session_mode": session_mode,
            "session_size_requested": requested_size,
            "scale_descriptor_count": len(eligible_descriptors),
            "remaining_new_after_batch": remaining_new_after_batch,
            "progression_phase": progression_phase,
            "progression_label": progression_label,
            "progression_note": progression_note,
            "review_descriptor_ids": list(review_descriptor_ids or []),
            "current_index": 0,
            "attempts": [],
            "feedbacks": [],
            "descriptor_finished": False,
            "last_result": None,
            "completed_records": [],
            "session_finished": False,
            "started_at": now,
            "descriptor_presented_at": now,
            "attempt_started_at": now,
            "prior_exposure_counts": dict(exposure_counts),
        }
        start_event = self._base_event(
            event_id=self._event_id(session_id, "session-started"),
            event_type="session_started",
            session_id=session_id,
            participant_id=participant_id,
            schema=state["schema"],
            modality=state["modality"],
            activity=state["activity"],
            scale=state["scale"],
            source_schema=first.get("source_schema", first["schema"]),
            source_modality=first.get("source_modality", first["modality"]),
            source_activity=first.get("source_activity", first["activity"]),
            seed=seed,
            descriptor_order=descriptor_ids,
            answer_levels=answer_levels,
            level_counts=dict(level_counts),
            include_plus_levels=include_plus_levels,
            session_mode=session_mode,
            session_size_requested=requested_size,
            scale_descriptor_count=len(eligible_descriptors),
            remaining_new_after_batch=remaining_new_after_batch,
            progression_phase=progression_phase,
            progression_label=progression_label,
            progression_note=progression_note,
            review_descriptor_ids=list(review_descriptor_ids or []),
            descriptor_count=len(descriptor_ids),
            prior_session_count=len(prior_sessions),
            occurred_at=now,
        )
        presented_event = self._presented_event(state)
        self.event_store.append_events([start_event, presented_event])
        return state

    def start_progressive_session(
        self,
        participant_id: str,
        display_name: str,
        descriptors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not descriptors:
            raise SessionError("La scala selezionata non contiene descrittori.")
        plan = self._progressive_plan(participant_id, descriptors)
        return self.start_session(
            participant_id,
            display_name,
            descriptors,
            include_plus_levels=True,
            selected_descriptor_ids=plan["descriptor_ids"],
            progression_phase=plan["phase"],
            progression_label=plan["label"],
            progression_note=plan["note"],
            review_descriptor_ids=plan["review_descriptor_ids"],
            answer_levels_override=plan["answer_levels"],
            remaining_new_override=plan["remaining_new"],
        )

    def _progressive_plan(
        self,
        participant_id: str,
        descriptors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the next gentle, data-driven encounter for one scale."""
        randomizer = random.Random(secrets.randbits(63))
        by_id = {item["descriptor_id"]: item for item in descriptors}
        first = descriptors[0]
        all_events = self.event_store.list_events(participant_id)
        starts = [
            event
            for event in all_events
            if event.get("event_type") == "session_started"
            and event.get("schema") == first["schema"]
            and event.get("modality") == first["modality"]
            and event.get("activity") == first["activity"]
            and event.get("scale") == first["scale"]
        ]
        session_ids = {str(event.get("session_id", "")) for event in starts}
        scale_events = [
            event
            for event in all_events
            if str(event.get("session_id", "")) in session_ids
        ]
        assigned: Counter[str] = Counter()
        last_assigned: dict[str, str] = {}
        for event in scale_events:
            if event.get("event_type") != "descriptor_presented":
                continue
            item_id = str(event.get("descriptor_id", ""))
            if item_id in by_id:
                assigned[item_id] += 1
                last_assigned[item_id] = str(event.get("occurred_at", ""))

        completions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in scale_events:
            item_id = str(event.get("descriptor_id", ""))
            if event.get("event_type") == "descriptor_completed" and item_id in by_id:
                completions[item_id].append(event)
        for records in completions.values():
            records.sort(key=lambda item: str(item.get("occurred_at", "")))

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for descriptor in descriptors:
            groups[str(descriptor["correct_level"])].append(descriptor)
        for items in groups.values():
            randomizer.shuffle(items)
            items.sort(key=lambda item: assigned[item["descriptor_id"]])

        def unseen_for(level: str) -> list[dict[str, Any]]:
            return [
                item for item in groups.get(level, [])
                if assigned[item["descriptor_id"]] == 0
            ]

        canonical_present = [
            level for level in CANONICAL_LEVELS if groups.get(level)
        ]
        previously_introduced = {
            level
            for level, items in groups.items()
            if any(assigned[item["descriptor_id"]] for item in items)
        }
        missing_orientation = [
            level
            for level in canonical_present
            if not any(assigned[item["descriptor_id"]] for item in groups[level])
        ]
        if missing_orientation:
            chosen = [unseen_for(level)[0] for level in missing_orientation]
            return self._progressive_plan_result(
                descriptors,
                chosen,
                [],
                "orientation",
                "Primi passi",
                "Cominciamo dalle differenze più riconoscibili tra i livelli.",
                assigned,
                canonical_present,
            )

        variation = []
        for level in canonical_present:
            encountered = sum(
                assigned[item["descriptor_id"]] > 0 for item in groups[level]
            )
            candidates = unseen_for(level)
            if encountered < 2 and candidates:
                variation.append(candidates[0])
        if variation:
            return self._progressive_plan_result(
                descriptors,
                variation,
                [],
                "canonical_variation",
                "Altri modi di esprimere lo stesso livello",
                "Uno stesso livello può presentarsi attraverso descrittori diversi.",
                assigned,
                canonical_present,
            )

        for plus_level, neighbours, label, note in (
            (
                "A2+",
                ("A2", "B1"),
                "Una sfumatura tra A2 e B1",
                "Aggiungiamo con calma un livello intermedio e ritroviamo i suoi vicini.",
            ),
            (
                "B1+",
                ("B1", "B2"),
                "Una sfumatura tra B1 e B2",
                "Osserviamo una nuova sfumatura confrontandola con i livelli vicini.",
            ),
        ):
            plus_candidates = unseen_for(plus_level)
            if plus_candidates and not any(
                assigned[item["descriptor_id"]] for item in groups[plus_level]
            ):
                reviews = self._neighbour_reviews(
                    groups,
                    neighbours,
                    completions,
                    last_assigned,
                    randomizer,
                )
                introduced_answers = [
                    level
                    for level in self.catalog.level_order
                    if level in previously_introduced
                    or level in canonical_present
                    or level == plus_level
                ]
                return self._progressive_plan_result(
                    descriptors,
                    [plus_candidates[0], *reviews],
                    [item["descriptor_id"] for item in reviews],
                    f"introduce_{plus_level.casefold().replace('+', '_plus')}",
                    label,
                    note,
                    assigned,
                    introduced_answers,
                )

        unseen = [
            item for item in descriptors if assigned[item["descriptor_id"]] == 0
        ]
        if unseen:
            chosen = self._balanced_selection(
                unseen, min(6, len(unseen)), randomizer, assigned
            )
            return self._progressive_plan_result(
                descriptors,
                chosen,
                [],
                "deepening",
                "Nuovi incontri",
                "Continuiamo a scoprire la varietà dei descrittori della scala.",
                assigned,
                [level for level in self.catalog.level_order if groups.get(level)],
            )

        due = self._review_candidates(
            descriptors, completions, last_assigned, randomizer
        )
        chosen = due[: min(6, len(due))]
        if not chosen:
            chosen = list(descriptors)
            randomizer.shuffle(chosen)
            chosen = chosen[: min(4, len(chosen))]
            phase = "maintenance"
            label = "Un piccolo giro per mantenere la familiarità"
            note = "Ritroviamo alcuni descrittori già conosciuti, senza fretta."
        else:
            phase = "consolidation"
            label = "Ritroviamo ciò che abbiamo già incontrato"
            note = "Un ritorno distanziato aiuta a confermare la familiarità, anche dopo una risposta immediata."
        return self._progressive_plan_result(
            descriptors,
            chosen,
            [item["descriptor_id"] for item in chosen],
            phase,
            label,
            note,
            assigned,
            [level for level in self.catalog.level_order if groups.get(level)],
        )

    def _progressive_plan_result(
        self,
        all_descriptors: list[dict[str, Any]],
        chosen: list[dict[str, Any]],
        review_ids: list[str],
        phase: str,
        label: str,
        note: str,
        assigned: Counter[str],
        answer_levels: list[str],
    ) -> dict[str, Any]:
        chosen_ids = [item["descriptor_id"] for item in chosen]
        remaining_new = sum(
            assigned[item["descriptor_id"]] == 0
            and item["descriptor_id"] not in chosen_ids
            for item in all_descriptors
        )
        return {
            "descriptor_ids": chosen_ids,
            "review_descriptor_ids": review_ids,
            "phase": phase,
            "label": label,
            "note": note,
            "remaining_new": remaining_new,
            "answer_levels": list(answer_levels),
        }

    def _neighbour_reviews(
        self,
        groups: dict[str, list[dict[str, Any]]],
        levels: tuple[str, str],
        completions: dict[str, list[dict[str, Any]]],
        last_assigned: dict[str, str],
        randomizer: random.Random,
    ) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []
        for level in levels:
            candidates = [
                item
                for item in groups.get(level, [])
                if item["descriptor_id"] in last_assigned
            ]
            randomizer.shuffle(candidates)
            candidates.sort(
                key=lambda item: self._review_priority(
                    item["descriptor_id"], completions, last_assigned
                )
            )
            if candidates:
                reviews.append(candidates[0])
        return reviews

    def _review_candidates(
        self,
        descriptors: list[dict[str, Any]],
        completions: dict[str, list[dict[str, Any]]],
        last_assigned: dict[str, str],
        randomizer: random.Random,
    ) -> list[dict[str, Any]]:
        candidates = [
            item
            for item in descriptors
            if sum(bool(record.get("resolved")) for record in completions[item["descriptor_id"]]) < 2
        ]
        randomizer.shuffle(candidates)
        candidates.sort(
            key=lambda item: self._review_priority(
                item["descriptor_id"], completions, last_assigned
            )
        )
        return candidates

    @staticmethod
    def _review_priority(
        descriptor_id: str,
        completions: dict[str, list[dict[str, Any]]],
        last_assigned: dict[str, str],
    ) -> tuple[int, int, str]:
        records = completions.get(descriptor_id, [])
        correct_confirmations = sum(bool(record.get("resolved")) for record in records)
        latest = records[-1] if records else {}
        attempt = latest.get("resolved_on_attempt")
        difficulty = 4 if latest and not latest.get("resolved") else int(attempt or 1)
        return (correct_confirmations, -difficulty, last_assigned.get(descriptor_id, ""))

    def _balanced_selection(
        self,
        descriptors: list[dict[str, Any]],
        limit: int,
        randomizer: random.Random,
        encounter_counts: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Sample levels round-robin, preferring less exposed descriptors."""
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for descriptor in descriptors:
            groups[str(descriptor["correct_level"])].append(descriptor)
        levels = [
            level for level in self.catalog.level_order if groups.get(level)
        ]
        randomizer.shuffle(levels)
        for level in levels:
            randomizer.shuffle(groups[level])
            groups[level].sort(
                key=lambda item: encounter_counts[item["descriptor_id"]]
            )

        selected: list[dict[str, Any]] = []
        while len(selected) < limit:
            added = False
            for level in levels:
                if groups[level] and len(selected) < limit:
                    selected.append(groups[level].pop(0))
                    added = True
            if not added:
                break
        return selected

    def submit_answer(
        self, state: dict[str, Any], selected_level: str
    ) -> dict[str, Any]:
        if state.get("descriptor_finished"):
            raise SessionError("Questo descrittore è già concluso.")
        if selected_level not in self.available_levels(state):
            raise SessionError("Seleziona uno dei livelli disponibili.")
        attempt_number = len(state.get("attempts", [])) + 1
        if attempt_number > 3:
            raise SessionError("Sono già stati usati tre tentativi.")

        answer_at = utc_now()
        updated = copy.deepcopy(state)
        descriptor = self.current_descriptor(updated)
        is_correct = selected_level == descriptor["correct_level"]
        is_finished = is_correct or attempt_number == 3
        feedback_text = (
            descriptor["rationale"]
            if is_finished
            else descriptor[f"hint_{attempt_number}"]
        )
        answer_event = self._base_event(
            event_id=self._event_id(
                updated["session_id"],
                f"{descriptor['descriptor_id']}:attempt:{attempt_number}",
            ),
            event_type="answer_submitted",
            session_id=updated["session_id"],
            participant_id=updated["participant_id"],
            descriptor_id=descriptor["descriptor_id"],
            position=updated["current_index"] + 1,
            attempt_number=attempt_number,
            selected_level=selected_level,
            correct_level=descriptor["correct_level"],
            is_correct=is_correct,
            feedback_text=feedback_text,
            feedback_stage="rationale" if is_finished else f"hint_{attempt_number}",
            error_distance=self.catalog.level_distance(
                selected_level, descriptor["correct_level"]
            ),
            response_time_ms=_elapsed_ms(
                updated.get("attempt_started_at"), answer_at
            ),
            descriptor_elapsed_ms=_elapsed_ms(
                updated.get("descriptor_presented_at"), answer_at
            ),
            exposure_number=(
                int(
                    updated.get("prior_exposure_counts", {}).get(
                        descriptor["descriptor_id"], 0
                    )
                )
                + 1
            ),
            client_request_id=self._event_id(
                updated["session_id"],
                f"{descriptor['descriptor_id']}:request:{attempt_number}",
            ),
            occurred_at=answer_at,
        )
        events = [answer_event]
        if is_finished:
            events.append(
                self._base_event(
                    event_id=self._event_id(
                        updated["session_id"],
                        f"{descriptor['descriptor_id']}:completed",
                    ),
                    event_type="descriptor_completed",
                    session_id=updated["session_id"],
                    participant_id=updated["participant_id"],
                    descriptor_id=descriptor["descriptor_id"],
                    position=updated["current_index"] + 1,
                    attempts=updated["attempts"] + [selected_level],
                    resolved=is_correct,
                    resolved_on_attempt=attempt_number if is_correct else None,
                    correct_level=descriptor["correct_level"],
                    rationale=descriptor["rationale"],
                    descriptor_text=descriptor["descriptor_text"],
                    schema=descriptor["schema"],
                    modality=descriptor["modality"],
                    activity=descriptor["activity"],
                    scale=descriptor["scale"],
                    source_schema=descriptor.get(
                        "source_schema", descriptor["schema"]
                    ),
                    source_modality=descriptor.get(
                        "source_modality", descriptor["modality"]
                    ),
                    source_activity=descriptor.get(
                        "source_activity", descriptor["activity"]
                    ),
                    content_version=descriptor["content_version"],
                    source=descriptor["source"],
                    source_version=descriptor["source_version"],
                    first_response_distance=self.catalog.level_distance(
                        (updated["attempts"] + [selected_level])[0],
                        descriptor["correct_level"],
                    ),
                    final_response_distance=self.catalog.level_distance(
                        selected_level, descriptor["correct_level"]
                    ),
                    descriptor_elapsed_ms=_elapsed_ms(
                        updated.get("descriptor_presented_at"), answer_at
                    ),
                    exposure_number=(
                        int(
                            updated.get("prior_exposure_counts", {}).get(
                                descriptor["descriptor_id"], 0
                            )
                        )
                        + 1
                    ),
                    occurred_at=answer_at,
                )
            )

        # State changes only after the complete event batch is confirmed.
        self.event_store.append_events(events)
        updated["attempts"].append(selected_level)
        updated["feedbacks"].append(feedback_text)
        updated["attempt_started_at"] = answer_at
        updated["last_result"] = {
            "is_correct": is_correct,
            "selected_level": selected_level,
            "correct_level": descriptor["correct_level"],
            "attempt_number": attempt_number,
        }
        if is_finished:
            updated["descriptor_finished"] = True
            updated["completed_records"].append(
                {
                    "descriptor_id": descriptor["descriptor_id"],
                    "attempts": list(updated["attempts"]),
                    "resolved": is_correct,
                    "resolved_on_attempt": attempt_number if is_correct else None,
                    "correct_level": descriptor["correct_level"],
                    "rationale": descriptor["rationale"],
                    "occurred_at": answer_at,
                    "first_response_distance": self.catalog.level_distance(
                        updated["attempts"][0], descriptor["correct_level"]
                    ),
                    "exposure_number": (
                        int(
                            updated.get("prior_exposure_counts", {}).get(
                                descriptor["descriptor_id"], 0
                            )
                        )
                        + 1
                    ),
                }
            )
        return updated

    def advance(self, state: dict[str, Any]) -> dict[str, Any]:
        if not state.get("descriptor_finished"):
            raise SessionError("Completa il descrittore prima di continuare.")
        updated = copy.deepcopy(state)
        if updated["current_index"] + 1 >= len(updated["descriptor_ids"]):
            summary = self.summary(updated)
            completed_at = utc_now()
            self.event_store.append_events(
                [
                    self._base_event(
                        event_id=self._event_id(
                            updated["session_id"], "session-completed"
                        ),
                        event_type="session_completed",
                        session_id=updated["session_id"],
                        participant_id=updated["participant_id"],
                        schema=updated["schema"],
                        modality=updated["modality"],
                        activity=updated["activity"],
                        scale=updated["scale"],
                        seed=updated["seed"],
                        descriptor_order=updated["descriptor_ids"],
                        duration_seconds=_elapsed_seconds(
                            updated.get("started_at"), completed_at
                        ),
                        occurred_at=completed_at,
                        **summary,
                    )
                ]
            )
            updated["session_finished"] = True
            return updated

        updated["current_index"] += 1
        updated["attempts"] = []
        updated["feedbacks"] = []
        updated["descriptor_finished"] = False
        updated["last_result"] = None
        presented_at = utc_now()
        updated["descriptor_presented_at"] = presented_at
        updated["attempt_started_at"] = presented_at
        self.event_store.append_events([self._presented_event(updated)])
        return updated

    def current_descriptor(self, state: dict[str, Any]) -> dict[str, Any]:
        descriptor_id = state["descriptor_ids"][state["current_index"]]
        return self.catalog.get(descriptor_id)

    def available_levels(self, state: dict[str, Any]) -> list[str]:
        return list(
            state.get("available_levels")
            or self.catalog.levels_for(state["descriptor_ids"])
        )

    def level_counts(self, state: dict[str, Any]) -> dict[str, int]:
        stored = state.get("level_counts")
        if stored:
            return {
                str(level): int(count) for level, count in stored.items()
            }
        counts = Counter(
            self.catalog.get(item_id)["correct_level"]
            for item_id in state["descriptor_ids"]
        )
        return dict(counts)

    def summary(self, state: dict[str, Any]) -> dict[str, Any]:
        records = state.get("completed_records", [])
        counts = {str(number): 0 for number in (1, 2, 3)}
        unresolved = 0
        for record in records:
            attempt = record.get("resolved_on_attempt")
            if attempt:
                counts[str(attempt)] += 1
            else:
                unresolved += 1
        return {
            "descriptors_completed": len(records),
            "correct_by_attempt": counts,
            "unresolved_after_three": unresolved,
            "first_attempt_rate": (
                counts["1"] / len(records) * 100 if records else 0.0
            ),
        }

    def incomplete_sessions(
        self, participant_id: str
    ) -> list[dict[str, Any]]:
        events = self.event_store.list_events(participant_id)
        grouped = _group_by_session(events)
        sessions: list[dict[str, Any]] = []
        for session_id, session_events in grouped.items():
            start = _first_of_type(session_events, "session_started")
            completed = _first_of_type(session_events, "session_completed")
            if start and not completed:
                finished_count = sum(
                    event.get("event_type") == "descriptor_completed"
                    for event in session_events
                )
                sessions.append(
                    {
                        "session_id": session_id,
                        "schema": start.get("schema", ""),
                        "modality": start.get("modality", ""),
                        "label": (
                            f"{start.get('scale', 'Scala')} · "
                            f"{finished_count}/{len(start.get('descriptor_order', []))} "
                            f"descrittori · {start['occurred_at'][:10]}"
                        ),
                        "occurred_at": start["occurred_at"],
                    }
                )
        return sorted(
            sessions, key=lambda item: item["occurred_at"], reverse=True
        )

    def restore_session(
        self, participant_id: str, display_name: str, session_id: str
    ) -> dict[str, Any]:
        events = [
            event
            for event in self.event_store.list_events(participant_id)
            if event.get("session_id") == session_id
        ]
        start = _first_of_type(events, "session_started")
        if not start:
            raise SessionError("Sessione incompleta non trovata.")
        if _first_of_type(events, "session_completed"):
            raise SessionError("La sessione selezionata è già completa.")

        order = list(start["descriptor_order"])
        presented = [
            event for event in events if event.get("event_type") == "descriptor_presented"
        ]
        current_id = (
            presented[-1]["descriptor_id"] if presented else order[0]
        )
        current_index = order.index(current_id)
        completion_events = [
            event for event in events if event.get("event_type") == "descriptor_completed"
        ]
        completed_records = [
            {
                "descriptor_id": event["descriptor_id"],
                "attempts": event.get("attempts", []),
                "resolved": event.get("resolved", False),
                "resolved_on_attempt": event.get("resolved_on_attempt"),
                "correct_level": event.get("correct_level"),
                "rationale": event.get("rationale", ""),
                "occurred_at": event.get("occurred_at", ""),
                "first_response_distance": event.get("first_response_distance"),
                "exposure_number": event.get("exposure_number"),
            }
            for event in completion_events
        ]
        answers = [
            event
            for event in events
            if event.get("event_type") == "answer_submitted"
            and event.get("descriptor_id") == current_id
        ]
        answers.sort(key=lambda item: int(item.get("attempt_number", 0)))
        current_completion = next(
            (
                event
                for event in completion_events
                if event.get("descriptor_id") == current_id
            ),
            None,
        )
        last_answer = answers[-1] if answers else None
        current_presented = next(
            (
                event
                for event in reversed(presented)
                if event.get("descriptor_id") == current_id
            ),
            None,
        )
        prior_exposure_counts: dict[str, int] = defaultdict(int)
        for event in self.event_store.list_events(participant_id):
            if (
                event.get("event_type") == "descriptor_completed"
                and event.get("session_id") != session_id
            ):
                prior_exposure_counts[str(event.get("descriptor_id", ""))] += 1
        return {
            "participant_id": participant_id,
            "display_name": display_name,
            "session_id": session_id,
            "schema": start["schema"],
            "modality": start["modality"],
            "activity": start["activity"],
            "scale": start["scale"],
            "seed": start["seed"],
            "descriptor_ids": order,
            "available_levels": list(
                start.get("answer_levels")
                or self.catalog.levels_for(order)
            ),
            "level_counts": dict(
                start.get("level_counts")
                or Counter(
                    self.catalog.get(item_id)["correct_level"]
                    for item_id in order
                )
            ),
            "include_plus_levels": bool(
                start.get("include_plus_levels", True)
            ),
            "session_mode": str(start.get("session_mode", "full")),
            "session_size_requested": start.get("session_size_requested"),
            "scale_descriptor_count": int(
                start.get("scale_descriptor_count", len(order))
            ),
            "remaining_new_after_batch": int(
                start.get("remaining_new_after_batch", 0)
            ),
            "progression_phase": str(start.get("progression_phase", "")),
            "progression_label": str(start.get("progression_label", "")),
            "progression_note": str(start.get("progression_note", "")),
            "review_descriptor_ids": list(
                start.get("review_descriptor_ids", [])
            ),
            "current_index": current_index,
            "attempts": [event["selected_level"] for event in answers],
            "feedbacks": [event["feedback_text"] for event in answers],
            "descriptor_finished": current_completion is not None,
            "last_result": (
                {
                    "is_correct": last_answer["is_correct"],
                    "selected_level": last_answer["selected_level"],
                    "correct_level": last_answer["correct_level"],
                    "attempt_number": last_answer["attempt_number"],
                }
                if last_answer
                else None
            ),
            "completed_records": completed_records,
            "session_finished": False,
            "started_at": start["occurred_at"],
            "descriptor_presented_at": (
                current_presented.get("occurred_at")
                if current_presented
                else start["occurred_at"]
            ),
            "attempt_started_at": (
                last_answer.get("occurred_at")
                if last_answer
                else (
                    current_presented.get("occurred_at")
                    if current_presented
                    else start["occurred_at"]
                )
            ),
            "prior_exposure_counts": dict(prior_exposure_counts),
        }

    def _presented_event(self, state: dict[str, Any]) -> dict[str, Any]:
        descriptor = self.current_descriptor(state)
        return self._base_event(
            event_id=self._event_id(
                state["session_id"],
                f"{descriptor['descriptor_id']}:presented",
            ),
            event_type="descriptor_presented",
            session_id=state["session_id"],
            participant_id=state["participant_id"],
            descriptor_id=descriptor["descriptor_id"],
            position=state["current_index"] + 1,
            schema=descriptor["schema"],
            modality=descriptor["modality"],
            activity=descriptor["activity"],
            scale=descriptor["scale"],
            source_schema=descriptor.get("source_schema", descriptor["schema"]),
            source_modality=descriptor.get(
                "source_modality", descriptor["modality"]
            ),
            source_activity=descriptor.get(
                "source_activity", descriptor["activity"]
            ),
            correct_level=descriptor["correct_level"],
            descriptor_text=descriptor["descriptor_text"],
            content_version=descriptor["content_version"],
            source=descriptor["source"],
            source_version=descriptor["source_version"],
            exposure_number=(
                int(
                    state.get("prior_exposure_counts", {}).get(
                        descriptor["descriptor_id"], 0
                    )
                )
                + 1
            ),
            occurred_at=state.get("descriptor_presented_at"),
        )

    def _base_event(
        self,
        *,
        event_id: str,
        event_type: str,
        session_id: str,
        participant_id: str,
        occurred_at: str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        now = occurred_at or utc_now()
        return {
            "schema_version": "2.0",
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": now,
            "received_at": now,
            "session_id": session_id,
            "participant_id_hash": participant_id,
            "content_revision": self.content_revision,
            "app_version": self.app_version,
            **payload,
        }

    @staticmethod
    def _event_id(session_id: str, key: str) -> str:
        return str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{key}"))


def _group_by_session(
    events: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("event_type") == "consent_recorded":
            continue
        grouped[str(event.get("session_id", ""))].append(event)
    for session_events in grouped.values():
        session_events.sort(key=lambda item: item.get("occurred_at", ""))
    return dict(grouped)


def _first_of_type(
    events: list[dict[str, Any]], event_type: str
) -> dict[str, Any] | None:
    return next(
        (event for event in events if event.get("event_type") == event_type),
        None,
    )


def _elapsed_ms(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        start_time = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(round((end_time - start_time).total_seconds() * 1000), 0)


def _elapsed_seconds(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        start_time = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(round((end_time - start_time).total_seconds()), 0)
