# Familiarizzap

Familiarizzap è un’app Gradio per aiutare docenti di lingua dei segni a
familiarizzare con descrittori e livelli CEFR. Presenta un descrittore, accetta
fino a tre tentativi, offre feedback progressivi e conserva il percorso senza
trasformarlo in una valutazione professionale.

**App online:** https://huggingface.co/spaces/Sibucs/Familiarizzap

## Stato del rilascio

Il codice include un catalogo dimostrativo originale e privo di testi CEFR
protetti. Per il pilot reale devono essere configurati:

- un Dataset Hugging Face privato per il catalogo approvato;
- un Dataset Hugging Face privato per registro partecipanti ed eventi;
- i secret dello Space descritti in `space/.env.example`;
- informativa, consenso, conservazione e licenze approvati dal progetto.

Se questi elementi non sono presenti, l’app mostra esplicitamente la modalità
dimostrativa e usa uno storage temporaneo.

## Organizzazione

```text
space/      app pubblicata su Hugging Face
tests/      test automatici
docs/       decisioni e contratto dei dati
.github/    test e automazione di pubblicazione
```

Tutto ciò che sta fuori da `space/` resta nel repository GitHub e non viene
pubblicato nello Space.

## Sviluppo locale

Richiede Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r space\requirements.txt
python -m pip install pytest
python -m pytest
Set-Location space
python app.py
```

L’app locale salva gli eventi in `space/data/runtime/`, cartella ignorata da Git.

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
- Il livello corretto proviene soltanto dal catalogo approvato.
- Nessun modello AI viene chiamato durante la sessione del docente.
- Lo Space Hugging Face è una destinazione di deploy e non si modifica a mano.
