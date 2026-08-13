# Archivio durevole su Hugging Face

FamiliarizzApp conserva gli eventi del pilot in un **Dataset Hugging Face
privato**. Il disco gratuito dello Space non è un archivio durevole e non va
usato per raccogliere dati di ricerca.

Questa configurazione può essere eseguita soltanto dal proprietario dello Space
`Sibucs/Familiarizzap` o da un collaboratore con accesso alle impostazioni.

## 1. Creare il Dataset privato

Creare il Dataset `Sibucs/Familiarizzap-events` e selezionare **Private**. Non
caricare manualmente nomi, password o file del pilot: sarà l’app a creare la
struttura `participants/` e `events/`.

## 2. Creare un token dedicato

Creare un token Hugging Face con il solo permesso di lettura e scrittura sul
Dataset privato degli eventi. Non riutilizzare password personali e non
inserire il token in GitHub, nei Markdown o nel codice.

## 3. Configurare lo Space

In **Settings → Variables and secrets** dello Space impostare:

| Tipo | Nome | Valore |
| --- | --- | --- |
| Variable | `EVENTS_REPO_ID` | `Sibucs/Familiarizzap-events` |
| Secret | `HF_DATA_TOKEN` | token dedicato del punto 2 |
| Secret | `PARTICIPANT_HASH_SALT` | valore casuale stabile già concordato |
| Secret | `RESEARCHER_ACCESS_KEY` | chiave privata del ricercatore |

`PARTICIPANT_HASH_SALT` non deve essere modificato dopo l’avvio del pilot: un
valore diverso produrrebbe identificativi diversi per lo stesso nome.

## 4. Verificare prima del pilot

Dopo il riavvio dello Space, la fascia informativa deve essere verde e mostrare
**Modalità pilot**. Se è arancione, manca almeno una configurazione; se è rossa,
il Dataset non è raggiungibile, il token non è valido oppure il Dataset non è
privato.

Eseguire quindi questa prova con un nome fittizio:

1. iniziare una scala e confermare almeno una risposta;
2. mettere in pausa la sessione;
3. riavviare lo Space;
4. riaprire il percorso con lo stesso nome;
5. verificare che la sessione e il tentativo siano ancora presenti;
6. verificare nel Dataset la comparsa dei file sotto `participants/` ed
   `events/`.

Eliminare i dati fittizi prima dell’avvio della raccolta reale. Il Dataset deve
rimanere privato per tutta la durata del pilot.
