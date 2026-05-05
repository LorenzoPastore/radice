# Radice — Convenzioni di sviluppo

Questo documento definisce lo stile di lavoro del progetto: git flow, naming, testing, documentazione. Rispettarlo rende il progetto mantenibile per decenni.

## Git flow

### Branch model

Flusso semplice a 2 branch (adeguato a single-developer):

- `main` — branch di produzione. Protetto. Deploy automatico a prod (Vercel + Railway production env)
- `develop` — branch di integrazione. Deploy automatico a staging. Merged in `main` dopo QA su staging
- `feat/*`, `fix/*`, `refactor/*` — feature branches, derivate da `develop`, merged in `develop` via PR

### Naming branch

```
feat/tree-distance-calculation
feat/permissions-pipeline-l1-archetype
fix/content-upload-presigned-expired
refactor/identity-registration-service
docs/adr-008-webpush-protocol
chore/upgrade-django-5.1
```

Prefissi:
- `feat/` — nuova feature
- `fix/` — bug fix
- `refactor/` — refactoring senza cambio comportamento
- `docs/` — solo documentazione
- `chore/` — dependency update, tooling, build config
- `test/` — solo test (raro, di solito parte di feat)

### Commit message

Convention: **Conventional Commits**.

```
<type>(<scope>): <subject>

<body (opzionale)>

<footer (opzionale)>
```

**Type**: feat, fix, refactor, test, docs, chore, perf, style

**Scope** (esempi): `identity`, `tree`, `permissions`, `content`, `medical`, `curatorship`, `governance`, `social`, `communication`, `frontend`, `ops`

**Esempi**:

```
feat(tree): add recursive CTE for person distance calculation

Implements distance_service.get_distance using PostgreSQL WITH
RECURSIVE. Includes MAX_DEPTH of 20 and lazy caching via
person_distances table.

Closes #42
```

```
fix(permissions): external_unknown returns 404 instead of 403

Matches the anti-leak requirement from permissions-model.md §
"Nessun leak via error messages". Updates DRF exception handler
and adds regression test.
```

```
refactor(content): extract media processing from upload service

Moves resize/WebP conversion logic from upload_service to
dedicated media_processing module (Celery task wrapper).
No behavior change.
```

### PR workflow

1. Branch da `develop`
2. Commit atomici con messaggi convenzionali
3. Push, apri PR verso `develop`
4. CI esegue: lint, test, coverage check, type check
5. Self-review (per single-developer è OK, ma fai review vera): rileggi la tua diff con occhio critico
6. Merge con **squash** se PR ha commit sciocchi ("wip", "fix typo"), **rebase** se ogni commit è atomico e leggibile
7. Delete branch

Deploy a prod: merge `develop` → `main` tramite PR dedicata dopo QA su staging.

## Naming conventions

### Python (backend)

- **Moduli**: snake_case (`distance_service.py`, `medical_record.py`)
- **Classi**: PascalCase (`DistanceService`, `MedicalRecord`)
- **Funzioni/metodi**: snake_case (`get_distance`, `calculate_visible_categories`)
- **Variabili**: snake_case (`viewer_user`, `target_person`, `request_cache`)
- **Costanti**: SCREAMING_SNAKE_CASE (`MAX_DEPTH`, `DISTANCE_CLOSE`, `SESSION_TTL`)
- **Enums** (TextChoices): PascalCase classe, SCREAMING_SNAKE_CASE valori
- **Fixture factories**: `PersonFactory`, `ContentFactory` (PascalCase con suffisso `Factory`)
- **Test**: `test_<subject>_<scenario>` (snake_case, descrittivo)

Specifico Radice:
- **User vs Person**: sempre esplicito nei nomi di parametro e variabile per evitare confusione
  - ✅ `viewer_user`, `actor_user`, `target_person`, `subject_person`
  - ❌ `user` (ambiguo in contesti dove esistono anche Person)

### TypeScript (frontend)

- **File componenti**: PascalCase (`PersonCard.tsx`, `TreeCanvas.tsx`)
- **File utility/hooks**: kebab-case (`date-utils.ts`) o camelCase con prefisso (`usePersonQuery.ts`)
- **Componenti React**: PascalCase (`PersonCard`)
- **Hooks**: camelCase con prefisso `use` (`usePersonQuery`, `useOfflineStatus`)
- **Functions**: camelCase (`formatDate`, `computeLayout`)
- **Types/Interfaces**: PascalCase (`PersonSummary`, `TreeNodeData`). Preferire `type` over `interface` per coerenza, salvo che serva `extends`.
- **Constants**: SCREAMING_SNAKE_CASE per costanti vere, PascalCase per enum-like oggetti
- **Cartelle**: kebab-case (`genealogical-layout/`, `offline/`)

### Database

- **Tabelle**: snake_case plurale (`persons`, `relationships`, `content_subjects`)
- **Colonne**: snake_case (`given_names`, `birth_date_precision`)
- **Indici**: `idx_<tabella>_<colonne>` (`idx_rel_person_a`)
- **Constraints**: descriptive (`unique_relationship_triple`, `no_self_relationship`, `check_parent_child_no_cycle`)
- **Foreign keys**: nome campo `<entità>_id` (`person_id`, `curator_user_id`)

### API

- **Endpoint**: kebab-case plurale per risorse (`/api/persons/`, `/api/access-requests/`, `/api/merge-proposals/`)
- **Azioni su risorsa**: verb dopo risorsa (`/api/persons/{id}/claim/`, `/api/contents/{id}/confirm-upload/`)
- **JSON keys**: snake_case (backend Django REST convention) — il frontend può convertire a camelCase tramite middleware client

## Testing conventions

Vedi `apps/permissions/CLAUDE.md` e agente `testing-guardian` per dettagli. Sintesi:

### Python

```python
# Naming: test_<what>_<when>_<expected>
def test_archetype_resolver_returns_self_when_viewer_is_target():
    ...

def test_medical_record_creation_fails_without_consent():
    ...
```

### Struttura

- Arrange-Act-Assert chiaramente separati (commenti `# Arrange`, `# Act`, `# Assert`)
- Fixture factories da `apps/{domain}/factories.py` (factory-boy)
- Shared fixtures in `conftest.py` (a livello di app o root)
- Mark di categoria: `@pytest.mark.integration`, `@pytest.mark.permissions`, `@pytest.mark.gdpr`, `@pytest.mark.performance`

### Coverage

Target per dominio in `docs/roadmap.md` e CLAUDE.md dei singoli domini. In CI, coverage check fallisce se scende sotto soglia.

### Performance tests separati

`@pytest.mark.performance` → job CI separato settimanale, non blocca PR.

## Documentazione

### Dove sta cosa

- **`docs/architecture.md`**: vista sistema
- **`docs/data-model.md`**: schema DB
- **`docs/permissions-model.md`**: modello permessi
- **`docs/roadmap.md`**: backlog e milestone
- **`docs/conventions.md`**: questo file
- **`docs/decisions/`**: ADR
- **`docs/runbooks/`**: procedure operative (backup restore, GDPR delete, migrazione complessa)
- **`CLAUDE.md`** root: contesto per agenti AI, pilastri, principi
- **`{backend,frontend}/CLAUDE.md`**: contesto di layer
- **`backend/apps/{domain}/CLAUDE.md`**: contesto di dominio
- **`.claude/agents/`**: agenti specializzati

### Quando aggiornare

- **Data model cambia** → aggiorna `docs/data-model.md` PRIMA di implementare
- **Decisione architetturale significativa** → scrivi ADR in `docs/decisions/` nel PR stesso
- **Nuovo runbook emerge da incident** → documenta appena risolto
- **CLAUDE.md del dominio cambia semantica** → aggiorna nello stesso PR

### Docstrings Python

Google style, ma essenziali:

```python
def get_distance(person_a, person_b, request_cache=None):
    """
    Calcola la distanza di parentela strutturale tra due Person.

    Usa cache lazy tramite PersonDistance table. Se non in cache,
    esegue CTE ricorsiva su relationships.

    Args:
        person_a: Prima Person
        person_b: Seconda Person
        request_cache: Dict opzionale per memoization per-request

    Returns:
        int: distanza di parentela (>=0)
        None: se le Person non sono connesse nell'albero

    Raises:
        ValueError: se person_a == person_b (uso improprio)
    """
```

Docstring **non** necessarie per metodi banali (es: getter property). Obbligatorie per ogni funzione service, ogni metodo complesso, ogni API endpoint.

### JSDoc TypeScript

TSDoc per interfacce API, tipi complessi, hook con side effects.

## Code style

### Python

- **Formatter**: `black`, line length 100
- **Linter**: `ruff`, configurato in `pyproject.toml`
- **Import order**: isort (integrato in ruff): stdlib → third-party → Django → local
- **Type hints**: sempre per firme di funzioni pubbliche; opzionali per internal helpers
- **f-string** preferiti a `.format()` e `%`

### TypeScript

- **Formatter**: `biome` (successore unified di prettier + eslint)
- **Strict mode**: `strict: true` in tsconfig. No `any` eccetto casi giustificati con commento
- **Import order**: biome order (standard → external → internal → relative)
- **Functional style**: preferire funzioni pure, useCallback/useMemo dove migliora perf

### Pre-commit

Configurato in `.pre-commit-config.yaml`:

- Backend: ruff (format + lint), mypy (type check), pytest on changed files
- Frontend: biome, tsc --noEmit, related vitest run
- Commit message linter (commitlint con Conventional Commits)

## Sicurezza e privacy

### Secrets management

- **Mai** committare secrets (API keys, DB passwords, signed keys)
- `.env.example` documenta variabili senza valori
- Secrets reali: Railway environment (backend), Vercel env (frontend)
- In locale: `.env.local` gitignored
- Rotate immediatamente se leak accidentale

### Dependency management

- **Backend**: `uv` o `pip-tools` per lockfile pinned
- **Frontend**: `pnpm` con lockfile committato
- **Upgrade schedule**: weekly dependabot, batch rilascio mensile (eccetto security patches immediate)
- **Audit**: `pip-audit` e `pnpm audit` in CI, fail on high/critical

### PII awareness

Ogni sviluppatore (incluso te solo) ricorda:
- Non loggare in clear: email, telefono, body messaggi, medical records, contenuti
- In log di debug: usa truncation o hash per identificatori
- In error reporting (Sentry): scrub sensitive fields via configurazione

## Release e versioning

### Versioning

Radice usa **calendar versioning**: `YYYY.MM.N` (es: `2026.05.1`, `2026.05.2`, ...).

Non semantic versioning perché il prodotto non espone API pubblica verso altri sistemi. Calendar versioning comunica chiaramente "quanto vecchio è questo deploy".

### Deploy cadence

Quando il progetto è vivo:
- Staging: continuous (ogni merge in `develop`)
- Production: settimanale (merge `develop` → `main` ogni venerdì mattina, dopo verifica su staging)
- Hotfix: quando serve, direct PR su `main` poi cherry-pick su `develop`

### Changelog

Generato automaticamente da Conventional Commits via `git-cliff` o simili. Committed in `CHANGELOG.md` root.

## Review self-discipline

Per progetto single-developer, non c'è co-reviewer. Sostituzioni:

1. **Self-review con tempo**: apri PR, vattene 15 minuti, torna con occhio fresco
2. **Checklist pre-merge**:
   - [ ] Test aggiunti/aggiornati
   - [ ] Documentazione aggiornata (se applicabile)
   - [ ] Migration con rollback testato
   - [ ] No secrets nel diff
   - [ ] CLAUDE.md del dominio ancora coerente
   - [ ] Anti-leak verificato (se tocca permessi)
3. **Claude Code come co-reviewer**: prima di merge, chiedi a Claude Code "rivedi questo diff e segnala problemi", usando gli agenti specializzati come supporto

## Gestione dei TODO e Technical Debt

### TODO in codice

Evitati quando possibile. Se necessario:

```python
# TODO(radice-M11): spostare consent version check a consent_service
```

Formato: `TODO(<milestone-id>): <descrizione>`. Ogni TODO è associato a una milestone o issue. Zero TODO senza riferimento.

### Technical debt tracking

Issues GitHub con label `tech-debt`. Review trimestrale: affronta almeno 1 item ogni release.

## Filosofia generale

Due principi guida sopra tutto:

1. **Scrivi codice per il Lorenzo tra 2 anni**, non per il Lorenzo di oggi. Il Lorenzo futuro avrà dimenticato perché hai fatto così: i commenti, i docstring, gli ADR, i test sono per lui.

2. **Semplicità vince su cleverness**. Pattern complessi "che potrebbero servire" aggiungono debito. Quando hai un dubbio, scegli la soluzione più semplice che risolve il problema attuale, con apertura a rifattorizzazione futura.
