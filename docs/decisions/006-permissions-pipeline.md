# ADR-006: Pipeline dei permessi stratificata in 3 livelli

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

I permessi di Radice sono complessi per natura: **6 categorie di campo × 8 archetipi di utente × preset personali × override per nodo × access grant espliciti × intersezioni per contenuti multi-soggetto**. L'implementazione naive (check inline in ogni view) diventa rapidamente ingestibile, non testabile e fragile.

Serve un approccio che:
- Renda i permessi **sempre calcolati** (nessun bypass per errore)
- Sia **testabile** in isolamento (unit test puri sulla logica permessi)
- Sia **performante** (il check dei permessi si ripete moltissime volte per ogni request)
- Sia **esplicitamente tracciabile** (si può spiegare a un utente perché vede/non vede qualcosa)

## Opzioni valutate

### Opzione 1: Check inline nelle views
Ogni view/endpoint implementa i propri check di permesso.

Pro:
- Nessuna astrazione, codice "dove lo cerchi"
- Ogni endpoint fa esattamente quello che serve

Contro:
- Duplicazione massiccia
- Impossibile testare i permessi senza testare le views
- Cambiamenti alla logica permessi richiedono modifiche in ogni endpoint
- Dimentichi un check → data leak silenzioso

### Opzione 2: Decorator monolitico
Un decorator che gestisce tutto (es: `@require_permission('view_person', target)`).

Pro:
- Meno duplicazione
- Più dichiarativo

Contro:
- La complessità (6 categorie × 8 archetipi × override) non si comprime in un singolo decorator
- I payload serializzati vanno filtrati dopo il check — decorator non basta
- Difficile testare la logica senza view

### Opzione 3: Pipeline stratificata in 3 livelli
Tre funzioni pure componibili:
1. **Archetype resolver**: `(viewer, target) → Archetype`
2. **Visibility calculator**: `(archetype, target, viewer) → Set[Category]`
3. **Field serializer**: `(person, visible_categories) → dict`

Pro:
- Ogni livello ha una sola responsabilità, testabile in isolamento
- Componibile: un serializer in DRF può chiamare `serialize_person_for_viewer(person, request.user)` che incapsula i 3 livelli
- Logica centralizzata in `apps/permissions/services/`, niente logica permessi sparsa
- Memoizzabile per request (archetype resolution è costosa ma stabile per la durata di una request)
- Tracciabilità naturale: se serve debug, si può loggare l'esito di ogni livello

Contro:
- Astrazione in più da capire (ma ben documentata)
- Overhead di chiamate di funzione (trascurabile)

## Decisione

**Opzione 3: pipeline stratificata in 3 livelli**.

Implementazione in `apps/permissions/services/`:
- `archetype_resolver.py` → Livello 1
- `visibility_calculator.py` → Livello 2
- `field_serializer.py` → Livello 3

Ogni livello è una funzione pura (input → output, nessun side effect) con cache per request. Unificata in un'API di alto livello:
```python
serialize_person_for_viewer(person, viewer_user) -> dict
is_content_visible_to(content, viewer_user) -> bool
```

**Invariante critica**: nessun endpoint restituisce dati di Person/Content senza passare dalla pipeline. Questo è un requisito di codice, enforced tramite:
- Code review su ogni PR che tocca serializer o views
- Test che verificano il comportamento "external_unknown non vede nulla" per ogni endpoint
- Lint custom che segnala serializer di Person che non delega a `serialize_person_for_viewer`

## Conseguenze

### Positive
- **Testabilità massima**: i 3 livelli si testano separatamente con coverage alta
- **Logica centralizzata**: cambi al modello permessi toccano solo `apps/permissions/services/`
- **Tracciabilità**: si può costruire un endpoint di debug "perché vedo/non vedo questo campo" che espone l'esito dei 3 livelli (utile per supporto utenti e per audit)
- **Performance adeguate**: la memoizzazione per-request riduce chiamate ripetute a O(n) distinct (viewer, target) pairs in una pagina, non O(n*fields)
- **Sicurezza by construction**: il pattern rende difficile bypassare i permessi accidentalmente

### Negative / Trade-off
- Astrazione da capire per nuovi contributor: Livello 1 e 2 potrebbero essere confusi come "stessa cosa"
- Richiede disciplina: la pipeline vale solo se tutti gli endpoint la usano. Un serializer "fai da te" in un dominio rompe l'invariante
- Test di ogni endpoint per verificare aderenza alla pipeline aggiungono volume di test (valore proporzionale)

### Trigger per riconsiderazione
- Se la pipeline si rivela significativamente più lenta di un approccio alternativo in profiling
- Se emergono casi d'uso che non si comprimono nei 3 livelli (improbabile dato il design)

## Note per implementazione

**Test density su `apps/permissions/`**: deve essere il dominio con più test del progetto. Ogni combinazione rilevante di:
- Archetype (8 valori)
- Category (6 valori)
- Preset (4 valori) + con/senza overrides
- is_living del target (2 valori)
- Presence/absence di access_grants

va testata esplicitamente. Il matrix test è obbligatorio prima della milestone 3 (permessi).

**Memoization**: implementata con `functools.lru_cache` a livello di funzione + cache per-request via middleware Django che inietta un dict cache nel request object. L'archetype resolver lo consulta prima di calcolare.

**Endpoint di debug**: da costruire entro milestone 5 (`GET /api/debug/permissions/?viewer=X&target=Y`), visibile solo a superuser. Restituisce archetype, visible_categories, sources (quale preset/override ha determinato ogni categoria).
