# ADR-007: Deploy su Vercel (frontend) + Railway (backend)

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

Radice necessita di un ambiente di deployment per backend (Django + Celery + Postgres + Redis), frontend (Next.js PWA), e storage media. Il maintainer già possiede account attivi su:

- **GitHub** (repo, Actions, Container Registry)
- **Vercel Hobby plan** (gratuito per uso personale)
- **Railway Hobby plan** ($5/mese di credito incluso)
- **AWS** (disponibile se necessario)

Il pilastro "longevità decennale" impone di evitare lock-in forti e dipendenze da servizi proprietari che possano sparire o diventare inaccettabilmente costosi.

## Opzioni valutate

### Opzione 1: Self-hosted su VPS Hetzner
Tutto su un VPS (o due: app + monitoring) con Docker Compose.

Pro:
- Controllo totale, nessun vendor lock-in applicativo
- Costi prevedibili e bassi (~8-15€/mese per istanza CX32 + monitoring)
- Skill-building per operations
- Stesso stack in dev e prod (Docker Compose)

Contro:
- Sysadmin overhead non trascurabile (aggiornamenti OS, backup, security patches, TLS renewal)
- Single point of failure se non configurato con ridondanza
- Tempo sottratto allo sviluppo soprattutto nelle fasi iniziali
- Ruba energia per un problema non core

### Opzione 2: Vercel + Railway (managed)
Frontend Next.js su Vercel Hobby, backend + DB + Redis + workers su Railway Hobby.

Pro:
- Zero overhead operazionale: deploy con git push, TLS automatico, backup Postgres inclusi
- Costi reali per Radice familiare: **~0-3€/mese** (dentro credito Railway)
- Scaling verticale automatico
- Tempo focalizzato sullo sviluppo, non sull'infra
- Vercel è la casa di Next.js: preview deployments, edge CDN, ottimizzazioni nativi
- Railway DX eccellente, molto sviluppator-friendly
- Docker Compose in dev replica il setup production

Contro:
- Vendor lock-in parziale (anche se non tecnico: il codice è portabile)
- Vercel Hobby vieta uso commerciale (non un problema finché Radice è familiare)
- Railway è una startup — longevità aziendale meno certa di AWS/Google
- Costi scalano male se arrivi a scala commerciale (Vercel Pro 20$/mese, Railway usage-based)

### Opzione 3: AWS (ECS Fargate + RDS + ElastiCache + Amplify)
Stack AWS completo.

Pro:
- Massima maturità, infinita scalabilità
- Servizi integrati (SES per email, Rekognition, ecc.)
- Longevità aziendale certissima

Contro:
- **Complessità enorme** per un progetto personale
- Costi alti anche a bassa scala (~50-100$/mese per setup decente)
- DX pesante: IAM, VPC, Route53, CloudFront
- Overkill per target "app familiare"

### Opzione 4: Mix managed (Vercel + AWS RDS + AWS ECS)
Frontend managed, backend AWS.

Pro:
- Backend robusto

Contro:
- Peggio dei due mondi: complessità AWS + dipendenza Vercel

## Decisione

**Vercel Hobby (frontend) + Railway Hobby (backend + DB + Redis + Celery workers) + Cloudflare R2 (media)**.

Motivazioni:

1. **Allineamento con risorse esistenti**: il maintainer paga già per Vercel e Railway. Ignorarle per self-host è masochismo.

2. **Costi reali praticamente nulli**: ~€1-5/mese totali in fase iniziale (R2 + eventuale backup B2). Impareggiabile.

3. **Zero overhead operativo**: il tempo di sviluppo va in codice, non in sysadmin. Per un progetto single-developer a tempo parziale, questo è il fattore più importante.

4. **Portabilità del codice**: il lock-in è nell'infrastruttura, non nel codice. Docker Compose locale è lo stesso stack di production (Postgres managed = Postgres, Redis = Redis, Django container = Django container). Migrare a self-hosted Hetzner è questione di 2 giorni, non di refactoring.

5. **Cloudflare R2** vince su S3 per Radice: egress gratuito. Le foto vengono viste molte volte, caricate raramente — R2 salva decine di euro al mese a regime.

6. **Disaster recovery adeguato**: Railway fa backup automatici di Postgres. Aggiungiamo un cron backup cifrato settimanale su Backblaze B2 per off-site (~€1/mese).

## Conseguenze

### Positive
- Deploy banali (git push → live in 2 minuti)
- Preview deployments su PR (Vercel lo fa nativo)
- Costi quasi zero per anni
- Tempo sviluppatore focalizzato sul codice
- TLS, CDN, DNS tutti gestiti

### Negative / Trade-off
- Se Railway diventa caro o sparisce, serve migrazione (ma è pianificabile)
- Vercel Hobby non permette uso commerciale — blocca path mercato
- Limiti di piani hobby (concurrent builds, bandwidth) vanno monitorati
- Logging e monitoring sono limitati rispetto a setup custom

### Trigger per riconsiderazione

Tre scenari farebbero scattare migrazione:

1. **Apertura commerciale**: Vercel Hobby vieta uso commerciale (ToS). Si migra a Vercel Pro ($20/mese) o Cloudflare Pages (gratis ma meno Next-nativo) o self-host.

2. **Costi Railway oltre €15-20/mese**: a quel punto Hetzner CX32 self-hosted (€8/mese) diventa economicamente sensato. Docker Compose è già pronto per il trasloco.

3. **Scala oltre 10k utenti**: serve architettura diversa (managed K8s, multi-region, load balancing avanzato). Ma è anni distante.

Fino ad allora, l'assetto attuale è il più efficiente.

## Note per implementazione

- **Repository structure**: Vercel monta `frontend/`, Railway monta `backend/`. Configurato in Railway via service root directory, su Vercel via Root Directory setting.

- **Environment variables**: gestite su Railway per backend, Vercel per frontend. `.env.example` nella root del repo documenta le variabili richieste senza esporre valori.

- **Backup strategy**: oltre ai backup Railway (7 giorni retention), cron Celery task settimanale esegue `pg_dump` cifrato e upload su Backblaze B2. Retention: 7 daily, 4 weekly, 12 monthly. **Restore drill trimestrale** per verificare che i backup siano effettivamente ripristinabili.

- **Monitoring**: Sentry free tier (5k eventi/mese) per errori. Railway metrics built-in per infra. Aggiungere UptimeRobot free per ping esterno.

- **Staging**: ambiente staging su Railway (branch `develop`) + Vercel preview deployments (ogni PR). Production su `main`.
