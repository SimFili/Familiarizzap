from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .settings import Settings


CEFR_LEVELS = ["A1", "A2", "A2+", "B1", "B1+", "B2", "C1", "C2"]

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


class CatalogError(ValueError):
    """Raised when the descriptor catalog is invalid."""


@dataclass(frozen=True)
class CatalogLoadResult:
    catalog: "Catalog"
    source_label: str
    is_demo: bool


class Catalog:
    def __init__(self, descriptors: Iterable[dict[str, Any]]):
        validated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for raw in descriptors:
            missing = REQUIRED_FIELDS.difference(raw)
            if missing:
                raise CatalogError(
                    "Campi mancanti nel catalogo: " + ", ".join(sorted(missing))
                )
            item = dict(raw)
            descriptor_id = str(item["descriptor_id"]).strip()
            if not descriptor_id or descriptor_id in seen_ids:
                raise CatalogError(
                    f"Identificativo mancante o duplicato: {descriptor_id!r}"
                )
            seen_ids.add(descriptor_id)
            item["descriptor_id"] = descriptor_id
            item["correct_level"] = str(item["correct_level"]).strip().upper()
            if item["correct_level"] not in CEFR_LEVELS:
                raise CatalogError(
                    f"Livello CEFR non valido per {descriptor_id}: "
                    f"{item['correct_level']}"
                )
            if not isinstance(item["active"], bool):
                raise CatalogError(
                    f"Il campo active deve essere booleano per {descriptor_id}."
                )
            if (
                item["active"]
                and str(item["status"]).strip().lower() == "approved"
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

    @classmethod
    def from_json(cls, path: Path) -> "Catalog":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Impossibile leggere il catalogo: {exc}") from exc
        if not isinstance(payload, list):
            raise CatalogError("Il catalogo deve essere una lista JSON.")
        return cls(payload)

    def get(self, descriptor_id: str) -> dict[str, Any]:
        try:
            return dict(self._by_id[descriptor_id])
        except KeyError as exc:
            raise CatalogError(f"Descrittore sconosciuto: {descriptor_id}") from exc

    def all(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._descriptors]

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
            if value:
                items = [item for item in items if item[key] == value]
        return sorted({str(item[field]) for item in items})

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
        return [level for level in CEFR_LEVELS if level in levels]


def load_catalog(settings: Settings) -> CatalogLoadResult:
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
                catalog=Catalog.from_json(Path(path)),
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
        catalog=Catalog.from_json(sample_path),
        source_label="catalogo dimostrativo incluso",
        is_demo=True,
    )
