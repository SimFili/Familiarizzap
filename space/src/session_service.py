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
            "current_index": 0,
            "attempts": [],
            "feedbacks": [],
            "descriptor_finished": False,
            "last_result": None,
            "completed_records": [],
            "session_finished": False,
            "started_at": utc_now(),
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
            client_request_id=self._event_id(
                updated["session_id"],
                f"{descriptor['descriptor_id']}:request:{attempt_number}",
            ),
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
                )
            )

        # State changes only after the complete event batch is confirmed.
        self.event_store.append_events(events)
        updated["attempts"].append(selected_level)
        updated["feedbacks"].append(feedback_text)
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
                }
            )
        return updated

    def advance(self, state: dict[str, Any]) -> dict[str, Any]:
        if not state.get("descriptor_finished"):
            raise SessionError("Completa il descrittore prima di continuare.")
        updated = copy.deepcopy(state)
        if updated["current_index"] + 1 >= len(updated["descriptor_ids"]):
            summary = self.summary(updated)
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
        self.event_store.append_events([self._presented_event(updated)])
        return updated

    def current_descriptor(self, state: dict[str, Any]) -> dict[str, Any]:
        descriptor_id = state["descriptor_ids"][state["current_index"]]
        return self.catalog.get(descriptor_id)

    def available_levels(self, state: dict[str, Any]) -> list[str]:
        return self.catalog.levels_for(state["descriptor_ids"])

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
        )

    def _base_event(
        self,
        *,
        event_id: str,
        event_type: str,
        session_id: str,
        participant_id: str,
        **payload: Any,
    ) -> dict[str, Any]:
        now = utc_now()
        return {
            "schema_version": "1.0",
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
