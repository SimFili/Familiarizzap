---
title: FamiliarizzApp
emoji: 🧭
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.20.0
python_version: '3.12'
app_file: app.py
pinned: false
---

# FamiliarizzApp

App di familiarizzazione con descrittori e livelli QCER per docenti di lingua
dei segni.

Il codice viene pubblicato automaticamente da
[GitHub](https://github.com/SimFili/Familiarizzap). Non modificare i file
direttamente nello Space: ogni modifica verrebbe sovrascritta alla pubblicazione
successiva.

Il catalogo incluso contiene 831 esercizi appartenenti a 52 scale. I feedback
sono brevi e tengono conto del tentativo e degli esiti precedenti nella sessione.
Il file di prevalidazione contiene 21 indizi specifici ricondotti per testo e
livello ai nuclei attivi; dopo la sospensione dei livelli “+” e delle scale
chiuse, 14 riguardano descrittori oggi esercitabili nella libera esplorazione.
Gli indizi sono nel file
versionato `data/feedback.prevalidated.json`: ciascuno riporta brevi passaggi
letterali del descrittore ed è legato all'impronta del suo testo completo.
L'app controlla ID, livello, impronta e passaggi prima di usare l'indizio: una
modifica del catalogo lo disattiva finché non viene ricontrollato. Le proposte
sospese non sono incluse. La corrispondenza testuale è stata ricontrollata,
ma non equivale alla validazione pedagogica umana.
Gli altri descrittori conservano, quando presente, una spiegazione editoriale
specifica. Se manca, l'app propone una domanda di confronto anziché spacciare
il livello del catalogo per una motivazione. Gli indizi sono provvisori e
richiedono verifica umana. Il repository contiene catalogo e feedback, non
nomi o tentativi dei docenti: questi sono eventi nell'archivio privato
configurato, oppure dati temporanei in modalità dimostrativa. I diritti di
pubblicazione dei testi devono essere verificati
prima dell’uso pubblico. Quando il Dataset degli eventi e i secret non sono
configurati, l’interfaccia segnala che gli eventi non sono durevoli.
Quando l’archivio remoto è configurato, l’app verifica che il Dataset sia
raggiungibile e privato prima di registrare nomi o tentativi.

La versione 0.7.0 separa la navigazione in passaggi successivi: prima
l’identificazione, poi gli ambiti disponibili e infine le scale dell’ambito
scelto. Percentuali, mappa e cronologia restano nella pagina personale separata
`/percorso`; la panoramica del ricercatore resta nella pagina riservata
`/ricercatore`. L’app conserva inoltre una cronologia longitudinale a eventi
immutabili, mostra riepiloghi cliccabili ed è ottimizzata per smartphone e tema
scuro. La cronologia personale usa schede leggibili e consente di riprendere
direttamente una sessione in corso. Le opzioni di risposta indicano quanti
descrittori della scala appartengono a ciascun livello. Per il primo pilot il
percorso principale comprende quattro tappe e 16 descrittori A1–B2, con guide
comparative ancora da validare umanamente. Le altre scale sono in una sezione
facoltativa, senza obbligo di completare il catalogo e con feedback spesso
generici. Gli incontri liberi iniziano dai livelli canonici, ne mostrano la
varietà interna e ripropongono gli elementi già visti; A2+ e B1+ sono sospesi
dagli esercizi e dalle risposte, ma restano nel catalogo e nella cronologia.
Gli incontri contengono da 4 a 6 descrittori distinti,
con la sola eccezione concordata di `Annunci pubblici`, che conserva i suoi 3
descrittori; le altre scale con meno di 4 descrittori non sono selezionabili.
Percentuali e riepiloghi personali considerano soltanto gli esiti conclusi;
gli esercizi lasciati a metà restano visibili separatamente come in corso.

Le scale mantengono il colore della categoria, con una
sfumatura distinta tra ricezione e produzione nelle competenze in lingua dei
segni. Queste competenze restano temporaneamente non disponibili nell’app in
attesa della validazione umana delle sottodimensioni e delle traiettorie. Il
catalogo completo usa
i livelli A1, A2, A2+, B1, B1+ e B2; i testi completi non
sono inseriti nel codice Python ma letti dal catalogo strutturato distribuito
con lo Space. Nessuna di queste funzioni usa AI durante la sessione.
