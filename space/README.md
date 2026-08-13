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

App di familiarizzazione con descrittori e livelli CEFR per docenti di lingua
dei segni.

Il codice viene pubblicato automaticamente da
[GitHub](https://github.com/SimFili/Familiarizzap). Non modificare i file
direttamente nello Space: ogni modifica verrebbe sovrascritta alla pubblicazione
successiva.

Il catalogo incluso contiene 831 esercizi appartenenti a 52 scale. I feedback
sono provvisori e i diritti di pubblicazione dei testi devono essere verificati
prima dell’uso pubblico. Quando il Dataset degli eventi e i secret non sono
configurati, l’interfaccia segnala che gli eventi non sono durevoli.

La versione 0.7.0 separa la navigazione in passaggi successivi: prima
l’identificazione, poi gli ambiti disponibili e infine le scale dell’ambito
scelto. Percentuali, mappa e cronologia restano nella pagina personale separata
`/percorso`; la panoramica del ricercatore resta nella pagina riservata
`/ricercatore`. L’app conserva inoltre una cronologia longitudinale a eventi
immutabili, mostra riepiloghi cliccabili ed è ottimizzata per smartphone e tema
scuro. La cronologia personale usa schede leggibili e consente di riprendere
direttamente una sessione in corso. Le opzioni di risposta indicano quanti
descrittori della scala appartengono a ciascun livello. Il percorso decide
automaticamente la progressione: comincia dai livelli canonici presenti,
introduce la varietà interna e solo dopo aggiunge A2+ e B1+ con i livelli
vicini; in seguito ripropone anche gli elementi riconosciuti subito per ridurre
l’effetto del guessing. Le scale mantengono il colore della categoria, con una
sfumatura distinta tra ricezione e produzione nelle competenze in lingua dei
segni. Queste competenze restano temporaneamente non disponibili nell’app in
attesa della validazione umana delle sottodimensioni e delle traiettorie. Il
catalogo completo usa
i livelli A1, A2, A2+, B1, B1+ e B2; i testi completi non
sono inseriti nel codice Python ma letti dal catalogo strutturato distribuito
con lo Space. Nessuna di queste funzioni usa AI durante la sessione.
