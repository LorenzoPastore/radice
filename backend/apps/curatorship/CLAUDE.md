# `apps/curatorship` — Contesto dominio

## Responsabilità

Gestisce la **curatela** dei nodi `Person` che non hanno un `User` associato (defunti, minori, anziani non digitali, non-ancora-registrati). La curatela è il meccanismo con cui uno o più utenti si prendono la responsabilità di mantenere, aggiornare e gestire la visibilità di un nodo.

Include anche il **sistema di voto** per decisioni straordinarie su nodi con curatela condivisa.

## Entità principali

- **`Curatorship`** — relazione attiva: un `User` è curatore (primary o co_curator) di una `Person`.
- **`CuratorshipRequest`** — richiesta pendente di diventare curatore (con auto-approvazione dopo N giorni se il primary non risponde).
- **`CuratorshipVote`** — proposta di decisione straordinaria che richiede voto dei co-curatori.
- **`CuratorshipVoteBallot`** — singolo voto di un co-curatore su una proposta.

## Dipendenze

- Dipende da: `core`, `identity`, `tree` (per determinare chi può richiedere curatela in base alla distanza)
- Fornisce servizi a: `permissions` (determina archetipo "primary_curator"/"co_curator"), `content`, `medical`, `governance`

## Vincoli critici

### Vincolo 1: Solo nodi senza User hanno curatela esplicita
Se `Person.user_id IS NOT NULL`, la curatela è implicita (l'utente è curatore di se stesso). Non devono esistere `curatorships` attive per Person con User. Quando un User reclama una Person, le curatorships preesistenti vanno terminate (status='ended').

### Vincolo 2: Al più un `primary` attivo per Person
Vincolo DB: UNIQUE INDEX parziale su `(person_id) WHERE role='primary' AND status='active'`. Se il primary cambia, serve un passaggio esplicito: il vecchio primary diventa co_curator, il nuovo diventa primary. Mai due primary in parallelo.

### Vincolo 3: Auto-approvazione richiede cron task
`CuratorshipRequest` con `auto_approve_at` futuro. Un Celery Beat task schedulato (`check_auto_approve_curatorships`, ogni 6h) scansiona request pendenti con `auto_approve_at < now()` e le promuove a `status='auto_approved'`. Se il task non gira per giorni, l'auto-approvazione è ritardata ma non persa.

### Vincolo 4: Chi può richiedere co-curatela
Solo utenti a **distanza ≤ 2** dal defunto (familiari stretti: figli, nipoti, fratelli, nipoti diretti, coniuge) possono richiedere co-curatela senza approvazione automatica a 14 giorni. Utenti più lontani possono richiedere ma non beneficiano dell'auto-approvazione; serve sempre approvazione esplicita del primary.

Enforced a livello di service (`request_service`), non di DB. Logica:
```python
if distance(requester, target_person) <= 2:
    auto_approve_at = now + 14 days
else:
    auto_approve_at = now + 30 days  # finestra più lunga, ma approvazione manuale più probabile
```

### Vincolo 5: Decisioni straordinarie richiedono voto
Azioni classificate come "straordinarie" (vedi lista sotto) NON possono essere eseguite da un singolo co-curatore quando esiste curatela condivisa. Richiedono `CuratorshipVote` + maggioranza.

**Azioni straordinarie**:
- Cambio `privacy_preset` o creazione `NodePolicyOverride` del nodo
- Approvazione di `MergeProposal` che coinvolge il nodo
- Archiviazione del nodo (`archive_person`)
- Revoca di un altro co-curatore
- Approvazione di inserimento di `medical_record` (unanimità richiesta, non maggioranza)

**Azioni ordinarie** (qualsiasi co-curatore può agire, tracciato in audit log):
- Aggiunta/modifica di `Content`
- Aggiunta/modifica di `Relationship` strutturale (con conferma dell'altra parte coinvolta)
- Aggiunta/modifica di `FamilyAffinity`
- Aggiornamento di `short_bio`, date, luoghi

### Vincolo 6: Voto — maggioranza vs unanimità
- **Maggioranza semplice**: decisioni straordinarie generiche. Maggioranza dei co-curatori attivi, calcolata su chi ha votato entro deadline.
- **Unanimità**: solo per approvazione di inserimento/modifica di `MedicalRecord`. Tutti i co-curatori attivi devono approvare. Se uno rifiuta o non vota, respinto.

In caso di parità in maggioranza semplice: **status quo vince** (nessun cambiamento).

## Flussi principali

### Creazione curatela per defunto

```
1. User crea Person con is_living=false
2. Transaction:
   - Crea Person (created_by_user_id = self)
   - Crea Curatorship(person, user, role='primary', status='active')
3. Audit log
```

### Richiesta co-curatela

```
1. User familiare (ideally distance ≤ 2) vede Person con curatela esistente
2. Compila CuratorshipRequest con reason opzionale
3. Calcolo auto_approve_at basato su distanza
4. Notifica al primary_curator
5. Primary approva → Curatorship creata con role='co_curator'
   Primary rifiuta → status='rejected', notifica al requester
   Nessuna risposta → dopo auto_approve_at, cron task promuove a 'auto_approved' e crea Curatorship
6. Audit log in tutti i casi
```

### Voto su decisione straordinaria

```
1. Co-curatore propone decisione → CuratorshipVote(proposal_type, proposal_payload, deadline=now+7days)
2. Notifica a tutti i co-curatori attivi
3. Ogni co-curatore vota: CuratorshipVoteBallot(ballot='approve'|'reject'|'abstain')
4. A scadenza (o quando tutti hanno votato):
   - Count votes
   - Applica regola (maggioranza/unanimità) in base a proposal_type
   - Updata status: 'passed' | 'rejected' | 'expired'
5. Se 'passed': eseguita l'azione proposta (esecuzione in service dedicato, es: applicare NodePolicyOverride)
6. Audit log con esito
```

### Passaggio di curatela

Se il primary si dimette, viene rimosso, o è inattivo per troppo tempo:
1. Proposta di successione (CuratorshipVote con proposal_type='revoke_curator')
2. Se approvata, il co-curator più anziano (prima `started_at`) diventa automaticamente primary
3. Se nessun co-curator esiste, la curatela rimane "orfana" fino a nuovo claim; i nodi orfani sono flaggati in admin per attenzione

## Servizi chiave

### `services/curatorship_service.py`
- `create_primary_curatorship(user, person)` → Curatorship
- `add_co_curator(person, user, approver_user)` → Curatorship
- `remove_co_curator(curatorship, remover_user)` → Curatorship
- `transfer_primary(from_user, to_user, person)` → (Curatorship, Curatorship)
- `end_curatorship(curatorship, reason)` → Curatorship
- `get_active_curators(person)` → list[User]

### `services/request_service.py`
- `request_curatorship(user, person, reason=None)` → CuratorshipRequest
- `approve_request(request, approver)` → Curatorship
- `reject_request(request, rejecter, reason)` → CuratorshipRequest
- `auto_approve_expired_requests()` → int (Celery task)

### `services/voting_service.py`
- `propose_decision(person, proposer, proposal_type, payload)` → CuratorshipVote
- `cast_ballot(vote, voter, ballot)` → CuratorshipVoteBallot
- `tally_vote(vote)` → decision_outcome
- `apply_decision(vote)` → esegue azione se passed (delega al service di dominio)
- `expire_votes()` → int (Celery task)

## File attesi

```
curatorship/
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
│   ├── curatorship_service.py
│   ├── request_service.py
│   └── voting_service.py
├── tasks.py                 # auto_approve_requests, expire_votes
├── factories.py
└── tests/
    ├── test_models.py
    ├── test_curatorship_lifecycle.py
    ├── test_request_flow.py
    ├── test_auto_approve.py
    ├── test_voting_majority.py
    ├── test_voting_unanimity.py
    └── test_primary_uniqueness.py
```

## Test density richiesta

75%+. Flussi complessi (auto-approvazione, voto con scadenze, passaggio primary) hanno molti rami che vanno tutti coperti. Test obbligatori per:
- Race condition: due richieste auto-approvate simultaneamente — solo una diventa Curatorship
- Voto scaduto con parità → status quo
- Voto con unanimità e un abstain → rejected (abstain conta come non-approvazione)
- Passaggio primary quando il primary è inattivo da >180 giorni
