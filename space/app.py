from __future__ import annotations

import hmac
from collections import defaultdict
from pathlib import Path
from typing import Any

import gradio as gr

from src.auth import IdentityError, display_name, participant_id
from src.catalog import CatalogError, load_catalog
from src.event_store import EventStoreError, create_event_store
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
        else "demo-1.0"
    ),
)


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
    return "Familiarizzap è pronta."


CSS = """
:root {
  --ink: #16322f;
  --muted: #58716d;
  --paper: #fbfdfb;
  --mint: #dff4ec;
  --teal: #167c70;
  --coral: #df6b57;
  --line: #cfe2dc;
}
.gradio-container {
  max-width: 1040px !important;
  margin: 0 auto !important;
  color: var(--ink);
}
.hero {
  padding: 1.6rem 1.4rem;
  border-radius: 1.25rem;
  background:
    radial-gradient(circle at 88% 10%, rgba(255,255,255,.9) 0 6%, transparent 7%),
    linear-gradient(135deg, #dff4ec 0%, #f9f4dd 100%);
  border: 1px solid var(--line);
  margin-bottom: 1rem;
}
.hero-kicker {
  color: var(--teal);
  font-weight: 750;
  letter-spacing: .08em;
  text-transform: uppercase;
  font-size: .78rem;
}
.hero h1 { margin: .25rem 0 .35rem; font-size: clamp(2rem, 6vw, 3.25rem); }
.hero p { margin: 0; color: var(--muted); max-width: 48rem; }
.descriptor-card {
  border: 1px solid var(--line);
  border-left: 6px solid var(--teal);
  border-radius: 1rem;
  padding: 1.15rem 1.2rem;
  background: var(--paper);
  font-size: 1.08rem;
  line-height: 1.65;
}
.non-evaluation {
  color: var(--muted);
  font-size: .92rem;
}
.storage-banner {
  border-radius: .85rem;
  padding: .2rem .8rem;
}
button.primary {
  background: var(--teal) !important;
  border-color: var(--teal) !important;
}
@media (max-width: 640px) {
  .gradio-container { padding: .65rem !important; }
  .hero { padding: 1.15rem 1rem; }
}
"""

THEME = gr.themes.Soft(
    primary_hue="teal",
    secondary_hue="orange",
    neutral_hue="slate",
)


def _empty_ui_state() -> dict[str, Any]:
    return {"participant_id": "", "display_name": "", "session": None}


def _storage_banner() -> str:
    catalog_note = (
        "catalogo dimostrativo originale"
        if CATALOG_RESULT.is_demo
        else f"catalogo `{CATALOG_RESULT.source_label}`"
    )
    if SETTINGS.storage_mode == "huggingface":
        return (
            f"🟢 **Modalità pilot:** {catalog_note}; gli eventi vengono salvati "
            "nel Dataset privato configurato."
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


def _dashboard(
    participant: str,
) -> tuple[str, list[tuple[str, str]]]:
    events = STORE.list_events(participant)
    starts = [
        event for event in events if event.get("event_type") == "session_started"
    ]
    completed = {
        event["session_id"]
        for event in events
        if event.get("event_type") == "session_completed"
    }
    descriptor_count = sum(
        event.get("event_type") == "descriptor_completed" for event in events
    )
    incomplete = SESSIONS.incomplete_sessions(participant)
    choices = [
        (session["label"], session["session_id"]) for session in incomplete
    ]
    total_scales = {
        (
            item["schema"],
            item["modality"],
            item["activity"],
            item["scale"],
        )
        for item in CATALOG.all()
    }
    markdown = (
        "### Il mio percorso\n\n"
        f"- **Scale disponibili:** {len(total_scales)}\n"
        f"- **Sessioni avviate:** {len(starts)}\n"
        f"- **Sessioni completate:** {len(completed)}\n"
        f"- **Descrittori incontrati:** {descriptor_count}\n\n"
        '<span class="non-evaluation">Questi dati descrivono il percorso svolto; '
        "non sono una valutazione professionale.</span>"
    )
    return markdown, choices


def identify_participant(
    first_name: str,
    last_name: str,
    consent: bool,
    state: dict[str, Any] | None,
):
    state = state or _empty_ui_state()
    if not consent:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            "",
            gr.Dropdown(choices=[], value=None),
            "Devi confermare di aver letto l’informativa dimostrativa.",
        )
    try:
        shown_name = display_name(first_name, last_name)
        identifier = participant_id(
            first_name, last_name, SETTINGS.effective_hash_salt
        )
        STORE.register_participant(identifier, shown_name)
        SESSIONS.record_consent(identifier, SETTINGS.consent_version)
        progress, resumes = _dashboard(identifier)
    except (IdentityError, EventStoreError) as exc:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            "",
            gr.Dropdown(choices=[], value=None),
            f"⚠️ {exc}",
        )

    updated = {
        "participant_id": identifier,
        "display_name": shown_name,
        "session": None,
    }
    return (
        updated,
        gr.update(visible=False),
        gr.update(visible=True),
        f"## Ciao, {shown_name}",
        progress,
        gr.Dropdown(
            choices=resumes,
            value=resumes[0][1] if resumes else None,
            interactive=bool(resumes),
            label="Sessione da riprendere",
        ),
        "",
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
        f'<div class="descriptor-card">{descriptor["descriptor_text"]}</div>'
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
        session = SESSIONS.start_session(
            participant_id=state["participant_id"],
            display_name=state["display_name"],
            descriptors=descriptors,
        )
        updated = dict(state)
        updated["session"] = session
        view = _exercise_view(session)
        return (
            updated,
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            *view,
            "",
        )
    except (KeyError, SessionError, EventStoreError, CatalogError) as exc:
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
            f"⚠️ La sessione non è stata avviata: {exc}",
        )


def resume_session(state: dict[str, Any], session_id: str | None):
    if not session_id:
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
            "Seleziona una sessione incompleta.",
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
            f"⚠️ Sessione non ripresa: {exc}",
        )


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


def _summary_markdown(session: dict[str, Any]) -> str:
    summary = SESSIONS.summary(session)
    counts = summary["correct_by_attempt"]
    return (
        "## Sessione completata\n\n"
        f"**Scala:** {session['scale']}  \n"
        f"**Descrittori completati:** {summary['descriptors_completed']}  \n\n"
        "| Esito | Descrittori |\n"
        "|---|---:|\n"
        f"| Corretti al primo tentativo | {counts['1']} |\n"
        f"| Corretti al secondo tentativo | {counts['2']} |\n"
        f"| Corretti al terzo tentativo | {counts['3']} |\n"
        f"| Non risolti entro tre tentativi | "
        f"{summary['unresolved_after_three']} |\n\n"
        '<span class="non-evaluation">Il riepilogo serve a rivedere il percorso '
        "di familiarizzazione e non esprime una valutazione professionale.</span>"
    )


def continue_session(state: dict[str, Any]):
    session = state.get("session")
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
            "",
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
                _summary_markdown(updated_session),
                "",
            )
        return (
            updated,
            gr.update(visible=True),
            gr.update(visible=False),
            *_exercise_view(updated_session),
            "",
            "",
        )
    except (SessionError, EventStoreError, CatalogError) as exc:
        view = _exercise_view(session)
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            *view,
            "",
            f"⚠️ Impossibile continuare: {exc}",
        )


def back_to_dashboard(state: dict[str, Any]):
    try:
        progress, resumes = _dashboard(state["participant_id"])
        updated = dict(state)
        updated["session"] = None
        return (
            updated,
            gr.update(visible=True),
            gr.update(visible=False),
            progress,
            gr.Dropdown(
                choices=resumes,
                value=resumes[0][1] if resumes else None,
                interactive=bool(resumes),
            ),
            "",
        )
    except (KeyError, EventStoreError) as exc:
        return (
            state,
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            gr.Dropdown(choices=[]),
            f"⚠️ Percorso non aggiornato: {exc}",
        )


def logout():
    return (
        _empty_ui_state(),
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        "",
        False,
        "",
    )


def researcher_overview(access_key: str):
    if not SETTINGS.researcher_access_key:
        return (
            "La panoramica è disattivata: configura `RESEARCHER_ACCESS_KEY` "
            "nei secret dello Space.",
            [],
        )
    if not hmac.compare_digest(
        access_key or "", SETTINGS.researcher_access_key
    ):
        return "Chiave non valida.", []
    try:
        participants = STORE.list_participants()
        events = STORE.list_events()
    except EventStoreError as exc:
        return f"Archivio non disponibile: {exc}", []

    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_participant[str(event.get("participant_id_hash", ""))].append(event)

    rows: list[list[Any]] = []
    for participant in participants:
        participant_events = by_participant.get(participant["participant_id"], [])
        starts = sum(
            event.get("event_type") == "session_started"
            for event in participant_events
        )
        completed = sum(
            event.get("event_type") == "session_completed"
            for event in participant_events
        )
        last_activity = max(
            (event.get("occurred_at", "") for event in participant_events),
            default=participant.get("updated_at", ""),
        )
        rows.append(
            [
                participant["display_name"],
                starts,
                completed,
                max(starts - completed, 0),
                last_activity[:19].replace("T", " "),
            ]
        )
    return f"Partecipanti trovati: **{len(rows)}**", rows


def build_demo() -> gr.Blocks:
    schemas, schema, modality, activity, scale = _first_path_values()
    with gr.Blocks(
        title="Familiarizzap",
    ) as demo:
        ui_state = gr.State(_empty_ui_state())
        gr.HTML(
            """
            <section class="hero">
              <div class="hero-kicker">Familiarizzazione CEFR</div>
              <h1>Familiarizzap</h1>
              <p>Esplora i descrittori, riconosci il livello e usa i feedback
              progressivi per affinare la tua lettura. Nessun voto, nessuna
              graduatoria.</p>
            </section>
            """
        )
        gr.Markdown(_storage_banner(), elem_classes="storage-banner")

        with gr.Tabs():
            with gr.Tab("Il mio percorso"):
                with gr.Group(visible=True) as login_group:
                    gr.Markdown(
                        "## Inizia dal tuo nome\n"
                        "Il nome permette di ritrovare il percorso, ma non "
                        "costituisce un sistema di autenticazione."
                    )
                    with gr.Row():
                        first_name = gr.Textbox(
                            label="Nome",
                            placeholder="Es. Giulia",
                            max_length=80,
                        )
                        last_name = gr.Textbox(
                            label="Cognome",
                            placeholder="Es. Rossi",
                            max_length=80,
                        )
                    consent = gr.Checkbox(
                        label=(
                            "Confermo di aver letto l’informativa dimostrativa "
                            "e di voler proseguire."
                        )
                    )
                    identify_button = gr.Button(
                        "Apri il mio percorso", variant="primary"
                    )

                with gr.Group(visible=False) as dashboard_group:
                    greeting = gr.Markdown()
                    progress_dashboard = gr.Markdown()
                    with gr.Accordion(
                        "Riprendi una sessione", open=False
                    ):
                        resume_choice = gr.Dropdown(
                            choices=[],
                            label="Sessione da riprendere",
                            interactive=False,
                        )
                        resume_button = gr.Button("Riprendi")

                    gr.Markdown("### Inizia una nuova sessione")
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
                    with gr.Row():
                        start_button = gr.Button(
                            "Inizia la sessione", variant="primary"
                        )
                        logout_button = gr.Button("Cambia partecipante")

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
                    summary = gr.Markdown()
                    dashboard_button = gr.Button(
                        "Torna al mio percorso", variant="primary"
                    )

                user_message = gr.Markdown()

            with gr.Tab("Panoramica ricercatore"):
                gr.Markdown(
                    "## Panoramica riservata\n"
                    "La chiave è configurata nei secret dello Space e non "
                    "compare nel codice."
                )
                researcher_key = gr.Textbox(
                    label="Chiave ricercatore", type="password"
                )
                researcher_button = gr.Button("Apri panoramica")
                researcher_message = gr.Markdown()
                researcher_table = gr.Dataframe(
                    headers=[
                        "Partecipante",
                        "Sessioni iniziate",
                        "Sessioni completate",
                        "Sessioni in corso",
                        "Ultima attività (UTC)",
                    ],
                    datatype=["str", "number", "number", "number", "str"],
                    interactive=False,
                    wrap=True,
                )

        identify_button.click(
            identify_participant,
            inputs=[first_name, last_name, consent, ui_state],
            outputs=[
                ui_state,
                login_group,
                dashboard_group,
                greeting,
                progress_dashboard,
                resume_choice,
                user_message,
            ],
        )
        schema_choice.change(
            update_schema,
            inputs=schema_choice,
            outputs=[modality_choice, activity_choice, scale_choice],
        )
        modality_choice.change(
            update_modality,
            inputs=[schema_choice, modality_choice],
            outputs=[activity_choice, scale_choice],
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
        )
        resume_button.click(
            resume_session,
            inputs=[ui_state, resume_choice],
            outputs=exercise_outputs,
        )
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
                summary,
                user_message,
            ],
        )
        dashboard_button.click(
            back_to_dashboard,
            inputs=ui_state,
            outputs=[
                ui_state,
                dashboard_group,
                summary_group,
                progress_dashboard,
                resume_choice,
                user_message,
            ],
        )
        logout_button.click(
            logout,
            outputs=[
                ui_state,
                login_group,
                dashboard_group,
                exercise_group,
                summary_group,
                first_name,
                last_name,
                consent,
                user_message,
            ],
        )
        researcher_button.click(
            researcher_overview,
            inputs=researcher_key,
            outputs=[researcher_message, researcher_table],
        )

    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=8).launch(theme=THEME, css=CSS)
