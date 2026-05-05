# Radice — Architettura del sistema

Questo documento descrive l'architettura di alto livello di Radice. Per i dettagli del data model vedi `data-model.md`, per i permessi `permissions-model.md`.

## Vista d'insieme

Radice è un'applicazione web composta da tre componenti principali:

1. **Backend API** (Django + DRF) — espone API REST, gestisce auth, persistenza, business logic, task asincroni
2. **Frontend PWA** (Next.js) — client mobile-first offline-first, comunica con il backend via API
3. **Media storage** (Cloudflare R2) — storage object-based per foto, audio, video, documenti

```
                        ┌─────────────────────┐
                        │   Frontend (PWA)    │
                        │   Next.js on Vercel │
                        └──────────┬──────────┘
                                   │ HTTPS
                  ┌────────────────┼────────────────┐
                  │                │                │
        ┌─────────▼────────┐       │       ┌────────▼────────┐
        │   Backend API    │       │       │  Media Storage  │
        │  Django + DRF    │       │       │  Cloudflare R2  │
        │   on Railway     │       │       │  (signed URLs)  │
        └────┬─────────┬───┘       │       └─────────────────┘
             │         │           │
        ┌────▼───┐ ┌───▼──────┐    │
        │ Redis  │ │PostgreSQL│    │
        │(cache+ │ │   16+    │    │
        │ queue) │ │          │    │
        └────┬───┘ └──────────┘    │
             │                     │
        ┌────▼──────────┐          │
        │ Celery Workers│◄─────────┘  (background processing)
        │ + Celery Beat │
        └───────────────┘
```

## Domini applicativi (bounded contexts)

Il backend è organizzato in 10 Django apps, ognuna corrispondente a un bounded context:

| App             | Responsabilità                                                               |
|-----------------|------------------------------------------------------------------------------|
| `core`          | Utilities trasversali: base models, mixins, middleware, validators comuni    |
| `identity`      | User, Person, PersonClaim, Invitation                                        |
| `tree`          | Relationship, FamilyAffinity, PersonDistance (cache distanze)                |
| `curatorship`   | Curatorship, CuratorshipRequest, CuratorshipVote                             |
| `content`       | Content, ContentSubject, ContentComment, ContentCollection                   |
| `permissions`   | PrivacyPolicy, NodePolicyOverride, AccessRequest, AccessGrant, pipeline 3 livelli |
| `medical`       | MedicalRecord, MedicalConsent, condition_code enum                           |
| `communication` | InAppMessage, ContactUnlock, Notification                                    |
| `governance`    | MergeProposal, MergeVote, AuditLog                                           |
| `social`        | SocialConnection (grafo guanxi)                                              |

Ogni app ha il suo `CLAUDE.md` con contesto specifico, le entità principali, le dipendenze da altri domini, e i vincoli di dominio.

## Pattern architetturali

### Service layer

Ogni app segue il pattern service layer esplicito:

- `models.py` → Solo ORM e validazione di campo
- `serializers.py` → Solo shape dei dati API (DRF)
- `views.py` → Solo orchestrazione, auth check, delega a services
- `services/` → Business logic reale, testabile in isolamento
- `tasks.py` → Wrapper Celery su services per esecuzione async

Motivazione: testabilità, chiarezza responsabilità, isolamento della logica di dominio.

### Pipeline permessi stratificata

Ogni accesso a dati sensibili passa per 3 livelli:

1. **Archetype resolver** (`permissions/services/archetype_resolver.py`) → data una coppia (viewer, target), calcola l'archetipo del viewer rispetto al target (Self, Curator, Co-curator, Close/Extended/Distant family, External connected/unknown)
2. **Visibility calculator** (`permissions/services/visibility_calculator.py`) → dato l'archetipo e le policy del target, calcola quali delle 6 categorie di campo sono visibili
3. **Field serializer** (`permissions/services/field_serializer.py`) → filtra i dati prima della serializzazione

Nessun endpoint bypassa questa pipeline. Vedi `docs/permissions-model.md` per i dettagli.

### Versioning selettivo

Quattro entità hanno versioning esplicito via tabella shadow:

- `Content` → `ContentVersion`
- `Person` → `PersonVersion`
- `Relationship` → `RelationshipVersion`
- `MedicalRecord` → `MedicalRecordVersion`

Ogni modifica crea una nuova versione; la tabella principale contiene lo stato corrente. Ripristino = UPDATE della principale con i campi di una versione storica.

### Audit log append-only

La tabella `audit_log` registra ogni azione sensibile: creazione/modifica di entità critiche, cambi di policy, voti su merge, approvazioni di accesso, hard delete GDPR. Constraint a livello DB: niente UPDATE, niente DELETE. Solo INSERT.

### Cache distanze di parentela lazy

La tabella `person_distances` è una cache: `(person_a, person_b, distance)`. Popolata on-demand tramite CTE ricorsiva su `relationships`. Invalidata da trigger su INSERT/UPDATE/DELETE di `relationships`. Non precalcolata in anticipo.

## Frontend

Struttura Next.js con App Router:

- `app/(public)/` → landing, login, flussi di invito (accessibili non autenticati)
- `app/(app)/` → app autenticata (tree, person, content, guanxi, settings)
- `components/ui/` → shadcn/ui components (base)
- `components/tree/` → visualizzazione albero, inclusi layout algoritmici custom
- `components/person/`, `components/content/`, `components/guanxi/` → componenti di dominio
- `lib/api/` → client API tipizzato (generato da OpenAPI)
- `lib/offline/` → IndexedDB via Dexie + sync queue + conflict resolver

### PWA offline-first

La strategia offline-first è centrale:

- Service worker (Serwist) intercetta richieste, serve da cache quando offline
- IndexedDB (Dexie) replica il sottoinsieme di dati rilevante per l'utente (il suo albero, i contenuti dei suoi curati, i suoi messaggi)
- Mutations offline accodate in una queue, sincronizzate al ritorno online
- Conflict resolution via timestamp last-write-wins per la maggior parte delle entità; per commenti e contenuti multi-soggetto, strategia append-only CRDT-light

## Task asincroni (Celery)

Task principali:

- Elaborazione media in upload (resize, conversione WebP/AVIF, estrazione EXIF)
- Invalidazione cache `person_distances` post-mutation di `Relationship`
- Invio email transazionali (inviti, notifiche, richieste)
- Notifiche push PWA
- Backup schedulati
- Cleanup di AccessGrant scaduti, sessioni, contenuti orfani
- Export GEDCOM/JSON on-demand

## Ambienti

- `local` — Docker Compose (Postgres, Redis, Django, Next, Celery worker, Celery beat)
- `staging` — Railway staging env (branch `develop`)
- `production` — Railway production env + Vercel (branch `main`)

## Osservabilità

- **Errori**: Sentry (free tier, 5k eventi/mese)
- **Performance backend**: Railway built-in metrics + query logging Django
- **Uptime**: monitoraggio esterno (UptimeRobot free)
- **Audit applicativo**: tabella `audit_log` interrogabile

## Sicurezza

- HTTPS ovunque (TLS terminato da Vercel/Railway/Cloudflare)
- URL firmati a scadenza per accesso ai media R2
- CSRF protection Django standard
- Rate limiting via `django-ratelimit` su endpoint pubblici (login, invite, password reset)
- GDPR: hard delete su richiesta, export dati on-demand, consenso esplicito per dati medici
- Backup cifrati su Backblaze B2 (opzionale, aggiunto dopo walking skeleton)
