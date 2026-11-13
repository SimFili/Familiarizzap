# Decisioni operative dell’MVP

Aggiornamento: 13 novembre 2026.

Questo file traduce in decisioni implementative la specifica consolidata e il
documento delle questioni aperte. Le scelte sono adatte a un prototipo
dimostrativo; quelle che incidono sul pilot devono essere confermate dal gruppo
di ricerca.

## Decisioni implementate

- Python 3.12 e Gradio, con deploy del solo contenuto di `space/`.
- Tutte le righe approvate e utilizzabili della scala diventano esercizi.
- `A2+` e `B1+` restano livelli autonomi nel catalogo e nella cronologia, ma
  sono sospesi dagli esercizi e dalle opzioni di risposta del primo pilot.
- I pulsanti mostrano una sola volta i livelli distinti presenti nella scala,
  ordinati secondo la progressione QCER.
- Una riga con testo `Nessun descrittore` non genera esercizi né pulsanti.
- Sono consentiti tre invii reali. Una risposta corretta chiude subito il
  descrittore; al terzo invio viene sempre mostrata la soluzione.
- I primi due feedback sono testi curati e non rivelano il livello corretto.
  Nessun modello AI viene eseguito durante la sessione.
- Nel percorso consigliato sono attive 16 guide specifiche: 13 marcate come
  validate per il pilot e 3 come soggette a revisione mirata ma mantenute nella
  sperimentazione corrente per decisione del ricercatore. Nell’esplorazione
  facoltativa restano feedback in parte essenziali o generici.
- Quando la risposta conclusiva è corretta, la spiegazione descrive gli elementi
  del target riconosciuto e non torna sui livelli scelti in precedenza. Soltanto
  una terza risposta ancora errata può ricevere il confronto con l’ultima scelta.
- La scrittura dei feedback privilegia le differenze fra livelli adiacenti. Il
  criterio deriva dal risultato di ricerca comunicato dal ricercatore: la
  grande maggioranza degli errori si trova a una o due posizioni dal livello
  target. Il primo suggerimento resta orientativo; il secondo evidenzia gli
  elementi che distinguono il target dai livelli vicini.
- L’ordine dei descrittori è casuale, riproducibile tramite il seme salvato e
  stabile alla ripresa.
- Il docente inserisce soltanto il nome. Il nome normalizzato viene trasformato
  in un HMAC deterministico che identifica sempre lo stesso percorso; il nome in
  chiaro compare soltanto nel registro privato dei partecipanti, non negli
  eventi.
- Il nome è un identificatore, non un’autenticazione. Due omonimi condividono lo
  stesso percorso e chi conosce il nome può aprirlo. Questa semplificazione è
  accettata soltanto per il piccolo gruppo interno; prima di un uso pubblico o
  con dati sensibili deve essere rivalutata.
- Ogni evento ha un identificatore deterministico per sessione e passaggio. Un
  retry dello stesso invio non crea un secondo tentativo.
- Il salvataggio dell’evento viene confermato prima di aggiornare lo stato
  dell’interfaccia. Un errore non consuma il tentativo.
- Ogni risposta continua a essere salvata subito. La presentazione del
  descrittore successivo viene registrata insieme alla sua prima risposta e la
  conclusione della sessione insieme alla risposta finale: il raggruppamento
  riduce le richieste remote senza perdere risposte.
- Partecipanti diversi possono salvare contemporaneamente. Un doppio invio
  dello stesso evento resta idempotente; conflitti e indisponibilità transitorie
  ricevono un retry breve e le richieste remote hanno un limite d’attesa.
- La panoramica del ricercatore è nella pagina separata `/ricercatore` ed è
  protetta da un unico secret.
- La pagina principale serve a scegliere una scala e svolgere gli esercizi.
  Percentuali, mappa dei descrittori già incontrati o in corso, cronologia e
  sessioni precedenti sono raccolte nella pagina personale separata
  `/percorso`.
- La scelta nella pagina principale è progressiva: identificazione, quadro
  degli ambiti disponibili e, in una schermata successiva, scale dell’ambito
  selezionato. La colonna `Competenza generale` non viene mostrata perché non
  contiene descrittori utilizzabili e renderebbe più confusa la scelta.
- Gli eventi nuovi usano lo schema `2.0` e conservano fotografia del
  descrittore, numero di esposizione, distanza della risposta dal target,
  tempi server e versioni. I dati precedenti in schema `1.0` restano leggibili.
- I risultati precedenti non vengono sostituiti: dashboard e riepiloghi vengono
  ricostruiti dalla sequenza degli eventi immutabili.
- L’indicatore principale è la percentuale di descrittori riconosciuti al primo
  tentativo. Non viene prodotto un voto composito. Nel percorso di una scala
  conta l’esito più recente di ciascun descrittore.
- Il riepilogo mostra la scala completa dall’alto verso il basso con stati
  verde scuro, verde chiaro, giallo, rosso chiaro e grigio, sempre accompagnati
  da etichette testuali.
- Il percorso consigliato comprende quattro tappe obbligatoriamente ordinate:
  Scala generale QCER, Comprensione orale generale, Produzione orale generale e
  Interazione orale generale. La tappa incompleta si riprende dal percorso.
- Dopo la quarta tappa l’app richiede il questionario finale. Le altre scale si
  sbloccano soltanto dopo il suo invio e restano un’esplorazione facoltativa.
- Il ricercatore dispone di filtri, cronologia individuale, eventi grezzi,
  risposte al questionario, verifica d’integrità e archivio ZIP con CSV e JSONL.
- In assenza di Dataset e secret, l’app dichiara la modalità demo e non promette
  persistenza.

## Elementi ancora da approvare prima del pilot

- catalogo reale, provenienza, licenze e traduzioni;
- motivazioni e feedback revisionati da un esperto;
- informativa, consenso, titolare del trattamento e procedura di ritiro;
- durata di conservazione, cancellazione e backup;
- inclusione o esclusione definitiva della mediazione;
- intervallo e protocollo di ripetizione delle scale nello studio;
- distinzione metodologica fra miglioramento sugli stessi descrittori e
  trasferimento a descrittori mai incontrati;
- procedura selettiva per distinguere ed eliminare i dati del pre-test prima
  delle analisi, senza cancellare le risposte della sperimentazione.
