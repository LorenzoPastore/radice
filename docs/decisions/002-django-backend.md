# ADR-002: Backend Django + Django REST Framework

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

Il backend di Radice deve gestire:
- Schema relazionale complesso (~33 tabelle interconnesse)
- Logica di permessi stratificata molto articolata
- Auth, registration, OAuth, invite flow, claim flow
- Task asincroni (media processing, email, cache invalidation, backup)
- API REST consumate da frontend Next.js

Il maintainer (Lorenzo) ha esperienza solida in Django, FastAPI, e NestJS/TypeScript. La scelta non è limitata dalla familiarità, ma va fatta per fit con il progetto.

## Opzioni valutate

### Opzione 1: Django + DRF + drf-spectacular
Framework full-stack Python, ORM Django, DRF per API, drf-spectacular per generare OpenAPI.

Pro:
- ORM Django gestisce relazioni complesse (FK multiple, reverse relations, prefetch) più produttivamente di SQLAlchemy o Prisma
- Admin panel gratuito — valore concreto per un progetto familiare con casi edge (merge manuali, consent inspection)
- Ecosistema maturissimo per auth (django-allauth), permessi (django-guardian), GDPR, audit (django-auditlog o simili)
- Migrations stabili e sicure
- Battle-tested in produzione da migliaia di progetti

Contro:
- Async ancora acerbo — task long-running vanno in Celery (comunque previsto)
- Pattern "API + SPA separate" aggiunge overhead vs framework full-stack (es: Next.js + tRPC)
- Meno moderno come DX rispetto a FastAPI o NestJS

### Opzione 2: FastAPI + SQLAlchemy 2 + Alembic
Async-first, più flessibile, DX moderna.

Pro:
- Async nativo, performance I/O migliori
- Schema OpenAPI generato automaticamente da Pydantic
- Libertà architetturale totale

Contro:
- SQLAlchemy è potente ma più verboso di Django ORM per relazioni complesse
- No admin panel built-in (SQLAdmin è un palliativo)
- Auth, permissions, audit da assemblare a mano con molte dipendenze
- Su 33 tabelle con molta business logic, la "libertà" diventa lavoro in più

### Opzione 3: NestJS + Prisma (TypeScript)
Tipizzazione end-to-end con Next.js, DX moderna.

Pro:
- TypeScript condiviso backend/frontend (tramite tRPC o schema generation)
- Prisma ha DX eccellente per CRUD semplici
- Ecosistema Node ricchissimo

Contro:
- Prisma limitato su query complesse: CTE ricorsive per distanze richiedono `$queryRaw` non type-safe
- Ecosistema auth Node frammentato (NextAuth è ok, ma meno integrato di django-allauth)
- Raddoppia la superficie di sviluppo (backend + frontend entrambi TS, ma patterns e librerie diversi)

## Decisione

**Django 5 + DRF + drf-spectacular**.

Tre ragioni concrete:

1. **Schema complesso**: 33 tabelle con molte FK, reverse relations, query che attraversano più domini. Django ORM è più produttivo qui di Prisma o SQLAlchemy. La logica di dominio cresce naturalmente con pattern service layer.

2. **Admin panel come asset nascosto**: casi edge di un progetto familiare (merge di nodi duplicati scoperti a posteriori, ispezione di consenso medico, correzioni di dati inseriti male da parenti) richiedono un'interfaccia amministrativa. Costruirla in Node/FastAPI sono settimane di lavoro. Django la dà gratis.

3. **Stack auth/permissions maturo**: django-allauth (email + OAuth), django-guardian (per-object permissions), ecosistema GDPR → tutto testato in produzione. L'equivalente Node è assemblare 4-5 librerie.

Il "costo" di non avere TypeScript end-to-end lo compensiamo con **drf-spectacular → OpenAPI → TypeScript types generation** sul frontend (via `openapi-typescript`). Non è elegante come tRPC ma è efficace e stabile.

## Conseguenze

### Positive
- Produttività alta sullo schema relazionale complesso
- Admin panel gratuito per operazioni edge
- Ecosistema maturo per ogni need (auth, Celery, migrations, DRF, GDPR)
- Stabilità di piattaforma per progetto decennale

### Negative / Trade-off
- Due linguaggi (Python backend, TypeScript frontend) invece di uno solo
- Tipi condivisi via generazione da OpenAPI, non nativi (build step)
- Async limitato: I/O pesante va in Celery workers

### Trigger per riconsiderazione
- Se il progetto diventasse prevalentemente realtime/streaming (WebSocket intensivi), valutare Django Channels o spostare a FastAPI
- Se le performance di I/O diventassero bottleneck (improbabile a scala familiare)
