# ADR-001: Monorepo per backend e frontend

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

Radice ha un backend Django e un frontend Next.js che condividono inevitabilmente tipi e schema API. Bisogna scegliere come organizzarli in termini di repository: monorepo (un solo repo per tutto) vs multi-repo (un repo per backend, uno per frontend, uno per shared).

## Opzioni valutate

### Opzione 1: Monorepo
Un unico repository `radice/` con cartelle `backend/`, `frontend/`, `shared/`, `docs/`.

Pro:
- Refactoring atomici: una modifica che tocca backend e frontend sta in una singola PR coerente
- Schema OpenAPI generato da Django e consumato dal frontend via pipeline interna di build
- Una sola GitHub Actions pipeline con path filtering per build incrementali
- Un solo CLAUDE.md radice più contesti per-dominio, agenti AI leggono tutto in una sola struttura
- Deploy configurato per leggere solo le cartelle rilevanti (Vercel → `frontend/`, Railway → `backend/`)

Contro:
- Repo cresce di dimensione
- Clonazione più lenta
- CI più complessa da ottimizzare per build incrementali

### Opzione 2: Multi-repo
`radice-backend`, `radice-frontend`, `radice-shared` come repository separati.

Pro:
- Separazione netta di responsabilità
- Dimensione repo contenuta
- Permessi di accesso granulari (se mai fossero rilevanti)

Contro:
- Cambio schema API richiede PR coordinate su 3 repo
- `radice-shared` va pubblicato come package (npm + pypi) o gestito come git submodule — entrambi dolorosi
- Contesto per agenti AI frammentato: devono saltare tra repo senza vista unificata

## Decisione

**Monorepo**.

Per un progetto personale single-developer con forte accoppiamento naturale tra backend e frontend, il monorepo elimina problemi reali (coordinamento PR, versioning shared package) in cambio di costi trascurabili (dimensione repo, CI). Il vantaggio principale è operativo: Claude Code e gli agenti specializzati hanno accesso a tutto il contesto in una singola struttura di cartelle, con CLAUDE.md contestuali per dominio.

## Conseguenze

### Positive
- PR atomiche e coerenti su tutto lo stack
- Schema API condiviso senza overhead di pubblicazione package
- Un solo backlog, un solo issue tracker, un solo set di GitHub Actions
- Documentazione centralizzata in `docs/`

### Negative / Trade-off
- CI deve gestire path filtering per non eseguire test frontend su PR solo-backend
- Build time iniziale può essere più lungo fino a configurazione cache corretta
- Repo diventa grande nel tempo (accettabile per almeno 5 anni)

### Trigger per riconsiderazione
- Se in futuro il progetto si dividesse in più app indipendenti con team separati
- Se la dimensione del repo superasse i 5GB (improbabile)
- Se servisse open-source separato di uno dei due componenti
