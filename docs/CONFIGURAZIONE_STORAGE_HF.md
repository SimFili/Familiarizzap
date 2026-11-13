# Archivio durevole su Hugging Face

FamiliarizzApp conserva gli eventi del pilot in un **Dataset Hugging Face
privato**. Il disco gratuito dello Space non è un archivio durevole e non va
usato per raccogliere dati di ricerca.

**Stato al 13 novembre 2026:** il Dataset privato e i secret necessari sono
configurati nello Space pubblico. I valori non sono riportati in Git. I dati
accumulati durante il pre-test non sono ancora stati eliminati: la rimozione
avverrà soltanto dopo l’identificazione esplicita dei partecipanti o delle
sessioni da escludere.

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

Dopo il riavvio, la modalità di ricerca correttamente configurata non aggiunge
una fascia tecnica alla schermata del docente. Se l’archivio remoto non è
utilizzabile, l’app mostra invece un avviso di salvataggio non disponibile e
chiede di interrompere la prova. In assenza completa della configurazione,
compare la dicitura **Modalità dimostrativa** e i dati non vanno usati per la
ricerca.

Eseguire quindi questa prova con un nome fittizio:

1. iniziare una scala e confermare almeno una risposta;
2. mettere in pausa la sessione;
3. riavviare lo Space;
4. riaprire il percorso con lo stesso nome;
5. verificare che la sessione e il tentativo siano ancora presenti;
6. verificare nel Dataset la comparsa dei file sotto `participants/` ed
   `events/`.

Eliminare i dati fittizi prima dell’analisi della raccolta reale. Prima della
cancellazione, esportare o elencare i record e verificare i bersagli con il
ricercatore; non usare cancellazioni generiche per data o per cartella se
potrebbero comprendere partecipanti reali. Il Dataset deve rimanere privato per
tutta la durata del pilot.

## 5. Prestazioni e garanzie di salvataggio

All’avvio dello Space, il controllo del Dataset e l’elenco dei percorsi evento
vengono preparati in background mentre il docente legge la prima schermata.

Ogni risposta viene confermata nel Dataset **prima** che l’interfaccia mostri il
nuovo stato. Un errore di rete non consuma il tentativo. Per ridurre le attese:

- la risposta, il completamento del descrittore e, quando pertinente, il
  completamento della sessione vengono inviati nello stesso commit;
- la presentazione del descrittore successivo resta nello stato della sessione
  e viene registrata insieme alla sua prima risposta;
- se la pagina viene ricaricata prima di quella risposta, nessuna risposta già
  data va persa: il percorso riparte dall’ultimo stato confermato;
- partecipanti diversi possono scrivere contemporaneamente, mentre due invii
  dello stesso evento vengono coordinati e producono un solo file;
- gli errori remoti transitori ricevono fino a due tentativi complessivi con
  una breve attesa; le richieste HTTP hanno limite di 10 secondi, con 5 secondi
  per connessione e attesa del pool.

La coda dell’app accetta fino a otto operazioni concorrenti. Nella verifica
locale del 13 novembre 2026, ingresso, risposte, passaggi e avvio della seconda
tappa hanno richiesto circa 0,1–0,2 secondi ciascuno; il tempo reale online
include comunque la scrittura nel Dataset Hugging Face.
