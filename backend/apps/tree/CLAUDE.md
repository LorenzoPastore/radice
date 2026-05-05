# `apps/tree` — Contesto dominio

## Responsabilità

Gestisce la **struttura dell'albero genealogico**: relazioni familiari tra `Person`, calcolo di distanze di parentela, gestione delle affinità di famiglia "percepita".

È il dominio che implementa una delle parti più tecnicamente insidiose del progetto: il **calcolo delle distanze** tramite CTE ricorsive con cache lazy (vedi ADR-003).

## Entità principali

- **`Relationship`** — relazione strutturale tra due `Person` (parent_child, spouse, sibling). Con subtype dettagliato (biological, legal_adoption, step_parent, de_facto, ecc.).
- **`RelationshipVersion`** — shadow versioning per `Relationship`.
- **`FamilyAffinity`** — relazioni soggettive percepite come familiari senza collegamento strutturale (es: "fratello di fatto", "zio non biologico"). Non influenzano il calcolo strutturale delle distanze.
- **`PersonDistance`** — **tabella di cache** delle distanze calcolate. PK composta (person_a_id, person_b_id) normalizzata con a < b. Popolata lazy, invalidata da trigger.

## Dipendenze

- Dipende da: `core`, `identity`
- Dominio fornitore per: `permissions` (che usa `PersonDistance` per archetype resolution), `curatorship`, `content`, `governance`, `medical`

## Vincoli critici

### Vincolo 1: Niente cicli in `parent_child`
Nessuno può essere antenato di se stesso. Enforced via trigger PostgreSQL `BEFORE INSERT/UPDATE ON relationships` che rifiuta inserimenti ciclici. **Il trigger è obbligatorio**, non affidarsi solo a validazione applicativa.

### Vincolo 2: Normalizzazione per simmetria
Per `type IN ('spouse', 'sibling')`, enforce `person_a_id < person_b_id` (lexicographic su UUID) per evitare duplicati invertiti. Per `parent_child`, la direzione è semantica (a = genitore, b = figlio), non va normalizzata.

Applicato via:
- CHECK constraint DB dove possibile
- Clean method del model
- Service layer che normalizza prima di salvare

### Vincolo 3: Cache distanze invalidata automaticamente
Qualsiasi modifica a `relationships` (INSERT, UPDATE, DELETE) invalida le righe di `person_distances` che coinvolgono le Person toccate. **Questo è implementato via trigger PostgreSQL**, non via signal Django. Motivo: se una migration o uno script bulk modifica relazioni, il signal può essere saltato; il trigger no.

### Vincolo 4: FamilyAffinity NON impatta la struttura
`FamilyAffinity` è metadato soggettivo, non struttura. Non viene considerato nel calcolo delle distanze. Non crea percorsi che collegano rami dell'albero. Serve solo per UI ("mostra affinità dichiarate") e per permessi personalizzati ("tratta X come close_family anche se la distanza strutturale non lo permette").

### Vincolo 5: CTE ricorsive sempre con LIMIT di profondità
Tutte le query ricorsive hanno un `MAX_DEPTH` (default 20) per prevenire runaway query. Gli alberi familiari reali raramente superano 15 livelli; 20 è safe margin.

## Algoritmo di calcolo distanze

Implementato in `services/distance_service.py`. Pseudocodice della CTE ricorsiva:

```sql
WITH RECURSIVE path AS (
  -- Base: tutti i vicini diretti di target_person
  SELECT
    person_a_id as from_id,
    person_b_id as to_id,
    1 as distance,
    ARRAY[person_a_id, person_b_id] as visited,
    type::text as path_types
  FROM relationships
  WHERE (person_a_id = :target OR person_b_id = :target)
    AND archived_at IS NULL

  UNION ALL

  -- Induction: estendo cammini, evitando cicli
  SELECT
    p.from_id,
    CASE WHEN r.person_a_id = p.to_id THEN r.person_b_id ELSE r.person_a_id END,
    p.distance + 1,
    p.visited || CASE WHEN r.person_a_id = p.to_id THEN r.person_b_id ELSE r.person_a_id END,
    p.path_types || '.' || r.type::text
  FROM path p
  JOIN relationships r ON (r.person_a_id = p.to_id OR r.person_b_id = p.to_id)
  WHERE p.distance < :max_depth
    AND NOT (CASE WHEN r.person_a_id = p.to_id THEN r.person_b_id ELSE r.person_a_id END = ANY(p.visited))
    AND r.archived_at IS NULL
)
SELECT from_id, to_id, MIN(distance) as distance, FIRST(path_types) as relationship_type_path
FROM path
WHERE to_id = :viewer
GROUP BY from_id, to_id;
```

Il servizio wrappa questa query con:
1. Check cache (`PersonDistance` table) prima di calcolare
2. Se miss, esegui CTE, salva risultato in cache
3. Return distanza

### Invalidazione cache

Trigger PostgreSQL `AFTER INSERT/UPDATE/DELETE ON relationships`:

```sql
DELETE FROM person_distances
WHERE person_a_id IN (NEW.person_a_id, NEW.person_b_id, OLD.person_a_id, OLD.person_b_id)
   OR person_b_id IN (NEW.person_a_id, NEW.person_b_id, OLD.person_a_id, OLD.person_b_id);
```

Questo invalida tutte le distanze che coinvolgono almeno una delle Person toccate. Aggressivo ma corretto: la modifica di una relazione può cambiare distanze a catena.

### Alternativa se performance diventa critica

Se CTE diventano lente (>50ms di media), tre ottimizzazioni:
1. Precalcolo eager delle coppie (person_a, person_b) più richieste via job Celery notturno
2. Materialized view parziale per sotto-alberi "caldi"
3. Migrazione ad Apache AGE (trigger per riconsiderazione ADR-003)

## Servizi chiave

### `services/relationship_service.py`
- `create_relationship(person_a, person_b, type, subtype, **kwargs)` → Relationship
- `update_relationship(relationship, **changes)` → Relationship (+ version entry)
- `archive_relationship(relationship, reason)` → Relationship
- `validate_no_cycle(person_a, person_b, type)` → bool (pre-check prima di salvare)
- Tutte le operazioni scrivono audit log

### `services/distance_service.py`
- `get_distance(person_a, person_b, request_cache=None)` → int | None (None se non connesse)
- `get_distance_batch(person_a, list_of_persons)` → dict[person_id, int | None] — ottimizzazione batch
- `get_relationship_path(person_a, person_b)` → str (es: "parent.sibling.child" = zio)
- `invalidate_cache_for(person_ids)` → int (numero righe invalidate)

### `services/affinity_service.py`
- `declare_affinity(from_person, to_person, affinity_type, context)` → FamilyAffinity
- `confirm_mutual_affinity(affinity, confirming_user)` → FamilyAffinity (is_mutual=True)

## File attesi

```
tree/
├── __init__.py
├── apps.py
├── CLAUDE.md
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── admin.py
├── signals.py
├── services/
│   ├── __init__.py
│   ├── relationship_service.py
│   ├── distance_service.py
│   └── affinity_service.py
├── sql/
│   ├── distance_cte.sql           # Query CTE documentata
│   ├── cycle_check_trigger.sql    # Trigger anti-ciclo
│   └── distance_cache_trigger.sql # Trigger invalidazione cache
├── migrations/
│   └── 0002_add_triggers.py       # Custom migration per trigger SQL
├── tasks.py
├── factories.py
└── tests/
    ├── test_relationship_model.py
    ├── test_cycle_prevention.py
    ├── test_distance_calculation.py  # Cases: lineare, cross, famiglie allargate
    ├── test_cache_invalidation.py
    ├── test_affinity.py
    └── fixtures/
        └── sample_family.py       # Famiglia di test con casi edge
```

## Casi di test obbligatori per `distance_service`

Una famiglia di fixture con questi casi:
1. **Lineare semplice**: padre → figlio → nipote (distanze 1, 2)
2. **Cugini**: due fratelli con figli (cugini a distanza 4)
3. **Matrimonio**: A e B sposati (distanza 1); A e madre di B (distanza 2)
4. **Famiglia allargata**: padre risposato con nuova partner che ha figli da precedente matrimonio (step-sibling a distanza 3 via step-parent)
5. **Cross-link**: cugini che si sposano (multiplo cammino, distanza corretta = MIN)
6. **Adozione**: adottato biologicamente sconosciuto, parent_child con subtype='legal_adoption'
7. **Disconnesso**: due Person senza relazione calcolabile (distanza = None)
8. **Grafo profondo**: catena di 15+ generazioni (verifica MAX_DEPTH e performance)

## Test density richiesta

75%+. Il calcolo distanze alimenta la pipeline permessi: bug qui significa data leak o data hiding.
