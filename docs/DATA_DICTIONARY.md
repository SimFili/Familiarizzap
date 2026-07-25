# Dizionario essenziale dei dati

## Catalogo

Il file pubblicato dal Dataset contenuti si chiama `catalog.json` ed è una lista
di oggetti. Campi obbligatori:

| Campo | Significato |
|---|---|
| `descriptor_id` | identificatore stabile |
| `schema` | macroarea dello schema descrittivo |
| `modality` | modalità di comunicazione |
| `activity` | attività, strategia o competenza |
| `scale` | scala scelta dal docente |
| `correct_level` | soluzione, mai determinata dall’AI |
| `descriptor_text` | testo mostrato |
| `rationale` | motivazione finale approvata |
| `hint_1`, `hint_2` | suggerimenti approvati che non rivelano la soluzione |
| `source`, `source_version` | provenienza |
| `license_or_permission` | base giuridica/editoriale per l’uso |
| `content_version` | versione editoriale |
| `status`, `active` | soltanto `approved` e `true` vengono pubblicati |

## Registro dei partecipanti

Percorso nel Dataset privato:

```text
participants/<participant_id>.json
```

Contiene identificativo pseudonimo, nome da mostrare, date e stato. È l’unica
area in cui viene conservato il nome.

## Eventi

Percorso nel Dataset privato:

```text
events/AAAA/MM/GG/<session_id>/<event_id>.json
```

Campi comuni: versione schema, ID evento, tipo, date UTC, ID sessione,
identificativo pseudonimo, revisione contenuti e versione app.

Tipi implementati:

- `consent_recorded`;
- `session_started`;
- `descriptor_presented`;
- `answer_submitted`;
- `descriptor_completed`;
- `session_completed`.

Gli eventi non contengono il nome del partecipante.
