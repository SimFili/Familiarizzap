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
partecipanti in un codice irreversibile (HMAC-SHA256). Serve a non conservare
mai i nomi in chiaro: dal codice non si risale alla persona, ma la stessa
persona ottiene sempre lo stesso codice, così si può seguirne il percorso.

> **Da non cambiare più** una volta raccolti dati reali: un salt diverso
> produce codici diversi per le stesse persone e spezza la continuità dei dati
> già registrati.

Manca ancora `HF_DATA_TOKEN`, e con esso i due Dataset privati (catalogo
approvato e registro eventi). Finché non ci sono, l'app resta in **modalità
dimostrativa**: funziona, ma gli eventi non vengono conservati e l'interfaccia
lo dichiara.

## 2026-07-30 — L'app si chiama «Familiarizzapp»

Rinominata con due «p» nei punti visibili agli utenti: header di Hugging Face,
titolo della scheda del browser, intestazione dell'interfaccia.

Gli identificatori tecnici restano **con una sola «p»** e non vanno toccati,
perché cambiarli romperebbe il collegamento fra GitHub e Hugging Face:

- Space Hugging Face: `Sibucs/Familiarizzap`
- Repository GitHub: `SimFili/Familiarizzap`
