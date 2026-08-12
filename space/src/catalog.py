from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .settings import Settings


PILOT_CEFR_LEVELS = ["A1", "A2", "A2+", "B1", "B1+", "B2"]
DEMO_CEFR_LEVELS = [*PILOT_CEFR_LEVELS, "C1", "C2"]

REQUIRED_FIELDS = {
    "descriptor_id",
    "schema",
    "modality",
    "activity",
    "scale",
    "correct_level",
    "descriptor_text",
    "rationale",
    "hint_1",
    "hint_2",
    "language",
    "source",
    "source_version",
    "license_or_permission",
    "content_version",
    "status",
    "active",
}
TEXT_FIELDS = {
    "schema",
    "modality",
    "activity",
    "scale",
    "descriptor_text",
    "rationale",
    "hint_1",
    "hint_2",
}


class CatalogError(ValueError):
    """Raised when the descriptor catalog is invalid."""


@dataclass(frozen=True)
class CatalogLoadResult:
    catalog: "Catalog"
    source_label: str
    is_demo: bool


class Catalog:
    def __init__(
        self,
        descriptors: Iterable[dict[str, Any]],
        *,
        allowed_statuses: Iterable[str] = ("approved",),
        allowed_levels: Iterable[str] = PILOT_CEFR_LEVELS,
    ):
        validated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        status_filter = {
            str(status).strip().casefold() for status in allowed_statuses
        }
        level_order = [
            str(level).strip().upper() for level in allowed_levels
        ]
        for raw in descriptors:
            missing = REQUIRED_FIELDS.difference(raw)
            if missing:
                raise CatalogError(
                    "Campi mancanti nel catalogo: " + ", ".join(sorted(missing))
                )
            item = dict(raw)
            for field in TEXT_FIELDS:
                item[field] = str(item[field] or "").strip()
            descriptor_id = str(item["descriptor_id"]).strip()
            if not descriptor_id or descriptor_id in seen_ids:
                raise CatalogError(
                    f"Identificativo mancante o duplicato: {descriptor_id!r}"
                )
            seen_ids.add(descriptor_id)
            item["descriptor_id"] = descriptor_id
            item["correct_level"] = str(item["correct_level"]).strip().upper()
            if item["correct_level"] not in level_order:
                raise CatalogError(
                    f"Livello CEFR non valido per {descriptor_id}: "
                    f"{item['correct_level']}"
                )
            item["status"] = str(item["status"]).strip().casefold()
            if not isinstance(item["active"], bool):
                raise CatalogError(
                    f"Il campo active deve essere booleano per {descriptor_id}."
                )
            if (
                item["active"]
                and item["status"] in status_filter
                and str(item["scale"]).strip()
                and str(item["descriptor_text"]).strip()
                and str(item["descriptor_text"]).strip().casefold()
                != "nessun descrittore"
            ):
                validated.append(item)
        if not validated:
            raise CatalogError("Il catalogo non contiene descrittori utilizzabili.")
        self._descriptors = validated
        self._by_id = {item["descriptor_id"]: item for item in validated}
        self._level_order = level_order

    @classmethod
    def from_json(
        cls,
        path: Path,
        *,
        allowed_statuses: Iterable[str] = ("approved",),
        allowed_levels: Iterable[str] = PILOT_CEFR_LEVELS,
    ) -> "Catalog":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Impossibile leggere il catalogo: {exc}") from exc
        if not isinstance(payload, list):
            raise CatalogError("Il catalogo deve essere una lista JSON.")
        return cls(
            payload,
            allowed_statuses=allowed_statuses,
            allowed_levels=allowed_levels,
        )

    def get(self, descriptor_id: str) -> dict[str, Any]:
        try:
            return dict(self._by_id[descriptor_id])
        except KeyError as exc:
            raise CatalogError(f"Descrittore sconosciuto: {descriptor_id}") from exc

    def all(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._descriptors]

    @property
    def level_order(self) -> list[str]:
        return list(self._level_order)

    def choices(
        self,
        field: str,
        *,
        schema: str | None = None,
        modality: str | None = None,
        activity: str | None = None,
    ) -> list[str]:
        items = self._descriptors
        filters = {
            "schema": schema,
            "modality": modality,
            "activity": activity,
        }
        for key, value in filters.items():
            if value is not None:
                items = [item for item in items if item[key] == value]
        return sorted(
            {
                str(item[field]).strip()
                for item in items
                if str(item[field]).strip()
            }
        )

    def for_scale(
        self, schema: str, modality: str, activity: str, scale: str
    ) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self._descriptors
            if item["schema"] == schema
            and item["modality"] == modality
            and item["activity"] == activity
            and item["scale"] == scale
        ]

    def levels_for(self, descriptor_ids: list[str]) -> list[str]:
        levels = {self._by_id[item_id]["correct_level"] for item_id in descriptor_ids}
        return [level for level in self._level_order if level in levels]

    def level_distance(self, first: str, second: str) -> int:
        try:
            return abs(
                self._level_order.index(str(first).strip().upper())
                - self._level_order.index(str(second).strip().upper())
            )
        except ValueError as exc:
            raise CatalogError(
                f"Impossibile calcolare la distanza tra {first!r} e {second!r}."
            ) from exc


def load_catalog(settings: Settings) -> CatalogLoadResult:
    if settings.content_file_path:
        path = Path(settings.content_file_path).expanduser()
        if not path.is_absolute():
            path = settings.base_dir / path
        return CatalogLoadResult(
            catalog=Catalog.from_json(
                path,
                allowed_statuses=("approved",),
                allowed_levels=PILOT_CEFR_LEVELS,
            ),
            source_label=(
                "completo incluso (831 esercizi, 52 scale)"
                if path.name == "catalog.full.json"
                else f"file {path.name}"
            ),
            is_demo=False,
        )

    if settings.content_repo_id:
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(
                repo_id=settings.content_repo_id,
                repo_type="dataset",
                filename="catalog.json",
                revision=settings.content_revision,
                token=settings.hf_data_token or None,
            )
            return CatalogLoadResult(
                catalog=Catalog.from_json(
                    Path(path),
                    allowed_statuses=("approved",),
                    allowed_levels=PILOT_CEFR_LEVELS,
                ),
                source_label=(
                    f"{settings.content_repo_id}@{settings.content_revision}"
                ),
                is_demo=False,
            )
        except Exception as exc:
            raise CatalogError(
                "Il catalogo remoto configurato non è disponibile o non è valido: "
                f"{exc}"
            ) from exc

    sample_path = settings.base_dir / "data" / "catalog.sample.json"
    return CatalogLoadResult(
        catalog=Catalog.from_json(
            sample_path,
            allowed_statuses=("demo",),
            allowed_levels=DEMO_CEFR_LEVELS,
        ),
        source_label="catalogo dimostrativo 2.0 incluso",
        is_demo=True,
    )
