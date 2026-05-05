# `apps/governance` — Contesto dominio

## Responsabilità

Gestisce due aree critiche trasversali:

1. **Merge di nodi duplicati** (`MergeProposal`, `MergeVote`) — quando due `Person` rappresentano la stessa persona reale ma sono state create indipendentemente (es: un cugino crea "nonno Giuseppe" che già esisteva), vanno unificate.
2. **Audit log** (`AuditLog`) — registro append-only di ogni azione sensibile del sistema. Fonte di verità per forensics, trasparenza tra curatori, e compliance GDPR.

## Entità principali

- **`MergeProposal`** — proposta di unire due `Person` in una. Ha un `person_a_id` (sopravvive) e `person_b_id` (assorbito).
- **`MergeVote`** — voto dei curatori di entrambi i nodi sulla proposta.
- **`AuditLog`** — entry immutabile per ogni azione sensibile. Nessun UPDATE, nessun DELETE.

## Dipendenze

- Dipende da: `core`, `identity`, `tree`, `curatorship`, `permissions`
- Viene **chiamato da** praticamente ogni altro dominio (per audit logging)

## Vincoli critici

### Vincolo 1: AuditLog è append-only (hard)
A livello DB:
- REVOKE UPDATE, DELETE sul ruolo applicativo per `audit_log`
- Trigger `BEFORE UPDATE OR DELETE ON audit_log RAISE EXCEPTION`

Anche un superuser/admin non può modificare o cancellare entry di audit log tramite applicazione. L'unica modalità di manutenzione è via superuser DB (es: dopo GDPR request per cancellare dati personali in entry storiche) e va fatto fuori dall'applicazione, con approvazione manuale.

### Vincolo 2: Ogni mutation scrive audit
Regola: se una funzione modifica stato persistente di un'entità principale (Person, Content, Relationship, MedicalRecord, Curatorship, Curatorships, AccessGrant, NodePolicyOverride, Invitation, PersonClaim, SocialConnection), **deve** scrivere un'entry in audit_log.

Pattern: helper `write_audit(action_type, entity, changes_diff=None, actor=None, context=None)` in `governance/services/audit_service.py`. Tutti i service di dominio lo chiamano.

Non usare signals auto per audit: vogliamo controllo esplicito sui dati registrati, e i signals rendono difficile l'attribuzione di `actor`.

### Vincolo 3: Merge è distruttivo e irreversibile (quasi)
Quando un `MergeProposal` viene `applied`:
- `person_b_id` (absorbed) viene hard-archiviato: `archived_at = now()`, marked as merged_into=person_a_id
- Tutti i riferimenti a `person_b_id` in altre tabelle (Relationship, ContentSubject, Curatorship, ecc.) vengono **repointed** a `person_a_id`
- Cache `person_distances` invalidata
- Audit log dettagliato con diff before/after

La reversibilità è limitata: se entro 30 giorni un curatore si accorge di errore, è possibile un "undo merge" manuale che ricrea person_b con copia di stato pre-merge (gli state sono preservati in audit_log entry dettagliato). Oltre 30 giorni, l'undo richiede intervento manuale via admin.

### Vincolo 4: Merge richiede consenso bilaterale
Un `MergeProposal` richiede approvazione da **entrambi i lati**:
- Curatori del person_a (sopravvive): voto di maggioranza semplice
- Curatori del person_b (absorbed): voto di maggioranza semplice

Se person_a o person_b ha `user_id` (è vivente con account), l'utente stesso è il solo "curatore" che deve approvare.

### Vincolo 5: Match automatico suggerisce, non applica
Un Celery task periodico può scansionare person con nome + anno nascita simili e creare `MergeProposal` con `confidence_score`. Ma **mai auto-applicare**. L'applicazione richiede sempre voto/approvazione umana.

### Vincolo 6: Audit log contiene il diff, non solo il fatto
`changes_diff` (JSONB) deve contenere before/after dei campi modificati. Esempio:
```json
{
  "before": {"short_bio": "Architetto a Milano"},
  "after": {"short_bio": "Architetto a Milano, laureato al Politecnico"}
}
```
Non è sufficiente `{"action": "updated"}`. Serve ricostruire cosa è cambiato per investigation/rollback.

## Flussi principali

### Merge proposal flow

```
1. Utente trova due Person che crede duplicati (o task automatico li trova)
2. POST /api/merge-proposals/ con person_a_id (sopravvive), person_b_id (absorbed), reason
3. Sistema determina curatori di entrambi i nodi
4. Crea MergeProposal(status='pending', proposed_at=now)
5. Notifiche a tutti i curatori coinvolti con link a view comparativa side-by-side
6. Ogni curatore vota: MergeVote(side='person_a' o 'person_b', ballot='approve'/'reject')
7. Quando ogni lato ha raggiunto maggioranza o rejection:
   - Entrambi approved → proceed
   - Anche uno solo rejected → MergeProposal.status='rejected'
8. Se approved, Celery task apply_merge(proposal):
   - Transaction:
     - Repoint relationships: UPDATE relationships SET person_a_id = NEW WHERE person_a_id = OLD, same for person_b_id
     - Repoint content_subjects, curatorships, curatorship_requests, curatorship_votes, social_connections, medical_records
     - Person_b archived_at = now, metadata.merged_into = person_a.id
     - Person_a short_bio merged (user-edited later, for now concatenate or keep person_a's)
     - Cache person_distances invalidated (trigger)
   - Audit log entry ESTESA con dump completo di person_b pre-merge e diff applicato
9. Notifica a tutti i curatori coinvolti: "merge completato"
```

### Undo merge (entro 30gg)

```
1. Curatore nota errore, POST /api/merges/{id}/undo/ (solo se applied_at < 30 days ago)
2. Servizio:
   - Ricrea person_b dalla entry di audit_log
   - Repoint parziale: entità dove ha senso riportare (content_subjects taggati manualmente dopo merge non vengono repointed — sono post-merge e rimangono su person_a)
   - Il comportamento "cosa repointare in undo" è documentato in docs/runbooks/merge-undo.md
   - Audit log entry di tipo 'undo_merge'
3. Solo entro 30gg automatico. Oltre, manual DB intervention.
```

### Write audit log

```python
from apps.governance.services.audit_service import write_audit

def update_person(person, changes, actor):
    old_state = {k: getattr(person, k) for k in changes.keys()}
    for k, v in changes.items():
        setattr(person, k, v)
    person.save()
    write_audit(
        action_type='update_person',
        entity=person,
        changes_diff={'before': old_state, 'after': changes},
        actor=actor,
    )
```

### Audit query

Endpoint admin-only: `GET /api/admin/audit/?entity_type=persons&entity_id=X`
Restituisce cronologia completa di un'entità, utile per:
- Trasparenza verso curatori: chi ha modificato cosa e quando
- Forensics in caso di contestazione
- Debug di bug in produzione

## Servizi chiave

### `services/audit_service.py`
- `write_audit(action_type, entity, changes_diff=None, actor=None, context=None)` → AuditLog
- `get_entity_history(entity_type, entity_id)` → list[AuditLog]
- `get_actor_actions(user, since=None)` → list[AuditLog]

### `services/merge_service.py`
- `propose_merge(person_a, person_b, proposer, reason=None, confidence=None)` → MergeProposal
- `cast_merge_vote(proposal, voter, side, ballot)` → MergeVote
- `tally_merge(proposal)` → proposal outcome (approved_both_sides / rejected)
- `apply_merge(proposal)` → Person (person_a, with merged state)
- `undo_merge(proposal)` → Person (person_b restored) — solo se applied_at < 30gg

### `services/duplicate_detector.py` (Celery task periodico)
- `find_potential_duplicates()` → list[MergeProposal] creati con confidence_score
- Usa rapidfuzz per matching su (given_names + surname + birth_year)
- Soglia di confidence_score configurabile, solo proposte sopra soglia

## File attesi

```
governance/
├── __init__.py
├── apps.py
├── CLAUDE.md
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── admin.py
├── services/
│   ├── __init__.py
│   ├── audit_service.py
│   ├── merge_service.py
│   └── duplicate_detector.py
├── tasks.py                   # find_duplicates, apply_approved_merges
├── factories.py
├── migrations/
│   └── 0002_audit_log_append_only.py    # trigger/grants per append-only
└── tests/
    ├── test_audit_append_only.py        # Try to update/delete → fails
    ├── test_merge_flow.py
    ├── test_merge_repoint.py
    ├── test_merge_undo.py
    ├── test_duplicate_detection.py
    └── test_audit_helpers.py
```

## Test density richiesta

80%+. Audit e merge sono critici per trasparenza e integrità dei dati. Test obbligatori:

- `audit_log` UPDATE/DELETE **impossibili** a livello DB (test SQL raw)
- Merge repoint è completo: nessun record "fantasma" che punta al person_b dopo merge
- Merge requires approvazione di entrambi i lati
- Undo merge entro 30gg funziona e ripristina stato
- Undo merge oltre 30gg è rifiutato
- Duplicate detector crea proposte, mai applica merge
