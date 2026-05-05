# `apps/permissions` — Contesto dominio

## Responsabilità

Implementa la **pipeline dei permessi stratificata in 3 livelli** (vedi ADR-006 e `docs/permissions-model.md`). Questo è **il dominio più critico del progetto**: ogni richiesta di dati sensibili passa da qui. Bug qui significano data leak o data hiding.

## Entità principali

- **`PrivacyPolicy`** — non è una tabella separata. Le policy degli utenti vivono come campi JSONB su `users`: `privacy_preset` (enum) + `privacy_custom_overrides` (JSONB opzionale).
- **`NodePolicyOverride`** — override deciso dal curatore per un nodo specifico, sovrascrive le policy del soggetto.
- **`AccessRequest`** — richiesta di vedere categorie aggiuntive oltre il default.
- **`AccessGrant`** — permesso attivo (permanente o a scadenza) dato a un viewer su un target.

## Dipendenze

- Dipende da: `core`, `identity`, `tree` (distance calculation), `curatorship` (check curator role)
- Fornisce servizi a: **tutti i domini che serializzano dati** (content, medical, communication, governance, social). Nessuno di loro deve serializzare dati senza passare da qui.

## Vincolo fondativo

**Nessun endpoint del sistema restituisce dati sensibili senza passare dalla pipeline permessi.** Questo include:
- API di lettura diretta di `Person`, `Content`, `MedicalRecord`
- API di lista (filtering a livello SQL prima della serializzazione)
- Query dal frontend tramite client API
- Export GDPR (filtrato per il viewer richiedente, eccetto l'export del proprio dato completo)
- Ricerca full-text
- Notifiche (il payload di una notifica può leakare dati)

Se aggiungi un endpoint, il tuo primo pensiero deve essere "come applico la pipeline qui?".

## I 3 livelli della pipeline

Implementati come moduli separati in `services/`. Ogni livello è una **funzione pura** (input → output, no side effects) memoizzabile per request.

### Livello 1 — Archetype resolver (`services/archetype_resolver.py`)

**Input**: `(viewer_user: User, target_person: Person, request_cache: dict | None)`
**Output**: `Archetype` enum

Logica:
1. Se `viewer_user.person_id == target_person.id` → `SELF`
2. Se esiste Curatorship attiva → `PRIMARY_CURATOR` o `CO_CURATOR`
3. Altrimenti, calcola distanza via `tree.services.distance_service.get_distance`
4. Se distanza `None` e connessione guanxi esiste → `EXTERNAL_CONNECTED`
5. Se distanza `None` e nessuna connessione → `EXTERNAL_UNKNOWN`
6. Altrimenti mappa distanza a categoria:
   - ≤ 2 → `CLOSE_FAMILY`
   - 3-5 → `EXTENDED_FAMILY`
   - \> 5 → `DISTANT_FAMILY`

**Memoization**: usa `request_cache[('archetype', viewer_id, target_id)]` come cache.

### Livello 2 — Visibility calculator (`services/visibility_calculator.py`)

**Input**: `(archetype: Archetype, target_person: Person, viewer_user: User, request_cache)`
**Output**: `set[Category]`

Logica (precedenza, dal più forte):
1. **Access grants espliciti**: se esiste `AccessGrant` attivo → le sue categories sono aggiunte al risultato (somma, non sostituzione rispetto ai default)
2. **Node override**: se esiste `NodePolicyOverride` attivo → usa le sue `override_rules`
3. **Personal policy del target**: se target ha User e `privacy_preset='custom'` → usa `privacy_custom_overrides`. Altrimenti usa preset defaults
4. **Fallback**: preset 'balanced' (usato per nodi senza User)

Le categorie di default variano anche in base a `target_person.is_living` (matrice diversa per viventi vs defunti, vedi `docs/permissions-model.md`).

### Livello 3 — Field serializer (`services/field_serializer.py`)

**Input**: `(person: Person, viewer_user: User, request_cache)`
**Output**: `dict` con solo campi visibili

Costruisce il dizionario serializzato includendo solo i campi delle categorie ammesse dal Livello 2. Se `visible_categories` è vuoto, solleva `PermissionDenied` (che viene mappato a 404, non 403 — vedi "nessun leak via error" sotto).

Funzioni esposte:
- `serialize_person_for_viewer(person, viewer_user, request=None) -> dict`
- `is_content_visible_to(content, viewer_user, request=None) -> bool`
- `filter_visible_contents(contents: list, viewer_user, request=None) -> list`
- `filter_visible_persons_queryset(queryset, viewer_user) -> QuerySet` (ottimizzazione SQL)

## Contenuti multi-soggetto — intersezione restrittiva

Un `Content` con N `ContentSubject` ha visibilità = intersezione delle visibility sui subject. Basta che **un solo** subject abbia policy che non mostra `memory` al viewer → il contenuto è nascosto.

Logica in `services/content_visibility.py`:

```python
def is_content_visible_to(content, viewer_user, request_cache=None):
    subjects = content.confirmed_subjects  # solo tag_status='confirmed'
    if not subjects:
        return False  # contenuti orfani mai visibili

    for subject_person in subjects:
        archetype = resolve_archetype(viewer_user, subject_person, request_cache)
        visible = calculate_visible_categories(archetype, subject_person, viewer_user, request_cache)
        if Category.MEMORY not in visible:
            return False  # anche un solo no blocca

    # Override del contenuto (dal uploader se è curatore)
    if content.visibility_override:
        return apply_content_override(content.visibility_override, viewer_user, request_cache)

    return True
```

### Ottimizzazione per query di lista

Per pagine che caricano N contenuti, iterare con Python è O(N * M) dove M è il costo del permission check. Serve pre-filtering SQL.

Strategia: il service expose un queryset filtrato che esclude contenuti con subject che hanno policy restrittiva per il viewer archetype:

```python
def filter_visible_contents_queryset(qs, viewer_user):
    # Step 1: trova le persons per cui il viewer può vedere 'memory'
    viewer_memory_visible_person_ids = compute_memory_visible_persons(viewer_user)
    # Step 2: escludi contenuti con almeno un subject NON in questo set
    return qs.exclude(
        subjects__in=Person.objects.exclude(id__in=viewer_memory_visible_person_ids)
    ).distinct()
```

Questa ottimizzazione è complessa e va scritta con attenzione — è normale avere test matrix dedicati per verificare equivalenza con la logica Python.

## Flussi di governance

### `AccessRequest` → `AccessGrant`

```
1. Viewer è in archetype che vede categoria X come 'on_request' (non di default)
2. Frontend offre "Richiedi accesso a [categoria]"
3. POST a /access-requests con target_person_id, categories, message opzionale
4. Notifica al primary_curator del target (o all'user stesso se vivente con account)
5. Curator approva → crea AccessGrant(grantee, target, categories, source_request_id=this)
   Curator rifiuta → AccessRequest.status='rejected' con response_message
6. Audit log in entrambi i casi
```

### `AccessGrant` revoca

```
1. Curator (o self del target se vivente) può revocare grant attivo
2. AccessGrant.revoked_at = now()
3. Il viewer non vede più le categorie granted (pipeline ricalcola)
4. Notifica al grantee
5. Audit log
```

### `NodePolicyOverride`

Creato da curatori per override di policy sui nodi che gestiscono. Esempi:
- "Per mio nonno defunto, memory visibile a tutto l'albero" (più permissivo)
- "Per questa zia, contactability chiusa anche a close_family" (più restrittivo)

Solo il primary_curator (o co-curator dopo voto se curatela condivisa) può creare/modificare un override.

## Considerazioni di sicurezza

### Nessun leak via error messages

`PermissionDenied` dalla pipeline deve mappare a **HTTP 404 Not Found**, non 403 Forbidden, quando il viewer è `EXTERNAL_UNKNOWN`. Motivo: 403 rivelerebbe che la risorsa esiste. Per viewer in altri archetipi che vedono esistenza ma non dettaglio, 403 è corretto.

Configurato in `core/exceptions.py` via DRF exception handler.

### Nessun leak via count/pagination

Liste e conteggi devono applicare i permessi a livello di query SQL. Mai fare `Person.objects.count()` per un viewer, filtrare in Python, e ritornare il totale — il totale iniziale sarebbe già un leak.

Pattern corretto:
```python
visible_qs = filter_visible_persons_queryset(Person.objects.all(), request.user)
count = visible_qs.count()
page = paginate(visible_qs, page_number)
```

### Rate limiting

`access_requests`, `curatorship_requests`, `in_app_messages` sono rate-limited per utente via `django-ratelimit`:
- 10 access_requests/ora per utente
- 5 curatorship_requests/ora per utente
- 50 in_app_messages/giorno per utente (più alto, ma per prevenire spam)

Limiti in `settings.RATELIMIT_*`.

### Endpoint di debug (solo superuser)

`GET /api/debug/permissions/?viewer_id=X&target_id=Y` (solo per superuser)
Restituisce:
```json
{
  "archetype": "close_family",
  "distance": 2,
  "visible_categories": ["existence_structure", "extended_identity", "biography", "memory"],
  "sources": {
    "existence_structure": "default_preset_balanced",
    "memory": "node_override_XYZ",
    ...
  },
  "active_grants": [...],
  "active_overrides": [...]
}
```

Aiuta a spiegare "perché vedo/non vedo" e debugga bug di permessi in produzione.

## File attesi

```
permissions/
├── __init__.py
├── apps.py
├── CLAUDE.md
├── models.py              # NodePolicyOverride, AccessRequest, AccessGrant
├── enums.py               # Archetype, Category (enums Python usati ovunque)
├── constants.py           # DISTANCE_THRESHOLDS, MAX_DEPTH, ecc.
├── presets.py             # RESERVED_PRESET, BALANCED_PRESET, OPEN_PRESET (dict)
├── serializers.py
├── views.py               # Debug endpoint, access_request endpoints
├── urls.py
├── admin.py
├── services/
│   ├── __init__.py
│   ├── archetype_resolver.py
│   ├── visibility_calculator.py
│   ├── field_serializer.py
│   ├── content_visibility.py
│   └── queryset_filters.py
├── decorators.py          # @requires_visibility decorator opzionale per DRF views
├── tasks.py               # cleanup_expired_grants
├── factories.py
└── tests/
    ├── test_archetype_resolver.py
    ├── test_visibility_calculator.py
    ├── test_field_serializer.py
    ├── test_content_intersection.py
    ├── test_access_grant_lifecycle.py
    ├── test_node_override.py
    ├── test_queryset_filters.py       # Verifica equivalenza SQL vs Python
    ├── test_no_error_leak.py          # 403 vs 404 correctness
    ├── test_matrix.py                 # Matrix test completo
    └── fixtures/
        └── permission_scenarios.py
```

## Test density richiesta

**90%+**. Questo è IL dominio dove i test contano più di qualsiasi altro. Test matrix obbligatorio:

Per ogni combinazione di:
- 8 archetipi
- 6 categorie
- 4 preset (reserved/balanced/open/custom)
- 2 stati is_living (true/false)
- presence/absence di NodePolicyOverride
- presence/absence di AccessGrant

Verificare che la pipeline ritorni il set atteso. Totale ~1500 test cases, ovviamente parametrizzati (pytest.mark.parametrize) non scritti a mano uno per uno.

## Anti-pattern da evitare

1. **Non bypassare la pipeline** "per performance" o "per questo caso semplice". Tutte le serializzazioni passano da qui.
2. **Non esporre archetipo/categorie raw al client**. Il client riceve dati filtrati, non metadati su permessi (tranne endpoint debug per superuser).
3. **Non hardcodare valori di preset**. I preset sono in `presets.py`, modificabili centralmente.
4. **Non fare query N+1** nella pipeline. Usa `select_related` e `prefetch_related` aggressivamente nei queryset filters.
