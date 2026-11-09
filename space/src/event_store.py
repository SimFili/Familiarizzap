from __future__ import annotations

import io
import json
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
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

    def warm_up(self) -> None:
        """Prepare inexpensive backend metadata before the first user action."""
        return None

    @property
    def cached_health_status(self) -> tuple[bool, str] | None:
        """Return the last known status without performing I/O."""
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
        self._cached_health_status: tuple[bool, str] | None = None
        self._cache_lock = RLock()
        self._event_paths: set[str] | None = None
        self._events_by_path: dict[str, dict[str, Any]] = {}
        self._participant_paths: set[str] | None = None
        self._participants_by_id: dict[str, dict[str, Any]] = {}
        self._participants_without_remote_history: set[str] = set()

    def health_check(self) -> tuple[bool, str]:
        try:
            self._require_private_repo()
            return True, ""
        except EventStoreError as exc:
            return False, str(exc)

    def warm_up(self) -> None:
        """Cache repository checks and paths while the first screen is read."""
        self._require_private_repo()
        with self._cache_lock:
            if self._event_paths is None:
                self._event_paths = set(self._list_files(prefix="events/"))

    @property
    def cached_health_status(self) -> tuple[bool, str] | None:
        return self._cached_health_status

    def register_participant(
        self,
        participant_id: str,
        display_name: str,
        name_lookup_hash: str | None = None,
    ) -> dict[str, Any]:
        self._require_private_repo()
        path = f"participants/{participant_id}.json"
        with self._cache_lock:
            cached = self._participants_by_id.get(participant_id)
        existing = (
            dict(cached)
            if cached is not None
            else self._download_json(path) or {}
        )
        if not existing:
            # No participant record means that this identity cannot have a
            # valid historic path yet.  Its first screen can therefore use the
            # events just written by this process instead of downloading every
            # other participant's archive.
            with self._cache_lock:
                self._participants_without_remote_history.add(participant_id)
        if (
            existing
            and existing.get("display_name") == display_name
            and (
                not name_lookup_hash
                or existing.get("name_lookup_hash") == name_lookup_hash
            )
        ):
            with self._cache_lock:
                self._participants_by_id[participant_id] = dict(existing)
            return dict(existing)
        record = _participant_record(
            participant_id,
            display_name,
            existing,
            name_lookup_hash=name_lookup_hash,
        )
        self._upload_participant(path, record, "Aggiorna registro partecipante")
        with self._cache_lock:
            self._participants_by_id[participant_id] = dict(record)
            if self._participant_paths is not None:
                self._participant_paths.add(path)
        return dict(record)

    def get_participant(
        self, participant_id: str
    ) -> dict[str, Any] | None:
        self._require_private_repo()
        with self._cache_lock:
            cached = self._participants_by_id.get(participant_id)
        if cached is not None:
            return dict(cached)
        record = self._download_json(f"participants/{participant_id}.json")
        if record is not None:
            with self._cache_lock:
                self._participants_by_id[participant_id] = dict(record)
            return dict(record)
        return None

    def append_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self._require_private_repo()
        try:
            from huggingface_hub import CommitOperationAdd

            # The remote file listing used to run before every answer.  Apart
            # from being needlessly expensive, that made interaction slower as
            # the research archive grew.  One process owns a coherent snapshot:
            # writes are serialized, then immediately added to that snapshot.
            with self._cache_lock:
                if self._event_paths is None:
                    self._event_paths = set(self._list_files(prefix="events/"))
                new_events = [
                    (event, _remote_event_path(event))
                    for event in events
                    if _remote_event_path(event) not in self._event_paths
                ]
                if not new_events:
                    return
                operations = [
                    CommitOperationAdd(
                        path_in_repo=path,
                        path_or_fileobj=io.BytesIO(_json_bytes(event)),
                    )
                    for event, path in new_events
                ]
                self.api.create_commit(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    operations=operations,
                    commit_message=(
                        "Registra evento"
                        if len(new_events) == 1
                        else "Registra eventi"
                    ),
                )
                for event, path in new_events:
                    self._event_paths.add(path)
                    self._events_by_path[path] = dict(event)
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
        with self._cache_lock:
            if self._event_paths is None:
                self._event_paths = set(self._list_files(prefix="events/"))
            if participant_id in self._participants_without_remote_history:
                missing = []
            else:
                missing = sorted(
                    self._event_paths.difference(self._events_by_path)
                )

        # The first read after a Space restart may need the historic archive.
        # Fetch independent immutable event files in parallel, once; subsequent
        # participant views and researcher filters are memory-only.
        if missing:
            workers = min(8, len(missing))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                downloaded = list(executor.map(self._download_json, missing))
            with self._cache_lock:
                for path, event in zip(missing, downloaded):
                    if event is not None:
                        self._events_by_path[path] = dict(event)

        with self._cache_lock:
            events = [
                dict(event)
                for event in self._events_by_path.values()
                if participant_id is None
                or event.get("participant_id_hash") == participant_id
            ]
        return sorted(events, key=lambda item: item.get("occurred_at", ""))

    def list_participants(self) -> list[dict[str, Any]]:
        self._require_private_repo()
        with self._cache_lock:
            if self._participant_paths is None:
                self._participant_paths = set(
                    self._list_files(prefix="participants/")
                )
            missing = [
                path
                for path in self._participant_paths
                if Path(path).stem not in self._participants_by_id
            ]
        if missing:
            workers = min(8, len(missing))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                downloaded = list(executor.map(self._download_json, missing))
            with self._cache_lock:
                for path, record in zip(missing, downloaded):
                    if record is not None:
                        self._participants_by_id[Path(path).stem] = dict(record)
        with self._cache_lock:
            participants = [
                dict(record) for record in self._participants_by_id.values()
            ]
        return sorted(participants, key=lambda item: item["display_name"].casefold())

    def _require_private_repo(self) -> None:
        with self._cache_lock:
            if self._private_repo_confirmed:
                return
            try:
                info = self.api.repo_info(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                )
            except Exception as exc:
                self._cached_health_status = (
                    False,
                    "Dataset degli eventi non raggiungibile o token non valido.",
                )
                raise EventStoreError(
                    "Dataset degli eventi non raggiungibile o token non valido."
                ) from exc
            if getattr(info, "private", None) is not True:
                self._cached_health_status = (
                    False,
                    "Il Dataset degli eventi deve essere privato.",
                )
                raise EventStoreError(
                    "Il Dataset degli eventi deve essere privato prima di poter "
                    "registrare partecipanti."
                )
            self._private_repo_confirmed = True
            self._cached_health_status = (True, "")

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
