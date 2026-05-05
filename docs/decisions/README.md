# Architecture Decision Records

Questa cartella contiene gli ADR (Architecture Decision Records) del progetto Radice. Ogni ADR documenta una decisione architetturale significativa: contesto, opzioni valutate, decisione presa, conseguenze.

## Indice

| ID  | Titolo                                                              | Status    |
|-----|---------------------------------------------------------------------|-----------|
| 001 | [Monorepo per backend e frontend](./001-monorepo.md)                | Accepted  |
| 002 | [Backend: Django + DRF](./002-django-backend.md)                    | Accepted  |
| 003 | [PostgreSQL puro, no estensioni grafo](./003-postgresql-only.md)    | Accepted  |
| 004 | [Visualizzazione: react-flow + layout custom](./004-react-flow.md)  | Accepted  |
| 005 | [Separazione User e Person](./005-user-person-separation.md)        | Accepted  |
| 006 | [Pipeline permessi stratificata in 3 livelli](./006-permissions-pipeline.md) | Accepted |
| 007 | [Deploy: Vercel + Railway](./007-vercel-railway.md)                 | Accepted  |

## Quando scrivere un nuovo ADR

Scrivi un ADR ogni volta che prendi una decisione che:
- Ha conseguenze a lungo termine sull'architettura
- È difficile da invertire
- Ha più opzioni plausibili
- Richiede giustificazione quando un nuovo collaboratore (o agente AI) la incontra

Non scrivere un ADR per:
- Dettagli di implementazione reversibili (scelta di una libreria minore)
- Scelte di naming o formattazione (vanno in `conventions.md`)
- Bug fix e feature incrementali

## Template

Copia `_template.md` per creare un nuovo ADR.

## Status possibili

- **Proposed** — proposta in discussione
- **Accepted** — decisione presa e attiva
- **Rejected** — proposta scartata
- **Deprecated** — decisione sostituita da un ADR successivo
- **Superseded by ADR-XXX** — esplicitamente sostituita
