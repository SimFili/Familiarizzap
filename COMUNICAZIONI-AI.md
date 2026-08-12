# Comunicazioni fra gli assistenti AI

Registro delle modifiche fatte fuori dal codice: configurazioni, decisioni,
cose accadute su Hugging Face che non si vedono dai commit.

Lavoriamo in due (Simone e Fabio) con due AI diverse, che non vedono le
rispettive conversazioni. Questo file è il punto in cui ciò che è stato deciso
o configurato da una parte diventa visibile all'altra.

**Se sei un assistente AI: leggi questo file all'inizio della sessione.**
Quando fai una modifica che non si capisce dal codice — un secret configurato,
un servizio esterno creato, una decisione presa a voce — aggiungi una voce in
cima all'elenco, con la data.

**Nessun valore segreto in questo file.** Il repository è pubblico: password,
token e chiavi si scrivono solo nei secret dello Space, mai qui. Qui si scrive
che *esistono* e a *cosa servono*.

---

## 2026-08-12 — Mappa progressiva dei descrittori 0.5.4

La fila di pallini nell’esercizio è diventata una mappa progressiva. Il
descrittore corrente è ingrandito, quelli futuri restano pallini vuoti e quelli
conclusi mostrano il livello corretto scoperto. Colore e simbolo indicano il
percorso: `1`, `2`, `3` per il tentativo risolutivo e `!` quando la soluzione è
stata mostrata dopo tre tentativi. Una legenda testuale evita di affidare
l’informazione al solo colore. Sulle scale lunghe la mappa scorre in orizzontale
e centra automaticamente il descrittore corrente.

## 2026-08-12 — Uscita confermata dall’esercizio 0.5.3

Durante un esercizio è disponibile `Torna alla scelta della scala`. Prima di
uscire l’app chiede conferma e chiarisce che i tentativi già registrati non
vengono cancellati. Confermando, la sessione rimane incompleta e può essere
ripresa dall’elenco dedicato; annullando si continua l’esercizio corrente.

## 2026-08-12 — Identificazione sempre esplicita 0.5.2

Anche quando il browser ricorda il nome, la home mostra sempre per primo il
solo passaggio di identificazione. Il nome può essere precompilato, ma il
docente deve confermare esplicitamente prima di vedere il catalogo. I link di
ripresa continuano a funzionare: dopo la conferma aprono direttamente la
sessione richiesta.

## 2026-08-12 — Catalogo completo online e correzione della prima pagina 0.5.1

Fabio ha confermato che la prima schermata deve contenere soltanto
l’identificazione. Il quadro degli ambiti compare esclusivamente dopo che il
docente ha inserito il nome e confermato l’informativa. Sotto `Competenza
generale` sono nuovamente visibili `Sapere`, `Saper fare` e `Saper essere`, ma
come mattoncini disattivati e senza la scritta «Non ancora disponibile».

Il catalogo validato di **831 esercizi e 52 scale** viene ora distribuito come
file strutturato insieme allo Space e caricato automaticamente. Questa scelta
rende pubblici nel repository GitHub e nello Space i testi del catalogo; la
verifica dei diritti di pubblicazione resta quindi necessaria prima dell’uso
pubblico definitivo. Un Dataset Hugging Face privato rimane una possibile
migrazione futura. Il Dataset degli eventi è invece ancora da configurare per
rendere durevoli i dati dei partecipanti.

## 2026-08-12 — Distribuzione dei livelli e percorso senza “+”

Le opzioni di risposta mostrano ora il numero di descrittori della sessione per
ciascun livello, ad esempio `B2 · 2 descrittori`. Il valore registrato resta il
livello CEFR (`B2`), non l’etichetta estesa.

Prima di avviare ogni nuova scala il docente può disattivare l’opzione
`Includi anche i livelli A2+ e B1+`. In tal caso gli esercizi A2+/B1+ e i
relativi pulsanti non entrano nella sessione. La scelta viene registrata negli
eventi e rispettata anche dopo una ripresa o una ripetizione mirata. Per
impostazione predefinita i livelli “+” restano inclusi. Le modifiche fanno parte
del branch `agent/navigazione-progressiva`; diventano online soltanto dopo
l’integrazione in `main` e la pubblicazione automatica dello Space.

## 2026-08-12 — Percorso personale e catalogo completo 0.5.0

Sono state preparate localmente le correzioni della pagina `/percorso`:
contrasto esplicito in tema scuro, etichette più chiare, filtro “Da
consolidare” senza includere i descrittori mai incontrati, cronologia a schede
e ripresa diretta con un solo clic. Il nome ricordato dal browser apre home e
percorso personale senza una seconda conferma del consenso.

Il convertitore `tools/build_catalog.py` ha validato il database Excel pulito:
**831 esercizi**, **52 scale**, nessuna riga scartata e soltanto i livelli A1,
A2, A2+, B1, B1+ e B2. Le celle vuote nelle colonne intermedie vengono colmate
solo nella navigazione; i valori originali restano nei campi `source_*` e negli
eventi. Il rapporto di conversione e i dati di collaudo sono ignorati da Git.

L’app 0.5.0 può caricare il catalogo completo da `CONTENT_FILE_PATH` in locale
o da `CONTENT_REPO_ID` nello Space. La decisione successiva 0.5.1 qui sopra ha
poi autorizzato la distribuzione del file strutturato insieme allo Space; resta
aperta la verifica dei diritti sui testi.

## 2026-08-04 — Navigazione progressiva 0.4.2

Fabio ha chiesto di separare la scelta iniziale in schermate successive. La
pagina principale ora mostra, nell’ordine:

1. identificazione tramite nome e consenso;
2. quadro degli ambiti di descrittori disponibili;
3. scale appartenenti all’ambito selezionato;
4. esercizio avviato scegliendo la scala.

La decisione successiva 0.5.1 ha ripristinato le sole voci `Sapere`, `Saper
fare` e `Saper essere` come riferimenti disattivati e senza l’etichetta «Non
ancora disponibile».

La navigazione mantiene una selezione testuale accessibile, il ritorno al
livello precedente e la ripresa delle sessioni dopo l’identificazione. La
verifica locale ha incluso 32 test automatici e il percorso completo su desktop
e smartphone. Non sono stati eseguiti commit, push o deploy.

## 2026-07-30 — Pagina personale separata 0.4.1

Fabio ha chiarito che anche il riepilogo personale non deve occupare la prima
pagina. La navigazione è ora divisa in tre spazi:

- `/`: scelta della scala, identificazione e svolgimento degli esercizi;
- `/percorso`: percentuali personali, mappa completa, cronologia, dettaglio dei
  descrittori e sessioni precedenti;
- `/ricercatore`: dati complessivi di tutti i partecipanti, protetti dalla
  chiave del ricercatore.

La pagina principale mantiene soltanto un avvio compatto e il comando per
riprendere eventuali sessioni incomplete. Il nome ricordato dal browser è
condiviso con la pagina personale; non sono stati reintrodotti codici o account.
La versione applicativa diventa `0.4.1`.

La verifica ha incluso 32 test automatici, compilazione, controllo delle
dipendenze, ricerca di secret e prove funzionali e visive su desktop e mobile,
anche in tema scuro. La modifica applicativa è nel commit GitHub `deadd99` del
branch `agent/familiarizzapp-0.3`.

Il workflow “Pubblica su Hugging Face” è terminato correttamente
([run 30572861634](https://github.com/SimFili/Familiarizzap/actions/runs/30572861634)).
Lo Space è tornato **Running on Zero**. Sono state verificate online la home
senza riepilogo personale, la pagina `/percorso` con mappa e cronologia e la
pagina separata `/ricercatore`.

## 2026-07-30 — Accesso e interfaccia 0.4

Fabio ha chiesto di semplificare l’accesso per il piccolo gruppo interno e di
correggere la struttura dell’interfaccia. Questa decisione sostituisce la logica
dei codici personali descritta nella voce 0.3 più sotto.

- Il docente inserisce soltanto il nome, senza cognome né codice.
- Il nome normalizzato genera tramite HMAC l’identificativo deterministico del
  percorso: lo stesso nome recupera lo stesso percorso anche da un altro
  dispositivo.
- Non è autenticazione. Gli omonimi condividono il percorso e chi conosce il
  nome può aprirlo; il rischio è accettato soltanto per circa dieci persone
  conosciute e va rivalutato prima di un uso pubblico o con dati sensibili.
- La pagina principale apre con lo schema descrittivo e con le scale
  disponibili. I colori sono fissati esplicitamente anche in tema scuro.
- La panoramica del ricercatore non è più una scheda nella pagina del docente:
  si trova nella pagina separata `/ricercatore`.
- Resta un solo secret, `RESEARCHER_ACCESS_KEY`, necessario perché la pagina
  riservata mostra nomi e percorsi di tutti i partecipanti.
- Schede dei descrittori, mappe e selettori sono stati adattati agli schermi
  stretti e non dipendono dai colori automatici del tema Gradio.

La versione applicativa è `0.4.0`. La verifica ha incluso 31 test automatici,
compilazione, controllo delle dipendenze, ricerca di secret, prova funzionale e
visiva su desktop e smartphone in tema chiaro e scuro. La modifica è nel commit
GitHub `2261947` del branch `agent/familiarizzapp-0.3`.

Il workflow “Pubblica su Hugging Face” è terminato correttamente
([run 30571293979](https://github.com/SimFili/Familiarizzap/actions/runs/30571293979)).
Lo Space è tornato **Running on Zero** e sono state verificate online sia la
pagina principale sia `/ricercatore`.

## 2026-07-30 — Percorso longitudinale e dashboard di ricerca 0.3

Fabio ha stabilito che l’app deve permettere sia al docente sia al ricercatore
di ricostruire il miglioramento nel tempo senza perdere o sostituire gli esiti
precedenti. È stata quindi implementata localmente una nuova architettura
funzionale:

- ogni accesso, esposizione, risposta e completamento aggiunge un evento
  immutabile;
- i nuovi eventi usano lo schema `2.0` e registrano fotografia del descrittore,
  numero dell’esposizione, distanza dal target, tempi server e versioni;
- gli eventi `1.0` già esistenti restano leggibili;
- le ripetizioni dello stesso descrittore sono riconoscibili e separate;
- mappe, percentuali e dashboard sono calcolate dagli eventi originali e
  possono essere ricostruite in futuro con criteri diversi.

Il docente riceve al primo accesso un codice personale di 12 caratteri. Il
codice può essere ricordato dal browser e permette di recuperare il percorso da
un altro dispositivo; nel Dataset viene salvato soltanto il suo hash. Se viene
perso, il ricercatore può sostituirlo: il reset viene registrato e invalida il
codice precedente.

I nuovi `participant_id` sono casuali. Un HMAC separato del nome serve soltanto
a trovare i profili candidati: in questo modo due omonimi possono avere percorsi
distinti e selezionarli tramite codici diversi. I vecchi identificativi derivati
dal nome restano compatibili.

Il riepilogo della sessione e il percorso personale ora includono:

- percentuale e conteggio dei descrittori riconosciuti al primo tentativo;
- barra proporzionale senza punteggio composito;
- mappa completa della scala, ordinata dai livelli più alti ai più bassi;
- verde scuro, verde chiaro, giallo, rosso chiaro e grigio, sempre con
  etichette testuali;
- schede cliccabili con risposte in sequenza, livello target, motivazione e
  cronologia;
- filtri `Mostra tutto`, `Concentrati`, `Da rivedere` e `Mai incontrati`;
- ripetizione selettiva dei descrittori da consolidare;
- date relative per il docente.

La dashboard del ricercatore include tutti i partecipanti, sessioni complete e
interrotte, tentativi, distanze, esposizioni, tempi, feedback mostrati,
revisioni, timestamp esatti in ora italiana e UTC, filtri per persona, scala e
periodo, registro degli eventi, controllo d’integrità e archivio ZIP con CSV,
JSONL e manifest. L’esportazione non contiene gli hash dei codici personali.

La navigazione iniziale riproduce in HTML il quadro a colori concordato:
categorie presenti nel catalogo cliccabili e categorie non ancora disponibili
attenuate. Per la prova 2.0 il ramo disponibile conduce alle tre scale di
ricezione.

Tutte queste funzioni sono deterministiche e non chiamano modelli AI durante
l’uso. La verifica locale è stata eseguita in tema chiaro e scuro, su desktop e
smartphone. I test automatici sono stati estesi. Non è stato eseguito alcun
commit, push o deploy.

## 2026-07-30 — Prima scala con feedback specifici

Fabio ha approvato lo stile editoriale proposto per i feedback. Per gli 8
descrittori della scala `Comprensione orale generale` sono stati preparati e
inseriti nel catalogo dimostrativo:

- un primo suggerimento che indica gli aspetti da osservare senza rivelare il
  livello;
- un secondo suggerimento più selettivo, concentrato sui confini con i livelli
  vicini;
- una motivazione finale che dichiara il livello e spiega gli elementi
  discriminanti.

Sono quindi presenti **24 testi specifici**. Le altre due scale della prova 2.0
mantengono per ora i feedback generici provvisori. Nel catalogo dimostrativo è
stato corretto anche il refuso `in un varietà` → `in una varietà`; il file Excel
originale non è stato modificato.

Fabio ha inoltre comunicato un risultato del suo studio recente sulla distanza
degli errori CEFR: 68% di risposte corrette, 28% a una posizione dal target, 3%
a due posizioni e 1% a tre posizioni. Considerando le sole risposte errate,
quasi tutte si collocano quindi a una o due posizioni dal livello corretto.
Questo dato orienta i feedback soprattutto verso la distinzione fra livelli
adiacenti, invece che verso confronti con livelli molto lontani.

Il feedback attuale resta specifico per descrittore ma non cambia ancora in base
alla risposta errata selezionata. Un eventuale suggerimento differenziato per
errore verso l’alto o verso il basso richiede una decisione pedagogica separata.

Queste modifiche sono locali; non è stato eseguito alcun commit, push o deploy.

## 2026-07-30 — Catalogo dimostrativo 2.0: tre scale di ricezione

Fabio ha scelto di preparare una versione intermedia dell’app con una scala per
ciascuna delle tre sottocategorie delle attività di ricezione:

- `Comprensione orale` → `Comprensione orale generale`: 8 descrittori;
- `Comprensione audiovisiva` → `Guardare la tv, film e video`: 9 descrittori;
- `Comprensione scritta` → `Comprensione generale di un testo scritto`: 5
  descrittori.

In totale il catalogo dimostrativo 2.0 contiene **22 esercizi**, estratti dalle
colonne B–G del file Excel del gruppo di ricerca. I livelli restano quelli
presenti in ciascuna scala: la scala di comprensione scritta non contiene
`B1+`, quindi quel pulsante non deve comparire in quella sessione.

Inizialmente le motivazioni e i due suggerimenti erano testi generici
provvisori. La scala `Comprensione orale generale` dispone ora dei feedback
specifici descritti nella voce più recente; le altre due scale devono ancora
essere revisionate. La provenienza e i diritti di pubblicazione dei descrittori
devono essere verificati prima di pubblicare questa versione su GitHub o
Hugging Face.

La navigazione concordata mantiene distinti nei dati `Attività` e `Strategie`,
ma può riunirli nella stessa vista della modalità `Ricezione`, aprendo in
evidenza il ramo da cui arriva l’utente.

Queste modifiche sono state preparate localmente; nessun commit, push o deploy
è implicito in questa voce.

## 2026-07-30 — Contrasto in tema scuro e confini del catalogo demo

Fabio ha confermato che il livello `C1` può rimanere nel catalogo
**esclusivamente dimostrativo**. Il futuro catalogo reale continuerà invece ad
ammettere soltanto `A1`, `A2`, `A2+`, `B1`, `B1+` e `B2`.

È stato corretto un problema di leggibilità su telefoni e computer impostati
con il tema scuro: il tema di Gradio rendeva quasi bianco il testo delle schede
che conservavano uno sfondo chiaro. Gli stili ora fissano esplicitamente colori
ad alto contrasto per intestazione e descrittori, senza disattivare il tema
scuro. È stato anche eliminato lo scorrimento orizzontale prodotto dal
contenitore principale sugli schermi stretti.

La verifica locale è stata eseguita sia in tema chiaro sia in tema scuro, anche
con una larghezza da smartphone. Il contrasto misurato nella scheda del
descrittore è **13,42:1**. Sono stati aggiunti test automatici per impedire che
le regole essenziali vengano rimosse accidentalmente.

## 2026-07-30 — Catalogo CEFR reale ripulito e regole confermate

Fabio ha completato una prima pulizia del database Excel reale dei descrittori.
Sono state eliminate interamente **15 righe** contenenti
`Nessun descrittore`; restano **831 righe valide**. Il file Excel pulito è
ancora conservato localmente e **non è stato caricato nel repository né nello
Space**.

Per la futura conversione in `catalog.json` valgono queste regole:

- colonna G: testo del descrittore mostrato nell'esercizio;
- colonna F: livello corretto;
- colonna E: scala;
- colonne B, C e D: gerarchia usata per la navigazione;
- ogni riga valida genera un esercizio;
- descrittori diversi dello stesso livello restano esercizi distinti;
- i pulsanti mostrano una sola volta i livelli presenti nella scala scelta;
- livelli ammessi e ordine: `A1`, `A2`, `A2+`, `B1`, `B1+`, `B2`;
- `A2+` e `B1+` sono livelli autonomi;
- `C1`, `C2` e qualsiasi altro livello non sono ammessi;
- il livello corretto proviene dal catalogo approvato, mai da un modello AI.

Resta aperta una decisione pedagogica: usare tutti i descrittori di una scala
oppure proporre prima un percorso base con un descrittore per livello e poi un
approfondimento. Finché questa decisione e le autorizzazioni sui contenuti non
sono confermate, il catalogo dimostrativo non deve essere sostituito.

## 2026-07-30 — Secret configurati sullo Space

Sono stati impostati due secret nello Space `Sibucs/Familiarizzap`
(Settings → Variables and secrets). Nel codice si leggono da
[space/src/settings.py](space/src/settings.py).

**`RESEARCHER_ACCESS_KEY`** — password che apre il pannello con la panoramica
dei partecipanti. Senza di essa quel pannello resta disattivato
([space/app.py:636](space/app.py:636)). Il valore è scelto da Simone e non è
scritto da nessuna parte nel repository: chi ha bisogno di usarlo se lo fa dare
da lui per via privata.

**`PARTICIPANT_HASH_SALT`** — stringa casuale di 64 caratteri usata da
[space/src/auth.py](space/src/auth.py) per trasformare nome e cognome dei
partecipanti in una chiave di ricerca irreversibile (HMAC-SHA256) e verificare
il codice personale. Il nome compare una sola volta nel registro privato dei
partecipanti; gli eventi contengono soltanto l’identificativo casuale
pseudonimo.

> **Da non cambiare più** una volta raccolti dati reali: un salt diverso
> produce codici diversi per le stesse persone e spezza la continuità dei dati
> già registrati.

Manca ancora `HF_DATA_TOKEN`, e con esso i due Dataset privati (catalogo
approvato e registro eventi). Finché non ci sono, l'app resta in **modalità
dimostrativa**: funziona, ma gli eventi non vengono conservati e l'interfaccia
lo dichiara.

## 2026-07-30 — L'app si chiama «FamiliarizzApp»

Il nome visibile confermato è `FamiliarizzApp`, con la `A` finale maiuscola,
nei punti visibili agli utenti: header di Hugging Face, titolo della scheda del
browser e intestazione dell'interfaccia.

Gli identificatori tecnici restano **con una sola «p»** e non vanno toccati,
perché cambiarli romperebbe il collegamento fra GitHub e Hugging Face:

- Space Hugging Face: `Sibucs/Familiarizzap`
- Repository GitHub: `SimFili/Familiarizzap`
