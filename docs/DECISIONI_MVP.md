# Decisioni operative dell’MVP

Aggiornamento: 24 luglio 2026.

Questo file traduce in decisioni implementative la specifica consolidata e il
documento delle questioni aperte. Le scelte sono adatte a un prototipo
dimostrativo; quelle che incidono sul pilot devono essere confermate dal gruppo
di ricerca.

## Decisioni implementate

- Python 3.12 e Gradio, con deploy del solo contenuto di `space/`.
- Tutte le righe approvate e utilizzabili della scala diventano esercizi.
- `A2+` e `B1+` restano livelli autonomi.
- I pulsanti mostrano una sola volta i livelli distinti presenti nella scala,
  ordinati secondo la progressione CEFR.
- Una riga con testo `Nessun descrittore` non genera esercizi né pulsanti.
- Sono consentiti tre invii reali. Una risposta corretta chiude subito il
  descrittore; al terzo invio viene sempre mostrata la soluzione.
- I primi due feedback sono testi curati e non rivelano il livello corretto.
  Nessun modello AI viene eseguito durante la sessione.
- L’ordine dei descrittori è casuale, riproducibile tramite il seme salvato e
  stabile alla ripresa.
- Il nome viene normalizzato e trasformato in un identificatore HMAC. Il nome
  compare soltanto nel registro privato dei partecipanti, non negli eventi.
- Ogni evento ha un identificatore deterministico per sessione e passaggio. Un
  retry dello stesso invio non crea un secondo tentativo.
- Il salvataggio dell’evento viene confermato prima di aggiornare lo stato
  dell’interfaccia. Un errore non consuma il tentativo.
- La panoramica del ricercatore è separata e protetta da un secret.
- In assenza di Dataset e secret, l’app dichiara la modalità demo e non promette
  persistenza.

## Elementi ancora da approvare prima del pilot

- catalogo reale, provenienza, licenze e traduzioni;
- motivazioni e feedback revisionati da un esperto;
- informativa, consenso, titolare del trattamento e procedura di ritiro;
- durata di conservazione, cancellazione e backup;
- inclusione o esclusione definitiva della mediazione;
- possibilità e regole di ripetizione delle scale;
- indicatori finali da mostrare senza effetto valutativo;
- configurazione effettiva dei Dataset privati e dei token a privilegio minimo.
