# `frontend/` — Contesto frontend

Questo documento è il contesto principale per qualsiasi lavoro sul codice frontend di Radice. Leggilo prima di modificare il codice in `frontend/`.

## Responsabilità

Il frontend è una **Progressive Web App (PWA) mobile-first, offline-first** che consuma le API del backend Django. Deve funzionare bene come app mobile installata sul telefono di familiari anziani (obiettivo principale) e come desktop web app (obiettivo secondario).

## Stack

- **Next.js 15** con App Router
- **React 19**
- **TypeScript** (strict mode)
- **Tailwind CSS** + **shadcn/ui** per componenti
- **react-flow (xyflow)** per visualizzazione albero e guanxi
- **Serwist** per service worker PWA
- **Dexie.js** per IndexedDB (offline storage)
- **Zustand** per state management globale
- **TanStack Query** per server state (fetching, caching, optimistic updates)
- **openapi-typescript** per generare tipi dal schema OpenAPI del backend

## Principi di lavoro

### 1. Mobile-first sempre

Ogni componente va pensato prima per mobile (viewport 360-420px), poi adattato per tablet/desktop. **Non** il contrario. Tailwind breakpoints:
- default (no prefix): mobile
- `sm:` tablet (640px+)
- `md:` laptop (768px+)
- `lg:` desktop (1024px+)

Touch targets minimi 44x44px. Bottoni importanti in fondo allo schermo per pollice.

### 2. Offline-first architettura

L'utente deve poter usare l'app senza rete. Implicazioni:
- **Reads**: prima si tenta IndexedDB, poi network (stale-while-revalidate)
- **Writes**: sempre locali prima, poi sync queue, poi network
- **UI**: mai bloccare su rete. Indicatore "sincronizzazione in corso" non-bloccante
- **Conflict resolution**: ogni mutation ha timestamp; last-write-wins per la maggior parte delle entità; append-only per commenti

### 3. Type safety end-to-end

Il backend espone OpenAPI schema. Script `npm run generate-types` rigenera `src/lib/api/generated/` da `shared/openapi/schema.yaml`. Ogni client API usa questi tipi. **Mai usare `any`** sui payload API.

Pre-commit hook verifica che i tipi generati siano aggiornati rispetto allo schema backend.

### 4. Pipeline permessi rispettata

Il frontend **non implementa** logica di permessi. Si fida del backend: se un campo arriva nel payload, significa che il viewer può vederlo. Se non arriva, nasconderlo UI-side senza assumere.

Pattern: componenti condizionali `if (person.short_bio) { render bio section }`. Non `if (canViewBio(viewer, person))` — quel check è server-side.

### 5. No business logic nel UI

Regole come "solo il primary curator può fare X" sono **enforced dal backend**. Il frontend mostra/nasconde azioni UI, ma non assume che ciò sia sicurezza. Un utente malintenzionato può modificare il client; il backend deve essere la sola fonte di verità.

### 6. Accessibilità seria

Target: zie/nonni over 65. Questo richiede:
- Dimensioni testo adeguate (base 16px, up to 20px possibile nelle settings utente)
- Contrasto WCAG AA almeno
- Screen reader support (aria-labels, semantic HTML)
- Navigazione tastiera funzionante
- Focus ring visibili e non rimossi

## Struttura cartelle

```
frontend/src/
├── app/                          # Next.js App Router
│   ├── (public)/                 # Route group: pagine accessibili non autenticati
│   │   ├── login/
│   │   ├── register/
│   │   ├── invite/[token]/
│   │   └── layout.tsx
│   ├── (app)/                    # Route group: app autenticata
│   │   ├── tree/
│   │   │   ├── page.tsx          # Vista albero
│   │   │   └── layout.tsx
│   │   ├── person/[id]/
│   │   │   ├── page.tsx          # Profilo persona
│   │   │   ├── content/
│   │   │   ├── medical/
│   │   │   └── edit/
│   │   ├── content/
│   │   │   └── [id]/page.tsx
│   │   ├── guanxi/
│   │   │   └── page.tsx
│   │   ├── inbox/
│   │   │   ├── messages/
│   │   │   └── notifications/
│   │   ├── settings/
│   │   └── layout.tsx            # Auth guard + navbar
│   ├── offline/page.tsx          # Pagina fallback offline
│   └── layout.tsx                # Root layout
├── components/
│   ├── ui/                       # shadcn/ui componenti base
│   ├── tree/                     # Visualizzazione albero (vedi CLAUDE.md dedicato)
│   ├── person/
│   ├── content/
│   │   ├── ContentCard.tsx
│   │   ├── ContentUploader.tsx
│   │   ├── TagManager.tsx
│   │   └── CommentThread.tsx
│   ├── guanxi/
│   ├── permission/               # Componenti per access requests, grants UI
│   └── shared/
│       ├── Avatar.tsx
│       ├── DatePrecisionInput.tsx
│       └── PersonSearch.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts             # fetch wrapper con auth headers
│   │   ├── generated/            # Da OpenAPI (NON EDITARE A MANO)
│   │   └── endpoints/            # Helpers per endpoint specifici
│   ├── offline/                  # IndexedDB + sync (vedi CLAUDE.md dedicato)
│   ├── auth/
│   │   ├── session.ts            # Session management
│   │   └── guards.ts             # Auth checks client-side
│   └── utils/
│       ├── date.ts               # Formattazione con precision
│       ├── permissions.ts        # UI helpers (es: render "richiedi accesso" button)
│       └── media.ts              # Gestione signed URL, preload
├── hooks/
│   ├── useCurrentUser.ts
│   ├── useOfflineStatus.ts
│   ├── useSyncQueue.ts
│   └── useDebouncedCallback.ts
├── stores/                       # Zustand stores
│   ├── authStore.ts
│   ├── uiStore.ts                # Modal, toast, theme
│   └── syncStore.ts              # Stato sync queue
└── types/                        # TS types condivisi custom
```

## Route structure — filosofia

- **Route groups** `(public)` e `(app)` separano zone autenticate vs non
- **Auth guard** nel `layout.tsx` di `(app)` reindirizza a `/login` se non autenticato
- **Offline fallback**: se una route richiede dati non disponibili offline, mostra versione degraded con notice "alcuni dati non disponibili offline"

## State management

Divisione delle responsabilità:

- **Server state** (dati dal backend): **TanStack Query**. Cache, invalidation, optimistic updates, mutations.
- **Client state UI effimera** (modal aperto, toast, theme, sidebar collapsed): **Zustand** store `uiStore`.
- **Client state persistente offline** (mutations pending, IndexedDB cache): gestito in `lib/offline/` con sync queue dedicata. **Non** in Zustand.
- **Auth state**: Zustand `authStore`, persisted in sessionStorage.

## PWA configurazione

- **Manifest**: `public/manifest.json` con icons, theme_color, display=standalone
- **Service worker**: Serwist config in `next.config.ts`
- **Install prompt**: custom UI per iOS Safari (nativo non esiste)
- **Push notifications**: Web Push Protocol, subscribe su settings utente

## Convenzioni codice

- **Componenti**: PascalCase, un componente per file
- **Hooks**: camelCase con prefisso `use`
- **Type/Interface**: PascalCase (`PersonSummary`, `ContentSubject`)
- **Utility functions**: camelCase
- **Constants**: SCREAMING_SNAKE_CASE per veri constants, PascalCase per enum-like objects
- **File naming**: `PersonCard.tsx`, `usePersonQuery.ts`, `date-utils.ts` (kebab-case per utils)

## Testing

- **Unit tests**: Vitest per logica pura (utilities, store, hooks)
- **Component tests**: React Testing Library per componenti critici
- **E2E**: Playwright per flussi completi (registration, upload, view tree)

Coverage target: 50% complessivo, 70% per componenti critici (tree canvas, content uploader, permission UI).

## CLAUDE.md per sottocartelle

Alcune aree frontend hanno CLAUDE.md dedicati per contesto profondo:
- `components/tree/CLAUDE.md` → algoritmo layout genealogico, interazioni canvas
- `lib/offline/CLAUDE.md` → strategia sync, conflict resolution, IndexedDB schema

Leggili quando lavori specificamente in quelle aree.

## Anti-pattern da evitare

1. **Non implementare logica permessi client-side** (vedi principio 4)
2. **Non usare `localStorage` per dati sensibili**. Solo per preferenze UI banali (theme, language). Dati utente in IndexedDB criptato se rilevante.
3. **Non fare polling** di endpoints. Usa SSE o push notifications per aggiornamenti realtime, refetch on visibility change per aggiornamenti leggeri.
4. **Non montare component tree complessi in `useEffect`**. Se un componente monta/smonta ripetutamente per dati, probabilmente hai sbagliato il flow di dati.
5. **Non ignorare l'accessibilità**. Target demografico lo esige.
6. **Non fare upload media via `POST` al backend**. Sempre presigned URL diretto a R2.
