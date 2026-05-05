# Radice

**Radice** is a family memory preservation web app. It's a mobile-first, offline-first PWA designed to help families collaboratively preserve photos, stories, and documents — especially about relatives who have passed away — alongside a light directory of living family members and a separate module for personal social networks (guanxi).

This is a long-term personal project intended to last 10+ years.

## Project status

Early development. Walking skeleton not yet implemented.

## Repository layout

```
radice/
├── backend/          Django 5 + DRF + Celery
├── frontend/         Next.js 15 + React 19 + TypeScript
├── shared/           OpenAPI schema and shared types
├── docs/             Architecture, data model, decisions
└── .claude/          Claude Code agents and commands
```

## Quick start (development)

_To be filled once the walking skeleton is implemented._

## Documentation

- [`CLAUDE.md`](./CLAUDE.md) — Entry point for AI agents working on this codebase
- [`docs/architecture.md`](./docs/architecture.md) — System overview
- [`docs/data-model.md`](./docs/data-model.md) — Complete database schema
- [`docs/permissions-model.md`](./docs/permissions-model.md) — Permission system design
- [`docs/roadmap.md`](./docs/roadmap.md) — Development backlog and milestones
- [`docs/conventions.md`](./docs/conventions.md) — Git flow, testing, naming
- [`docs/decisions/`](./docs/decisions/) — Architecture Decision Records

## License

_TBD — personal project, not yet licensed for external use._

## Author

Lorenzo Pastore
