from __future__ import annotations

from app import (
    CSS,
    MAP_JS,
    MAP_TEMPLATE,
    SCALE_SELECTOR_TEMPLATE,
    TAXONOMY_TEMPLATE,
    _taxonomy_data,
)


def _css_rule(selector: str) -> str:
    start = CSS.index(f"{selector} {{")
    end = CSS.index("}", start)
    return CSS[start:end]


def test_light_surfaces_keep_dark_text_in_dark_mode() -> None:
    descriptor_rule = _css_rule(".descriptor-card")
    hero_rule = _css_rule(".hero h1")

    assert "color: var(--fapp-ink) !important;" in descriptor_rule
    assert "color: var(--fapp-ink) !important;" in hero_rule


def test_mobile_container_does_not_overflow_due_to_padding() -> None:
    container_rule = _css_rule(".gradio-container")

    assert "box-sizing: border-box;" in container_rule
    assert "width: 100% !important;" in container_rule
    assert "min-width: 0 !important;" in container_rule


def test_outcome_colors_have_text_labels_and_dark_mode_contrast() -> None:
    assert "--fapp-first: #2e7d32;" in CSS
    assert ".status-first { background: var(--fapp-first); color: #fff; }" in CSS
    assert ".status-unresolved" in CSS
    for label in (
        "status_label",
        "descriptor_id",
        "aria-label",
    ):
        assert label in MAP_TEMPLATE
    assert "trigger('click'" in MAP_JS


def test_taxonomy_and_scale_maps_use_real_buttons() -> None:
    assert "<button" in TAXONOMY_TEMPLATE
    assert "disabled" in TAXONOMY_TEMPLATE
    assert "<button" in SCALE_SELECTOR_TEMPLATE
    columns = _taxonomy_data()
    reception = next(
        item
        for column in columns
        if column["title"] == "Attività linguistico-comunicative"
        for item in column["items"]
        if item["label"] == "Ricezione"
    )
    mediation = next(
        item
        for column in columns
        if column["title"] == "Attività linguistico-comunicative"
        for item in column["items"]
        if item["label"] == "Mediazione"
    )
    assert reception["available"] is True
    assert mediation["available"] is False
