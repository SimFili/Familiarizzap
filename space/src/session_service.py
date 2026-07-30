from __future__ import annotations

import copy
import random
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .catalog import Catalog
from .event_store import EventStore


EVENT_NAMESPACE = uuid.UUID("a302ad37-79ac-4ce0-96f6-1721259d980d")


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
    ) -> dict[str, Any]:
        if not descriptors:
            raise SessionError("La scala selezionata non contiene descrittori.")
        seed = secrets.randbits(63)
        descriptor_ids = [item["descriptor_id"] for item in descriptors]
        random.Random(seed).shuffle(descriptor_ids)
        session_id = str(uuid.uuid4())
        first = self.catalog.get(descriptor_ids[0])
        scale_descriptor_ids = [
            item["descriptor_id"]
            for item in self.catalog.for_scale(
                first["schema"],
                first["modality"],
                first["activity"],
                first["scale"],
            )
        ]
        answer_levels = self.catalog.levels_for(scale_descriptor_ids)
        now = utc_now()
        exposure_counts: dict[str, int] = defaultdict(int)
        prior_sessions: set[str] = set()
        for event in self.event_store.list_events(participant_id):
            if event.get("event_type") == "descriptor_completed":
                exposure_counts[str(event.get("descriptor_id", ""))] += 1
            if event.get("event_type") == "session_started":
                prior_sessions.add(str(event.get("session_id", "")))
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
            seed=seed,
            descriptor_order=descriptor_ids,
            answer_levels=answer_levels,
            descriptor_count=len(descriptor_ids),
            prior_session_count=len(prior_sessions),
            occurred_at=now,
        )
        presented_event = self._presented_event(state)
        self.event_store.append_events([start_event, presented_event])
        return state

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
