from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.catalog import Catalog, CatalogError, DEMO_CEFR_LEVELS
from src.settings import Settings


def test_settings_selects_the_bundled_full_catalog_by_default(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("CONTENT_FILE_PATH", raising=False)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "catalog.full.json").write_text("[]", encoding="utf-8")

    settings = Settings.from_env(tmp_path)

    assert settings.content_file_path == "data/catalog.full.json"
    assert settings.app_version == "0.7.0"


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


def test_demo2_catalog_has_one_scale_for_each_reception_activity():
    path = (
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json"
    )
    catalog = Catalog.from_json(
        path,
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )

    expected = {
        ("Comprensione orale", "Comprensione orale generale"): 8,
        ("Comprensione audiovisiva", "Guardare la tv, film e video"): 9,
        (
            "Comprensione scritta",
            "Comprensione generale di un testo scritto",
        ): 5,
    }
    actual = {}
    for activity, scale in expected:
        descriptors = catalog.for_scale(
            "Attività linguistico-comunicative",
            "Ricezione",
            activity,
            scale,
        )
        actual[(activity, scale)] = len(descriptors)

    assert actual == expected
    assert len(catalog.all()) == 22
    assert all(
        "qualificator"
        not in f"{item['hint_1']} {item['hint_2']} {item['rationale']}".casefold()
        for item in catalog.all()
    )


def test_oral_scale_has_descriptor_specific_feedback():
    path = (
        Path(__file__).resolve().parents[1]
        / "space"
        / "data"
        / "catalog.sample.json"
    )
    catalog = Catalog.from_json(
        path,
        allowed_statuses=("demo",),
        allowed_levels=DEMO_CEFR_LEVELS,
    )
    descriptors = catalog.for_scale(
        "Attività linguistico-comunicative",
        "Ricezione",
        "Comprensione orale",
        "Comprensione orale generale",
    )

    assert len({item["hint_1"] for item in descriptors}) == 8
    assert len({item["hint_2"] for item in descriptors}) == 8
    assert len({item["rationale"] for item in descriptors}) == 8
    assert all(
        item["content_version"] == "demo-2.0-feedback-oral-1"
        for item in descriptors
    )
    assert all(
        not item["hint_1"].startswith("Feedback provvisorio:")
        for item in descriptors
    )


def test_pilot_catalog_rejects_levels_above_b2():
    row = {
        "descriptor_id": "c1",
        "schema": "Schema",
        "modality": "Ricezione",
        "activity": "Attività",
        "scale": "Scala",
        "correct_level": "C1",
        "descriptor_text": "Descrittore",
        "rationale": "Motivazione",
        "hint_1": "Primo indizio",
        "hint_2": "Secondo indizio",
        "language": "it",
        "source": "Test",
        "source_version": "1",
        "license_or_permission": "Test",
        "content_version": "1",
        "status": "approved",
        "active": True,
    }

    with pytest.raises(CatalogError, match="Livello CEFR non valido"):
        Catalog([row])


def test_choices_can_filter_an_explicit_empty_parent_value():
    row = {
        "descriptor_id": "blank-parent",
        "schema": "Schema",
        "modality": "",
        "activity": "Pragmatica",
        "scale": "Scala",
        "correct_level": "A1",
        "descriptor_text": "Descrittore",
        "rationale": "Motivazione",
        "hint_1": "Primo indizio",
        "hint_2": "Secondo indizio",
        "language": "it",
        "source": "Test",
        "source_version": "1",
        "license_or_permission": "Test",
        "content_version": "1",
        "status": "approved",
        "active": True,
    }
    catalog = Catalog([row])

    assert catalog.choices("activity", schema="Schema", modality="") == [
        "Pragmatica"
    ]
