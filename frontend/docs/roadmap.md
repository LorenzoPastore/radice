# Radice — Roadmap di sviluppo

Questo documento descrive l'ordine di implementazione di Radice, dal walking skeleton al prodotto funzionale per la famiglia Pastore. È un documento **vivo**: va aggiornato man mano che milestone vengono completate o riprioritizzate.

## Filosofia di progressione

Ogni milestone è **end-to-end funzionale**: completa un caso d'uso reale dall'UI al database, non un layer tecnologico. Questo evita il rischio di accumulare mesi di "fondamenta senza tetto".

Ogni milestone ha:
- **Obiettivo utente** — cosa un utente reale (tu o tua sorella) può fare alla fine
- **Scope tecnico** — cosa include
- **Criterio di completamento** — come si verifica che sia "fatta"
- **Deploy** — ogni milestone finisce con un deploy funzionante (staging almeno)

## Milestone 0 — Setup infrastrutturale

**Obiettivo**: repository vivo, ambienti configurati, CI/CD minima funzionante.

**Scope**:
- Monorepo inizializzato con struttura cartelle da `docs/architecture.md`
- `backend/` scaffold Django 5 con `apps/core`
- `frontend/` scaffold Next.js 15 con shadcn/ui
- Docker Compose locale: postgres, redis, django, next, celery worker
- GitHub Actions: lint + test base
- Deploy: backend su Railway staging, frontend su Vercel preview
- Health check endpoint `/api/health/` che ritorna status DB + Redis
- Pre-commit hooks: ruff, black, biome, eslint

**Criterio completamento**:
- `docker compose up` avvia l'intero stack locale senza errori
- `https://staging.radice.xyz` carica homepage Next.js
- `https://api-staging.radice.xyz/api/health/` ritorna 200

**Tempo stimato**: 1 settimana

## Milestone 1 — Identity minimale

**Obiettivo utente**: posso registrarmi, fare login, vedere il mio profilo base.

**Scope**:
- `apps/identity`: modelli User, Person, PersonClaim, Invitation
- Flussi: registrazione nuova (email + password → User + Person associata), login, email verification, logout, password reset
- `apps/core`: BaseModel, AuditContextMiddleware, RequestCacheMiddleware
- `apps/governance`: AuditLog con trigger append-only
- Frontend: pagine `/register`, `/login`, `/verify-email`, `/settings/profile` (edit dei dati Person propri)
- API endpoint: `/api/auth/*`, `/api/me/`
- Test: invarianti User/Person (test pesanti), audit append-only

**Criterio completamento**:
- Mi posso registrare, verificare email, fare login, modificare mio nome, fare logout
- Se provo UPDATE/DELETE su audit_log via psql → errore
- Coverage `identity` ≥ 70%, `governance` ≥ 80%

**Tempo stimato**: 2 settimane

## Milestone 2 — Tree structure base

**Obiettivo utente**: posso creare mio nonno defunto e stabilire che sono suo nipote.

**Scope**:
- `apps/tree`: modelli Relationship, FamilyAffinity, PersonDistance (cache), trigger no-cycle + invalidazione cache
- `apps/curatorship`: modelli Curatorship, CuratorshipRequest — ma solo creazione primary curator automatica per chi crea un nodo defunto. No co-curatela ancora, no voto
- Service: `relationship_service.create_relationship`, `distance_service.get_distance` con CTE ricorsive
- API: POST `/api/persons/` (creare Person defunta), POST `/api/relationships/`, GET `/api/persons/{id}/`, GET `/api/persons/{id}/relatives/` (lista familiari diretti)
- Frontend: pagina `/person/[id]` con info base + lista relatives, form "aggiungi genitore/figlio/coniuge/fratello"
- Test: family fixture italiana estesa, calcoli distanza su 7 casi definiti in `tree/CLAUDE.md`

**Criterio completamento**:
- Posso creare il mio albero base (io + genitori + nonni + fratelli)
- Le distanze tra me e ogni altro membro sono calcolate correttamente
- Trigger no-cycle previene errori strutturali
- Coverage `tree` ≥ 75%

**Tempo stimato**: 2-3 settimane

## Milestone 3 — Permissions pipeline base

**Obiettivo utente**: mia sorella vede il mio albero ma non i miei dettagli personali oltre il necessario.

**Scope**:
- `apps/permissions`: pipeline in 3 livelli completa
  - `archetype_resolver` funzionante con tutti gli 8 archetipi
  - `visibility_calculator` con preset reserved/balanced/open + Category.EXISTENCE_STRUCTURE/EXTENDED_IDENTITY/BIOGRAPHY
  - `field_serializer` applicato a Person
  - Queryset filter SQL-level per lista Person
- Preset in `presets.py` con matrici documentate
- Endpoint debug `/api/debug/permissions/` (superuser only)
- Frontend: visualizzazione Person con fields adaptive (campi mancanti nascosti, non placeholder)
- Test matrix obbligatorio ≥ 500 casi parametrizzati
- Test anti-leak: external_unknown → 404, close_family vede Biography, distant_family no

**Criterio completamento**:
- Creo un account "sorella" e la registro come Person sister di me. Lei vede il mio nome ma non il mio bio.
- Cambio il mio preset a 'open': lei ora vede anche bio. Verificato.
- External unknown che fa GET di una Person → 404 (non 403)
- Coverage `permissions` ≥ 85% (non ancora 90 perché medical e content non implementati)

**Tempo stimato**: 3 settimane (il dominio più complesso, non vergognarsi)

## Milestone 4 — Content upload e memorial base

**Obiettivo utente**: posso caricare foto di mio nonno e scriverci una storia. Mia sorella vede le foto e può commentare.

**Scope**:
- `apps/content`: modelli Content, ContentSubject, ContentComment. No collezioni ancora
- Servizi: `upload_service` con presigned URL R2, `media_processing` async (Celery) per resize/WebP
- `media_service`: signed URL per delivery
- Integrazione pipeline permessi per `is_content_visible_to` con intersezione multi-soggetto
- API: POST `/api/contents/upload-intent/`, PUT direct a R2, POST `/api/contents/{id}/confirm-upload/`, GET `/api/persons/{id}/contents/`, POST comments
- Frontend: pagina `/person/[id]/content` con grid di foto, modal upload con tagging multi-subject, thread commenti
- Cloudflare R2 bucket creati e CORS configurato
- Backup settimanale R2 → Backblaze B2 via Celery beat

**Criterio completamento**:
- Carico 10 foto di mio nonno taggando me + sorella + nonno
- Le foto vengono ridimensionate automaticamente
- Mia sorella vede le foto (ha confermato i tag)
- Un "cugino distante" di test non vede le foto (intersezione restrittiva)
- Commenti funzionano, cronologia preservata
- Coverage `content` ≥ 65%

**Tempo stimato**: 3 settimane

## Milestone 5 — Visualizzazione albero

**Obiettivo utente**: vedo il mio albero graficamente, posso zoommare, cliccare su un nodo per aprire il profilo.

**Scope**:
- Frontend `components/tree/`: TreeCanvas con react-flow, PersonNode con modalità full/stub/compact, edges tipizzati
- Layout genealogico custom in `layout/genealogical-layout.ts`, supporta i 7 casi test (lineare, cugini, matrimonio, step, cross-link, adozione, disconnesso)
- Interazioni: pan, zoom, click node → sidebar profilo, focus-change
- Animazioni entry (stagger fade+scale)
- Performance: 500 nodi senza lag su mobile mid-range

**Criterio completamento**:
- Apro `/tree`, vedo mio albero (15-30 nodi reali)
- Zoom in/out fluido, pan touch mobile funziona
- Click nonno → sidebar con suo profilo
- Test layout: 7 casi fixture passano
- E2E Playwright: render + interact + navigate to person

**Tempo stimato**: 3-4 settimane (layout algoritmico è lavoro vero)

## Milestone 6 — PWA offline-first

**Obiettivo utente**: in treno senza rete posso comunque navigare il mio albero e vedere foto già caricate.

**Scope**:
- Serwist configurato in `next.config.ts`
- IndexedDB via Dexie: schema per persons, contents (references), relationships, my_profile
- Sync queue in `lib/offline/sync-queue.ts`: mutations offline accodate e replayate
- Conflict resolver: last-write-wins per edit, append-only per commenti
- UI indicators: offline badge, sync progress non-bloccante, "alcuni dati non disponibili offline"
- Cache signed URLs con TTL appropriate (short per immagini, longer per metadata)
- Fallback page `/offline`
- PWA install: manifest, icons, install prompt custom per iOS

**Criterio completamento**:
- Carico app online, metto telefono in airplane mode, posso navigare persons e foto già viste
- Creo un commento offline → quando torno online, si sincronizza
- Installo PWA come app dal telefono
- Test: simulazione offline in Playwright

**Tempo stimato**: 3 settimane

## Milestone 7 — Curatela completa

**Obiettivo utente**: mia sorella può diventare co-curatrice dei nonni e contribuire memorie insieme a me.

**Scope**:
- `apps/curatorship` completo: CuratorshipRequest con auto-approvazione 14gg, voting per decisioni straordinarie
- Celery beat: `auto_approve_expired_requests`, `expire_votes`
- Frontend: pagina "gestione curatela nodo" per ogni Person curata, UI voto straordinario
- API: POST curatorship-request, POST votes, approve/reject
- Notification per richieste, esito voti
- Audit log dettagliato di ogni azione di curatela

**Criterio completamento**:
- Mia sorella richiede co-curatela di nonno, io accetto
- Propongo cambio visibility del nodo nonno, mia sorella vota, decisione applicata a maggioranza
- Coverage `curatorship` ≥ 75%

**Tempo stimato**: 2 settimane

## Milestone 8 — Communication e notifiche

**Obiettivo utente**: posso mandare un messaggio a un cugino appena aggiunto all'albero senza esporre il mio numero.

**Scope**:
- `apps/communication`: InAppMessage, ContactUnlock, Notification
- Frontend: inbox pagina, conversation view, contact unlock flow
- Rate limiting: 50 msg/day, 3 unread threshold
- Push notifications via Web Push Protocol
- Email digest opzionale (daily/weekly)

**Criterio completamento**:
- Mando messaggio a cugino → arriva notifica, lui può rispondere
- Richiedo scambio contatti → lui accetta → vediamo email/telefono
- Rate limit bloccato dopo 50 msg
- Push notification funziona (mobile)

**Tempo stimato**: 2 settimane

## Milestone 9 — Affinità simboliche e famiglie allargate

**Obiettivo utente**: posso dichiarare che i figli della compagna di mio padre sono "come fratelli" per me.

**Scope**:
- `apps/tree`: FamilyAffinity completo con API
- Frontend: UI per dichiarare affinity, mostrare in profilo, edges distintivi in tree canvas
- Subtype esteso per Relationship già presente dalla M2
- Rendering edges: biological pieno, step/de_facto tratteggiato, affinity tratteggiato tenue

**Criterio completamento**:
- Dichiaro affinity like_sibling verso figlia della compagna di mio padre
- Rendering tree la mostra come "sibling simbolico"
- Permette personalizzazione di permessi ("tratta come close_family")

**Tempo stimato**: 1-2 settimane

## Milestone 10 — Content collections

**Obiettivo utente**: creo un album "Matrimonio dei nonni 1952" che raggruppa le 30 foto di quel giorno.

**Scope**:
- `apps/content`: ContentCollection, ContentCollectionItem
- Frontend: creazione collection, drag & drop ordine, cover image, filtri per type

**Criterio completamento**:
- Creo collection type='event', aggiungo 30 foto, ordine personalizzato
- Collection visibile da profilo nonni + pagina dedicata
- Eredita visibility dall'intersezione dei contenuti

**Tempo stimato**: 1 settimana

## Milestone 11 — Medical data

**Obiettivo utente**: registro che mio nonno paterno è morto di infarto a 65, così un giorno saprò della mia familiarità cardiovascolare.

**Scope**:
- `apps/medical`: MedicalRecord, MedicalConsent, lista chiusa condition_code con ~80 codici
- Consent v1.md scritto e committato
- Service consanguinity_service (path biologici only)
- Voto unanimità per defunti
- UI: pagina medical familiare con filtri per category, view "familiarità per condizione"
- Celery: hard delete 30gg dopo revoca

**Criterio completamento**:
- Inserisco record medico su nonno con consenso (vedo testo, accetto)
- Lo vedo io (discendente), NON lo vede mia madre (coniuge, non consanguinea)
- NON lo vede mio padrino (affinity, non strutturale)
- Revoca consenso → record archiviati immediatamente
- Coverage `medical` ≥ 85%

**Tempo stimato**: 2 settimane

## Milestone 12 — Guanxi (social network)

**Obiettivo utente**: mantengo la mia rete di amici e colleghi separatamente dall'albero.

**Scope**:
- `apps/social`: SocialConnection
- Frontend: pagina `/guanxi`, rendering con react-flow force-directed, CRUD connessioni
- Privacy settings guanxi_visibility
- Integrazione archetype_resolver (EXTERNAL_CONNECTED derivato da guanxi)

**Criterio completamento**:
- Aggiungo 20 amici/colleghi al guanxi
- Rendering force-directed funziona
- Un amico conferma reciprocità
- Setting private/mutual_only/public rispettato

**Tempo stimato**: 2 settimane

## Milestone 13 — Merge e governance duplicates

**Obiettivo utente**: un cugino crea "nonno Giuseppe" che già esisteva nel mio albero. Propongo merge, lui conferma, duplicato risolto.

**Scope**:
- `apps/governance`: MergeProposal, MergeVote, apply_merge, duplicate_detector
- rapidfuzz per fuzzy matching su nome+surname+birth_year
- Celery task periodico di detection
- Frontend: UI side-by-side per voto merge, "proponi merge" da profilo
- Undo merge entro 30gg

**Criterio completamento**:
- Due Person duplicate → detector crea proposta
- Voto da entrambi i lati → applicazione
- Verifico repointing completo (nessun ref fantasma)
- Undo entro 30gg funziona

**Tempo stimato**: 2 settimane

## Milestone 14 — Export GDPR e longevità

**Obiettivo utente**: esporto tutti i miei dati in formato standard per archivio personale.

**Scope**:
- Export endpoint `/api/me/export/` che genera ZIP async
- Formato: GEDCOM per albero, JSON per contenuti/metadata, files originali per media
- Hard delete GDPR: cancella User data, anonimizza Person struttura
- Documentazione runbook per richieste GDPR

**Criterio completamento**:
- Esporto mio account → ZIP con GEDCOM + JSON + media
- Richiesta hard delete → User eliminato, Person diventa "Utente cancellato" ma struttura preservata
- Import GEDCOM in GRAMPS (software genealogico) funziona parzialmente

**Tempo stimato**: 2 settimane

## Milestone 15 — Polishing, UX, onboarding

**Obiettivo utente**: posso invitare mia zia settantenne a usare l'app e lei ci riesce.

**Scope**:
- Onboarding guidato per nuovi utenti (wizard "crea tuoi primi 5 nodi")
- Accessibility audit (WCAG AA)
- Performance audit su mobile entry-level
- Copy/UX tweaks
- Tutorial videos brevi incorporati
- Email digest settings
- Preparazione per invito famiglia vera

**Criterio completamento**:
- Faccio test con persona anziana reale della mia famiglia
- Completa l'onboarding senza assistenza su mobile

**Tempo stimato**: 2-3 settimane

---

## Totale stimato

Milestone 0-15 → circa **30-40 settimane** di lavoro focalizzato a tempo parziale.

A tempo pieno equivalente: 4-6 mesi.
A tempo parziale sostenuto (10-15h/settimana): 8-10 mesi.

**Nessuna urgenza.** Il progetto è pensato per durare decenni, non per essere completato in sprint.

## Priorità per partire

Ordine suggerito **da non cambiare**: M0 → M1 → M2 → M3 → M4. Questi 5 compongono un prodotto minimo usabile (registrazione, albero base, permessi base, contenuti base). Tua sorella può già iniziare a contribuire sulla memoria dei nonni.

Dopo M4 hai flessibilità: puoi scegliere M5 (visualizzazione, visibile ma non essenziale) o M7 (curatela collaborativa, più valore utente immediato per tua sorella), in base a cosa ti entusiasma di più.

## Note per gli agenti AI

Quando si lavora su una milestone:
- Leggere questa roadmap per capire il contesto
- Rispettare lo scope: non implementare feature di milestone successive
- Aggiornare questo documento se uno scope si espande/riduce
- Segnalare esplicitamente se una dipendenza non documentata emerge
