# Radice — Contesto principale per Claude Code

Questo documento è il punto di ingresso per qualsiasi agente AI che lavora su questo progetto. Leggilo **sempre** all'inizio di una sessione prima di eseguire task.

## Cos'è Radice

Radice è una web app (PWA mobile-first, offline-first) per famiglie. Il suo cuore è la **preservazione collaborativa della memoria familiare**: foto, storie, documenti dei parenti — soprattutto dei defunti — che altrimenti si perderebbero sparsi tra cassetti e album di casa.

Secondariamente, Radice è una **directory leggera** della famiglia viva (chi è, cosa fa, come contattarlo) e include una sezione separata per il **guanxi** dell'utente — la sua rete sociale non familiare (amici, colleghi, mentori).

**Radice NON è**:
- un social network attivo (nessun feed, nessuna ricerca di contatti, nessuna interazione virale)
- uno strumento di ricerca genealogica (no DNA, no matching con database storici, no documenti ufficiali)
- un prodotto commerciale generico (parte per una famiglia, può crescere, ma la filosofia non cambia)

## Pilastri non negoziabili

Questi sono i principi strutturali del progetto. Qualsiasi scelta di design, architettura o implementazione deve rispettarli. Se un task ti porta a violarli, **fermati e chiedi conferma umana**.

1. **Longevità decennale come vincolo di design.** Il prodotto deve poter vivere 10+ anni. Niente lock-in, niente dipendenze esotiche, niente scelte "cool" a scapito della stabilità. Export sempre disponibile in formati standard (GEDCOM, JSON, file system per media).

2. **Privacy come architettura, non come feature.** I permessi sono stratificati in 3 livelli (archetype resolution → visibility calculation → field serialization). Non esistono shortcut. Vedi `docs/permissions-model.md`.

3. **User ≠ Person.** Questa distinzione è sacra. Un `User` è un account. Una `Person` è una persona reale che può o non può avere un account. La maggior parte delle `Person` nel sistema (defunti, antenati, non-ancora-registrati) non avrà mai uno `User`.

4. **Contenuti come entità di prima classe multi-soggetto.** Un `Content` (foto, storia, audio) può ritrarre/riguardare più `Person`. La sua visibilità è l'intersezione restrittiva delle policy di tutti i soggetti. Mai semplificare questo.

5. **Contatti veri mai esposti.** Email e telefono non sono mai visibili ad altri utenti. La comunicazione passa sempre via proxy in-app. Solo dopo mutuo consenso esplicito in una conversazione specifica i contatti reali possono essere sbloccati.

6. **Dati medici sono categoria speciale.** GDPR Art. 9. Lista chiusa di `condition_code`, consenso esplicito versionato, visibilità esclusiva consanguinea calcolata strutturalmente. Nessun testo libero nelle condizioni mediche.

7. **Hard delete solo via GDPR.** Tutto il resto è soft delete / archiviazione. In caso di hard delete GDPR: cancellazione dei dati personali, preservazione della struttura familiare anonimizzata.

8. **Audit log append-only.** Ogni azione sensibile è tracciata in `audit_log`. Nessun UPDATE, nessun DELETE su quella tabella.

## Stack tecnologico

Questi sono gli strumenti scelti. Non suggerire alternative a meno che non sia esplicitamente richiesto.

**Backend**: Django 5 + Django REST Framework + drf-spectacular (OpenAPI)
**Database**: PostgreSQL 16+ (puro, no estensioni grafo per ora)
**Task queue**: Celery + Celery Beat + Redis
**Auth**: django-allauth
**Frontend**: Next.js 15 (App Router) + React 19 + TypeScript + Tailwind + shadcn/ui
**Visualizzazione albero**: react-flow (xyflow) + layout genealogico custom
**PWA offline**: Serwist + Dexie.js (IndexedDB)
**Media storage**: Cloudflare R2 (S3-compatible)
**Deploy**: Vercel Hobby (frontend) + Railway Hobby (backend + DB + Redis + workers)
**CI/CD**: GitHub Actions
**Monitoring**: Sentry (free tier)

## Principi di lavoro per agenti AI

Leggi queste regole con attenzione. Violarle causa più danni che non fare niente.

### 1. Decidi poco, esegui bene

Le grandi decisioni architetturali sono state prese durante le fasi di design e documentate. Il tuo compito è **eseguire secondo le decisioni documentate**, non rimetterle in discussione. Se noti che una decisione porta a un problema concreto, **segnalalo all'utente prima di modificare l'architettura**.

### 2. Leggi il contesto giusto prima di agire

Ogni dominio (`apps/identity/`, `apps/tree/`, ecc.) ha un suo `CLAUDE.md`. **Leggi sempre il CLAUDE.md del dominio su cui stai lavorando** prima di modificare file. Non assumere.

### 3. Test density proporzionale alla criticità

- Domini **critici** (permissions, tree/distance_service, medical, governance/audit): 80%+ coverage, test di casi edge obbligatori.
- Domini **importanti** (identity, curatorship, content, communication): 60%+ coverage.
- Domini **accessori** (notifications UI, pagine statiche): coverage opportunistica.

### 4. No silent failures

Se non riesci a completare un task come richiesto, **dichiaralo esplicitamente** nella tua risposta. Non lasciare TODO nascosti, non restituire codice che fa finta di funzionare. Preferibile dire "questa parte non sono riuscito a implementarla perché X" rispetto a nascondere il problema.

### 5. Audit log is non-negotiable

Ogni mutazione che tocca entità soggette a versioning o audit (Person, Content, Relationship, MedicalRecord, Curatorship, AccessGrant, ecc.) **deve** scrivere nell'audit log. Se aggiungi una nuova mutation, aggiungi anche l'audit entry. Niente eccezioni.

### 6. Preserva la separazione dei layer

Il pattern è rigoroso:

- **Models**: solo ORM, validazioni di campo, property semplici.
- **Serializers**: solo shape dei dati, nessuna business logic.
- **Views**: solo orchestrazione, auth, dispatch a servizi.
- **Services**: tutta la business logic.
- **Tasks Celery**: solo wrappers su servizi per esecuzione async.

Non mettere business logic nei models o nei views. Mai.

### 7. Permessi sempre calcolati, mai assunti

Ogni endpoint, ogni componente, ogni query che restituisce dati deve passare attraverso la pipeline permessi (archetype → visibility → field serialization). Non esistono dati "di default visibili". Se non sai il viewer, non mostri nulla.

### 8. Commit atomici e message chiari

Ogni commit deve essere un'unità logica coerente, con messaggio che segue convenzione (vedi `docs/conventions.md`). Niente commit giganti, niente commit "wip".

## Struttura del progetto

Vedi `docs/architecture.md` per la vista d'insieme e `docs/data-model.md` per lo schema completo.

Layout monorepo:

- `backend/` — Django project
- `frontend/` — Next.js app
- `shared/` — OpenAPI schema e tipi condivisi
- `docs/` — documentazione persistente (leggila, non ignorarla)
- `.claude/` — agenti specializzati e comandi custom

## Come chiedere aiuto quando sei bloccato

Se un task è ambiguo o una decisione documentata sembra in conflitto con un'altra, **chiedi all'utente prima di procedere**. Spiega:

1. Cosa stavi cercando di fare
2. Il conflitto o l'ambiguità che hai trovato
3. Le due o tre opzioni che vedi
4. La tua raccomandazione motivata

Non procedere per intuizione su decisioni architetturali.

## Riferimenti ai documenti chiave

Leggili nell'ordine quando inizi a lavorare:

1. Questo file (`CLAUDE.md`)
2. `docs/architecture.md` — vista d'insieme
3. `docs/data-model.md` — schema completo
4. `docs/permissions-model.md` — logica permessi stratificata
5. `docs/roadmap.md` — backlog e milestone correnti
6. `docs/conventions.md` — git flow, testing, naming
7. `docs/decisions/` — ADR delle scelte architetturali

Poi, in base al task, il `CLAUDE.md` del dominio specifico.
