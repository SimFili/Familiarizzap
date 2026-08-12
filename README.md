# FamiliarizzApp

FamiliarizzApp è un’app Gradio per aiutare docenti di lingua dei segni a
familiarizzare con descrittori e livelli CEFR. Presenta un descrittore, accetta
fino a tre tentativi, offre feedback progressivi e conserva il percorso senza
trasformarlo in una valutazione professionale.

La versione 0.5.2 include:

- accesso al proprio percorso tramite il solo nome;
- navigazione progressiva: identificazione, ambiti disponibili e infine scale;
- schema descrittivo a colori mostrato soltanto dopo l’identificazione;
- pagina personale `/percorso` separata dalla scelta e dagli esercizi;
- panoramica del ricercatore in una pagina separata e protetta;
- interfaccia leggibile su smartphone e con tema scuro;
- cronologia longitudinale senza sovrascrivere gli esiti precedenti;
- mappa cliccabile della scala con esito e data relativa;
- percentuale di riconoscimento al primo tentativo, senza voto composito;
- ripetizione mirata dei descrittori da consolidare;
- conteggio dei descrittori presenti per ciascun livello nelle opzioni di
  risposta;
- scelta facoltativa, prima di ogni sessione, per escludere A2+ e B1+;
- cronologia a schede e ripresa diretta di una sessione in corso;
- intero catalogo distribuito con lo Space: 831 descrittori, 52 scale e livelli
  `A1`, `A2`, `A2+`, `B1`, `B1+`, `B2`;
- dashboard del ricercatore con filtri, timestamp esatti, dati grezzi,
  controllo d’integrità ed esportazione ZIP.

**App online:** https://huggingface.co/spaces/Sibucs/Familiarizzap

## Stato del rilascio

La versione pubblica include 831 descrittori ricavati dal database validato del
gruppo di ricerca, organizzati in 52 scale. I feedback sono provvisori.
Provenienza e diritti di pubblicazione dei testi devono essere verificati prima
dell’uso pubblico definitivo.

Per il pilot reale devono essere configurati:

- un Dataset Hugging Face privato per registro partecipanti ed eventi;
- i secret dello Space descritti in `space/.env.example`;
- informativa, consenso, conservazione e licenze approvati dal progetto.

Se lo storage remoto e i relativi secret non sono presenti, l’app usa il
catalogo completo ma mostra esplicitamente che i dati del percorso sono
temporanei.

Il convertitore `tools/build_catalog.py` legge il foglio di lavoro approvato e
produce `space/data/catalog.full.json`. Il file completo è incluso nello Space
per rendere disponibili tutti gli esercizi; il rapporto locale di conversione
resta ignorato da Git. `CONTENT_FILE_PATH` può selezionare un file diverso in
locale; `CONTENT_REPO_ID` resta disponibile per una futura migrazione a un
Dataset Hugging Face privato.

La modalità locale e quella dimostrativa servono esclusivamente al collaudo:
la continuità dei dati della ricerca richiede il Dataset privato configurato.

## Organizzazione

```text
space/      app pubblicata su Hugging Face
tests/      test automatici
docs/       decisioni e contratto dei dati
.github/    test e automazione di pubblicazione
```

[COMUNICAZIONI-AI.md](COMUNICAZIONI-AI.md) raccoglie le modifiche fatte fuori dal
codice (secret configurati, decisioni, servizi esterni). Va letto a inizio
sessione e aggiornato quando si cambia qualcosa che dai commit non si vede.

[docs/RICERCA_LONGITUDINALE.md](docs/RICERCA_LONGITUDINALE.md) descrive unità
di osservazione, indicatori, distinzione fra ripetizione e trasferimento,
timestamp, integrità ed esportazione.

Tutto ciò che sta fuori da `space/` resta nel repository GitHub e non viene
pubblicato nello Space.

## Sviluppo locale

Richiede Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
Set-Location space
python app.py
```

L’app locale salva gli eventi in `space/data/runtime/`, cartella ignorata da Git.

Per rigenerare il catalogo completo distribuito con lo Space:

```powershell
python tools\build_catalog.py "PERCORSO\database descrittori app final.xlsx" `
  "space\data\catalog.full.json"
$env:CONTENT_FILE_PATH="data/catalog.full.json"
Set-Location space
python app.py
```

## Flusso di lavoro

1. aggiornare `main`;
2. creare un branch per la modifica;
3. eseguire i test;
4. aprire una Pull Request;
5. integrare in `main` dopo revisione.

Un push su `main` che modifica `space/` avvia la pubblicazione automatica nello
Space `Sibucs/Familiarizzap`.

## Regole di sicurezza

- Nessuna chiave, token o password nei file: il repository è pubblico.
- I dati della ricerca non entrano mai nel repository del codice.
- Il nome identifica il percorso ma non autentica la persona: omonimi e accessi
  da parte di chi conosce il nome sono un rischio accettato soltanto per il
  piccolo gruppo interno.
- Il livello corretto proviene soltanto dal catalogo approvato.
- Nessun modello AI viene chiamato durante la sessione del docente.
- Lo Space Hugging Face è una destinazione di deploy e non si modifica a mano.
