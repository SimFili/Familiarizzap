from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from tools.build_catalog import build_catalog


def test_build_catalog_preserves_source_and_fills_navigation_gaps(
    tmp_path: Path,
):
    source = tmp_path / "catalog.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["No", "Schema", "Modalità", "Attività", "Scala", "Livello", "Descrittore"])
    sheet.append(
        [
            17,
            "Competenze nella lingua dei segni",
            None,
            "Pragmatica",
            "Strutturazione del testo",
            "B1+",
            "Descrittore di prova",
        ]
    )
    workbook.save(source)

    rows, report = build_catalog(
        source,
        tmp_path / "missing-sample.json",
        expected_rows=1,
    )

    assert report["catalog_rows"] == 1
    assert report["blank_source_modality"] == 1
    assert rows[0]["modality"] == "Pragmatica"
    assert rows[0]["activity"] == "Scale generali"
    assert rows[0]["source_modality"] == ""
    assert rows[0]["correct_level"] == "B1+"
