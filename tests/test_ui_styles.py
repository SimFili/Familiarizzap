from __future__ import annotations

import builtins
import inspect
import symtable

import app
from app import (
    CSS,
    MAP_JS,
    MAP_TEMPLATE,
    SCALE_SELECTOR_TEMPLATE,
    TAXONOMY_TEMPLATE,
    EXERCISE_PROGRESS_JS,
    THEME_SYNC_JS,
    _taxonomy_data,
    _journey_sessions_html,
    build_demo,
)


def _css_rule(selector: str) -> str:
    start = CSS.index(f"{selector} {{")
    end = CSS.index("}", start)
    return CSS[start:end]


def test_app_functions_do_not_reference_undefined_global_names() -> None:
    source = inspect.getsource(app)
    table = symtable.symtable(source, "space/app.py", "exec")
    module_names = {symbol.get_name() for symbol in table.get_symbols()}
    builtin_names = set(dir(builtins))
    missing: list[tuple[str, int, str]] = []

    def inspect_scope(scope) -> None:
        for symbol in scope.get_symbols():
            if (
                symbol.is_referenced()
                and symbol.is_global()
                and symbol.get_name() not in module_names
                and symbol.get_name() not in builtin_names
            ):
                missing.append(
                    (scope.get_name(), scope.get_lineno(), symbol.get_name())
                )
        for child in scope.get_children():
            inspect_scope(child)

    inspect_scope(table)

    assert missing == []


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


def test_summary_scale_button_shows_the_scale_panel_directly() -> None:
    source = inspect.getsource(app.build_demo)
    binding_start = source.index("dashboard_button.click")
    binding_end = source.index("summary_taxonomy_button.click", binding_start)
    binding = source[binding_start:binding_end]

    assert "scale_group" in binding
    assert ").then(" not in binding


def test_every_main_stage_exposes_a_clear_way_back_or_forward() -> None:
    source = inspect.getsource(app.build_demo)

    for label in (
        "Continua con questo nome",
        "Continua con questo ambito",
        "Torna alla scelta del percorso",
        "Torna alla scelta della scala",
        "Scegli un’altra scala",
        "Cambia ambito",
        "Cambia nome",
    ):
        assert label in source

    assert "summary_taxonomy_button.click" in source
    assert "bind_logout(summary_logout_button)" in source


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


def test_annunci_pubblici_is_the_only_selectable_short_scale() -> None:
    all_choices = [label for label, _ in app._scale_choices()]
    activity_schema = next(
        path[0]
        for path in app._all_catalog_paths()
        if path[1:] == (
            "Produzione",
            "Produzione orale",
            "Annunci pubblici",
        )
    )
    production = app._scale_selector_data(activity_schema, "Produzione")
    visible_scales = {
        item["scale"]
        for activity in production
        for item in activity["scales"]
    }

    assert any("Annunci pubblici" in label for label in all_choices)
    assert all(
        not app._is_sign_language_schema(app._decode_path(value)[0])
        for _, value in app._scale_choices()
    )
    assert "Annunci pubblici" in visible_scales
    assert "Annunci pubblici" in app._available_scales(
        activity_schema,
        "Produzione",
        "Produzione orale",
    )
    short_paths = [
        path
        for path in app._all_catalog_paths()
        if len(app.CATALOG.for_scale(*path)) < 4
    ]
    assert len(short_paths) == 1
    assert short_paths[0][1:] == (
        "Produzione",
        "Produzione orale",
        "Annunci pubblici",
    )
    assert app._participant_scale_is_available(short_paths[0]) is True
    assert app._participant_scale_is_available(
        (*short_paths[0][:-1], "Una scala diversa")
    ) is False


def test_pilot_requires_four_non_plus_descriptors_except_annunci_pubblici():
    planning = next(
        path for path in app._all_catalog_paths()
        if path[3] == "Pianificazione"
        and path[0] == "Strategie linguistico-comunicative"
    )
    assert len(app.CATALOG.for_scale(*planning)) == 4
    assert sum(
        item["correct_level"] not in {"A2+", "B1+"}
        for item in app.CATALOG.for_scale(*planning)
    ) == 3
    assert app._participant_scale_is_available(planning) is False


def test_reviewed_mixed_scales_are_available_without_reopening_others() -> None:
    suspended_names = {
        "Utilizzare le telecomunicazioni",
        "Conversazione e discussione on line",
        "Transazioni e collaborazione on line finalizzate a uno scopo",
    }
    restored_name = (
        "Individuare indizi e fare inferenze (ricezione orale, "
        "nella lingua dei segni e scritta)"
    )
    active_name = (
        "Comprendere mezzi di comunicazione audio (o nella lingua dei segni) "
        "e registrazioni"
    )
    paths = {
        path[3]: path
        for path in app._all_catalog_paths()
        if path[3] in suspended_names | {active_name, restored_name}
    }

    assert set(paths) == suspended_names | {active_name, restored_name}
    assert app._participant_scale_is_available(paths[active_name]) is True
    assert paths[restored_name][:3] == (
        "Strategie linguistico-comunicative",
        "Ricezione",
        "Scale disponibili",
    )
    assert len(app.CATALOG.for_scale(*paths[restored_name])) == 16
    assert app._participant_scale_is_available(paths[restored_name]) is True
    assert all(
        app._participant_scale_is_available(paths[name]) is False
        for name in suspended_names
    )

    participant_values = {
        app._decode_path(value) for _, value in app._scale_choices()
    }
    assert paths[active_name] in participant_values
    assert paths[restored_name] in participant_values
    assert all(paths[name] not in participant_values for name in suspended_names)

    selector = app._scale_selector_data(*paths[restored_name][:2])
    restored_card = next(
        card
        for group in selector
        for card in group["scales"]
        if card["scale"] == restored_name
    )
    assert restored_card["activity"] == "Scale disponibili"
    assert restored_card["available"] is True


def test_written_reception_production_and_interaction_are_suspended() -> None:
    written_activities = {
        "Comprensione scritta": 6,
        "Produzione scritta": 3,
        "Interazione scritta": 3,
    }
    paths = [
        path
        for path in app._all_catalog_paths()
        if path[2] in written_activities
    ]

    assert len(paths) == sum(written_activities.values())
    assert {
        activity: sum(path[2] == activity for path in paths)
        for activity in written_activities
    } == written_activities
    assert all(
        app._participant_scale_is_available(path) is False for path in paths
    )

    participant_values = {
        app._decode_path(value) for _, value in app._scale_choices()
    }
    assert all(path not in participant_values for path in paths)

    for schema, modality, activity, scale in paths:
        selector = app._scale_selector_data(schema, modality)
        card = next(
            item
            for group in selector
            if group["activity"] == activity
            for item in group["scales"]
            if item["scale"] == scale
        )
        assert card["available"] is False


def test_suspended_scales_stay_visible_as_disabled_cards() -> None:
    path = next(
        path
        for path in app._all_catalog_paths()
        if path[3] == "Conversazione e discussione on line"
    )
    selector = app._scale_selector_data(path[0], path[1])
    cards = {
        card["scale"]: card
        for group in selector
        for card in group["scales"]
    }

    assert cards[path[3]]["available"] is False
    assert "{{#unless available}}disabled{{/unless}}" in SCALE_SELECTOR_TEMPLATE
    assert "Non ancora disponibile" in SCALE_SELECTOR_TEMPLATE


def test_reviewed_descriptor_wording_and_strikethrough() -> None:
    descriptor_71 = app.CATALOG.get("SRC-71")
    descriptor_72 = app.CATALOG.get("SRC-72")
    descriptor_76 = app.CATALOG.get("SRC-76")

    assert "<s>via radio</s>" in app._participant_descriptor_html(
        descriptor_71
    )
    assert "<s>per radio</s>" in app._participant_descriptor_html(
        descriptor_72
    )
    assert "~~via radio~~" in app._participant_descriptor_markdown(
        descriptor_71
    )
    assert "~~per radio~~" in app._participant_descriptor_markdown(
        descriptor_72
    )
    assert "parlino/segnino" in descriptor_76["descriptor_text"]


def test_zero_unseen_items_are_absent_from_summary_legend() -> None:
    legend = app._legend_html(
        {"first": 2, "second": 0, "third": 0, "unresolved": 0, "unseen": 0}
    )

    assert "1° tentativo" in legend
    assert "Non ancora incontrato" not in legend


def test_researcher_choices_keep_closed_scales_for_historical_data() -> None:
    researcher_values = [
        app._decode_path(value)
        for _, value in app._scale_choices(include_closed=True)
    ]

    assert any(app._is_sign_language_schema(path[0]) for path in researcher_values)
    assert any(path[3] == "Annunci pubblici" for path in researcher_values)


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


def test_journey_describes_only_the_map_of_encountered_descriptors() -> None:
    source = inspect.getsource(app.build_demo)

    assert "mappa completa" not in source.casefold()
    assert "mappa dei descrittori" in source.casefold()
    assert "Il mio percorso completo" not in source


def test_pilot_guided_track_is_primary_and_free_catalog_is_optional() -> None:
    demo = app.build_demo()
    accordions = [
        component["props"] for component in demo.config["components"]
        if component["type"] == "accordion"
    ]
    optional = next(
        props for props in accordions
        if "esplorazione facoltativa" in props.get("label", "")
    )
    assert optional["open"] is False
    source = inspect.getsource(app.build_demo)
    assert "Il percorso principale del pilot ha 16 descrittori" in source
    assert "Non devi completare tutto il catalogo" in source
    assert "I loro feedback sono ancora" in source


def test_researcher_link_is_secondary_in_the_journey_header() -> None:
    source = inspect.getsource(app.build_demo)
    route_start = source.index('with demo.route(\n        "Il mio percorso"')
    hero_start = source.index('<section class="hero">', route_start)
    load_start = source.index("demo.load(", hero_start)
    header = source[route_start:hero_start]
    journey_body = source[hero_start:load_start]

    assert 'class="page-links journey-page-links"' in header
    assert "Torna a FamiliarizzApp" in header
    assert "Panoramica ricercatore" in header
    assert "Panoramica ricercatore" not in journey_body
    assert ".journey-page-links" in CSS


def test_dark_theme_uses_coherent_surfaces_and_selected_filter_contrast() -> None:
    assert "--fapp-page: #0f1714;" in CSS
    assert "--fapp-paper: #17251f;" in CSS
    assert "--fapp-soft: #22352e;" in CSS
    assert "--fapp-action: #214039;" in CSS
    assert "--fapp-mint: #203b34;" in CSS
    assert "--fapp-unseen: #34433f;" in CSS
    assert "--fapp-unseen-text: #f1f5f9;" in CSS
    assert "body.dark label.selected" in CSS
    assert "background: #0b665e !important;" in CSS
    assert "color: #fff !important;" in CSS
    assert "--fapp-in-progress: #284861;" in CSS
    assert ".status-in_progress" in CSS


def test_color_theme_follows_user_choice_across_internal_pages() -> None:
    assert "@media (prefers-color-scheme: dark)" not in CSS
    assert "body.dark" in CSS
    assert "html," in CSS
    assert "background: var(--fapp-page) !important;" in CSS
    assert 'window.localStorage.setItem(storageKey, requestedTheme)' in THEME_SYNC_JS
    assert 'window.localStorage.removeItem(storageKey)' in THEME_SYNC_JS
    assert 'target.searchParams.set("__theme", selectedTheme)' in THEME_SYNC_JS
    assert 'link.setAttribute("data-sveltekit-reload", "true")' in THEME_SYNC_JS
    assert "MutationObserver" in THEME_SYNC_JS


def test_cross_page_links_force_a_full_gradio_reload() -> None:
    source = inspect.getsource(app.build_demo)

    assert 'href="/percorso"' in source
    assert 'href="/ricercatore"' in source
    assert source.count('data-sveltekit-reload="true"') >= 6


def test_theme_sync_is_loaded_with_the_gradio_app() -> None:
    source = inspect.getsource(app)

    assert "js=THEME_SYNC_JS" in source


def test_personal_sessions_are_cards_with_direct_resume_links() -> None:
    rendered = _journey_sessions_html(
        [
            {
                "session_id": "session 1",
                "schema": "Attività linguistico-comunicative",
                "modality": "Ricezione",
                "activity": "Comprensione orale",
                "scale": "Comprensione orale generale",
                "descriptor_ids": [
                    next(
                        item["descriptor_id"]
                        for item in app.CATALOG.for_scale(
                            "Attività linguistico-comunicative",
                            "Ricezione",
                            "Comprensione orale",
                            "Comprensione orale generale",
                        )
                        if item["correct_level"] == "B1"
                    )
                ],
                "available_levels": ["A1", "A2", "B1", "B2"],
                "status": "in_progress",
                "status_label": "In corso",
                "descriptors_completed": 1,
                "descriptors_planned": 8,
                "descriptors_started": 2,
                "descriptors_in_progress": 1,
                "attempts_submitted_in_progress": 1,
                "first": 1,
                "first_attempt_rate": 100,
                "last_activity_at": "2026-08-12T08:00:00+00:00",
            }
        ]
    )

    assert "journey-session-card" in rendered
    assert "Riprendi questa sessione" in rendered
    assert "/?resume=session%201" in rendered
    assert 'data-sveltekit-reload="true"' in rendered
    assert "2 iniziati" in rendered
    assert "1 tentativo salvato" in rendered
    assert "CSV" not in rendered


def test_personal_sessions_do_not_link_to_a_suspended_scale() -> None:
    rendered = _journey_sessions_html(
        [
            {
                "session_id": "sign-session",
                "schema": "Competenze nelle lingue dei segni",
                "modality": "Linguistica",
                "activity": "Ricezione",
                "scale": "Scala sospesa",
                "status": "in_progress",
                "status_label": "In corso",
                "descriptors_completed": 1,
                "descriptors_planned": 4,
                "last_activity_at": "2026-08-12T08:00:00+00:00",
            }
        ]
    )

    assert "Riprendi questa sessione" not in rendered
    assert "resta nella cronologia" in rendered


def test_personal_view_ignores_an_unavailable_latest_session(monkeypatch) -> None:
    allowed_path = app._catalog_paths()[0]
    unavailable_session = {
        "schema": "Competenze nelle lingue dei segni",
        "modality": "Linguistica",
        "activity": "Ricezione",
        "scale": "Scala sospesa",
        "status": "completed",
        "completed_at": "2026-08-12T09:00:00+00:00",
        "last_activity_at": "2026-08-12T09:00:00+00:00",
        "first_attempt_rate": 0,
    }
    available_session = {
        "schema": allowed_path[0],
        "modality": allowed_path[1],
        "activity": allowed_path[2],
        "scale": allowed_path[3],
        "status": "completed",
        "completed_at": "2026-08-11T09:00:00+00:00",
        "last_activity_at": "2026-08-11T09:00:00+00:00",
        "first_attempt_rate": 0,
    }

    class Store:
        @staticmethod
        def list_events(participant):
            return []

    monkeypatch.setattr(app, "STORE", Store())
    monkeypatch.setattr(
        app,
        "session_records",
        lambda events, catalog: [unavailable_session, available_session],
    )

    result = app._personal_view("participant")

    assert result[1].value == app._path_value(allowed_path)


def test_partial_descriptor_detail_does_not_reveal_the_correct_level() -> None:
    rendered = app._descriptor_detail_markdown(
        {
            "descriptor": {
                "correct_level": "B2",
                "scale": "Scala di prova",
                "descriptor_text": "Testo del descrittore",
            },
            "history": [],
            "in_progress": [
                {
                    "session_id": "session 1",
                    "occurred_at": "2026-08-12T08:00:00+00:00",
                    "attempts": ["A2"],
                    "attempts_text": "A2",
                }
            ],
        },
        researcher=False,
    )

    assert "### In corso" in rendered
    assert "Tentativi già salvati: `A2`" in rendered
    assert "/?resume=session%201" in rendered
    assert 'data-sveltekit-reload="true"' in rendered
    assert "B2" not in rendered


def test_journey_copy_describes_completed_latest_outcomes() -> None:
    source = inspect.getsource(app._personal_view)

    assert "nell’incontro più recente" not in source
    assert "esito completato più recente" in source
    assert "descrittori in corso" in source


def test_remote_storage_banner_does_not_claim_success_when_unhealthy(
    monkeypatch,
) -> None:
    class _RemoteSettings:
        storage_mode = "huggingface"

    class _UnhealthyStore:
        @staticmethod
        def health_check():
            return False, "token non valido"

    monkeypatch.setattr(app, "SETTINGS", _RemoteSettings())
    monkeypatch.setattr(app, "STORE", _UnhealthyStore())

    banner = app._storage_banner()

    assert "Archivio non disponibile" in banner
    assert "Non usare l’app per raccogliere dati" in banner
    assert "token non valido" not in banner


def test_demo_storage_banner_uses_short_copy_without_catalog_detail(monkeypatch) -> None:
    class _DemoSettings:
        storage_mode = "demo"

    monkeypatch.setattr(app, "SETTINGS", _DemoSettings())

    assert app._storage_banner() == (
        "**Modalità dimostrativa:** i dati sono temporanei e possono sparire "
        "al riavvio. Non usare questa modalità per la ricerca."
    )
