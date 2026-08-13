from __future__ import annotations

import io
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import Settings


class EventStoreError(RuntimeError):
    """Raised when durable storage cannot confirm a write."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventStore(ABC):
    mode: str

    def health_check(self) -> tuple[bool, str]:
        """Return whether this backend can currently be used."""
        return True, ""

    @abstractmethod
    def register_participant(
        self,
        participant_id: str,
        display_name: str,
        name_lookup_hash: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_participant(
        self, participant_id: str
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def append_events(self, events: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_events(
        self, participant_id: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_participants(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class LocalEventStore(EventStore):
    def __init__(self, root: Path, mode: str = "local"):
        self.root = root
        self.mode = mode
        self.participants_dir = root / "participants"
        self.events_dir = root / "events"

    def register_participant(
        self,
        participant_id: str,
        display_name: str,
        name_lookup_hash: str | None = None,
    ) -> dict[str, Any]:
        self.participants_dir.mkdir(parents=True, exist_ok=True)
        target = self.participants_dir / f"{participant_id}.json"
        existing = self.get_participant(participant_id) or {}
        record = _participant_record(
            participant_id,
            display_name,
            existing,
            name_lookup_hash=name_lookup_hash,
        )
        _atomic_write_json(target, record)
        return record

    def get_participant(
        self, participant_id: str
    ) -> dict[str, Any] | None:
        target = self.participants_dir / f"{participant_id}.json"
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EventStoreError(
                f"Registro partecipante illeggibile: {target.name}: {exc}"
            ) from exc

    def append_events(self, events: list[dict[str, Any]]) -> None:
        staged: list[tuple[Path, Path]] = []
        try:
            for event in events:
                target = self._event_path(event)
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(event, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                staged.append((temporary, target))
            for temporary, target in staged:
                os.replace(temporary, target)
        except OSError as exc:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            raise EventStoreError(f"Salvataggio locale non riuscito: {exc}") from exc

    def _event_path(self, event: dict[str, Any]) -> Path:
        occurred = datetime.fromisoformat(str(event["occurred_at"]))
        return (
            self.events_dir
            / f"{occurred:%Y}"
            / f"{occurred:%m}"
            / f"{occurred:%d}"
            / str(event["session_id"])
            / f"{event['event_id']}.json"
        )

    def list_events(
        self, participant_id: str | None = None
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not self.events_dir.exists():
            return events
        for path in self.events_dir.rglob("*.json"):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EventStoreError(
                    f"Evento illeggibile: {path}: {exc}"
                ) from exc
            if (
                participant_id is None
                or event.get("participant_id_hash") == participant_id
            ):
                events.append(event)
        return sorted(events, key=lambda item: item.get("occurred_at", ""))

    def list_participants(self) -> list[dict[str, Any]]:
        if not self.participants_dir.exists():
            return []
        participants: list[dict[str, Any]] = []
        for path in self.participants_dir.glob("*.json"):
            try:
                participants.append(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise EventStoreError(
                    f"Registro partecipante illeggibile: {path}: {exc}"
                ) from exc
        return sorted(participants, key=lambda item: item["display_name"].casefold())


class HuggingFaceEventStore(EventStore):
    mode = "huggingface"

    def __init__(self, repo_id: str, token: str, api: Any | None = None):
        if api is None:
            from huggingface_hub import HfApi

            api = HfApi(token=token)
        self.repo_id = repo_id
        self.token = token
        self.api = api
        self._private_repo_confirmed = False

    def health_check(self) -> tuple[bool, str]:
        try:
            self._require_private_repo()
            return True, ""
        except EventStoreError as exc:
            return False, str(exc)

    def register_participant(
        self,
        participant_id: str,
        display_name: str,
        name_lookup_hash: str | None = None,
    ) -> dict[str, Any]:
        self._require_private_repo()
        path = f"participants/{participant_id}.json"
        existing = self._download_json(path) or {}
        record = _participant_record(
            participant_id,
            display_name,
            existing,
            name_lookup_hash=name_lookup_hash,
        )
        self._upload_participant(path, record, "Aggiorna registro partecipante")
        return record

    def get_participant(
        self, participant_id: str
    ) -> dict[str, Any] | None:
        self._require_private_repo()
        return self._download_json(f"participants/{participant_id}.json")

    def append_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self._require_private_repo()
        try:
            from huggingface_hub import CommitOperationAdd

            existing_paths = set(self._list_files(prefix="events/"))
            operations = [
                CommitOperationAdd(
                    path_in_repo=_remote_event_path(event),
                    path_or_fileobj=io.BytesIO(_json_bytes(event)),
                )
                for event in events
                if _remote_event_path(event) not in existing_paths
            ]
            if not operations:
                return
            self.api.create_commit(
                repo_id=self.repo_id,
                repo_type="dataset",
                operations=operations,
                commit_message=(
                    "Registra evento" if len(events) == 1 else "Registra eventi"
                ),
            )
        except Exception as exc:
            raise EventStoreError(f"Eventi non salvati: {exc}") from exc

    def _upload_participant(
        self, path: str, record: dict[str, Any], commit_message: str
    ) -> None:
        try:
            self.api.upload_file(
                path_or_fileobj=io.BytesIO(_json_bytes(record)),
                path_in_repo=path,
                repo_id=self.repo_id,
                repo_type="dataset",
                commit_message=commit_message,
            )
        except Exception as exc:
            raise EventStoreError(
                f"Registro partecipante non salvato: {exc}"
            ) from exc

    def list_events(
        self, participant_id: str | None = None
    ) -> list[dict[str, Any]]:
        self._require_private_repo()
        events: list[dict[str, Any]] = []
        for path in self._list_files(prefix="events/"):
            event = self._download_json(path)
            if not event:
                continue
            if (
                participant_id is None
                or event.get("participant_id_hash") == participant_id
            ):
                events.append(event)
        return sorted(events, key=lambda item: item.get("occurred_at", ""))

    def list_participants(self) -> list[dict[str, Any]]:
        self._require_private_repo()
        participants = [
            record
            for path in self._list_files(prefix="participants/")
            if (record := self._download_json(path))
        ]
        return sorted(participants, key=lambda item: item["display_name"].casefold())

    def _require_private_repo(self) -> None:
        if self._private_repo_confirmed:
            return
        try:
            info = self.api.repo_info(
                repo_id=self.repo_id,
                repo_type="dataset",
            )
        except Exception as exc:
            raise EventStoreError(
                "Dataset degli eventi non raggiungibile o token non valido."
            ) from exc
        if getattr(info, "private", None) is not True:
            raise EventStoreError(
                "Il Dataset degli eventi deve essere privato prima di poter "
                "registrare partecipanti."
            )
        self._private_repo_confirmed = True

    def _list_files(self, prefix: str) -> list[str]:
        try:
            files = self.api.list_repo_files(
                repo_id=self.repo_id, repo_type="dataset"
            )
            return [
                path
                for path in files
                if path.startswith(prefix) and path.endswith(".json")
            ]
        except Exception as exc:
            raise EventStoreError(f"Lettura archivio non riuscita: {exc}") from exc

    def _download_json(self, path: str) -> dict[str, Any] | None:
        try:
            from huggingface_hub import hf_hub_download

            local_path = hf_hub_download(
                repo_id=self.repo_id,
                repo_type="dataset",
                filename=path,
                token=self.token,
                force_download=True,
            )
            return json.loads(Path(local_path).read_text(encoding="utf-8"))
        except Exception as exc:
            name = type(exc).__name__
            status_code = getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if "EntryNotFound" in name or status_code == 404:
                return None
            raise EventStoreError(
                f"File dell’archivio non leggibile ({path}): {exc}"
            ) from exc


def create_event_store(settings: Settings) -> EventStore:
    if settings.storage_mode == "huggingface":
        return HuggingFaceEventStore(
            repo_id=settings.events_repo_id,
            token=settings.hf_data_token,
        )
    return LocalEventStore(settings.local_data_dir, mode=settings.storage_mode)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise EventStoreError(f"Scrittura non riuscita: {exc}") from exc


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _remote_event_path(event: dict[str, Any]) -> str:
    occurred = datetime.fromisoformat(str(event["occurred_at"]))
    return (
        f"events/{occurred:%Y/%m/%d}/{event['session_id']}/"
        f"{event['event_id']}.json"
    )


def _participant_record(
    participant_id: str,
    display_name: str,
    existing: dict[str, Any],
    *,
    name_lookup_hash: str | None,
) -> dict[str, Any]:
    now = utc_now()
    record = {
        "participant_id": participant_id,
        "display_name": display_name,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "status": existing.get("status", "active"),
        "merged_into": existing.get("merged_into"),
        "name_lookup_hash": existing.get("name_lookup_hash")
        or name_lookup_hash,
    }
    return record
