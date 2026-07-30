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

Il catalogo incluso è la prova dimostrativa 2.0: contiene una scala per ciascuna
delle tre sottocategorie di ricezione (orale, audiovisiva e scritta). I feedback
sono provvisori e i diritti di pubblicazione dei testi devono essere verificati
prima dell’uso pubblico. Quando Dataset e secret non sono configurati,
l’interfaccia segnala che gli eventi non sono durevoli.

La versione 0.4.1 apre con lo schema descrittivo a colori, identifica il
percorso con il solo nome e colloca percentuali, mappa e cronologia nella pagina
personale separata `/percorso`. La panoramica del ricercatore resta nella pagina
riservata `/ricercatore`. Conserva inoltre una cronologia longitudinale a eventi
immutabili, mostra riepiloghi cliccabili ed è ottimizzata per smartphone e tema
scuro. Nessuna di queste funzioni usa AI durante la sessione.
