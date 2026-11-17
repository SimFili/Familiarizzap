from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Condition, RLock
from typing import Any

from .settings import Settings


PARTICIPANT_DELETE_SCOPES = frozenset({"questionnaire", "events", "profile"})


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

    def preview_participant_deletion(
        self, participant_id: str, scope: str
    ) -> dict[str, Any]:
        """Describe an administrative deletion without changing the archive."""
        participant = self.get_participant(participant_id)
        if participant is None:
            raise EventStoreError("Partecipante non trovato.")
        events = self.list_events(participant_id)
        return _participant_deletion_preview(participant, events, scope)

    @abstractmethod
    def delete_participant_data(
        self,
        participant_id: str,
        scope: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        """Delete the exact data confirmed by a researcher preview."""
        raise NotImplementedError


class LocalEventStore(EventStore):
    def __init__(self, root: Path, mode: str = "local"):
        self.root = root
        self.mode = mode
        self.participants_dir = root / "participants"
        self.events_dir = root / "events"
        self._deletion_lock = RLock()

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
        with self._deletion_lock:
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
                raise EventStoreError(
                    f"Salvataggio locale non riuscito: {exc}"
                ) from exc

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

    def delete_participant_data(
        self,
        participant_id: str,
        scope: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        with self._deletion_lock:
            participant = self.get_participant(participant_id)
            if participant is None:
                raise EventStoreError("Partecipante non trovato.")
            events = self.list_events(participant_id)
            preview = _participant_deletion_preview(participant, events, scope)
            _require_matching_deletion_revision(preview, expected_revision)
            selected = _events_for_deletion(events, scope)
            paths = [self._event_path(event) for event in selected]
            if scope == "profile":
                paths.append(self.participants_dir / f"{participant_id}.json")
            try:
                for path in paths:
                    path.unlink(missing_ok=True)
            except OSError as exc:
                raise EventStoreError(
                    f"Cancellazione locale non riuscita: {exc}"
                ) from exc
        return {**preview, "deleted_files": len(paths)}


class HuggingFaceEventStore(EventStore):
    mode = "huggingface"
    _MAX_COMMIT_ATTEMPTS = 2
    _PENDING_WRITE_TIMEOUT_SECONDS = 30.0

    def __init__(self, repo_id: str, token: str, api: Any | None = None):
        if api is None:
            import httpx
            from huggingface_hub import HfApi, set_client_factory

            # huggingface_hub otherwise creates a shared client without any
            # timeout.  A stalled Hub request would leave a participant's
            # button waiting indefinitely.
            set_client_factory(
                lambda: httpx.Client(
                    follow_redirects=True,
                    timeout=httpx.Timeout(10.0, connect=5.0, pool=5.0),
                )
            )

            api = HfApi(token=token)
        self.repo_id = repo_id
        self.token = token
        self.api = api
        self._private_repo_confirmed = False
        self._cached_health_status: tuple[bool, str] | None = None
        self._cache_lock = RLock()
        self._event_condition = Condition(self._cache_lock)
        self._event_paths: set[str] | None = None
        self._pending_event_paths: set[str] = set()
        self._events_by_path: dict[str, dict[str, Any]] = {}
        self._participant_paths: set[str] | None = None
        self._participants_by_id: dict[str, dict[str, Any]] = {}
        self._participants_without_remote_history: set[str] = set()
        self._participants_pending_deletion: set[str] = set()

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
        event_paths = [
            (event, _remote_event_path(event)) for event in events
        ]
        reserved_paths: set[str] = set()
        try:
            # The remote file listing used to run before every answer.  Apart
            # from being needlessly expensive, that made interaction slower as
            # the research archive grew.  Reserve only the target paths under
            # the lock; the network request itself must remain outside it so
            # independent participants can save concurrently.
            with self._event_condition:
                participant_ids = {
                    str(event.get("participant_id_hash", "")) for event in events
                }
                if participant_ids & self._participants_pending_deletion:
                    raise EventStoreError(
                        "I dati del partecipante sono in eliminazione. Riprova."
                    )
                if self._event_paths is None:
                    self._event_paths = set(self._list_files(prefix="events/"))
                ready = self._event_condition.wait_for(
                    lambda: all(
                        path not in self._pending_event_paths
                        for _, path in event_paths
                    ),
                    timeout=self._PENDING_WRITE_TIMEOUT_SECONDS,
                )
                if not ready:
                    raise EventStoreError(
                        "Salvataggio già in corso per questa risposta. Riprova."
                    )
                new_events = [
                    (event, path)
                    for event, path in event_paths
                    if path not in self._event_paths
                ]
                if not new_events:
                    return
                reserved_paths = {path for _, path in new_events}
                self._pending_event_paths.update(reserved_paths)

            self._commit_events(new_events)

            with self._event_condition:
                for event, path in new_events:
                    self._event_paths.add(path)
                    self._events_by_path[path] = dict(event)
                self._pending_event_paths.difference_update(reserved_paths)
                self._event_condition.notify_all()
                reserved_paths.clear()
        except EventStoreError:
            raise
        except Exception as exc:
            raise EventStoreError(f"Eventi non salvati: {exc}") from exc
        finally:
            if reserved_paths:
                with self._event_condition:
                    self._pending_event_paths.difference_update(reserved_paths)
                    self._event_condition.notify_all()

    def _commit_events(
        self, events: list[tuple[dict[str, Any], str]]
    ) -> None:
        from huggingface_hub import CommitOperationAdd

        for attempt in range(self._MAX_COMMIT_ATTEMPTS):
            operations = [
                CommitOperationAdd(
                    path_in_repo=path,
                    path_or_fileobj=io.BytesIO(_json_bytes(event)),
                )
                for event, path in events
            ]
            try:
                self.api.create_commit(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    operations=operations,
                    commit_message=(
                        "Registra evento"
                        if len(events) == 1
                        else "Registra eventi"
                    ),
                )
                return
            except Exception as exc:
                if (
                    attempt + 1 >= self._MAX_COMMIT_ATTEMPTS
                    or not _is_transient_remote_error(exc)
                ):
                    raise
                time.sleep(0.2 * (2**attempt))

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

    def delete_participant_data(
        self,
        participant_id: str,
        scope: str,
        *,
        expected_revision: str,
    ) -> dict[str, Any]:
        self._require_private_repo()
        with self._event_condition:
            if participant_id in self._participants_pending_deletion:
                raise EventStoreError("Cancellazione già in corso.")
            self._participants_pending_deletion.add(participant_id)
            ready = self._event_condition.wait_for(
                lambda: not self._pending_event_paths,
                timeout=self._PENDING_WRITE_TIMEOUT_SECONDS,
            )
            if not ready:
                self._participants_pending_deletion.discard(participant_id)
                self._event_condition.notify_all()
                raise EventStoreError(
                    "Un salvataggio è ancora in corso. Riprova tra poco."
                )

        try:
            participant = self.get_participant(participant_id)
            if participant is None:
                raise EventStoreError("Partecipante non trovato.")
            events = self.list_events(participant_id)
            preview = _participant_deletion_preview(participant, events, scope)
            _require_matching_deletion_revision(preview, expected_revision)
            selected = _events_for_deletion(events, scope)
            event_paths = [_remote_event_path(event) for event in selected]
            paths = list(event_paths)
            participant_path = f"participants/{participant_id}.json"
            if scope == "profile":
                # The profile is deliberately last: a partial remote failure
                # must never leave anonymous events without their registry row.
                paths.append(participant_path)

            deleted = 0
            for offset in range(0, len(paths), 50):
                batch = paths[offset : offset + 50]
                self._commit_deletions(batch)
                deleted += len(batch)
                with self._event_condition:
                    for path in batch:
                        if self._event_paths is not None:
                            self._event_paths.discard(path)
                        self._events_by_path.pop(path, None)
                        if path == participant_path:
                            if self._participant_paths is not None:
                                self._participant_paths.discard(path)
                            self._participants_by_id.pop(participant_id, None)
            with self._event_condition:
                if scope in {"events", "profile"}:
                    self._participants_without_remote_history.add(participant_id)
                if scope == "profile":
                    self._participants_without_remote_history.discard(participant_id)
            return {**preview, "deleted_files": deleted}
        except EventStoreError:
            raise
        except Exception as exc:
            raise EventStoreError(f"Cancellazione non riuscita: {exc}") from exc
        finally:
            with self._event_condition:
                self._participants_pending_deletion.discard(participant_id)
                self._event_condition.notify_all()

    def _commit_deletions(self, paths: list[str]) -> None:
        if not paths:
            return
        from huggingface_hub import CommitOperationDelete

        for attempt in range(self._MAX_COMMIT_ATTEMPTS):
            try:
                self.api.create_commit(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    operations=[
                        CommitOperationDelete(path_in_repo=path) for path in paths
                    ],
                    commit_message="Rimuove dati selezionati dall’area ricercatore",
                )
                return
            except Exception as exc:
                if (
                    attempt + 1 >= self._MAX_COMMIT_ATTEMPTS
                    or not _is_transient_remote_error(exc)
                ):
                    raise
                time.sleep(0.2 * (2**attempt))

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


def _events_for_deletion(
    events: list[dict[str, Any]], scope: str
) -> list[dict[str, Any]]:
    if scope not in PARTICIPANT_DELETE_SCOPES:
        raise EventStoreError("Tipo di cancellazione non valido.")
    if scope == "questionnaire":
        return [
            event
            for event in events
            if event.get("event_type") == "questionnaire_submitted"
        ]
    return list(events)


def _participant_deletion_preview(
    participant: dict[str, Any],
    events: list[dict[str, Any]],
    scope: str,
) -> dict[str, Any]:
    selected = _events_for_deletion(events, scope)
    revision_payload = {
        "participant_id": str(participant.get("participant_id", "")),
        "participant": participant,
        "scope": scope,
        "events": sorted(
            json.dumps(event, ensure_ascii=False, sort_keys=True)
            for event in selected
        ),
    }
    revision = hashlib.sha256(
        json.dumps(
            revision_payload, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    questionnaire_count = sum(
        event.get("event_type") == "questionnaire_submitted"
        for event in selected
    )
    profile_count = 1 if scope == "profile" else 0
    return {
        "participant_id": str(participant.get("participant_id", "")),
        "display_name": str(participant.get("display_name", "")),
        "scope": scope,
        "event_count": len(selected),
        "questionnaire_count": questionnaire_count,
        "profile_count": profile_count,
        "total_files": len(selected) + profile_count,
        "revision": revision,
    }


def _require_matching_deletion_revision(
    preview: dict[str, Any], expected_revision: str
) -> None:
    if not expected_revision or not hmac.compare_digest(
        str(preview["revision"]), str(expected_revision)
    ):
        raise EventStoreError(
            "I dati sono cambiati dopo l’anteprima. Controllali di nuovo prima "
            "di cancellare."
        )


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


def _is_transient_remote_error(exc: Exception) -> bool:
    status_code = getattr(
        getattr(exc, "response", None), "status_code", None
    )
    if status_code in {408, 409, 423, 425, 429, 500, 502, 503, 504}:
        return True
    name = type(exc).__name__.casefold()
    return any(
        marker in name
        for marker in (
            "timeout",
            "connect",
            "network",
            "remoteprotocol",
        )
    )


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
