# `frontend/src/lib/offline/` — Contesto PWA offline-first

Questo documento fornisce contesto per la parte offline-first dell'app: IndexedDB, sync queue, conflict resolution, service worker.

## Responsabilità

L'utente deve poter:
- **Leggere** dati precedentemente visti anche senza connessione
- **Scrivere** (mutations) offline, con sync automatica al ritorno online
- **Installare** l'app come PWA su mobile e desktop
- **Ricevere push notifications** anche con app chiusa (se sottoscritto)

Questo è **core di Radice**, non feature accessoria. I familiari anziani useranno l'app in scenari con rete scarsa (treno, casa di campagna, ospedale).

## Architettura

```
lib/offline/
├── CLAUDE.md                  (questo file)
├── db.ts                      # Dexie schema e istanza DB
├── sync-queue.ts              # Queue mutations offline
├── conflict-resolver.ts       # Risolve conflitti al sync
├── schema/                    # Type schemas per IndexedDB
│   ├── persons-schema.ts
│   ├── contents-schema.ts
│   ├── relationships-schema.ts
│   └── index.ts
├── adapters/                  # Layer tra API e IndexedDB
│   ├── person-adapter.ts
│   ├── content-adapter.ts
│   └── tree-adapter.ts
├── service-worker/
│   ├── serwist-config.ts
│   └── push-handler.ts
└── hooks/
    ├── useOfflineStatus.ts    # Detect online/offline
    ├── useSyncQueue.ts        # Stato pending sync
    └── usePersistentQuery.ts  # TanStack Query con fallback IndexedDB
```

## Schema IndexedDB

Le tabelle IndexedDB mirror un subset del backend, focalizzato sui dati rilevanti per l'utente (non tutto il sistema).

```typescript
// db.ts
import Dexie, { Table } from 'dexie';

export class RadiceDB extends Dexie {
  persons!: Table<LocalPerson, string>;              // Person visibili al viewer
  relationships!: Table<LocalRelationship, string>;   // Relazioni dell'albero locale
  contents!: Table<LocalContent, string>;             // Metadata contenuti (non media files!)
  comments!: Table<LocalComment, string>;             // Commenti (append-only)
  messages!: Table<LocalMessage, string>;             // Messaggi in-app
  notifications!: Table<LocalNotification, string>;
  sync_queue!: Table<SyncQueueItem, string>;          // Mutations pending
  meta!: Table<MetaRecord, string>;                   // Last sync time, user info cached

  constructor() {
    super('radice');
    this.version(1).stores({
      persons: 'id, surname, is_living, updated_at',
      relationships: 'id, person_a_id, person_b_id, type, updated_at',
      contents: 'id, [uploaded_by_user_id+uploaded_at], reference_date',
      comments: 'id, content_id, created_at',
      messages: 'id, sender_user_id, recipient_user_id, sent_at, read_at',
      notifications: 'id, recipient_user_id, created_at, read_at',
      sync_queue: 'id, entity_type, created_at, status',
      meta: 'key',
    });
  }
}

export const db = new RadiceDB();
```

**Important**: le **foto e media non sono memorizzati in IndexedDB** (troppo spazio). Sono cached via Cache Storage del service worker (Serwist), con TTL configurato.

## Reads: online-first con fallback

Pattern: **stale-while-revalidate** via TanStack Query + IndexedDB fallback.

```typescript
// hooks/usePersistentQuery.ts
export function usePersistentPersonQuery(personId: string) {
  return useQuery({
    queryKey: ['person', personId],
    queryFn: async () => {
      // Tenta fetch network
      try {
        const data = await api.getPerson(personId);
        // Salva su IndexedDB per prossimo offline
        await db.persons.put(data);
        return data;
      } catch (err) {
        if (!navigator.onLine) {
          // Offline: fallback IndexedDB
          const local = await db.persons.get(personId);
          if (local) return local;
        }
        throw err;
      }
    },
    staleTime: 60_000,          // 1 minuto cache "fresh"
    gcTime: 1000 * 60 * 60,     // 1h cache mem
  });
}
```

Per liste (`useTreeQuery`, `usePersonContentsQuery`), stesso pattern con query su IndexedDB per fallback.

## Writes: offline queue

Tutte le mutations passano per la sync queue. Pattern:

```typescript
// Esempio: creare un commento su un contenuto
export async function createComment(contentId: string, body: string) {
  const tempId = crypto.randomUUID();
  const comment: LocalComment = {
    id: tempId,
    content_id: contentId,
    body,
    author_user_id: currentUser.id,
    created_at: new Date().toISOString(),
    local_only: true,  // flag: non ancora sincronizzato
  };

  // 1. Salva localmente (optimistic update)
  await db.comments.add(comment);

  // 2. Accoda per sync
  await db.sync_queue.add({
    id: crypto.randomUUID(),
    entity_type: 'comment',
    entity_id: tempId,
    action: 'create',
    payload: { content_id: contentId, body },
    created_at: new Date().toISOString(),
    status: 'pending',
    attempts: 0,
  });

  // 3. Trigger sync se online
  if (navigator.onLine) {
    triggerSync();
  }

  return comment;
}
```

Il componente UI vede immediatamente il commento (optimistic). Al sync, l'id temp viene sostituito con l'id vero dal server e `local_only` rimosso.

## Sync queue processor

```typescript
// sync-queue.ts
export async function processSyncQueue() {
  if (!navigator.onLine) return;

  const pending = await db.sync_queue
    .where('status').equals('pending')
    .toArray();

  for (const item of pending) {
    try {
      await db.sync_queue.update(item.id, { status: 'syncing' });

      const result = await executeApiCall(item);

      // Successo: rimuovi da queue, aggiorna entità locale
      await db.sync_queue.delete(item.id);
      await applyServerResponse(item, result);

    } catch (err) {
      if (isConflict(err)) {
        await handleConflict(item, err);
      } else {
        // Error temporaneo: retry
        const attempts = item.attempts + 1;
        if (attempts >= 5) {
          await db.sync_queue.update(item.id, { status: 'failed', last_error: err.message });
          notifyUser(`Sync failed per ${item.entity_type}: ${err.message}`);
        } else {
          await db.sync_queue.update(item.id, {
            status: 'pending',
            attempts,
            next_retry_at: exponentialBackoff(attempts),
          });
        }
      }
    }
  }
}
```

Trigger sync:
- Al ritorno online: `window.addEventListener('online', processSyncQueue)`
- Periodicamente: `setInterval(processSyncQueue, 30_000)` quando app attiva
- On mount: `useEffect(() => processSyncQueue(), [])` nel root layout

## Conflict resolution

I conflitti emergono quando la stessa entità viene modificata dal client offline e da altri utenti online durante la disconnessione.

### Strategia per tipo di entità

**Last-write-wins con timestamp** (maggior parte):
- Person (campi biografici)
- Relationship (metadata)
- Content (title, body)

Quando il server rileva conflitto (tramite `If-Unmodified-Since` header o `version` field), risponde con 409. Il client:
1. Mostra UI di conflitto: "Il contenuto è stato modificato. Vedi le versioni?"
2. Utente sceglie: mantieni mia | mantieni server | merge manuale
3. Applica scelta

**Append-only** (niente conflitti):
- Commenti (possono essere creati in parallelo senza conflitto)
- Messaggi in-app
- Notifiche
- Content upload (ogni upload è un nuovo Content, non sovrascrittura)

**Conflict complesso** (vote, tagging):
- Se offline voto "approve" ma online altri hanno già votato e la proposta è chiusa → messaggio informativo "la proposta è stata risolta"
- Se offline taggo Person X in contenuto ma X è stato archiviato → rifiuta tag, notifica

## Service worker (Serwist)

Configurazione in `next.config.ts`:

```typescript
import withSerwist from '@serwist/next';

export default withSerwist({
  swSrc: 'src/lib/offline/service-worker/sw.ts',
  swDest: 'public/sw.js',
  cacheOnNavigation: true,
})({ /* next config */ });
```

Strategie cache per tipo risorsa:

- **App shell** (HTML, JS, CSS): `StaleWhileRevalidate`
- **API GET responses**: `NetworkFirst` con fallback cache (5s timeout)
- **Avatar e media thumbnails**: `CacheFirst` con expiration (30 giorni)
- **Full-size media**: `NetworkFirst` con fallback cache (7 giorni)
- **Signed URLs R2**: non cachare (scadono)

## Push notifications

Flusso:

1. Utente in settings attiva notifiche push
2. Frontend: `navigator.serviceWorker.ready.then(reg => reg.pushManager.subscribe(...))`
3. Invia subscription al backend: `POST /api/push-subscriptions/`
4. Backend salva PushSubscription (user_id, endpoint, keys)
5. Quando notifica applicativa creata con `push_eligible=true`:
   - Backend chiama servizio Web Push (via `pywebpush`)
   - Service worker riceve messaggio, mostra notifica

Gestione in service worker:

```typescript
// push-handler.ts
self.addEventListener('push', (event) => {
  const data = event.data?.json();
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icons/icon-192.png',
      badge: '/icons/badge.png',
      data: { url: data.url }, // deep link
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
```

## Considerazioni di privacy

IndexedDB **non è crittografato** per default nel browser. Dato che Radice contiene PII:

- **Non salvare dati medici su IndexedDB**. I record medici richiedono sempre fetch online. Se offline, mostra "Dati medici non disponibili offline".
- **Non salvare messaggi privati su IndexedDB a lungo termine**. TTL 7 giorni per messaggi cached.
- **Export/delete**: la funzione "cancella dati locali" deve cancellare IndexedDB + Cache Storage + service worker.
- **Logout**: al logout, wipe IndexedDB (eccetto preferenze UI non sensibili).

## Testing

### Unit tests

Sync queue logic, conflict resolver, adapter transforms — tutti testabili senza browser:

```typescript
test('sync queue retries with exponential backoff', async () => {
  const item = { id: 'x', entity_type: 'comment', attempts: 0, ... };
  await simulateNetworkError(() => processSyncQueue());
  const updated = await db.sync_queue.get('x');
  expect(updated.attempts).toBe(1);
  expect(new Date(updated.next_retry_at).getTime() - Date.now()).toBeGreaterThan(1000);
});
```

### E2E offline tests

Playwright con `page.context().setOffline(true)`:

```typescript
test('user can create comment offline and sync when back online', async ({ page, context }) => {
  await page.goto('/person/123');
  await context.setOffline(true);
  await page.fill('[data-testid="comment-input"]', 'Offline comment');
  await page.click('[data-testid="submit-comment"]');
  await expect(page.locator('[data-testid="comment"]', { hasText: 'Offline comment' })).toBeVisible();
  await expect(page.locator('[data-testid="sync-indicator"]')).toHaveText(/1 pending/);

  await context.setOffline(false);
  await page.waitForSelector('[data-testid="sync-indicator"]', { state: 'hidden' });
});
```

## Anti-pattern da evitare

- **Non salvare dati medici in IndexedDB** (privacy)
- **Non saltare sync queue per mutations**. Tutte le mutations passano per queue, anche se online.
- **Non mostrare stati "strani" in UI**. Il sync è invisibile all'utente per default; solo se qualcosa fallisce, notifica.
- **Non usare localStorage per dati**. Solo per preferenze UI banali (theme).
- **Non cachare signed URLs in IndexedDB**. Hanno TTL breve, salvarli è inutile e rischioso.
- **Non assumere che IndexedDB funzioni**. In Safari private mode potrebbe fallire; gestisci gracefully.

## Metriche da monitorare

(Quando il progetto è vivo)

- `sync_queue.status = 'failed'` count: alert se > threshold
- Media tempo di sync per mutation
- Cache hit rate per tipo risorsa
- Storage IndexedDB per utente (evitare over-fill)

## Estensioni future

- **Selective sync**: permetti all'utente di scegliere cosa tenere offline (es: "solo il ramo materno")
- **Background sync API**: registration di sync periodic per sync anche con app chiusa
- **Encrypted IndexedDB**: wrapper che cifra prima di salvare, per dati sensibili (futuro)
- **P2P sync**: se due familiari sono sulla stessa rete locale, possibile sync diretto via WebRTC (sperimentale)
