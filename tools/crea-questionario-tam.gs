/**
 * Crea su Google Moduli la copia esterna del questionario finale di
 * FamiliarizzApp. Il testo coincide con il questionario integrato nell'app.
 *
 * COME USARLO
 * 1. Vai su https://script.google.com e crea un nuovo progetto.
 * 2. Cancella il contenuto di Codice.gs e incolla tutto questo file.
 * 3. Salva, scegli la funzione creaQuestionario, premi Esegui.
 * 4. Autorizza lo script quando Google lo chiede.
 * 5. Nel registro di esecuzione trovi i link di modifica e compilazione.
 */

var ACCORDO_MIN = "per nulla d'accordo";
var ACCORDO_MAX = "completamente d'accordo";

function creaQuestionario() {
  var form = FormApp.create("Valutazione esplorativa di FamiliarizzApp");

  form.setDescription(
    "Questionario rivolto a docenti di LIS dopo il completamento del percorso " +
    "consigliato di FamiliarizzApp, lo strumento per familiarizzare con i " +
    "descrittori e i livelli del QCER.\n\n" +
    "Obiettivo: raccogliere valutazioni esplorative su facilità d'uso, utilità " +
    "percepita, qualità dei feedback e intenzione d'uso.\n\n" +
    "Tempo stimato: 6-8 minuti. Non vengono richiesti istituzione o luogo di " +
    "lavoro. Le risposte saranno analizzate in forma aggregata. Per concludere " +
    "il pilot è necessario rispondere agli item chiusi; le due domande aperte " +
    "sono facoltative."
  );

  form.setProgressBar(true);
  form.setCollectEmail(false);

  form.addCheckboxItem()
    .setTitle("Consenso alla raccolta dei dati")
    .setChoiceValues([
      "Acconsento alla raccolta e al trattamento delle risposte fornite in " +
      "questo questionario, in forma pseudonimizzata e aggregata, per finalità " +
      "di ricerca e pubblicazione scientifica."
    ])
    .setRequired(true);

  sezione(form, "Il tuo profilo", "Tre domande di inquadramento.");
  scala(form,
    "1. Prima di questa prova, quanto conoscevi il QCER e i suoi descrittori?",
    "per nulla", "molto bene");

  form.addMultipleChoiceItem()
    .setTitle("2. Da quanti anni insegni LIS?")
    .setChoiceValues(["Meno di 1 anno", "1-3 anni", "4-10 anni", "Più di 10 anni"])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle("3. In quale contesto insegni? (seleziona tutte le opzioni pertinenti)")
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

  sezione(form, "Utilità dello strumento",
    "Rispondi pensando a quello che hai visto in questa prova. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");
  [
    "4. Usare FamiliarizzApp mi permetterebbe di orientarmi più rapidamente tra i livelli del QCER.",
    "5. Usare FamiliarizzApp renderebbe più efficace il mio modo di riconoscere il livello di un descrittore.",
    "6. Usare FamiliarizzApp renderebbe più facile il mio lavoro con il QCER."
  ].forEach(function (testo) { accordo(form, testo); });

  sezione(form, "Facilità d'uso",
    "Rispondi pensando a quello che hai visto in questa prova. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");
  [
    "7. Imparare a usare FamiliarizzApp è stato difficile per me.",
    "8. La mia interazione con FamiliarizzApp è stata chiara e comprensibile.",
    "9. Credo che per me sarebbe facile acquisire dimestichezza nell'uso di FamiliarizzApp.",
    "10. Nel complesso, trovo FamiliarizzApp facile da usare."
  ].forEach(function (testo) { accordo(form, testo); });

  sezione(form, "Intenzione d'uso",
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");
  [
    "11. Ho intenzione di usare di nuovo FamiliarizzApp nei prossimi mesi.",
    "12. Consiglierei FamiliarizzApp a un/a collega che insegna LIS."
  ].forEach(function (testo) { accordo(form, testo); });

  sezione(form, "Feedback e familiarizzazione",
    "Questa parte riguarda i feedback ricevuti e il percorso di familiarizzazione. " +
    "(1 = per nulla d'accordo; 5 = completamente d'accordo)");
  [
    "13. I feedback ricevuti dopo un tentativo mi hanno aiutato a capire perché il livello era quello.",
    "14. Dopo questa prova mi sento più sicuro/a nel riconoscere il livello QCER di un descrittore."
  ].forEach(function (testo) { accordo(form, testo); });

  sezione(form, "Le tue parole",
    "Due domande aperte facoltative. Rispondi liberamente, anche in poche righe.");
  aperta(form,
    "15. Quali problemi hai trovato usando FamiliarizzApp? Segnalaceli, proveremo a risolverli.",
    false);
  aperta(form,
    "16. Ci sono lati positivi dell'applicazione che vuoi sottolineare?",
    false);

  form.setConfirmationMessage("Grazie della collaborazione!");
  Logger.log("Modulo creato.");
  Logger.log("Modifica:     " + form.getEditUrl());
  Logger.log("Compilazione: " + form.getPublishedUrl());
}

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
