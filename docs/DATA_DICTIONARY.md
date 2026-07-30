# Dizionario dei dati

Aggiornamento: 30 luglio 2026. Schema eventi corrente: `2.0`.

## Principio longitudinale

Gli eventi della ricerca sono immutabili: una nuova attività aggiunge un file e
non modifica i risultati precedenti. Riepiloghi, percentuali, mappe e dashboard
sono viste ricalcolabili dagli eventi originali.

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
| `license_or_permission` | base editoriale per l’uso |
| `content_version` | versione editoriale |
| `status`, `active` | nel catalogo remoto soltanto `approved` e `true` vengono pubblicati; il catalogo incluso usa `demo` |

Il catalogo remoto del pilot accetta soltanto `A1`, `A2`, `A2+`, `B1`,
`B1+` e `B2`. L’ordine degli oggetti nella stessa scala conserva l’ordine della
fonte e viene usato nella mappa finale, dopo il raggruppamento discendente per
livello.

## Registro privato dei partecipanti

Percorso nel Dataset privato:

```text
participants/<participant_id>.json
```

| Campo | Significato |
|---|---|
| `participant_id` | identificativo casuale pseudonimo, indipendente dal nome |
| `display_name` | nome e cognome mostrati soltanto nelle viste riservate |
| `name_lookup_hash` | HMAC del nome normalizzato usato per trovare uno o più profili omonimi |
| `created_at`, `updated_at` | timestamp UTC del registro |
| `status`, `merged_into` | gestione di profili attivi, ritirati o uniti |
| `access_code_hash` | hash HMAC del codice personale; il codice in chiaro non viene salvato nel Dataset |
| `access_code_version` | versione del formato del codice |
| `access_code_updated_at` | ultimo rilascio o reset del codice |

Il nome è conservato in chiaro esclusivamente in questo registro privato. Non è
ripetuto negli eventi.

I nuovi profili usano un ID casuale, così due persone omonime possono avere
percorsi diversi. I profili precedenti, il cui ID coincideva con l’HMAC del
nome, restano compatibili e vengono aggiornati al nuovo schema al primo accesso.

## Codice personale del percorso

Il codice ha 12 caratteri leggibili, visualizzati in tre gruppi. Viene:

- generato al primo accesso;
- mostrato una sola volta e memorizzato nel browser mediante `BrowserState`;
- verificato sul server tramite HMAC;
- sostituibile dal ricercatore se viene perso;
- escluso in chiaro sia dagli eventi sia dalle esportazioni.

Il reset produce un evento immutabile e rende invalido il codice precedente.

## Eventi

Percorso nel Dataset privato:

```text
events/AAAA/MM/GG/<session_id>/<event_id>.json
```

Campi comuni:

| Campo | Significato |
|---|---|
| `schema_version` | versione dello schema; i nuovi eventi usano `2.0` |
| `event_id` | identificatore univoco e idempotente |
| `event_type` | tipo dell’azione registrata |
| `occurred_at`, `received_at` | timestamp UTC generati dal server |
| `session_id` | sessione o accesso cui appartiene l’evento |
| `participant_id_hash` | identificativo pseudonimo |
| `content_revision` | revisione esatta del catalogo |
| `app_version` | versione dell’app |

Tipi implementati:

- `consent_recorded`;
- `participant_accessed`;
- `access_code_issued`;
- `access_code_reset`;
- `session_started`;
- `descriptor_presented`;
- `answer_submitted`;
- `descriptor_completed`;
- `session_completed`.

### `session_started`

Registra gerarchia e scala, seme casuale, ordine dei descrittori, livelli
selezionabili, numero di descrittori e numero di sessioni precedenti.

### `descriptor_presented`

Registra posizione, numero dell’esposizione e una fotografia del contenuto
effettivamente mostrato: testo, livello, gerarchia, versione, fonte e revisione.
Questo permette di ricostruire lo studio anche se il catalogo viene aggiornato.

### `answer_submitted`

Registra:

- numero del tentativo;
- livello scelto e livello corretto;
- esito;
- distanza assoluta fra i due livelli nell’ordine CEFR;
- feedback effettivamente mostrato e sua fase;
- tempo dal tentativo precedente;
- tempo totale trascorso sul descrittore;
- numero dell’esposizione;
- `client_request_id` per l’idempotenza.

### `descriptor_completed`

Registra la sequenza completa delle risposte, il tentativo risolutivo,
l’eventuale mancata risoluzione, la distanza iniziale e finale, la motivazione,
la durata e la fotografia del descrittore.

### `session_completed`

Registra conteggi per tentativo, non risolti, percentuale al primo tentativo,
durata, ordine e revisione dei contenuti.

## Indicatori derivati

L’indicatore principale è:

```text
riconoscimento senza suggerimenti =
descrittori corretti al primo tentativo / descrittori considerati × 100
```

Non viene calcolato un punteggio composito arbitrario. Nella vista longitudinale
di una scala, per ogni descrittore conta l’esito dell’incontro più recente. Il
100% si raggiunge soltanto quando tutti i descrittori della scala risultano
riconosciuti al primo tentativo nell’incontro più recente.

Stati visuali:

- verde scuro: primo tentativo;
- verde chiaro: secondo tentativo;
- giallo: terzo tentativo;
- rosso chiaro: non risolto;
- grigio: mai incontrato.

Ogni colore è accompagnato da un’etichetta testuale.

## Timestamp

Gli eventi conservano UTC esatto. La dashboard del ricercatore mostra sia
l’orario italiano completo sia l’UTC. Il docente vede una forma relativa:
`pochi minuti fa`, `circa 2 ore fa`, `ieri`, `4 giorni fa` oppure la data.

## Esportazione per la ricerca

La dashboard produce un archivio ZIP con:

- `participants.csv`;
- `sessions.csv`;
- `descriptor_history.csv`;
- `attempts.csv`;
- `events.jsonl`;
- `integrity.csv`;
- `manifest.json`.

L’archivio contiene nomi perché è destinato al ricercatore autorizzato, ma non
contiene gli hash dei codici personali.
