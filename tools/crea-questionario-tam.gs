/**
 * Crea su Google Moduli il questionario di valutazione di FamiliarizzApp.
 *
 * Impianto: Technology Acceptance Model (Davis, 1989), in forma breve.
 * Davis valida due scale da sei item; qui se ne usano quattro per costrutto,
 * come in TAM2 e UTAUT, che è la prassi negli studi applicativi: l'affidabilità
 * regge e il questionario resta sotto i dieci minuti. Sotto i tre item per
 * costrutto non sarebbe più difendibile.
 *
 * Struttura e tono ricalcano il questionario già usato per l'altra valutazione
 * esplorativa, così i due studi restano confrontabili.
 *
 * Gli item sono al passato/presente e non al condizionale: i rispondenti l'app
 * l'hanno già usata, quindi non stimano un uso futuro.
 *
 * COME USARLO
 * 1. Vai su https://script.google.com e crea un nuovo progetto.
 * 2. Cancella il contenuto di Codice.gs e incolla tutto questo file.
 * 3. Salva, scegli la funzione creaQuestionario, premi Esegui.
 * 4. Autorizza lo script quando Google lo chiede (serve solo a creare il modulo).
 * 5. Nel registro di esecuzione trovi i due link: modifica e compilazione.
 */

var ACCORDO_MIN = "per nulla d'accordo";
var ACCORDO_MAX = "completamente d'accordo";

function creaQuestionario() {
  var form = FormApp.create("Valutazione esplorativa di FamiliarizzApp");

  form.setDescription(
    "Questionario rivolto a docenti di lingua dei segni dopo una prova di FamiliarizzApp, " +
    "lo strumento per familiarizzare con i descrittori e i livelli del QCER.\n\n" +
    "Obiettivo: raccogliere valutazioni esplorative su facilità d'uso, utilità percepita, " +
    "qualità dei feedback e intenzione d'uso.\n\n" +
    "Tempo stimato: 7-8 minuti. La partecipazione è volontaria; non vengono richiesti nome, " +
    "istituzione o luogo di lavoro. Le risposte saranno analizzate in forma aggregata e potranno " +
    "essere utilizzate per finalità di ricerca e pubblicazione scientifica. È possibile " +
    "interrompere la compilazione in qualsiasi momento prima dell'invio."
  );

  form.setProgressBar(true);
  form.setCollectEmail(false);

  // --- Consenso ------------------------------------------------------------

  form.addCheckboxItem()
    .setTitle("Consenso alla partecipazione")
    .setChoiceValues([
      "Acconsento volontariamente a partecipare e all'uso anonimo e aggregato delle mie " +
      "risposte per finalità di ricerca e pubblicazione."
    ])
    .setRequired(true);

  // --- Profilo -------------------------------------------------------------

  sezione(form, "Il tuo profilo",
    "Tre domande di inquadramento. Nessuna permette di identificarti.");

  form.addMultipleChoiceItem()
    .setTitle("Da quanti anni insegni lingua dei segni?")
    .setChoiceValues(["Meno di 1 anno", "1-3 anni", "4-10 anni", "Più di 10 anni"])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle("In quale contesto insegni? (seleziona tutte le opzioni pertinenti)")
    .setChoiceValues([
      "Corsi per adulti",
      "Scuola",
      "Università",
      "Formazione di interpreti",
      "Corsi privati o individuali",
      "Associazioni ed enti del terzo settore"
    ])
    .showOtherOption(true)
    .setRequired(true);

  scala(form, "Prima di questa prova, quanto conoscevi il QCER e i suoi descrittori?",
    "per nulla", "molto bene");

  // --- Utilità percepita — Davis (1989), forma breve a quattro item ---------

  sezione(form, "Utilità dello strumento",
    "Rispondi pensando a quello che hai visto in questa prova. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");

  [
    "Usare FamiliarizzApp mi permetterebbe di orientarmi più rapidamente tra i livelli del QCER.",
    "Usare FamiliarizzApp renderebbe più efficace il mio modo di riconoscere il livello di un descrittore.",
    "Usare FamiliarizzApp renderebbe più facile il mio lavoro con il QCER.",
    "Nel complesso, troverei FamiliarizzApp utile per la mia attività didattica."
  ].forEach(function (testo) { accordo(form, testo); });

  // --- Facilità d'uso percepita — Davis (1989), forma breve -----------------

  sezione(form, "Facilità d'uso",
    "Rispondi pensando a quello che hai visto in questa prova. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");

  [
    "Imparare a usare FamiliarizzApp è stato facile per me.",
    "La mia interazione con FamiliarizzApp è stata chiara e comprensibile.",
    "Credo che mi sarebbe facile diventare abile nell'uso di FamiliarizzApp.",
    "Nel complesso, trovo FamiliarizzApp facile da usare."
  ].forEach(function (testo) { accordo(form, testo); });

  // --- Intenzione d'uso ----------------------------------------------------

  sezione(form, "Intenzione d'uso",
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");

  [
    "Ho intenzione di usare di nuovo FamiliarizzApp nei prossimi mesi.",
    "Consiglierei FamiliarizzApp a un collega che insegna lingua dei segni."
  ].forEach(function (testo) { accordo(form, testo); });

  // --- Contenuti, feedback e apprendimento percepito ------------------------

  sezione(form, "Descrittori e feedback",
    "Questa parte riguarda i contenuti dell'esercizio, non l'interfaccia. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");

  [
    "I testi dei descrittori proposti erano comprensibili.",
    "I feedback ricevuti dopo un tentativo mi hanno aiutato a capire perché il livello era quello.",
    "Dopo questa prova mi sento più sicuro nel riconoscere il livello QCER di un descrittore.",
    "I descrittori del QCER, pensati per le lingue vocali, mi sembrano applicabili alla lingua dei segni."
  ].forEach(function (testo) { accordo(form, testo); });

  // --- Domande aperte ------------------------------------------------------

  sezione(form, "Le tue parole",
    "Tre domande aperte. Rispondi liberamente, anche in poche righe.");

  aperta(form, "Qual è l'aspetto più utile dello strumento per la tua pratica didattica?", true);

  aperta(form, "Qual è la principale criticità o difficoltà che hai incontrato? " +
    "Se riguarda l'applicazione dei descrittori alla lingua dei segni, scrivilo qui.", true);

  aperta(form, "Ulteriori commenti liberi", false);

  form.setConfirmationMessage("Grazie della collaborazione!");

  Logger.log("Modulo creato.");
  Logger.log("Modifica:     " + form.getEditUrl());
  Logger.log("Compilazione: " + form.getPublishedUrl());
}

// --- Funzioni di servizio ---------------------------------------------------

function sezione(form, titolo, aiuto) {
  form.addPageBreakItem().setTitle(titolo).setHelpText(aiuto);
}

function accordo(form, testo) {
  scala(form, testo, ACCORDO_MIN, ACCORDO_MAX);
}

function scala(form, testo, etichettaMin, etichettaMax) {
  form.addScaleItem()
    .setTitle(testo)
    .setBounds(1, 5)
    .setLabels(etichettaMin, etichettaMax)
    .setRequired(true);
}

function aperta(form, testo, obbligatoria) {
  form.addParagraphTextItem().setTitle(testo).setRequired(obbligatoria);
}
