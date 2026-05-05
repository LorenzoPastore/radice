# `apps/identity` — Contesto dominio

## Responsabilità

Gestisce le **entità di identità** del sistema: account utente (`User`), persone reali (`Person`), i flussi di rivendicazione (`PersonClaim`) e invito (`Invitation`).

Questo dominio implementa la **separazione fondamentale User ↔ Person** (vedi ADR-005). È uno dei domini più critici del progetto: se la distinzione si offusca qui, tutto il resto si rompe.

## Entità principali

- **`User`** — account registrato. Ha email, password, preferenze, locale. Relazione 1:1 obbligatoria con `Person` (`User.person_id` FK unique NOT NULL).
- **`Person`** — persona reale (viva o morta). Può avere o non avere uno `User` associato (`Person.user_id` FK unique nullable).
- **`PersonClaim`** — richiesta di un `User` di rivendicare una `Person` esistente (es: "io sono questo nodo già creato da altri").
- **`Invitation`** — invito a un futuro utente, con token one-time, può essere legato a un `target_person_id` specifico (claim su invito) o generico (registrazione libera).

## Dipendenze

- Dipende da: `core` (base models, middleware)
- Dipende **da nessun altro dominio** per la logica di base (identity è vicino alla radice delle dipendenze)
- Domini che dipendono da `identity`: **tutti gli altri**

## Vincoli critici (non negoziabili)

### Vincolo 1: Separazione User ↔ Person
Mai fondere questi due concetti. Ogni volta che serve "l'utente che ha fatto X", usa `User`. Ogni volta che serve "la persona di cui parliamo", usa `Person`. In query, serializer, nomi di variabile, tutto.

Naming conventions:
- `viewer_user`, `actor_user`, `request.user` → sempre `User`
- `target_person`, `subject_person`, `person` → sempre `Person`
- In caso di ambiguità, specificare: `created_by_user` invece di `created_by`

### Vincolo 2: Ogni User ha esattamente una Person
Alla registrazione, il flusso crea **sempre** una Person associata. Non esistono User senza Person. Questo è enforced via:
- `User.person_id` FK NOT NULL UNIQUE
- Transazione atomica nel registration service
- Test che verificano l'invariante

### Vincolo 3: Una Person può avere zero o uno User
`Person.user_id` è nullable e unique. La maggior parte delle Person non avrà mai uno User (defunti, antenati). Le query devono gestire entrambi i casi.

### Vincolo 4: Claim è un processo, non un'operazione atomica
Quando un User reclama una Person preesistente, è una **richiesta** (`PersonClaim` con `status='pending'`). Viene approvata da chi ha creato originariamente la Person (e ne è curatore primario). Solo dopo approvazione la relazione `Person.user_id = claiming_user_id` viene stabilita.

## Flussi principali

### Registrazione nuova (utente senza Person preesistente)

```
1. User compila form registrazione con email, password, dati base (nome, cognome, data nascita)
2. Transaction:
   - Crea User
   - Crea Person (is_living=true, created_by_user_id=self)
   - Associa: User.person_id = Person.id, Person.user_id = User.id
   - Crea Curatorship implicita (skippata: l'user è curatore di se stesso by design)
3. Invia email verification
4. User deve verificare email prima di poter interagire con altri User
```

### Registrazione su invito (utente con Person preesistente)

```
1. Inviter crea Invitation(target_person_id=X, invited_email=Y)
2. Email inviata con token one-time
3. Invitee clicca link → landing con token
4. Se email match Y: shortcut, auto-claim automatico
   Se email diversa: compila form standard + claim manuale
5. Transaction:
   - Crea User con email
   - Person X viene reclamata: Person.user_id = User.id, Person.is_claimed = true
   - Invitation.status = 'accepted'
   - Crea PersonClaim con status='approved' (per audit)
   - Termina Curatorship preesistente del creator (automatic)
6. Email verification flow
```

### Claim di nodo esistente (da utente già registrato)

```
1. User navigando l'albero trova Person che crede essere se stesso
2. Invia PersonClaim(person_id, claiming_user_id=self)
3. Notifica al created_by_user_id della Person
4. Creator approva/rifiuta
5. Se approvato:
   - Person.user_id = claiming_user_id
   - Person.is_claimed = true
   - Vecchia Person eventualmente associata al claiming_user viene archiviata (merge considerato separatamente)
   - Audit log entry
```

## Servizi chiave

### `services/registration_service.py`
- `register_new_user(email, password, person_data)` → (User, Person)
- `register_from_invitation(token, password)` → (User, Person)

### `services/claim_service.py`
- `request_claim(user, target_person)` → PersonClaim
- `approve_claim(claim, approver_user)` → Person (updated)
- `reject_claim(claim, approver_user, reason)` → PersonClaim (updated)

### `services/invitation_service.py`
- `create_invitation(inviter, email, target_person=None, message=None)` → Invitation
- `revoke_invitation(invitation, revoker)` → Invitation
- Celery task per scadenza automatica (`expires_at`)

## File attesi

```
identity/
├── __init__.py
├── apps.py
├── CLAUDE.md
├── models.py
├── managers.py
├── serializers.py
├── views.py
├── urls.py
├── admin.py
├── signals.py               # Hook per audit log, notifications
├── services/
│   ├── __init__.py
│   ├── registration_service.py
│   ├── claim_service.py
│   └── invitation_service.py
├── tasks.py                 # Celery: invitation expiry, email verification resend
├── factories.py             # Test factories
└── tests/
    ├── test_models.py
    ├── test_registration.py
    ├── test_claim.py
    ├── test_invitation.py
    └── test_user_person_invariants.py   # Test critici sui vincoli
```

## Admin Django

- `UserAdmin` custom: mostra User + Person linkata, azioni per gestire claim manuali, export GDPR
- `PersonAdmin`: mostra claims pendenti, curatorships attive, link a nodi correlati
- Admin per `Invitation`, `PersonClaim` con filtri per status

## Test density richiesta

70%+. I vincoli User/Person sono fondativi e la loro violazione è catastrofica. Test obbligatori per:
- Invariante: ogni User ha una Person
- Invariante: ogni Person ha al massimo uno User
- Flusso claim (tutti i rami: approvato, rifiutato, scaduto)
- Flusso invitation (tutti i rami incluso token expiry, revoca, mismatched email)
- GDPR delete preserva struttura ma anonimizza User data
