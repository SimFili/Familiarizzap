from __future__ import annotations

import json
from pathlib import Path

from src.catalog import Catalog


def test_catalog_filters_unusable_rows_and_orders_levels(tmp_path: Path):
    required = {
        "schema": "Schema",
        "modality": "Interazione",
        "activity": "Turni",
        "scale": "Scala",
        "rationale": "Motivazione",
        "hint_1": "Primo indizio",
        "hint_2": "Secondo indizio",
        "language": "it",
        "source": "Test",
        "source_version": "1",
        "license_or_permission": "CC0",
        "content_version": "1",
        "status": "approved",
        "active": True,
    }
    rows = [
        {
            **required,
            "descriptor_id": "b1",
            "correct_level": "B1",
            "descriptor_text": "Descrittore B1",
        },
        {
            **required,
            "descriptor_id": "a2plus",
            "correct_level": "A2+",
            "descriptor_text": "Descrittore A2+",
        },
        {
            **required,
            "descriptor_id": "empty",
            "correct_level": "A1",
            "descriptor_text": "Nessun descrittore",
        },
        {
            **required,
            "descriptor_id": "draft",
            "correct_level": "B2",
            "descriptor_text": "Bozza",
            "status": "draft",
        },
    ]
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(rows), encoding="utf-8")

    catalog = Catalog.from_json(path)

    assert [item["descriptor_id"] for item in catalog.all()] == ["b1", "a2plus"]
    assert catalog.levels_for(["b1", "a2plus"]) == ["A2+", "B1"]
