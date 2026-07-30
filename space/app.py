from __future__ import annotations

import hmac
import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import gradio as gr

from src.analytics import (
    OUTCOME_LABELS,
    descriptor_details,
    descriptor_history,
    exact_timestamp,
    integrity_report,
    participant_overview,
    relative_timestamp,
    scale_map,
    session_records,
)
from src.auth import (
    IdentityError,
    display_name_only,
    participant_name_id,
)
from src.catalog import CatalogError, load_catalog
from src.event_store import EventStoreError, create_event_store
from src.research_export import build_research_export
from src.session_service import SessionError, SessionService
from src.settings import Settings


BASE_DIR = Path(__file__).resolve().parent
SETTINGS = Settings.from_env(BASE_DIR)
CATALOG_RESULT = load_catalog(SETTINGS)
CATALOG = CATALOG_RESULT.catalog
STORE = create_event_store(SETTINGS)
SESSIONS = SessionService(
    catalog=CATALOG,
    event_store=STORE,
    app_version=SETTINGS.app_version,
    content_revision=(
        SETTINGS.content_revision
        if not CATALOG_RESULT.is_demo
        else "demo-2.0"
    ),
)
ROME = ZoneInfo("Europe/Rome")


try:
    import spaces
except ImportError:  # pragma: no cover - used only outside Hugging Face ZeroGPU
    class _SpacesFallback:
        @staticmethod
        def GPU(*args: Any, **kwargs: Any):
            del args, kwargs

            def decorator(function):
                return function

            return decorator

    spaces = _SpacesFallback()


@spaces.GPU(duration=1)
def zero_gpu_probe() -> str:
    """Declarative ZeroGPU probe required by the configured Space hardware."""
    return "FamiliarizzApp è pronta."


CSS = """
:root {
  --fapp-ink: #16322f;
  --fapp-muted: #58716d;
  --fapp-paper: #fbfdfb;
  --fapp-mint: #dff4ec;
  --fapp-teal: #167c70;
  --fapp-coral: #df6b57;
  --fapp-line: #cfe2dc;
  --fapp-first: #2e7d32;
  --fapp-second: #c8e6c9;
  --fapp-third: #ffe69c;
  --fapp-unresolved: #f8d7da;
  --fapp-unseen: #e9ecef;
  --fapp-reception: #3b57ed;
  --fapp-production: #f13312;
  --fapp-interaction: #50139c;
  --fapp-mediation: #ff8c27;
  --fapp-linguistic: #31b3d2;
  --fapp-sociolinguistic: #54c900;
  --fapp-pragmatic: #ff0060;
  --fapp-taxonomy: #d1c29f;
}
.gradio-container {
  box-sizing: border-box;
  width: 100% !important;
  min-width: 0 !important;
  max-width: 1180px !important;
  margin: 0 auto !important;
  color: var(--fapp-ink);
}
.hero {
  padding: 1.6rem 1.4rem;
  border-radius: 1.25rem;
  background:
    radial-gradient(circle at 88% 10%, rgba(255,255,255,.9) 0 6%, transparent 7%),
    linear-gradient(135deg, #dff4ec 0%, #f9f4dd 100%);
  border: 1px solid var(--fapp-line);
  color: var(--fapp-ink) !important;
  margin-bottom: 1rem;
}
.hero-kicker {
  color: var(--fapp-teal) !important;
  font-weight: 750;
  letter-spacing: .08em;
  text-transform: uppercase;
  font-size: .78rem;
}
.hero h1 {
  margin: .25rem 0 .35rem;
  color: var(--fapp-ink) !important;
  font-size: clamp(2rem, 6vw, 3.25rem);
}
.hero p {
  margin: 0;
  color: var(--fapp-muted) !important;
  max-width: 48rem;
}
.descriptor-card {
  border: 1px solid var(--fapp-line);
  border-left: 6px solid var(--fapp-teal);
  border-radius: 1rem;
  padding: 1.15rem 1.2rem;
  background: var(--fapp-paper) !important;
  color: var(--fapp-ink) !important;
  font-size: 1.08rem;
  line-height: 1.65;
  overflow-wrap: anywhere;
  word-break: normal;
}
.descriptor-card * { color: inherit !important; }
.non-evaluation {
  color: var(--fapp-muted);
  font-size: .92rem;
}
.storage-banner {
  border-radius: .85rem;
  padding: .2rem .8rem;
}
button.primary {
  background: var(--fapp-teal) !important;
  border-color: var(--fapp-teal) !important;
}
.journey-overview {
  border: 1px solid var(--fapp-line);
  border-radius: 1rem;
  padding: 1rem;
  background: var(--fapp-paper);
  color: var(--fapp-ink) !important;
}
.journey-overview * { color: inherit; }
.journey-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: .65rem;
  margin: .8rem 0;
}
.journey-metric {
  border: 1px solid var(--fapp-line);
  border-radius: .8rem;
  padding: .75rem;
  background: #f4faf7;
}
.journey-metric strong { display: block; font-size: 1.25rem; }
.stacked-bar {
  display: flex;
  overflow: hidden;
  min-height: 1.15rem;
  border-radius: 999px;
  background: var(--fapp-unseen);
  border: 1px solid rgba(22,50,47,.18);
}
.stacked-bar span { min-width: 0; }
.stack-first { background: var(--fapp-first); }
.stack-second { background: var(--fapp-second); }
.stack-third { background: var(--fapp-third); }
.stack-unresolved { background: var(--fapp-unresolved); }
.stack-unseen { background: var(--fapp-unseen); }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: .4rem .9rem;
  margin-top: .65rem;
  font-size: .88rem;
}
.legend-item::before {
  content: "";
  display: inline-block;
  width: .8rem;
  height: .8rem;
  margin-right: .3rem;
  border-radius: .2rem;
  vertical-align: -.05rem;
  border: 1px solid rgba(22,50,47,.28);
}
.legend-first::before { background: var(--fapp-first); }
.legend-second::before { background: var(--fapp-second); }
.legend-third::before { background: var(--fapp-third); }
.legend-unresolved::before { background: var(--fapp-unresolved); }
.legend-unseen::before { background: var(--fapp-unseen); }
.trend-list { display: grid; gap: .6rem; margin-top: .75rem; }
.trend-row {
  display: grid;
  grid-template-columns: minmax(9rem, .45fr) minmax(8rem, 1fr) 4.2rem;
  gap: .6rem;
  align-items: center;
}
.trend-label { font-size: .88rem; }
.trend-track {
  height: .8rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--fapp-unseen);
  border: 1px solid rgba(22,50,47,.18);
}
.trend-fill { height: 100%; background: var(--fapp-first); }
.trend-value { font-weight: 750; text-align: right; }
.scale-map {
  display: grid;
  gap: .55rem;
  width: 100%;
}
.scale-descriptor {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(3.6rem, .16fr) minmax(0, 1fr) minmax(8rem, .25fr);
  gap: .75rem;
  align-items: center;
  border: 1px solid rgba(22,50,47,.28);
  border-radius: .85rem;
  padding: .85rem;
  text-align: left;
  cursor: pointer;
  transition: transform .12s ease, box-shadow .12s ease;
  overflow: hidden;
}
.scale-descriptor .scale-level,
.scale-descriptor .scale-text,
.scale-descriptor .scale-result,
.scale-descriptor .scale-when {
  color: inherit !important;
}
.scale-descriptor:hover,
.scale-descriptor:focus-visible {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(22,50,47,.18);
  outline: 3px solid rgba(22,124,112,.28);
  outline-offset: 2px;
}
.scale-level {
  font-weight: 800;
  font-size: 1.05rem;
}
.scale-text { line-height: 1.45; }
.scale-result { text-align: right; font-weight: 720; }
.scale-when {
  display: block;
  margin-top: .2rem;
  font-size: .82rem;
  font-weight: 500;
}
.status-first { background: var(--fapp-first); color: #fff; }
.status-second { background: var(--fapp-second); color: #102d1d; }
.status-third { background: var(--fapp-third); color: #332700; }
.status-unresolved { background: var(--fapp-unresolved); color: #481319; }
.status-unseen { background: var(--fapp-unseen); color: #263238; }
.taxonomy-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(155px, 1fr));
  gap: .75rem;
  align-items: start;
  overflow-x: auto;
  padding: .25rem 0 .8rem;
  scrollbar-width: thin;
}
.taxonomy-column {
  display: grid;
  gap: .6rem;
  min-width: 155px;
}
.taxonomy-title,
.taxonomy-item {
  border: 0;
  border-radius: .9rem;
  padding: .8rem .6rem;
  text-align: center;
  font-weight: 750;
  line-height: 1.2;
}
.taxonomy-title {
  min-height: 4.3rem;
  display: grid;
  place-items: center;
  background: var(--fapp-taxonomy) !important;
  color: #0f1720 !important;
}
.taxonomy-item {
  min-height: 3.8rem;
  color: #fff !important;
  cursor: pointer;
  border: 1px solid rgba(15, 23, 32, .08) !important;
  box-shadow: 0 3px 8px rgba(15, 23, 32, .12);
}
.taxonomy-item * { color: inherit !important; }
.taxonomy-item:focus-visible {
  outline: 3px solid rgba(22,124,112,.35);
  outline-offset: 2px;
}
.taxonomy-item[disabled] {
  cursor: not-allowed;
  opacity: .34 !important;
  filter: saturate(.72);
}
.tax-reception { background: var(--fapp-reception) !important; }
.tax-production { background: var(--fapp-production) !important; }
.tax-interaction { background: var(--fapp-interaction) !important; }
.tax-mediation { background: var(--fapp-mediation) !important; }
.tax-linguistic { background: var(--fapp-linguistic) !important; }
.tax-sociolinguistic { background: var(--fapp-sociolinguistic) !important; }
.tax-pragmatic { background: var(--fapp-pragmatic) !important; }
.tax-neutral {
  background: #e9e4da !important;
  color: #263238 !important;
}
.availability {
  display: block;
  margin-top: .25rem;
  font-size: .7rem;
  font-weight: 600;
}
.scale-selector {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: .75rem;
}
.scale-branch {
  border-left: 2px solid rgba(59,87,237,.25);
  padding-left: .65rem;
}
.scale-branch h4 {
  margin: 0 0 .5rem;
  color: var(--fapp-ink) !important;
}
.scale-choice-button {
  width: 100%;
  margin: .25rem 0;
  border: 0;
  border-radius: .75rem;
  padding: .75rem;
  background: var(--fapp-reception) !important;
  color: #fff !important;
  font-weight: 700;
  cursor: pointer;
}
.scale-choice-button * { color: inherit !important; }
.scale-choice-button:hover,
.scale-choice-button:focus-visible {
  filter: brightness(.92);
  outline: 3px solid rgba(59,87,237,.25);
  outline-offset: 2px;
}
.taxonomy-intro {
  margin-top: .35rem;
}
.researcher-link {
  display: inline-flex;
  margin-top: 1.5rem;
  padding: .75rem 1rem;
  border: 1px solid var(--fapp-line);
  border-radius: .75rem;
  color: var(--fapp-teal) !important;
  background: var(--fapp-paper) !important;
  font-weight: 720;
  text-decoration: none !important;
}
@media (prefers-color-scheme: dark) {
  .gradio-container {
    color: #f1f5f9 !important;
  }
  .journey-overview,
  .descriptor-card,
  .scale-branch,
  .researcher-link {
    color: var(--fapp-ink) !important;
  }
  .journey-metric { color: var(--fapp-ink) !important; }
  .taxonomy-title { color: #0f1720 !important; }
  .taxonomy-item { color: #fff !important; }
  .tax-neutral { color: #263238 !important; }
  .scale-choice-button { color: #fff !important; }
}
@media (max-width: 720px) {
  .gradio-container { padding: .65rem !important; }
  .hero { padding: 1.15rem 1rem; }
  .descriptor-card {
    padding: 1rem;
    font-size: 1rem;
    line-height: 1.52;
  }
  .scale-descriptor {
    grid-template-columns: 3rem minmax(0, 1fr);
    gap: .5rem;
    padding: .8rem;
  }
  .scale-text {
    min-width: 0;
    font-size: .95rem;
    line-height: 1.42;
    overflow-wrap: anywhere;
  }
  .scale-result {
    grid-column: 2;
    text-align: left;
    font-size: .88rem;
  }
  .trend-row {
    grid-template-columns: minmax(0, 1fr) 3.8rem;
  }
  .trend-track { grid-column: 1 / -1; grid-row: 2; }
  .taxonomy-grid {
    grid-template-columns: repeat(5, minmax(165px, 74vw));
    scroll-snap-type: x proximity;
    padding-bottom: 1rem;
  }
  .taxonomy-column { scroll-snap-align: start; }
  .taxonomy-title { min-height: 4.8rem; }
  .taxonomy-item { min-height: 4.15rem; }
  .scale-selector { grid-template-columns: 1fr; }
}
"""

THEME = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="orange",
    neutral_hue="slate",
)

MAP_TEMPLATE = """
<div class="scale-map" role="list" aria-label="Mappa dei descrittori">
{{#each value}}
  <button type="button"
          class="scale-descriptor status-{{status}}"
          data-descriptor-id="{{descriptor_id}}"
          aria-label="{{level}}. {{status_label}}. Apri il dettaglio"
          role="listitem">
    <span class="scale-level">{{level}}</span>
    <span class="scale-text">{{text}}</span>
    <span class="scale-result">
      {{status_label}}
      {{#if when}}<span class="scale-when">{{when}}</span>{{/if}}
    </span>
  </button>
{{else}}
  <p>Nessun descrittore corrisponde al filtro selezionato.</p>
{{/each}}
</div>
"""

MAP_JS = """
const bindMap = () => {
  element.querySelectorAll('.scale-descriptor').forEach((button) => {
    if (button.dataset.bound === '1') return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => {
      trigger('click', {descriptor_id: button.dataset.descriptorId});
    });
  });
};
bindMap();
watch('value', bindMap);
"""

TAXONOMY_TEMPLATE = """
<div class="taxonomy-grid" aria-label="Quadro delle categorie">
{{#each value}}
  <section class="taxonomy-column">
    <div class="taxonomy-title">{{title}}</div>
    {{#each items}}
      <button type="button"
              class="taxonomy-item tax-{{color}}"
              data-schema="{{schema}}"
              data-modality="{{modality}}"
              {{#unless available}}disabled{{/unless}}>
        {{label}}
        <span class="availability">
          {{#if available}}Disponibile{{else}}Non ancora disponibile{{/if}}
        </span>
      </button>
    {{/each}}
  </section>
{{/each}}
</div>
"""

TAXONOMY_JS = """
const bindTaxonomy = () => {
  element.querySelectorAll('.taxonomy-item:not([disabled])').forEach((button) => {
    if (button.dataset.bound === '1') return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => {
      trigger('click', {
        schema: button.dataset.schema,
        modality: button.dataset.modality
      });
    });
  });
};
bindTaxonomy();
watch('value', bindTaxonomy);
"""

SCALE_SELECTOR_TEMPLATE = """
<div class="scale-selector" aria-label="Scale disponibili">
{{#each value}}
  <section class="scale-branch">
    <h4>{{activity}}</h4>
    {{#each scales}}
      <button type="button"
              class="scale-choice-button"
              data-schema="{{schema}}"
              data-modality="{{modality}}"
              data-activity="{{activity}}"
              data-scale="{{scale}}">
        {{scale}}
      </button>
    {{/each}}
  </section>
{{else}}
  <p>Seleziona una categoria disponibile nella mappa.</p>
{{/each}}
</div>
"""

SCALE_SELECTOR_JS = """
const bindScales = () => {
  element.querySelectorAll('.scale-choice-button').forEach((button) => {
    if (button.dataset.bound === '1') return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => {
      trigger('click', {
        schema: button.dataset.schema,
        modality: button.dataset.modality,
        activity: button.dataset.activity,
        scale: button.dataset.scale
      });
    });
  });
};
bindScales();
watch('value', bindScales);
"""


def _empty_ui_state() -> dict[str, Any]:
    return {
        "participant_id": "",
        "display_name": "",
        "session": None,
        "summary_outcome_filter": "all",
        "summary_level_filter": "all",
    }


def _empty_browser_identity() -> dict[str, str]:
    return {"name": ""}


def _storage_banner() -> str:
    catalog_note = (
        (
            "catalogo dimostrativo 2.0 con tre scale di ricezione; "
            "i feedback editoriali sono ancora provvisori"
        )
        if CATALOG_RESULT.is_demo
        else f"catalogo `{CATALOG_RESULT.source_label}`"
    )
    if SETTINGS.storage_mode == "huggingface":
        return (
            f"🟢 **Modalità pilot:** {catalog_note}; percorso ed eventi vengono "
            "salvati nel Dataset privato configurato."
        )
    if SETTINGS.storage_mode == "local":
        return (
            f"🔵 **Sviluppo locale:** {catalog_note}; i dati restano soltanto "
            "nella cartella locale ignorata da Git."
        )
    return (
        f"🟠 **Modalità dimostrativa:** {catalog_note}; i dati sono temporanei "
        "e possono sparire al riavvio. Non usare questa modalità per la ricerca."
    )


def _first_path_values() -> tuple[list[str], str, str, str, str]:
    schemas = CATALOG.choices("schema")
    schema = schemas[0]
    modality = CATALOG.choices("modality", schema=schema)[0]
    activity = CATALOG.choices(
        "activity", schema=schema, modality=modality
    )[0]
    scale = CATALOG.choices(
        "scale", schema=schema, modality=modality, activity=activity
    )[0]
    return schemas, schema, modality, activity, scale


def _path_value(path: tuple[str, str, str, str]) -> str:
    return json.dumps(list(path), ensure_ascii=False)


def _decode_path(value: str | None) -> tuple[str, str, str, str] | None:
    if not value:
        return None
    try:
        parts = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parts, list) or len(parts) != 4:
        return None
    return tuple(str(part) for part in parts)  # type: ignore[return-value]


def _catalog_paths() -> list[tuple[str, str, str, str]]:
    paths: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in CATALOG.all():
        path = (
            item["schema"],
            item["modality"],
            item["activity"],
            item["scale"],
        )
        if path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def _scale_choices() -> list[tuple[str, str]]:
    return [
        (
            f"{path[1]} · {path[2]} · {path[3]}",
            _path_value(path),
        )
        for path in _catalog_paths()
    ]


def _taxonomy_data() -> list[dict[str, Any]]:
    available = {
        (item["schema"].casefold(), item["modality"].casefold())
        for item in CATALOG.all()
    }

    def present(schema_terms: tuple[str, ...], modality: str) -> bool:
        modality_fold = modality.casefold()
        return any(
            any(term in schema for term in schema_terms)
            and stored_modality == modality_fold
            for schema, stored_modality in available
        )

    def actual_schema(schema_terms: tuple[str, ...], fallback: str) -> str:
        for item in CATALOG.all():
            if any(
                term in item["schema"].casefold() for term in schema_terms
            ):
                return item["schema"]
        return fallback

    columns = [
        {
            "title": "Competenza generale",
            "items": [
                {
                    "label": label,
                    "color": "neutral",
                    "schema": "Competenza generale",
                    "modality": label,
                    "available": False,
                }
                for label in ("Sapere", "Saper fare", "Saper essere", "Saper apprendere")
            ],
        },
        {
            "title": "Competenze linguistico-comunicative",
            "items": [
                {
                    "label": label,
                    "color": color,
                    "schema": actual_schema(
                        ("competenze linguistico",),
                        "Competenze linguistico-comunicative",
                    ),
                    "modality": label,
                    "available": present(("competenze linguistico",), label),
                }
                for label, color in (
                    ("Linguistica", "linguistic"),
                    ("Sociolinguistica", "sociolinguistic"),
                    ("Pragmatica", "pragmatic"),
                )
            ],
        },
        {
            "title": "Competenze nelle lingue dei segni",
            "items": [
                {
                    "label": label,
                    "color": color,
                    "schema": actual_schema(
                        ("lingua dei segni", "lingue dei segni"),
                        "Competenze nelle lingue dei segni",
                    ),
                    "modality": label,
                    "available": present(
                        ("lingua dei segni", "lingue dei segni"), label
                    ),
                }
                for label, color in (
                    ("Linguistica", "linguistic"),
                    ("Sociolinguistica", "sociolinguistic"),
                    ("Pragmatica", "pragmatic"),
                )
            ],
        },
        {
            "title": "Attività linguistico-comunicative",
            "items": [
                {
                    "label": label,
                    "color": color,
                    "schema": actual_schema(
                        ("attività linguistico",),
                        "Attività linguistico-comunicative",
                    ),
                    "modality": label,
                    "available": (
                        label != "Mediazione"
                        and present(("attività linguistico",), label)
                    ),
                }
                for label, color in (
                    ("Ricezione", "reception"),
                    ("Produzione", "production"),
                    ("Interazione", "interaction"),
                    ("Mediazione", "mediation"),
                )
            ],
        },
        {
            "title": "Strategie linguistico-comunicative",
            "items": [
                {
                    "label": label,
                    "color": color,
                    "schema": actual_schema(
                        ("strategie linguistico",),
                        "Strategie linguistico-comunicative",
                    ),
                    "modality": label,
                    "available": (
                        label != "Mediazione"
                        and present(("strategie linguistico",), label)
                    ),
                }
                for label, color in (
                    ("Ricezione", "reception"),
                    ("Produzione", "production"),
                    ("Interazione", "interaction"),
                    ("Mediazione", "mediation"),
                )
            ],
        },
    ]
    return columns


def _scale_selector_data(schema: str, modality: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in CATALOG.all():
        if item["schema"] == schema and item["modality"] == modality:
            if item["scale"] not in grouped[item["activity"]]:
                grouped[item["activity"]].append(item["scale"])
    return [
        {
            "activity": activity,
            "scales": [
                {
                    "schema": schema,
                    "modality": modality,
                    "activity": activity,
                    "scale": scale,
                }
                for scale in scales
            ],
        }
        for activity, scales in grouped.items()
    ]


def _progress_html(
    title: str,
    counts: dict[str, int] | Counter[str],
    total: int,
    *,
    primary_count: int,
    primary_label: str,
    subtitle: str,
) -> str:
    safe_total = max(total, 0)
    first_rate = primary_count / safe_total * 100 if safe_total else 0.0
    segments = []
    for key in ("first", "second", "third", "unresolved", "unseen"):
        count = int(counts.get(key, 0))
        width = count / safe_total * 100 if safe_total else 0
        segments.append(
            f'<span class="stack-{key}" style="width:{width:.4f}%" '
            f'title="{html.escape(OUTCOME_LABELS[key])}: {count}"></span>'
        )
    return (
        '<section class="journey-overview">'
        f"<h3>{html.escape(title)}</h3>"
        f"<p>{html.escape(subtitle)}</p>"
        '<div class="journey-metrics">'
        f'<div class="journey-metric"><strong>{first_rate:.1f}%</strong>'
        f"{html.escape(primary_label)} · {primary_count} su {safe_total}</div>"
        f'<div class="journey-metric"><strong>{safe_total}</strong>'
        "descrittori considerati</div>"
        "</div>"
        f'<div class="stacked-bar" aria-label="{html.escape(primary_label)}">'
        + "".join(segments)
        + "</div>"
        + _legend_html(counts)
        + "</section>"
    )


def _legend_html(counts: dict[str, int] | Counter[str]) -> str:
    return (
        '<div class="legend">'
        + "".join(
            f'<span class="legend-item legend-{key}">'
            f"{html.escape(OUTCOME_LABELS[key])}: {int(counts.get(key, 0))}</span>"
            for key in ("first", "second", "third", "unresolved", "unseen")
        )
        + "</div>"
    )


def _scale_progress_html(
    events: list[dict[str, Any]],
    path: tuple[str, str, str, str],
) -> str:
    descriptors = CATALOG.for_scale(*path)
    descriptor_ids = {item["descriptor_id"] for item in descriptors}
    latest = {
        record["descriptor_id"]: record
        for record in descriptor_history(events, CATALOG)
        if record["descriptor_id"] in descriptor_ids
    }
    counts = Counter(record["outcome"] for record in latest.values())
    counts["unseen"] = max(len(descriptors) - len(latest), 0)
    return _progress_html(
        f"Percorso sulla scala · {path[3]}",
        counts,
        len(descriptors),
        primary_count=counts["first"],
        primary_label="descrittori attualmente riconosciuti senza suggerimenti",
        subtitle=(
            "Conta l’esito più recente di ciascun descrittore della scala. "
            "Il 100% si raggiunge quando tutti risultano riconosciuti al primo "
            "tentativo nell’incontro più recente."
        ),
    )


def _session_trend_html(sessions: list[dict[str, Any]]) -> str:
    completed = [
        session for session in reversed(sessions)
        if session["status"] == "completed"
    ][-10:]
    if not completed:
        return ""
    rows = []
    for session in completed:
        rate = float(session["first_attempt_rate"])
        label = (
            f"{relative_timestamp(session['completed_at'])} · "
            f"{session['scale']}"
        )
        rows.append(
            '<div class="trend-row">'
            f'<span class="trend-label">{html.escape(label)}</span>'
            '<span class="trend-track">'
            f'<span class="trend-fill" style="display:block;width:{rate:.4f}%">'
            "</span></span>"
            f'<span class="trend-value">{rate:.1f}%</span>'
            "</div>"
        )
    return (
        '<section class="journey-overview"><h3>Andamento verso l’autonomia</h3>'
        "<p>Percentuale riconosciuta al primo tentativo in ciascuna sessione "
        "completata. Scale diverse possono avere difficoltà diverse.</p>"
        '<div class="trend-list">'
        + "".join(rows)
        + "</div></section>"
    )


def _personal_view(
    participant: str,
    selected_path_value: str | None = None,
    outcome_filter: str = "all",
):
    events = STORE.list_events(participant)
    overview = participant_overview(events, CATALOG)
    all_paths = _catalog_paths()
    sessions = session_records(events, CATALOG)
    latest_path = None
    if sessions:
        latest = sessions[0]
        latest_path = (
            latest["schema"],
            latest["modality"],
            latest["activity"],
            latest["scale"],
        )
    path = _decode_path(selected_path_value) or latest_path or all_paths[0]
    path_value = _path_value(path)
    rows = scale_map(
        CATALOG, events, path, outcome_filter=outcome_filter
    )
    scale_progress = _scale_progress_html(events, path)
    latest_counts = Counter(
        record["outcome"]
        for record in {
            item["descriptor_id"]: item
            for item in descriptor_history(events, CATALOG)
        }.values()
    )
    latest_counts["unseen"] = max(
        overview["descriptors_available"]
        - overview["descriptors_encountered"],
        0,
    )
    overview_html = _progress_html(
        "Il mio percorso complessivo",
        latest_counts,
        overview["descriptors_available"],
        primary_count=overview["latest_first_count"],
        primary_label="riconoscimento senza suggerimenti",
        subtitle=(
            "Il colore riporta l’esito più recente di ogni descrittore. "
            "Non è un voto e non confronta il percorso con quello dei colleghi."
        ),
    )
    overview_html += _session_trend_html(sessions)
    session_rows = [
        [
            relative_timestamp(session["last_activity_at"]),
            session["scale"],
            session["status_label"],
            (
                f"{session['descriptors_completed']}/"
                f"{session['descriptors_planned']}"
            ),
            (
                f"{session['first_attempt_rate']:.1f}% "
                f"({session['first']}/{session['descriptors_completed']})"
                if session["descriptors_completed"]
                else "—"
            ),
        ]
        for session in sessions
    ]
    incomplete = SESSIONS.incomplete_sessions(participant)
    resume_choices = [
        (session["label"], session["session_id"]) for session in incomplete
    ]
    return (
        overview_html,
        gr.Dropdown(
            choices=_scale_choices(),
            value=path_value,
            label="Scala da esplorare",
        ),
        scale_progress,
        rows,
        session_rows,
        gr.Dropdown(
            choices=resume_choices,
            value=resume_choices[0][1] if resume_choices else None,
            interactive=bool(resume_choices),
            label="Sessione da riprendere",
        ),
    )


def prefill_identity(saved: dict[str, str] | None):
    saved = saved or {}
    return saved.get("name", "")


def identify_participant(
    name: str,
    consent: bool,
    state: dict[str, Any] | None,
):
    state = state or _empty_ui_state()
    hidden_personal = (
        "",
        gr.Dropdown(choices=[], value=None),
        "",
        [],
        [],
        gr.Dropdown(choices=[], value=None),
    )
    if not consent:
        return (
            state,
            _empty_browser_identity(),
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            *hidden_personal,
            "",
            "Devi confermare di aver letto l’informativa dimostrativa.",
        )
    try:
        shown_name = display_name_only(name)
        identifier = participant_name_id(
            name, SETTINGS.effective_hash_salt
        )
        STORE.register_participant(
            identifier,
            shown_name,
            name_lookup_hash=identifier,
        )
        SESSIONS.record_consent(identifier, SETTINGS.consent_version)
        SESSIONS.record_participant_access(identifier, "name_only")
        personal = _personal_view(identifier)
    except (IdentityError, EventStoreError) as exc:
        return (
            state,
            _empty_browser_identity(),
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            *hidden_personal,
            "",
            f"⚠️ {exc}",
        )

    updated = {
        **_empty_ui_state(),
        "participant_id": identifier,
        "display_name": shown_name,
    }
    browser_identity = {
        "name": name.strip(),
    }
    return (
        updated,
        browser_identity,
        gr.update(visible=False),
        gr.update(visible=True),
        f"## Ciao, {shown_name}",
        *personal,
        "",
        "",
    )


def update_personal_path(
    state: dict[str, Any], path_value: str, outcome_filter: str
):
    if not state.get("participant_id"):
        return "", [], ""
    try:
        path = _decode_path(path_value)
        if not path:
            return "", [], "Seleziona una scala."
        events = STORE.list_events(state["participant_id"])
        rows = scale_map(
            CATALOG,
            events,
            path,
            outcome_filter=outcome_filter,
        )
        return _scale_progress_html(events, path), rows, ""
    except (EventStoreError, CatalogError) as exc:
        return "", [], f"⚠️ Percorso non disponibile: {exc}"


def _event_descriptor_id(evt: gr.EventData) -> str:
    return str(getattr(evt, "descriptor_id", "") or "")


def personal_descriptor_click(state: dict[str, Any], evt: gr.EventData):
    descriptor_id = _event_descriptor_id(evt)
    if not descriptor_id or not state.get("participant_id"):
        return ""
    details = descriptor_details(
        descriptor_id,
        STORE.list_events(state["participant_id"]),
        CATALOG,
        user_facing_time=True,
    )
    return _descriptor_detail_markdown(details, researcher=False)


def _descriptor_detail_markdown(
    details: dict[str, Any], *, researcher: bool
) -> str:
    descriptor = details["descriptor"]
    history = details["history"]
    formatter = exact_timestamp if researcher else relative_timestamp
    lines = [
        f"### {descriptor.get('correct_level', '—')} · "
        f"{descriptor.get('scale', 'Descrittore')}",
        "",
        f"> {descriptor.get('descriptor_text', 'Testo non disponibile')}",
    ]
    if not history:
        lines.extend(["", "**Non ancora incontrato.**"])
        return "\n".join(lines)
    lines.extend(["", "#### Cronologia"])
    for record in reversed(history):
        lines.extend(
            [
                "",
                f"- **{formatter(record['occurred_at'])} — "
                f"{record['outcome_label']}**",
                f"  - Risposte: `{record['attempts_text']}`",
                f"  - Livello corretto: **{record['level']}**",
                f"  - Esposizione numero: {record['exposure_number']}",
            ]
        )
        if researcher:
            lines.append(
                f"  - Distanza della prima risposta: "
                f"{record.get('first_response_distance', '—')}"
            )
    latest = history[-1]
    if latest.get("rationale"):
        lines.extend(["", "#### Motivazione", latest["rationale"]])
    return "\n".join(lines)


def navigation_click(evt: gr.EventData):
    schema = str(getattr(evt, "schema", "") or "")
    modality = str(getattr(evt, "modality", "") or "")
    activities = CATALOG.choices(
        "activity", schema=schema, modality=modality
    )
    activity = activities[0] if activities else None
    scales = CATALOG.choices(
        "scale", schema=schema, modality=modality, activity=activity
    )
    return (
        _scale_selector_data(schema, modality),
        gr.Dropdown(choices=CATALOG.choices("schema"), value=schema),
        gr.Dropdown(
            choices=CATALOG.choices("modality", schema=schema),
            value=modality,
        ),
        gr.Dropdown(choices=activities, value=activity),
        gr.Dropdown(choices=scales, value=scales[0] if scales else None),
        (
            f"Categoria selezionata: **{schema} → {modality}**. "
            "Ora scegli una scala nella mappa sottostante."
        ),
    )


def scale_selector_click(evt: gr.EventData):
    schema = str(getattr(evt, "schema", "") or "")
    modality = str(getattr(evt, "modality", "") or "")
    activity = str(getattr(evt, "activity", "") or "")
    scale = str(getattr(evt, "scale", "") or "")
    return (
        gr.Dropdown(choices=CATALOG.choices("schema"), value=schema),
        gr.Dropdown(
            choices=CATALOG.choices("modality", schema=schema),
            value=modality,
        ),
        gr.Dropdown(
            choices=CATALOG.choices(
                "activity", schema=schema, modality=modality
            ),
            value=activity,
        ),
        gr.Dropdown(
            choices=CATALOG.choices(
                "scale",
                schema=schema,
                modality=modality,
                activity=activity,
            ),
            value=scale,
        ),
        f"Scala selezionata: **{scale}**.",
    )


def update_schema(schema: str):
    modalities = CATALOG.choices("modality", schema=schema)
    modality = modalities[0] if modalities else None
    activities = CATALOG.choices(
        "activity", schema=schema, modality=modality
    )
    activity = activities[0] if activities else None
    scales = CATALOG.choices(
        "scale", schema=schema, modality=modality, activity=activity
    )
    return (
        gr.Dropdown(choices=modalities, value=modality),
        gr.Dropdown(choices=activities, value=activity),
        gr.Dropdown(choices=scales, value=scales[0] if scales else None),
        _scale_selector_data(schema, modality) if modality else [],
    )


def update_modality(schema: str, modality: str):
    activities = CATALOG.choices(
        "activity", schema=schema, modality=modality
    )
    activity = activities[0] if activities else None
    scales = CATALOG.choices(
        "scale", schema=schema, modality=modality, activity=activity
    )
    return (
        gr.Dropdown(choices=activities, value=activity),
        gr.Dropdown(choices=scales, value=scales[0] if scales else None),
        _scale_selector_data(schema, modality),
    )


def update_activity(schema: str, modality: str, activity: str):
    scales = CATALOG.choices(
        "scale", schema=schema, modality=modality, activity=activity
    )
    return gr.Dropdown(
        choices=scales,
        value=scales[0] if scales else None,
    )


def _exercise_view(session: dict[str, Any]):
    descriptor = SESSIONS.current_descriptor(session)
    total = len(session["descriptor_ids"])
    position = session["current_index"] + 1
    breadcrumb = (
        f"**{session['schema']}**  \n"
        f"{session['modality']} → {session['activity']} → {session['scale']}"
    )
    progress = (
        f"### Descrittore {position} di {total}\n\n"
        f"`{'●' * position}{'○' * (total - position)}`"
    )
    descriptor_text = (
        f'<div class="descriptor-card">'
        f'{html.escape(descriptor["descriptor_text"])}</div>'
    )
    finished = bool(session["descriptor_finished"])
    attempts_used = len(session["attempts"])
    attempt_label = (
        f"**Descrittore concluso in {attempts_used} "
        f"{'tentativo' if attempts_used == 1 else 'tentativi'}.**"
        if finished
        else f"**Tentativo {attempts_used + 1} di 3**"
    )

    feedback_parts: list[str] = []
    if finished and session.get("last_result"):
        result = session["last_result"]
        if result["is_correct"]:
            feedback_parts.append(
                f"✅ **Risposta corretta: {result['correct_level']}**"
            )
        else:
            feedback_parts.append(
                f"ℹ️ **Il livello corretto è {result['correct_level']}.**"
            )
    for index, text in enumerate(session.get("feedbacks", []), start=1):
        is_final = finished and index == len(session["feedbacks"])
        label = "Motivazione" if is_final else f"Suggerimento {index}"
        feedback_parts.append(f"#### {label}\n{text}")
    feedback = "\n\n".join(feedback_parts)
    levels = SESSIONS.available_levels(session)
    continue_label = (
        "Vedi il riepilogo"
        if position == total
        else "Descrittore successivo"
    )
    return (
        breadcrumb,
        progress,
        descriptor_text,
        gr.Radio(
            choices=levels,
            value=None,
            interactive=not finished,
            label="A quale livello appartiene?",
        ),
        attempt_label,
        feedback,
        gr.Button(
            "Conferma risposta",
            visible=not finished,
            interactive=not finished,
            variant="primary",
        ),
        gr.Button(
            continue_label,
            visible=finished,
            interactive=finished,
            variant="primary",
        ),
    )


def start_session(
    state: dict[str, Any],
    schema: str,
    modality: str,
    activity: str,
    scale: str,
):
    try:
        descriptors = CATALOG.for_scale(schema, modality, activity, scale)
        return _start_descriptors(state, descriptors)
    except (KeyError, SessionError, EventStoreError, CatalogError) as exc:
        return _exercise_error(
            state, f"⚠️ La sessione non è stata avviata: {exc}"
        )


def _start_descriptors(
    state: dict[str, Any], descriptors: list[dict[str, Any]]
):
    session = SESSIONS.start_session(
        participant_id=state["participant_id"],
        display_name=state["display_name"],
        descriptors=descriptors,
    )
    updated = dict(state)
    updated["session"] = session
    updated["summary_outcome_filter"] = "all"
    updated["summary_level_filter"] = "all"
    return (
        updated,
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(visible=False),
        *_exercise_view(session),
        "",
    )


def _exercise_error(state: dict[str, Any], message: str):
    return (
        state,
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        "",
        "",
        gr.Radio(choices=[]),
        "",
        "",
        gr.Button(visible=False),
        gr.Button(visible=False),
        message,
    )


def resume_session(state: dict[str, Any], session_id: str | None):
    if not session_id:
        return _exercise_error(
            state, "Seleziona una sessione incompleta."
        )
    try:
        session = SESSIONS.restore_session(
            state["participant_id"], state["display_name"], session_id
        )
        updated = dict(state)
        updated["session"] = session
        return (
            updated,
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            *_exercise_view(session),
            "",
        )
    except (SessionError, EventStoreError, CatalogError) as exc:
        return _exercise_error(state, f"⚠️ Sessione non ripresa: {exc}")


def submit_answer(state: dict[str, Any], selected_level: str | None):
    session = state.get("session")
    if not session:
        return (
            state,
            gr.Radio(choices=[]),
            "",
            "",
            gr.Button(visible=False),
            gr.Button(visible=False),
            "La sessione non è attiva.",
        )
    if not selected_level:
        view = _exercise_view(session)
        return (
            state,
            view[3],
            view[4],
            view[5],
            view[6],
            view[7],
            "Seleziona un livello prima di confermare.",
        )
    try:
        updated_session = SESSIONS.submit_answer(session, selected_level)
        updated = dict(state)
        updated["session"] = updated_session
        view = _exercise_view(updated_session)
        return (
            updated,
            view[3],
            view[4],
            view[5],
            view[6],
            view[7],
            "",
        )
    except (SessionError, EventStoreError, CatalogError) as exc:
        view = _exercise_view(session)
        return (
            state,
            view[3],
            view[4],
            view[5],
            view[6],
            view[7],
            "⚠️ Il dato non è stato confermato e il tentativo non è stato "
            f"consumato. Riprova. Dettaglio: {exc}",
        )


def _session_map(
    session: dict[str, Any],
    outcome_filter: str = "all",
    level_filter: str = "all",
) -> list[dict[str, Any]]:
    events = STORE.list_events(session["participant_id"])
    rows = scale_map(
        CATALOG,
        events,
        (
            session["schema"],
            session["modality"],
            session["activity"],
            session["scale"],
        ),
        session_id=session["session_id"],
        outcome_filter=outcome_filter,
    )
    if level_filter != "all":
        rows = [row for row in rows if row["level"] == level_filter]
    return rows


def _summary_components(session: dict[str, Any]):
    summary = SESSIONS.summary(session)
    counts = {
        "first": summary["correct_by_attempt"]["1"],
        "second": summary["correct_by_attempt"]["2"],
        "third": summary["correct_by_attempt"]["3"],
        "unresolved": summary["unresolved_after_three"],
        "unseen": 0,
    }
    total = summary["descriptors_completed"]
    stats = _progress_html(
        f"Sessione completata · {session['scale']}",
        counts,
        total,
        primary_count=counts["first"],
        primary_label="riconoscimento senza suggerimenti",
        subtitle=(
            "L’obiettivo è arrivare a riconoscere tutti i descrittori senza "
            "suggerimenti. Il riepilogo descrive questa sessione e non è una "
            "valutazione professionale."
        ),
    )
    button_updates = [
        gr.Button(
            f"{OUTCOME_LABELS[key]} · {counts[key]}",
            interactive=counts[key] > 0,
            visible=True,
        )
        for key in ("first", "second", "third", "unresolved")
    ]
    levels = SESSIONS.available_levels(session)
    focus_records = [
        record
        for record in session.get("completed_records", [])
        if record.get("resolved_on_attempt") != 1
    ]
    focus_choices = [
        (
            f"{CATALOG.get(record['descriptor_id'])['correct_level']} · "
            f"{CATALOG.get(record['descriptor_id'])['descriptor_text'][:90]}",
            record["descriptor_id"],
        )
        for record in focus_records
    ]
    return (
        stats,
        *button_updates,
        gr.Dropdown(
            choices=[("Tutti i livelli", "all"), *[(level, level) for level in levels]],
            value="all",
            label="Filtra per livello target",
        ),
        _session_map(session),
        gr.CheckboxGroup(
            choices=focus_choices,
            value=[value for _, value in focus_choices],
            label="Descrittori da ripetere",
            visible=bool(focus_choices),
        ),
        gr.Button(
            "Ripeti i descrittori selezionati",
            visible=bool(focus_choices),
            interactive=bool(focus_choices),
            variant="primary",
        ),
    )


def continue_session(state: dict[str, Any]):
    session = state.get("session")
    empty_summary = (
        "",
        gr.Button(visible=False),
        gr.Button(visible=False),
        gr.Button(visible=False),
        gr.Button(visible=False),
        gr.Dropdown(choices=[]),
        [],
        gr.CheckboxGroup(choices=[], visible=False),
        gr.Button(visible=False),
    )
    if not session:
        return (
            state,
            gr.update(visible=False),
            gr.update(visible=False),
            "",
            "",
            "",
            gr.Radio(choices=[]),
            "",
            "",
            gr.Button(visible=False),
            gr.Button(visible=False),
            *empty_summary,
            "La sessione non è attiva.",
        )
    try:
        updated_session = SESSIONS.advance(session)
        updated = dict(state)
        updated["session"] = updated_session
        if updated_session["session_finished"]:
            return (
                updated,
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                "",
                "",
                gr.Radio(choices=[]),
                "",
                "",
                gr.Button(visible=False),
                gr.Button(visible=False),
                *_summary_components(updated_session),
                "",
            )
        return (
            updated,
            gr.update(visible=True),
            gr.update(visible=False),
            *_exercise_view(updated_session),
            *empty_summary,
            "",
        )
    except (SessionError, EventStoreError, CatalogError) as exc:
        view = _exercise_view(session)
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            *view,
            *empty_summary,
            f"⚠️ Impossibile continuare: {exc}",
        )


def filter_summary_map(
    state: dict[str, Any],
    outcome_filter: str,
    level_filter: str,
):
    session = state.get("session")
    if not session:
        return state, [], ""
    updated = dict(state)
    updated["summary_outcome_filter"] = outcome_filter
    updated["summary_level_filter"] = level_filter or "all"
    return (
        updated,
        _session_map(
            session,
            outcome_filter=outcome_filter,
            level_filter=level_filter or "all",
        ),
        "",
    )


def filter_summary_level(
    state: dict[str, Any], level_filter: str
):
    return filter_summary_map(
        state,
        state.get("summary_outcome_filter", "all"),
        level_filter,
    )


def summary_descriptor_click(state: dict[str, Any], evt: gr.EventData):
    session = state.get("session")
    descriptor_id = _event_descriptor_id(evt)
    if not session or not descriptor_id:
        return ""
    details = descriptor_details(
        descriptor_id,
        STORE.list_events(session["participant_id"]),
        CATALOG,
        session_id=session["session_id"],
        user_facing_time=True,
    )
    return _descriptor_detail_markdown(details, researcher=False)


def repeat_selected_descriptors(
    state: dict[str, Any], descriptor_ids: list[str] | None
):
    if not descriptor_ids:
        return _exercise_error(
            state, "Seleziona almeno un descrittore da ripetere."
        )
    try:
        descriptors = [CATALOG.get(item_id) for item_id in descriptor_ids]
        return _start_descriptors(state, descriptors)
    except (CatalogError, SessionError, EventStoreError) as exc:
        return _exercise_error(
            state, f"⚠️ Ripetizione non avviata: {exc}"
        )


def back_to_dashboard(state: dict[str, Any]):
    try:
        personal = _personal_view(state["participant_id"])
        updated = dict(state)
        updated["session"] = None
        return (
            updated,
            gr.update(visible=True),
            gr.update(visible=False),
            *personal,
            "",
            "",
        )
    except (KeyError, EventStoreError, CatalogError) as exc:
        return (
            state,
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            gr.Dropdown(choices=[]),
            "",
            [],
            [],
            gr.Dropdown(choices=[]),
            "",
            f"⚠️ Percorso non aggiornato: {exc}",
        )


def logout():
    return (
        _empty_ui_state(),
        _empty_browser_identity(),
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        False,
        "",
    )


def _research_authorized(state: dict[str, Any] | None) -> bool:
    return bool(state and state.get("authorized"))


def _research_dataset():
    participants = STORE.list_participants()
    events = STORE.list_events()
    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_participant[str(event.get("participant_id_hash", ""))].append(event)
    return participants, events, by_participant


def _research_overview_rows(
    participants: list[dict[str, Any]],
    by_participant: dict[str, list[dict[str, Any]]],
):
    rows = []
    for participant in participants:
        participant_events = by_participant.get(
            participant["participant_id"], []
        )
        overview = participant_overview(participant_events, CATALOG)
        rows.append(
            [
                participant["display_name"],
                overview["sessions_started"],
                overview["sessions_completed"],
                overview["sessions_in_progress"],
                overview["descriptors_encountered"],
                f"{overview['latest_first_rate']:.1f}%",
                exact_timestamp(overview["last_activity_at"]),
            ]
        )
    return rows


def researcher_login(access_key: str):
    if not SETTINGS.researcher_access_key:
        return (
            {"authorized": False},
            gr.update(visible=False),
            "La panoramica è disattivata: configura `RESEARCHER_ACCESS_KEY` "
            "nei secret dello Space.",
            "",
            [],
            gr.Dropdown(choices=[], value=None),
            gr.Dropdown(choices=[], value="all"),
            None,
            [],
        )
    if not hmac.compare_digest(
        access_key or "", SETTINGS.researcher_access_key
    ):
        return (
            {"authorized": False},
            gr.update(visible=False),
            "Chiave non valida.",
            "",
            [],
            gr.Dropdown(choices=[], value=None),
            gr.Dropdown(choices=[], value="all"),
            None,
            [],
        )
    try:
        participants, events, by_participant = _research_dataset()
        issues = integrity_report(events, participants)
        archive = build_research_export(participants, events, CATALOG)
    except EventStoreError as exc:
        return (
            {"authorized": False},
            gr.update(visible=False),
            f"Archivio non disponibile: {exc}",
            "",
            [],
            gr.Dropdown(choices=[], value=None),
            gr.Dropdown(choices=[], value="all"),
            None,
            [],
        )
    participant_choices = [
        (item["display_name"], item["participant_id"]) for item in participants
    ]
    first_participant = participant_choices[0][1] if participant_choices else None
    global_html = _research_global_html(participants, events, issues)
    scale_choices = [("Tutte le scale", "all"), *_scale_choices()]
    issue_rows = [
        [item["severity"], item["scope"], item["message"]] for item in issues
    ]
    return (
        {"authorized": True},
        gr.update(visible=True),
        "Accesso autorizzato.",
        global_html,
        _research_overview_rows(participants, by_participant),
        gr.Dropdown(
            choices=participant_choices,
            value=first_participant,
            interactive=bool(participant_choices),
        ),
        gr.Dropdown(choices=scale_choices, value="all"),
        archive,
        issue_rows,
    )


def _research_global_html(
    participants: list[dict[str, Any]],
    events: list[dict[str, Any]],
    issues: list[dict[str, str]],
) -> str:
    sessions = sum(
        event.get("event_type") == "session_started" for event in events
    )
    completions = sum(
        event.get("event_type") == "descriptor_completed" for event in events
    )
    return (
        '<section class="journey-overview"><h3>Archivio della ricerca</h3>'
        '<div class="journey-metrics">'
        f'<div class="journey-metric"><strong>{len(participants)}</strong>'
        "partecipanti</div>"
        f'<div class="journey-metric"><strong>{sessions}</strong>'
        "sessioni avviate</div>"
        f'<div class="journey-metric"><strong>{completions}</strong>'
        "descrittori completati</div>"
        f'<div class="journey-metric"><strong>{len(events)}</strong>'
        "eventi immutabili</div>"
        f'<div class="journey-metric"><strong>{len(issues)}</strong>'
        "segnalazioni di integrità</div>"
        "</div></section>"
    )


def _parse_date_boundary(
    value: str | float | datetime | None, *, end: bool
) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (float, int)):
        parsed = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=ROME,
            hour=23 if end else 0,
            minute=59 if end else 0,
            second=59 if end else 0,
        )
    return parsed.astimezone(timezone.utc)


def _in_period(
    timestamp: str,
    start_value: str | float | datetime | None,
    end_value: str | float | datetime | None,
) -> bool:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    start = _parse_date_boundary(start_value, end=False)
    end = _parse_date_boundary(end_value, end=True)
    return (not start or parsed >= start) and (not end or parsed <= end)


def researcher_detail(
    research_state: dict[str, Any],
    participant: str | None,
    scale_value: str,
    date_from: str | float | datetime | None,
    date_to: str | float | datetime | None,
):
    if not _research_authorized(research_state):
        return "", [], [], [], "Accesso ricercatore non autorizzato."
    if not participant:
        return "", [], [], [], "Seleziona un partecipante."
    try:
        participant_record = STORE.get_participant(participant)
        all_events = STORE.list_events(participant)
    except EventStoreError as exc:
        return "", [], [], [], f"Archivio non disponibile: {exc}"
    if not participant_record:
        return "", [], [], [], "Partecipante non trovato."

    sessions = session_records(all_events, CATALOG)
    histories = descriptor_history(all_events, CATALOG)
    selected_path = _decode_path(scale_value) if scale_value != "all" else None
    if selected_path:
        sessions = [
            row
            for row in sessions
            if (
                row["schema"],
                row["modality"],
                row["activity"],
                row["scale"],
            )
            == selected_path
        ]
        histories = [
            row
            for row in histories
            if (
                row["schema"],
                row["modality"],
                row["activity"],
                row["scale"],
            )
            == selected_path
        ]
    sessions = [
        row
        for row in sessions
        if _in_period(row["started_at"], date_from, date_to)
    ]
    histories = [
        row
        for row in histories
        if _in_period(row["occurred_at"], date_from, date_to)
    ]
    session_ids = {row["session_id"] for row in sessions}
    filtered_events = [
        event
        for event in all_events
        if _in_period(event.get("occurred_at", ""), date_from, date_to)
        and (
            not selected_path
            or event.get("session_id") in session_ids
            or event.get("event_type")
            in {
                "consent_recorded",
                "participant_accessed",
            }
        )
    ]
    first_count = sum(row["outcome"] == "first" for row in histories)
    summary_html = _progress_html(
        f"Percorso di {participant_record['display_name']}",
        Counter(row["outcome"] for row in histories),
        len(histories),
        primary_count=first_count,
        primary_label="esiti al primo tentativo nel filtro",
        subtitle=(
            f"Profilo pseudonimo {participant[:10]}… · accesso tramite nome"
        ),
    )
    session_rows = [
        [
            row["session_id"],
            row["scale"],
            row["status_label"],
            exact_timestamp(row["started_at"]),
            exact_timestamp(row["completed_at"]),
            row["duration_seconds"],
            row["descriptors_completed"],
            row["first"],
            row["second"],
            row["third"],
            row["unresolved"],
            f"{row['first_attempt_rate']:.1f}%",
            row["content_revision"],
            row["app_version"],
        ]
        for row in sessions
    ]
    history_rows = [
        [
            exact_timestamp(row["occurred_at"]),
            row["session_id"],
            row["scale"],
            row["descriptor_id"],
            row["level"],
            row["attempts_text"],
            row["outcome_label"],
            row["first_response_distance"],
            row["exposure_number"],
            (
                round(row["response_time_ms"] / 1000, 2)
                if row.get("response_time_ms") is not None
                else None
            ),
            row["descriptor_text"],
        ]
        for row in sorted(histories, key=lambda item: item["occurred_at"], reverse=True)
    ]
    raw_rows = [
        [
            exact_timestamp(event.get("occurred_at")),
            event.get("event_type", ""),
            event.get("session_id", ""),
            event.get("descriptor_id", ""),
            event.get("attempt_number"),
            event.get("selected_level", ""),
            event.get("correct_level", ""),
            event.get("is_correct"),
            event.get("error_distance"),
            event.get("response_time_ms"),
            event.get("feedback_text") or event.get("rationale", ""),
            event.get("schema_version", ""),
            event.get("content_revision", ""),
            event.get("app_version", ""),
            event.get("event_id", ""),
        ]
        for event in sorted(
            filtered_events,
            key=lambda item: item.get("occurred_at", ""),
            reverse=True,
        )
    ]
    return summary_html, session_rows, history_rows, raw_rows, ""


def refresh_research_export(research_state: dict[str, Any]):
    if not _research_authorized(research_state):
        return None, "Accesso ricercatore non autorizzato."
    try:
        participants = STORE.list_participants()
        events = STORE.list_events()
        return build_research_export(participants, events, CATALOG), (
            "Esportazione aggiornata. Contiene CSV derivati, eventi JSONL "
            "originali, manifest e controllo d’integrità."
        )
    except EventStoreError as exc:
        return None, f"Esportazione non riuscita: {exc}"


def build_demo() -> gr.Blocks:
    schemas, schema, modality, activity, scale = _first_path_values()
    first_scale_selector = _scale_selector_data(schema, modality)

    with gr.Blocks(title="FamiliarizzApp") as demo:
        ui_state = gr.State(_empty_ui_state())
        browser_identity = gr.BrowserState(
            _empty_browser_identity(),
            storage_key="familiarizzapp-personal-name",
            secret=SETTINGS.effective_hash_salt,
        )
        gr.HTML(
            """
            <section class="hero">
              <div class="hero-kicker">Familiarizzazione CEFR</div>
              <h1>FamiliarizzApp</h1>
              <p>Esplora i descrittori, riconosci il livello e usa i feedback
              progressivi per affinare la tua lettura. Nessun voto, nessuna
              graduatoria.</p>
            </section>
            """
        )
        gr.Markdown(_storage_banner(), elem_classes="storage-banner")

        with gr.Group(visible=True) as selection_group:
            gr.Markdown(
                "## Scegli una nuova scala\n"
                "Le categorie mantengono i colori del quadro di riferimento. "
                "Quelle attenuate non sono ancora presenti nel catalogo usato.",
                elem_classes="taxonomy-intro",
            )
            taxonomy = gr.HTML(
                _taxonomy_data(),
                html_template=TAXONOMY_TEMPLATE,
                js_on_load=TAXONOMY_JS,
            )
            scale_selector = gr.HTML(
                first_scale_selector,
                html_template=SCALE_SELECTOR_TEMPLATE,
                js_on_load=SCALE_SELECTOR_JS,
            )
            path_selection_message = gr.Markdown()
            with gr.Accordion("Selezione testuale accessibile", open=False):
                schema_choice = gr.Dropdown(
                    choices=schemas,
                    value=schema,
                    label="Schema descrittivo",
                )
                modality_choice = gr.Dropdown(
                    choices=CATALOG.choices("modality", schema=schema),
                    value=modality,
                    label="Modalità di comunicazione",
                )
                activity_choice = gr.Dropdown(
                    choices=CATALOG.choices(
                        "activity", schema=schema, modality=modality
                    ),
                    value=activity,
                    label="Attività, strategia o competenza",
                )
                scale_choice = gr.Dropdown(
                    choices=CATALOG.choices(
                        "scale",
                        schema=schema,
                        modality=modality,
                        activity=activity,
                    ),
                    value=scale,
                    label="Scala",
                )

        with gr.Group(visible=True) as login_group:
            gr.Markdown(
                "## Apri il tuo percorso\n"
                "Per questo piccolo gruppo è sufficiente inserire il proprio "
                "nome. Usa sempre la stessa forma per ritrovare la cronologia."
            )
            name = gr.Textbox(
                label="Nome",
                placeholder="Es. Giulia",
                max_length=80,
            )
            consent = gr.Checkbox(
                label=(
                    "Confermo di aver letto l’informativa dimostrativa "
                    "e di voler proseguire."
                )
            )
            identify_button = gr.Button(
                "Continua con questo nome", variant="primary"
            )

        with gr.Group(visible=False) as dashboard_group:
            greeting = gr.Markdown()
            with gr.Row():
                start_button = gr.Button(
                    "Inizia la scala selezionata", variant="primary"
                )
                logout_button = gr.Button("Cambia nome")

            progress_dashboard = gr.HTML()
            gr.Markdown("### Esplora la tua mappa")
            with gr.Row():
                personal_scale_choice = gr.Dropdown(
                    choices=_scale_choices(),
                    label="Scala da esplorare",
                )
                personal_filter = gr.Radio(
                    choices=[
                        ("Mostra tutto", "all"),
                        ("Concentrati", "focus"),
                        ("Da rivedere", "unresolved"),
                        ("Mai incontrati", "unseen"),
                    ],
                    value="all",
                    label="Filtro",
                )
            personal_scale_summary = gr.HTML()
            personal_map = gr.HTML(
                [],
                html_template=MAP_TEMPLATE,
                js_on_load=MAP_JS,
            )
            personal_detail = gr.Markdown()
            with gr.Accordion("Sessioni precedenti", open=False):
                personal_sessions = gr.Dataframe(
                    headers=[
                        "Quando",
                        "Scala",
                        "Stato",
                        "Descrittori",
                        "Senza suggerimenti",
                    ],
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    show_search="filter",
                )
            with gr.Accordion("Riprendi una sessione", open=False):
                resume_choice = gr.Dropdown(
                    choices=[],
                    label="Sessione da riprendere",
                    interactive=False,
                )
                resume_button = gr.Button("Riprendi")

        with gr.Group(visible=False) as exercise_group:
            breadcrumb = gr.Markdown()
            exercise_progress = gr.Markdown()
            descriptor = gr.HTML()
            attempt_label = gr.Markdown()
            level_choice = gr.Radio(
                choices=[],
                label="A quale livello appartiene?",
            )
            feedback = gr.Markdown()
            with gr.Row():
                submit_button = gr.Button(
                    "Conferma risposta", variant="primary"
                )
                continue_button = gr.Button(
                    "Descrittore successivo",
                    visible=False,
                    variant="primary",
                )

        with gr.Group(visible=False) as summary_group:
            summary_stats = gr.HTML()
            gr.Markdown(
                "### Apri i descrittori per esito\n"
                "I numeri sono pulsanti: selezionandoli ritrovi i "
                "descrittori corrispondenti."
            )
            with gr.Row():
                first_summary_button = gr.Button("1° tentativo · 0")
                second_summary_button = gr.Button("2° tentativo · 0")
                third_summary_button = gr.Button("3° tentativo · 0")
                unresolved_summary_button = gr.Button("Da rivedere · 0")
            with gr.Row():
                summary_all_button = gr.Button("Mostra tutto")
                summary_focus_button = gr.Button("Concentrati")
                summary_level_filter = gr.Dropdown(
                    choices=[],
                    label="Livello target",
                )
            summary_map = gr.HTML(
                [],
                html_template=MAP_TEMPLATE,
                js_on_load=MAP_JS,
            )
            summary_detail = gr.Markdown()
            repeat_choices = gr.CheckboxGroup(
                choices=[],
                visible=False,
                label="Descrittori da ripetere",
            )
            repeat_button = gr.Button(
                "Ripeti i descrittori selezionati",
                visible=False,
                variant="primary",
            )
            dashboard_button = gr.Button(
                "Torna al mio percorso", variant="primary"
            )

        user_message = gr.Markdown()
        gr.HTML(
            '<a class="researcher-link" href="/ricercatore" target="_blank">'
            "Apri la panoramica del ricercatore in una pagina separata ↗</a>"
        )

        demo.load(
            prefill_identity,
            inputs=browser_identity,
            outputs=name,
        )
        identify_button.click(
            identify_participant,
            inputs=[name, consent, ui_state],
            outputs=[
                ui_state,
                browser_identity,
                login_group,
                dashboard_group,
                greeting,
                progress_dashboard,
                personal_scale_choice,
                personal_scale_summary,
                personal_map,
                personal_sessions,
                resume_choice,
                personal_detail,
                user_message,
            ],
        )
        personal_scale_choice.change(
            update_personal_path,
            inputs=[ui_state, personal_scale_choice, personal_filter],
            outputs=[
                personal_scale_summary,
                personal_map,
                personal_detail,
            ],
        )
        personal_filter.change(
            update_personal_path,
            inputs=[ui_state, personal_scale_choice, personal_filter],
            outputs=[
                personal_scale_summary,
                personal_map,
                personal_detail,
            ],
        )
        personal_map.click(
            personal_descriptor_click,
            inputs=ui_state,
            outputs=personal_detail,
        )
        taxonomy.click(
            navigation_click,
            outputs=[
                scale_selector,
                schema_choice,
                modality_choice,
                activity_choice,
                scale_choice,
                path_selection_message,
            ],
        )
        scale_selector.click(
            scale_selector_click,
            outputs=[
                schema_choice,
                modality_choice,
                activity_choice,
                scale_choice,
                path_selection_message,
            ],
        )
        schema_choice.change(
            update_schema,
            inputs=schema_choice,
            outputs=[
                modality_choice,
                activity_choice,
                scale_choice,
                scale_selector,
            ],
        )
        modality_choice.change(
            update_modality,
            inputs=[schema_choice, modality_choice],
            outputs=[activity_choice, scale_choice, scale_selector],
        )
        activity_choice.change(
            update_activity,
            inputs=[schema_choice, modality_choice, activity_choice],
            outputs=scale_choice,
        )

        exercise_outputs = [
            ui_state,
            dashboard_group,
            exercise_group,
            summary_group,
            breadcrumb,
            exercise_progress,
            descriptor,
            level_choice,
            attempt_label,
            feedback,
            submit_button,
            continue_button,
            user_message,
        ]
        start_button.click(
            start_session,
            inputs=[
                ui_state,
                schema_choice,
                modality_choice,
                activity_choice,
                scale_choice,
            ],
            outputs=exercise_outputs,
        ).then(lambda: gr.update(visible=False), outputs=selection_group)
        resume_button.click(
            resume_session,
            inputs=[ui_state, resume_choice],
            outputs=exercise_outputs,
        ).then(lambda: gr.update(visible=False), outputs=selection_group)
        submit_button.click(
            submit_answer,
            inputs=[ui_state, level_choice],
            outputs=[
                ui_state,
                level_choice,
                attempt_label,
                feedback,
                submit_button,
                continue_button,
                user_message,
            ],
        )
        continue_button.click(
            continue_session,
            inputs=ui_state,
            outputs=[
                ui_state,
                exercise_group,
                summary_group,
                breadcrumb,
                exercise_progress,
                descriptor,
                level_choice,
                attempt_label,
                feedback,
                submit_button,
                continue_button,
                summary_stats,
                first_summary_button,
                second_summary_button,
                third_summary_button,
                unresolved_summary_button,
                summary_level_filter,
                summary_map,
                repeat_choices,
                repeat_button,
                user_message,
            ],
        )

        def bind_summary_filter(button, outcome):
            button.click(
                lambda state, level: filter_summary_map(
                    state, outcome, level or "all"
                ),
                inputs=[ui_state, summary_level_filter],
                outputs=[ui_state, summary_map, summary_detail],
            )

        bind_summary_filter(first_summary_button, "first")
        bind_summary_filter(second_summary_button, "second")
        bind_summary_filter(third_summary_button, "third")
        bind_summary_filter(unresolved_summary_button, "unresolved")
        bind_summary_filter(summary_all_button, "all")
        bind_summary_filter(summary_focus_button, "focus")
        summary_level_filter.change(
            filter_summary_level,
            inputs=[ui_state, summary_level_filter],
            outputs=[ui_state, summary_map, summary_detail],
        )
        summary_map.click(
            summary_descriptor_click,
            inputs=ui_state,
            outputs=summary_detail,
        )
        repeat_button.click(
            repeat_selected_descriptors,
            inputs=[ui_state, repeat_choices],
            outputs=exercise_outputs,
        ).then(lambda: gr.update(visible=False), outputs=selection_group)
        dashboard_button.click(
            back_to_dashboard,
            inputs=ui_state,
            outputs=[
                ui_state,
                dashboard_group,
                summary_group,
                progress_dashboard,
                personal_scale_choice,
                personal_scale_summary,
                personal_map,
                personal_sessions,
                resume_choice,
                personal_detail,
                user_message,
            ],
        ).then(lambda: gr.update(visible=True), outputs=selection_group)
        logout_button.click(
            logout,
            outputs=[
                ui_state,
                browser_identity,
                login_group,
                dashboard_group,
                exercise_group,
                summary_group,
                name,
                consent,
                user_message,
            ],
        )

    with demo.route(
        "Panoramica ricercatore",
        "/ricercatore",
        show_in_navbar=False,
    ):
        researcher_state = gr.State({"authorized": False})
        gr.HTML(
            '<a class="researcher-link" href="/">← Torna a FamiliarizzApp</a>'
        )
        gr.HTML(
            """
            <section class="hero">
              <div class="hero-kicker">Area riservata</div>
              <h1>Panoramica ricercatore</h1>
              <p>Percorsi longitudinali, risposte, tempi, integrità ed
              esportazioni sono raccolti in questa pagina separata.</p>
            </section>
            """
        )
        gr.Markdown(
            "La chiave del ricercatore protegge i dati complessivi dei "
            "partecipanti e non viene richiesta a chi svolge gli esercizi."
        )
        researcher_key = gr.Textbox(
            label="Chiave ricercatore", type="password"
        )
        researcher_button = gr.Button("Apri panoramica", variant="primary")
        researcher_message = gr.Markdown()
        with gr.Group(visible=False) as researcher_content:
            researcher_global = gr.HTML()
            researcher_table = gr.Dataframe(
                headers=[
                    "Partecipante",
                    "Sessioni iniziate",
                    "Sessioni completate",
                    "Sessioni in corso",
                    "Descrittori incontrati",
                    "% attuale senza suggerimenti",
                    "Ultima attività",
                ],
                datatype=[
                    "str",
                    "number",
                    "number",
                    "number",
                    "number",
                    "str",
                    "str",
                ],
                interactive=False,
                wrap=True,
                show_search="filter",
            )
            gr.Markdown("### Percorso individuale")
            with gr.Row():
                researcher_participant = gr.Dropdown(
                    choices=[],
                    label="Partecipante",
                )
                researcher_scale = gr.Dropdown(
                    choices=[("Tutte le scale", "all")],
                    value="all",
                    label="Scala",
                )
            with gr.Row():
                researcher_from = gr.DateTime(
                    label="Dal giorno",
                    include_time=False,
                    type="string",
                    timezone="Europe/Rome",
                )
                researcher_to = gr.DateTime(
                    label="Al giorno",
                    include_time=False,
                    type="string",
                    timezone="Europe/Rome",
                )
                researcher_refresh = gr.Button("Applica filtri")
            researcher_personal_summary = gr.HTML()
            researcher_detail_message = gr.Markdown()
            with gr.Accordion("Sessioni", open=True):
                researcher_sessions = gr.Dataframe(
                    headers=[
                        "ID sessione",
                        "Scala",
                        "Stato",
                        "Inizio esatto",
                        "Fine esatta",
                        "Durata s",
                        "Completati",
                        "1°",
                        "2°",
                        "3°",
                        "Non risolti",
                        "% 1°",
                        "Revisione catalogo",
                        "Versione app",
                    ],
                    interactive=False,
                    wrap=True,
                    show_search="filter",
                )
            with gr.Accordion("Cronologia dei descrittori", open=True):
                researcher_descriptors = gr.Dataframe(
                    headers=[
                        "Quando",
                        "ID sessione",
                        "Scala",
                        "ID descrittore",
                        "Target",
                        "Risposte",
                        "Esito",
                        "Distanza iniziale",
                        "Esposizione n.",
                        "Tempo risposta s",
                        "Descrittore",
                    ],
                    interactive=False,
                    wrap=True,
                    show_search="filter",
                )
            with gr.Accordion("Registro completo degli eventi", open=False):
                researcher_events = gr.Dataframe(
                    headers=[
                        "Timestamp esatto",
                        "Tipo",
                        "Sessione",
                        "Descrittore",
                        "Tentativo",
                        "Scelta",
                        "Corretto",
                        "Esito",
                        "Distanza",
                        "Tempo ms",
                        "Feedback o motivazione",
                        "Schema dati",
                        "Revisione contenuti",
                        "Versione app",
                        "ID evento",
                    ],
                    interactive=False,
                    wrap=True,
                    show_search="filter",
                )
            with gr.Accordion("Integrità e backup", open=False):
                researcher_integrity = gr.Dataframe(
                    headers=["Gravità", "Ambito", "Messaggio"],
                    interactive=False,
                    wrap=True,
                )
                with gr.Row():
                    researcher_export = gr.DownloadButton(
                        "Scarica archivio completo"
                    )
                    researcher_export_refresh = gr.Button(
                        "Rigenera esportazione"
                    )
                researcher_export_message = gr.Markdown()

        researcher_button.click(
            researcher_login,
            inputs=researcher_key,
            outputs=[
                researcher_state,
                researcher_content,
                researcher_message,
                researcher_global,
                researcher_table,
                researcher_participant,
                researcher_scale,
                researcher_export,
                researcher_integrity,
            ],
        ).then(
            researcher_detail,
            inputs=[
                researcher_state,
                researcher_participant,
                researcher_scale,
                researcher_from,
                researcher_to,
            ],
            outputs=[
                researcher_personal_summary,
                researcher_sessions,
                researcher_descriptors,
                researcher_events,
                researcher_detail_message,
            ],
        )
        researcher_refresh.click(
            researcher_detail,
            inputs=[
                researcher_state,
                researcher_participant,
                researcher_scale,
                researcher_from,
                researcher_to,
            ],
            outputs=[
                researcher_personal_summary,
                researcher_sessions,
                researcher_descriptors,
                researcher_events,
                researcher_detail_message,
            ],
        )
        researcher_participant.change(
            researcher_detail,
            inputs=[
                researcher_state,
                researcher_participant,
                researcher_scale,
                researcher_from,
                researcher_to,
            ],
            outputs=[
                researcher_personal_summary,
                researcher_sessions,
                researcher_descriptors,
                researcher_events,
                researcher_detail_message,
            ],
        )
        researcher_export_refresh.click(
            refresh_research_export,
            inputs=researcher_state,
            outputs=[researcher_export, researcher_export_message],
        )

    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=8).launch(theme=THEME, css=CSS)
