from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    app_env: str
    app_version: str
    content_file_path: str
    content_repo_id: str
    content_revision: str
    events_repo_id: str
    hf_data_token: str
    participant_hash_salt: str
    researcher_access_key: str
    consent_version: str
    local_data_dir: Path

    @classmethod
    def from_env(cls, base_dir: Path) -> "Settings":
        is_space = bool(os.getenv("SPACE_ID"))
        app_env = os.getenv("APP_ENV", "production" if is_space else "local").strip()
        default_local_dir = (
            Path("/tmp/familiarizzap-demo")
            if is_space
            else base_dir / "data" / "runtime"
        )
        return cls(
            base_dir=base_dir,
            app_env=app_env,
            app_version=os.getenv("APP_VERSION", "0.5.2").strip(),
            content_file_path=os.getenv(
                "CONTENT_FILE_PATH",
                (
                    "data/catalog.full.json"
                    if (base_dir / "data" / "catalog.full.json").exists()
                    else ""
                ),
            ).strip(),
            content_repo_id=os.getenv("CONTENT_REPO_ID", "").strip(),
            content_revision=os.getenv("CONTENT_REVISION", "main").strip(),
            events_repo_id=os.getenv("EVENTS_REPO_ID", "").strip(),
            hf_data_token=os.getenv("HF_DATA_TOKEN", "").strip(),
            participant_hash_salt=os.getenv(
                "PARTICIPANT_HASH_SALT", ""
            ).strip(),
            researcher_access_key=os.getenv(
                "RESEARCHER_ACCESS_KEY", ""
            ).strip(),
            consent_version=os.getenv("CONSENT_VERSION", "demo-2026-07").strip(),
            local_data_dir=Path(
                os.getenv("LOCAL_DATA_DIR", str(default_local_dir))
            ),
        )

    @property
    def has_remote_storage(self) -> bool:
        return bool(
            self.events_repo_id
            and self.hf_data_token
            and self.participant_hash_salt
        )

    @property
    def storage_mode(self) -> str:
        if self.has_remote_storage:
            return "huggingface"
        if self.app_env in {"local", "test"}:
            return "local"
        return "demo"

    @property
    def effective_hash_salt(self) -> str:
        if self.participant_hash_salt:
            return self.participant_hash_salt
        return "familiarizzap-demo-only-not-for-research"
