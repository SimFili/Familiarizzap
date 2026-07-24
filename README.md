# Familiarizzap

> Descrizione dell'app da inserire.

**App online:** https://huggingface.co/spaces/Sibucs/Familiarizzap

## Com'è organizzato il repo

```
space/      Ciò che viene pubblicato online (l'app vera e propria)
.github/    Automazione di pubblicazione
```

Tutto quello che sta **fuori** da `space/` — appunti, documentazione, materiali di
lavoro — resta nel repo e non finisce nell'app pubblicata.

## Come si lavora

Si lavora **solo qui su GitHub**. Lo Space Hugging Face è la vetrina: si aggiorna da
solo e non va modificato a mano (le modifiche fatte là vengono sovrascritte).

```bash
git pull            # prendi le novità dell'altro
# ...modifiche...
git add -A && git commit -m "cosa ho fatto"
git push            # manda le tue
```

Quando il push tocca `space/`, GitHub Actions pubblica sullo Space in circa un minuto.
Lo stato delle pubblicazioni si vede nel tab **Actions**.

## Regole

- **Nessuna chiave API nei file.** Vanno nei secret: quelle che servono all'app mentre
  gira nei *secret dello Space* (HF → Settings → Variables and secrets), quelle che
  servono alla pubblicazione nei *secret di GitHub*. Il repo è pubblico.
- Un **branch per funzionalità** e Pull Request per integrare, così l'altro vede cosa
  cambia prima che entri in `main`.
- Le decisioni di progetto si scrivono nei file del repo, non solo nella chat con l'AI:
  è l'unica memoria che vediamo entrambi.

## Note operative

Lo Space gira su hardware **ZeroGPU** (`zero-a10g`), l'unica configurazione gratuita
per gli Space Gradio. ZeroGPU rifiuta l'avvio se non trova una funzione dichiarata
`@spaces.GPU`: quando arriverà `space/app.py` servirà una sonda dichiarativa, anche se
l'app non fa calcolo su GPU.
