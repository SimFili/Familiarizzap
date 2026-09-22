# Feedback ragionati: tre scale campione

Stato: **bozza editoriale da discutere e validare; non pubblicata**. I testi
sono associati ai descrittori originali delle scale «Comprensione orale
generale», «Produzione orale generale» e «Interazione orale generale» nel catalogo
`space/data/catalog.full.json`. ID, livello, impronta del testo e frammenti
letterali sono controllati prima dell'uso. Le proposte sono in
`space/data/feedback.descriptor_guides.json`.

## Come cambia il feedback

1. Dopo il primo errore, una domanda porta l'attenzione su azione, contenuto
   o condizione del descrittore. Nella scala «Interazione orale generale» la
   domanda cambia anche in base al livello scelto. Non anticipa il livello.
2. Dopo il secondo errore, il confronto riguarda **il livello scelto in quel
   tentativo**, usando un descrittore reale della stessa scala. Ogni livello
   effettivamente disponibile ha un confronto distinto.
3. Alla conclusione, una breve motivazione riprende una scelta effettiva del
   docente. Se l'ultimo tentativo è sbagliato, confronta proprio quel livello;
   se la risposta viene corretta dopo un errore, riprende un livello sbagliato
   non già confrontato nel suggerimento precedente. La risposta esatta al
   primo tentativo riceve comunque una spiegazione: può essere fortunata.
4. Sullo schermo compare solo il suggerimento più recente; la cronologia
   completa dei tentativi resta registrata. Nessun suggerimento apre con
   «Non ancora.».

Esempio per `SRC-9`, se il docente sceglie prima A2 e poi B2:

- Primo errore: «Hai scelto A2. Il risultato richiesto è un dato isolato, i
  punti salienti o seguire un discorso lungo? Conta anche la familiarità dei
  temi.»
- Secondo errore: «Confronta con B2: lì si segue un discorso lungo e
  argomentazioni complesse; qui bastano i punti salienti di un discorso
  chiaro.»
- Conclusione: «Esatto: B1. Confronta con A2: lì si comprendono espressioni di
  priorità immediata, non i punti salienti di un discorso.»

I confronti di questo esempio si appoggiano, rispettivamente, a `SRC-11`
(A2) e `SRC-7` (B2). Sono confronti **interni a questa scala**, non regole
generali che associano una singola parola a un livello.

Esempio per `SRC-408` («Interazione orale generale»), con A2+ seguito da B1+:

- Primo errore: «Hai scelto A2+. Le situazioni sono solo strutturate e
  prevedibili, o la persona interviene senza preparazione?»
- Secondo errore: «Confronta con B1+: lì si affrontano anche situazioni meno
  frequenti e temi più astratti; qui prevalgono questioni familiari e vita
  quotidiana.»
- Conclusione: «Esatto: B1. Confronta con A2+: lì l'interazione è breve e
  strutturata, con eventuale collaborazione; qui si interviene senza
  preparazione su temi familiari.»

## Verifica prima di estendere il metodo

Nella prima scala, per ciascuno degli otto descrittori sono stati preparati
cinque confronti: uno per ogni livello sbagliato possibile. Nella seconda,
quattro descrittori hanno tre confronti ciascuno, perché i livelli disponibili
sono A1, A2, B1 e B2. Per `SRC-230` (B1), ad esempio, il confronto con A2
considera l'elenco di frasi semplici, mentre quello con B2 considera le idee
sviluppate e sostenute da esempi. Nella terza scala, sei descrittori hanno
cinque confronti ciascuno; anche il primo indizio distingue fra i cinque
livelli sbagliati possibili. Il controllo automatico verifica
che il descrittore di confronto appartenga alla stessa scala e abbia proprio
il livello selezionato. Verifica anche che i primi due messaggi non rivelino
il livello corretto, siano distinti e restino brevi. Questo non sostituisce
la valutazione pedagogica dei testi.

Chiediamo di valutare soprattutto:

- se il confronto identifica una differenza realmente utile, senza attribuire
  a un intero livello una proprietà attestata solo in un descrittore;
- se il primo suggerimento orienta senza rendere l'esercizio banale;
- se il secondo tiene conto in modo convincente della risposta scelta;
- se la spiegazione finale è corretta, accessibile e non troppo lunga;
- se la progressione dei suggerimenti cambia davvero il ragionamento.

La bozza resta disattivata nell'esplorazione libera per impostazione
predefinita. Può essere provata per tutte e tre le scale in locale con
`FAMILIARIZZAPP_DRAFT_FEEDBACK=1`. Un'eccezione locale è il percorso
consigliato iniziale: vi vengono usate le guide dei suoi **16 descrittori
selezionati**, comprese quattro formulazioni della Scala generale QCER
fornite nell'immagine del ricercatore. Il file contiene quindi **21 guide
utilizzabili nella prova locale**: 17 per le tre scale del catalogo e 4 per la
nuova scala introduttiva. La guida di `SRC-10` è sospesa: il confronto A2/A2+
non è stato giudicato sufficientemente distintivo e il descrittore resta nel
catalogo. Nessuna
di queste modifiche è stata ancora inviata allo Space. Per gli altri, il vecchio materiale non è ancora stato
riscritto: non presentiamo queste scale campione come revisione completa dei
feedback né come via libera al pilot.

Per il pilot locale, A2+ e B1+ sono sospesi anche nell'esplorazione libera.
Le 16 guide della sequenza consigliata restano attive solo in quella sequenza;
nelle altre scale esercitabili sono operativi 14 indizi prevalidati e cinque
spiegazioni editoriali specifiche, ma non guide comparative complete. Le sei
motivazioni-segnaposto ancora presenti nel catalogo non vengono più mostrate
come spiegazioni: l'app usa una domanda di riflessione. Le altre scale sono
indicate esplicitamente come facoltative e con feedback ancora essenziali.
