# `apps/core` — Contesto dominio

## Responsabilità

Questo modulo **non** è un dominio di business. È il contenitore di **utilities trasversali** usate da tutti gli altri domini. Include:

- Base models astratti (mixin per timestamp, soft delete, UUID PK)
- Base permission classes DRF
- Middleware applicativi (request cache, locale, audit context)
- Validators riutilizzabili (date precision, enum values, UUID format)
- Exception classes custom con error codes applicativi
- Helpers per serializzazione DRF comuni
- Factory di base per testing (via factory-boy)

**Non deve contenere logica di business specifica di altri domini.** Se una utility è usata solo da un dominio, vive in quel dominio, non qui.

## Entità chiave

Nessuna entità di dominio. Solo astrazioni:

- `TimestampedModel` — abstract, aggiunge `created_at`, `updated_at`
- `SoftDeletableModel` — abstract, aggiunge `archived_at` e manager `objects` che esclude soft-deleted
- `UUIDModel` — abstract, PK UUID v4
- `BaseModel` — combina i 3 sopra, è la base di quasi ogni model del progetto

## Dipendenze

- **Nessuna dipendenza da altri moduli `apps/`**. `core` è foglia nel grafo delle dipendenze.
- Dipende solo da Django core, DRF, e librerie standard.

## Vincoli importanti

1. **Le base class devono rimanere agnostiche al dominio**. Non aggiungere metodi o campi che hanno senso solo per `Person` o `Content`.

2. **Soft delete di default per entità principali**. `SoftDeletableModel.objects.all()` esclude automaticamente archiviate. Per vederle: `SoftDeletableModel.all_objects.all()`.

3. **Audit context via middleware**. Il middleware `AuditContextMiddleware` inietta `request.audit_context` con `actor_user_id`, `ip`, `user_agent`. I signals negli altri moduli leggono questo context per scrivere `audit_log`.

4. **Non è un posto per "miscellaneous"**. Se una utility non si categorizza chiaramente (validator, model mixin, exception, middleware), probabilmente è logica di dominio mal collocata.

## File attesi

```
core/
├── __init__.py
├── apps.py
├── CLAUDE.md                (questo file)
├── models.py                # TimestampedModel, SoftDeletableModel, UUIDModel, BaseModel
├── managers.py              # SoftDeleteManager
├── permissions.py           # Base DRF permission classes (IsAuthenticatedAndActive, ecc.)
├── validators.py            # precision_validator, enum_validator, ecc.
├── exceptions.py            # RadiceException, PermissionDenied, ValidationError wrappers
├── middleware.py            # AuditContextMiddleware, RequestCacheMiddleware
├── mixins.py                # VersionedModelMixin (helper per entità versionate)
├── factories.py             # Factory base e helper per factory-boy in test
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_middleware.py
    └── test_validators.py
```

## Pattern critici

### Request-scoped cache

Il middleware `RequestCacheMiddleware` attacca un `dict` a `request.cache`. Serve come cache per la pipeline permessi (memoization di archetype resolution per viewer/target coppie). Pattern:

```python
def resolve_archetype(viewer_user, target_person, request=None):
    cache_key = (viewer_user.id, target_person.id)
    if request and hasattr(request, 'cache'):
        if cache_key in request.cache:
            return request.cache[cache_key]
    result = _compute_archetype(viewer_user, target_person)
    if request and hasattr(request, 'cache'):
        request.cache[cache_key] = result
    return result
```

### Audit context flow

Ogni mutation di entità sensibile chiama `write_audit_log(action_type, entity, changes_diff)` che legge `current_request().audit_context` (via thread-local) per popolare `actor_user_id`, `context`. Nessun chiamante deve passare `actor_user_id` manualmente — è il middleware che lo fornisce.

### Exception mapping

`RadiceException` ha un `error_code` applicativo (es: `'PERM_001_DENIED_EXTERNAL_UNKNOWN'`). DRF exception handler custom mappa questi a HTTP status + payload strutturato. Mai propagare messaggi di errore interni al client senza passare per `RadiceException`.

## Test density richiesta

60%+. Le base class sono usate ovunque, un bug qui rompe tutto il progetto.
