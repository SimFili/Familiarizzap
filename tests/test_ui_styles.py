from __future__ import annotations

import inspect

import app
from app import (
    CSS,
    MAP_JS,
    MAP_TEMPLATE,
    SCALE_SELECTOR_TEMPLATE,
    TAXONOMY_TEMPLATE,
    EXERCISE_PROGRESS_JS,
    _taxonomy_data,
    _journey_sessions_html,
    build_demo,
)


def _css_rule(selector: str) -> str:
    start = CSS.index(f"{selector} {{")
    end = CSS.index("}", start)
    return CSS[start:end]


def test_light_surfaces_keep_dark_text_in_dark_mode() -> None:
    descriptor_rule = _css_rule(".descriptor-card")
    hero_rule = _css_rule(".hero h1")

    assert "color: var(--fapp-ink) !important;" in descriptor_rule
    assert "color: var(--fapp-hero-ink) !important;" in hero_rule


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


def test_exercise_progress_is_scrollable_and_not_color_only() -> None:
    assert ".exercise-progress-track" in CSS
    assert "overflow-x: auto;" in _css_rule(".exercise-progress-track")
    assert ".exercise-step-done.progress-first" in CSS
    assert ".exercise-step-done.progress-unresolved" in CSS
    assert "scrollIntoView" in EXERCISE_PROGRESS_JS
    source = inspect.getsource(app.build_demo)
    for label in (
        "1 = riconosciuto subito",
        "2 = al secondo tentativo",
        "3 = al terzo tentativo",
        "! = soluzione mostrata",
    ):
        assert label in source


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
    assert [column["title"] for column in columns] == [
        "Competenze linguistico-comunicative",
        "Competenze nelle lingue dei segni",
        "Attività linguistico-comunicative",
        "Strategie linguistico-comunicative",
    ]
    assert "Competenza generale" not in {column["title"] for column in columns}
    signed = next(
        column
        for column in columns
        if column["title"] == "Competenze nelle lingue dei segni"
    )
    assert all(not item["available"] for item in signed["items"])
    assert "{{#if show_availability}}" in TAXONOMY_TEMPLATE
    assert reception["available"] is True
    assert mediation["available"] is False


def test_home_places_general_navigation_after_identification() -> None:
    source = inspect.getsource(app.build_demo)
    login_start = source.index("with gr.Group(visible=True) as login_group")
    taxonomy_start = source.index(
        "with gr.Group(visible=False) as taxonomy_group"
    )
    hero_start = source.index('<section class="hero">')
    page_links_start = source.index('aria-label="Altre pagine"')

    assert login_start < taxonomy_start < hero_start
    assert taxonomy_start < page_links_start


def test_exercise_exit_handlers_are_registered_on_the_home_route() -> None:
    source = inspect.getsource(app.build_demo)
    personal_route = source.index('with demo.route(\n        "Il mio percorso"')

    assert source.index("leave_exercise_button.click") < personal_route
    assert source.index("cancel_leave_exercise_button.click") < personal_route
    assert source.index("confirm_leave_exercise_button.click") < personal_route


def test_taxonomy_uses_the_approved_palette_in_all_themes() -> None:
    expected = {
        "--fapp-taxonomy": "#d1c29f",
        "--fapp-reception": "#3b57ed",
        "--fapp-production": "#f13312",
        "--fapp-interaction": "#50139c",
        "--fapp-mediation": "#ff8c27",
        "--fapp-linguistic": "#31b3d2",
        "--fapp-sociolinguistic": "#54c900",
        "--fapp-pragmatic": "#ff0060",
    }
    for variable, color in expected.items():
        assert f"{variable}: {color};" in CSS
    for selector in (
        ".tax-reception",
        ".tax-production",
        ".tax-interaction",
        ".tax-mediation",
        ".tax-linguistic",
        ".tax-sociolinguistic",
        ".tax-pragmatic",
    ):
        assert "!important;" in _css_rule(selector)


def test_taxonomy_columns_use_symmetric_rows() -> None:
    desktop = _css_rule(".taxonomy-column")

    assert "grid-template-rows: 4.3rem repeat(4, 3.8rem);" in desktop
    assert "grid-template-rows: 4.8rem repeat(4, 4.15rem);" in CSS


def test_sign_language_schema_is_not_offered_by_text_navigation() -> None:
    schemas = app._available_schemas()

    assert schemas
    assert all("segni" not in schema.casefold() for schema in schemas)
    sign_schema = next(
        item for item in app.CATALOG.choices("schema") if "segni" in item.casefold()
    )
    assert app._is_sign_language_schema(sign_schema) is True


def test_scale_buttons_inherit_category_colors_and_sign_language_tones() -> None:
    for selector in (
        '.scale-choice-button[data-modality="Ricezione"]',
        '.scale-choice-button[data-modality="Produzione"]',
        '.scale-choice-button[data-modality="Interazione"]',
        '.scale-choice-button[data-modality="Linguistica"]',
        '.scale-choice-button[data-modality="Sociolinguistica"]',
        '.scale-choice-button[data-modality="Pragmatica"]',
    ):
        assert "--scale-color:" in _css_rule(selector)

    sign_schema = next(
        item for item in app.CATALOG.choices("schema") if "segni" in item.casefold()
    )
    reception = app._scale_selector_data(sign_schema, "Linguistica")
    reception_card = next(item for item in reception if item["activity"] == "Ricezione")
    production_card = next(item for item in reception if item["activity"] == "Produzione")
    assert all(item["color"] == "linguistic" for item in reception_card["scales"])
    assert all(item["tone"] == "sign-reception" for item in reception_card["scales"])
    assert all(item["tone"] == "sign-production" for item in production_card["scales"])


def test_journey_and_researcher_overviews_are_separate_pages() -> None:
    demo = build_demo()
    pages = {(page[0], page[1]) for page in demo.pages}

    assert ("", "Home") in pages
    assert ("percorso", "Il mio percorso") in pages
    assert ("ricercatore", "Panoramica ricercatore") in pages


def test_dark_theme_uses_coherent_surfaces_and_selected_filter_contrast() -> None:
    assert "--fapp-paper: #17251f;" in CSS
    assert "--fapp-unseen: #34433f;" in CSS
    assert "--fapp-unseen-text: #f1f5f9;" in CSS
    assert "body.dark label.selected" in CSS
    assert "background: #0b665e !important;" in CSS
    assert "color: #fff !important;" in CSS


def test_personal_sessions_are_cards_with_direct_resume_links() -> None:
    rendered = _journey_sessions_html(
        [
            {
                "session_id": "session 1",
                "scale": "Comprensione orale generale",
                "status": "in_progress",
                "status_label": "In corso",
                "descriptors_completed": 1,
                "descriptors_planned": 8,
                "first": 1,
                "first_attempt_rate": 100,
                "last_activity_at": "2026-08-12T08:00:00+00:00",
            }
        ]
    )

    assert "journey-session-card" in rendered
    assert "Riprendi questa sessione" in rendered
    assert "/?resume=session%201" in rendered
    assert "CSV" not in rendered
