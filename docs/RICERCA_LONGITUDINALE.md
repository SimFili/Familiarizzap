# Ricerca longitudinale in FamiliarizzApp

Aggiornamento: 30 luglio 2026.

## Obiettivo

Permettere di studiare come cambia nel tempo il riconoscimento dei livelli CEFR
di ciascun docente, conservando separatamente ogni esposizione e senza
sovrascrivere risultati precedenti.

## Unità di osservazione

L’unità primaria è l’incontro fra:

```text
partecipante × descrittore × esposizione
```

Per ogni incontro vengono conservati sessione, versione del contenuto, ordine,
risposte, distanze dal target, suggerimenti mostrati, esito, tempi e timestamp.

## Indicatori principali

### Riconoscimento senza suggerimenti

```text
corretti al primo tentativo / descrittori considerati × 100
```

È sempre mostrato insieme al conteggio, per esempio `80% — 4 su 5`.

### Distanza della prima risposta

Numero di posizioni fra livello scelto e livello target nell’ordine:

```text
A1 → A2 → A2+ → B1 → B1+ → B2
```

Zero indica una risposta corretta; uno e due distinguono gli errori vicini al
target.

### Suggerimenti necessari

L’esito distingue:

- primo tentativo;
- secondo tentativo;
- terzo tentativo;
- non risolto entro tre tentativi.

### Copertura

La mappa distingue i descrittori mai incontrati da quelli già affrontati.
Questo impedisce che una percentuale alta su pochi elementi sembri copertura
completa.

## Miglioramento individuale

Per ogni descrittore la cronologia può mostrare, per esempio:

```text
non risolto → secondo tentativo → primo tentativo
```

La vista corrente usa l’incontro più recente, non il risultato migliore mai
ottenuto. La storia completa resta comunque disponibile.

## Due fenomeni da non confondere

### Familiarizzazione o memoria

Miglioramento sugli stessi descrittori già incontrati.

### Trasferimento

Miglioramento su descrittori mai incontrati prima ma appartenenti agli stessi
livelli o alle stesse scale.

L’app registra il numero dell’esposizione per rendere possibile questa
distinzione. Il protocollo di studio deve ancora stabilire intervalli,
campionamento e presenza di elementi nuovi.

## Timestamp

- archivio: UTC esatto generato dal server;
- ricercatore: ora italiana esatta più UTC;
- docente: tempo relativo, tranne attività più lontane mostrate come data.

I tempi di risposta possono essere studiati, ma non devono essere interpretati
automaticamente come competenza: includono pause, interruzioni e differenze di
dispositivo.

## Dashboard del ricercatore

La dashboard riservata permette:

- panoramica di tutti i partecipanti;
- dettaglio di sessioni complete e interrotte;
- cronologia di ogni descrittore;
- risposte e feedback effettivamente mostrati;
- filtri per partecipante, scala e periodo;
- registro completo degli eventi;
- controllo delle incoerenze;
- reset tracciato del codice personale;
- esportazione completa.

## Esportazione

Il file ZIP contiene dati grezzi e derivati. Per un’analisi riproducibile:

1. conservare `events.jsonl` come fonte primaria;
2. conservare `manifest.json` con data e quantità;
3. usare i CSV per l’analisi;
4. non modificare gli eventi originali;
5. documentare ogni esclusione o trasformazione;
6. effettuare copie locali protette secondo il protocollo approvato.

Gli hash dei codici personali e le chiavi HMAC usate per cercare i nomi non
sono inclusi nell'esportazione.

## Integrità e compatibilità

- identificativi evento deterministici impediscono doppioni nei retry;
- un errore di salvataggio non consuma il tentativo;
- un evento esistente non viene sovrascritto;
- file corrotti vengono segnalati, non ignorati;
- lo schema `2.0` convive con gli eventi `1.0`;
- mappe e percentuali possono essere ricalcolate dagli eventi originali.

## Aspetti ancora da approvare

Prima della raccolta reale:

- consenso e informativa;
- titolare e accessi;
- durata di conservazione;
- procedura di ritiro, cancellazione o anonimizzazione;
- frequenza e cifratura dei backup;
- licenze dei contenuti;
- protocollo delle ripetizioni;
- criteri di analisi statistica.
