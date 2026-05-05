# Radice — Data Model

Questo documento descrive lo schema completo del database. È la fonte di verità per lo schema. Migrations e ORM devono essere allineati a questo documento. Se una migration diverge, aggiorna prima questo documento.

## Principi generali

- **PostgreSQL 16+**, schema relazionale puro. No estensioni grafo (per ora).
- **UUID v4** come primary key per tutte le entità principali. Motivi: portabilità, export, privacy dei sequential ID.
- **`created_at` / `updated_at`** automatici via mixin base (`TimestampedModel`).
- **Soft delete** via campo `archived_at` nullable per entità principali; hard delete solo via flusso GDPR.
- **JSONB** per campi flessibili (metadata, preferences, diff changes).
- **Enum PostgreSQL** per valori chiusi; mai testo libero dove la lista è nota.
- **Foreign key** con `ON DELETE RESTRICT` per integrità referenziale; cascade solo dove esplicitamente giustificato.
- **Indici** su tutte le FK, sui campi frequentemente filtrati, e su composite key per query calde.

## Separazione fondamentale: User vs Person

Questa è la distinzione centrale di tutto lo schema.

- **`User`** è un account registrato nell'app (email, password, sessione, preferenze).
- **`Person`** è una persona reale, viva o morta, con o senza account.

Relazione:
- Ogni `User` ha esattamente una `Person` (`User.person_id` FK unique, NOT NULL).
- Una `Person` può avere zero o uno `User` (`Person.user_id` FK unique, nullable).

Implicazioni:
- Un defunto è sempre `Person` senza `User`.
- Un utente che si registra o crea una nuova `Person` per sé, o rivendica (claim) una `Person` esistente creata da altri.

## Entità per dominio

### Dominio identity

#### `users`
```
id                    UUID PK
email                 text UNIQUE NOT NULL
email_verified_at     timestamptz NULL
password_hash         text NULL                    -- null se solo OAuth
oauth_providers       JSONB DEFAULT '[]'            -- ["google", "apple"]
person_id             UUID FK persons(id) UNIQUE NOT NULL
display_name          text NOT NULL
locale                text DEFAULT 'it-IT'
timezone              text DEFAULT 'Europe/Rome'
notification_preferences JSONB DEFAULT '{}'
privacy_preset        enum('reserved','balanced','open','custom') DEFAULT 'balanced'
privacy_custom_overrides JSONB NULL                 -- overrides granulari se preset='custom'
last_login_at         timestamptz NULL
created_at            timestamptz NOT NULL
updated_at            timestamptz NOT NULL
deleted_at            timestamptz NULL              -- soft delete
```

#### `persons`
```
id                    UUID PK
user_id               UUID FK users(id) UNIQUE NULL  -- backref se esiste account
given_names           text NOT NULL
surname               text NOT NULL
surname_at_birth      text NULL                      -- per cognome da nubile
nicknames             text[] DEFAULT '{}'
is_living             boolean NOT NULL
birth_date            date NULL
birth_date_precision  enum('exact','month','year','decade','unknown')
birth_place           text NULL
death_date            date NULL
death_date_precision  enum('exact','month','year','decade','unknown')
death_place           text NULL
gender                enum('male','female','non_binary','unknown','other')
profile_photo_content_id UUID FK contents(id) NULL
short_bio             text NULL
is_claimed            boolean DEFAULT false
created_by_user_id    UUID FK users(id) NOT NULL
created_at            timestamptz NOT NULL
updated_at            timestamptz NOT NULL
archived_at           timestamptz NULL               -- soft delete
```

Vincoli:
- Se `is_living = false`, `death_date` deve esistere (anche con precisione bassa).
- Se `death_date` e `birth_date` entrambe precise: `birth_date <= death_date`.

#### `person_claims`
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
claiming_user_id      UUID FK users(id) NOT NULL
status                enum('pending','approved','rejected','expired') DEFAULT 'pending'
requested_at          timestamptz NOT NULL
resolved_at           timestamptz NULL
resolved_by_user_id   UUID FK users(id) NULL
rejection_reason      text NULL
```

#### `invitations`
```
id                    UUID PK
invited_email         text NOT NULL
target_person_id      UUID FK persons(id) NULL       -- per claim di nodo esistente
inviter_user_id       UUID FK users(id) NOT NULL
token                 text UNIQUE NOT NULL           -- hash one-time
status                enum('sent','accepted','revoked','expired') DEFAULT 'sent'
message               text NULL
sent_at               timestamptz NOT NULL
accepted_at           timestamptz NULL
expires_at            timestamptz NOT NULL
```

### Dominio tree

#### `relationships`
```
id                    UUID PK
person_a_id           UUID FK persons(id) NOT NULL
person_b_id           UUID FK persons(id) NOT NULL
type                  enum('parent_child','spouse','sibling') NOT NULL
subtype               text NOT NULL                  -- enum esteso, vedi sotto
start_date            date NULL                      -- per matrimoni
start_date_precision  enum('exact','month','year','decade','unknown')
end_date              date NULL                      -- per divorzi, decessi
end_date_precision    enum('exact','month','year','decade','unknown')
metadata              JSONB DEFAULT '{}'
is_verified           boolean DEFAULT false          -- confermato da entrambe le parti
created_by_user_id    UUID FK users(id) NOT NULL
created_at            timestamptz NOT NULL
updated_at            timestamptz NOT NULL
archived_at           timestamptz NULL
```

Valori di `subtype`:

Per `type='parent_child'`:
- `biological`, `legal_adoption`, `step_parent`, `de_facto_parent`, `godparent`, `foster`

Per `type='spouse'`:
- `marriage`, `civil_union`, `de_facto_partnership`, `engaged`

Per `type='sibling'`:
- `full_biological`, `half_biological`, `step`, `adoptive`, `de_facto`

Vincoli (via DB constraint e/o trigger):
- `person_a_id != person_b_id`
- Unicità della tripla `(person_a_id, person_b_id, type)`
- Per `type='parent_child'`: direzionato, `person_a_id` è il genitore, `person_b_id` il figlio
- Per `type='spouse'` e `type='sibling'`: normalizzazione con `person_a_id < person_b_id` per evitare duplicati invertiti
- Nessun ciclo in `parent_child` (nessuno antenato di se stesso), enforced via trigger

#### `relationship_versions`
Snapshot delle modifiche a `relationships`:
```
id                    UUID PK
relationship_id       UUID FK relationships(id) NOT NULL
version_number        int NOT NULL
subtype               text
start_date            date NULL
start_date_precision  text
end_date              date NULL
end_date_precision    text
metadata              JSONB
edited_by_user_id     UUID FK users(id) NOT NULL
edited_at             timestamptz NOT NULL
edit_reason           text NULL
UNIQUE (relationship_id, version_number)
```

#### `family_affinities`
Relazioni soggettive di "famiglia percepita":
```
id                    UUID PK
from_person_id        UUID FK persons(id) NOT NULL
to_person_id          UUID FK persons(id) NOT NULL
affinity_type         enum('like_parent','like_sibling','like_child','like_aunt_uncle','like_cousin','like_grandparent','like_grandchild','other')
context               text NULL
is_mutual             boolean DEFAULT false
declared_by_user_id   UUID FK users(id) NOT NULL
created_at            timestamptz NOT NULL
archived_at           timestamptz NULL
```

Vincoli:
- `from_person_id != to_person_id`

#### `person_distances` (cache)
```
person_a_id           UUID FK persons(id) NOT NULL
person_b_id           UUID FK persons(id) NOT NULL
distance              int NOT NULL
relationship_type_path text NOT NULL                  -- es: "parent.sibling.child" = zio
calculated_at         timestamptz NOT NULL
PRIMARY KEY (person_a_id, person_b_id)
```

Vincoli:
- Normalizzazione `person_a_id < person_b_id` (simmetria)
- Invalidazione via trigger su `relationships` INSERT/UPDATE/DELETE

### Dominio curatorship

#### `curatorships`
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
curator_user_id       UUID FK users(id) NOT NULL
role                  enum('primary','co_curator') NOT NULL
started_at            timestamptz NOT NULL
ended_at              timestamptz NULL
status                enum('active','suspended','ended') DEFAULT 'active'
```

Vincoli:
- Al più un `role='primary'` attivo per `person_id` (constraint condizionale: `WHERE status='active' AND role='primary'`)
- Se `persons.user_id` IS NOT NULL, non possono esistere curatorships attivi (l'utente è curatore di se stesso implicitamente)

#### `curatorship_requests`
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
requesting_user_id    UUID FK users(id) NOT NULL
requested_role        enum('primary','co_curator') NOT NULL
reason                text NULL
status                enum('pending','approved','rejected','auto_approved','expired') DEFAULT 'pending'
requested_at          timestamptz NOT NULL
resolved_at           timestamptz NULL
resolved_by_user_id   UUID FK users(id) NULL
auto_approve_at       timestamptz NOT NULL             -- tipicamente +14 giorni
```

#### `curatorship_votes`
Per decisioni straordinarie su nodi con curatela condivisa:
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
proposal_type         enum('change_visibility','approve_merge','archive_node','revoke_curator','approve_medical_entry','other')
proposal_payload      JSONB NOT NULL                   -- dettagli proposta
proposed_by_user_id   UUID FK users(id) NOT NULL
proposed_at           timestamptz NOT NULL
voting_deadline       timestamptz NOT NULL
status                enum('voting','passed','rejected','expired')
resolved_at           timestamptz NULL
```

#### `curatorship_vote_ballots`
Singoli voti per una proposta:
```
id                    UUID PK
vote_id               UUID FK curatorship_votes(id) NOT NULL
voter_user_id         UUID FK users(id) NOT NULL
ballot                enum('approve','reject','abstain') NOT NULL
cast_at               timestamptz NOT NULL
UNIQUE (vote_id, voter_user_id)
```

### Dominio content

#### `contents`
```
id                    UUID PK
type                  enum('photo','text_story','audio','video','document','letter_scan')
title                 text NULL
body                  text NULL                        -- per text_story
media_url             text NULL                        -- URL a R2 (null per text_story)
media_metadata        JSONB DEFAULT '{}'                -- dimensioni, durata, EXIF
reference_date        date NULL                        -- data dell'evento
reference_date_precision enum('exact','month','year','decade','unknown')
reference_location    text NULL
uploaded_by_user_id   UUID FK users(id) NOT NULL
uploaded_at           timestamptz NOT NULL
visibility_override   JSONB NULL                       -- override del curatore rispetto all'intersezione default
archived_at           timestamptz NULL
```

Vincoli:
- Se `type IN ('photo','audio','video','document','letter_scan')`: `media_url NOT NULL`
- Se `type = 'text_story'`: `body NOT NULL`
- Almeno un `ContentSubject` deve esistere (enforced in service layer, non via DB constraint hard)

#### `content_versions`
```
id                    UUID PK
content_id            UUID FK contents(id) NOT NULL
version_number        int NOT NULL
title                 text
body                  text
media_metadata        JSONB
reference_date        date NULL
reference_date_precision text
reference_location    text NULL
edited_by_user_id     UUID FK users(id) NOT NULL
edited_at             timestamptz NOT NULL
edit_reason           text NULL
UNIQUE (content_id, version_number)
```

#### `content_subjects`
```
content_id            UUID FK contents(id) NOT NULL
person_id             UUID FK persons(id) NOT NULL
tagged_by_user_id     UUID FK users(id) NOT NULL
tag_status            enum('proposed','confirmed','rejected') DEFAULT 'proposed'
tag_confirmed_at      timestamptz NULL
PRIMARY KEY (content_id, person_id)
```

#### `content_comments`
```
id                    UUID PK
content_id            UUID FK contents(id) NOT NULL
author_user_id        UUID FK users(id) NOT NULL
body                  text NOT NULL
created_at            timestamptz NOT NULL
edited_at             timestamptz NULL
archived_at           timestamptz NULL
```

#### `content_collections`
```
id                    UUID PK
title                 text NOT NULL
description           text NULL
type                  enum('album','correspondence','event','chronological_story','custom')
reference_date_start  date NULL
reference_date_end    date NULL
cover_content_id      UUID FK contents(id) NULL
visibility_inherit    boolean DEFAULT true
created_by_user_id    UUID FK users(id) NOT NULL
created_at            timestamptz NOT NULL
archived_at           timestamptz NULL
```

#### `content_collection_items`
```
collection_id         UUID FK content_collections(id) NOT NULL
content_id            UUID FK contents(id) NOT NULL
order_index           int NOT NULL DEFAULT 0
caption_override      text NULL
PRIMARY KEY (collection_id, content_id)
```

### Dominio permissions

#### `privacy_policies`
Integrato in `users` via `privacy_preset` e `privacy_custom_overrides` JSONB. Non serve tabella separata.

Schema dei preset (constanti applicative, definite in `apps/permissions/presets.py`):
- `reserved`: default restrittivo
- `balanced`: default medio (default di registrazione)
- `open`: default permissivo
- `custom`: usa `privacy_custom_overrides`

Struttura di `privacy_custom_overrides`:
```json
{
  "by_archetype": {
    "close_family": ["existence_structure", "extended_identity", "biography", "memory"],
    "extended_family": ["existence_structure", "extended_identity"],
    "distant_family": ["existence_structure"],
    ...
  },
  "contactability": {
    "accept_messages_from": "close_family"
  }
}
```

#### `node_policy_overrides`
Override di visibilità deciso dal curatore per un nodo specifico:
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
override_rules        JSONB NOT NULL                   -- stessa struttura di privacy_custom_overrides
reason                text NULL
decided_by_user_id    UUID FK users(id) NOT NULL
decided_at            timestamptz NOT NULL
valid_until           timestamptz NULL                 -- null = permanente
archived_at           timestamptz NULL
```

#### `access_requests`
```
id                    UUID PK
requesting_user_id    UUID FK users(id) NOT NULL
target_person_id      UUID FK persons(id) NOT NULL
requested_categories  text[] NOT NULL                  -- ['biography','memory']
message               text NULL
status                enum('pending','approved','rejected','expired') DEFAULT 'pending'
requested_at          timestamptz NOT NULL
resolved_at           timestamptz NULL
resolved_by_user_id   UUID FK users(id) NULL
response_message      text NULL
```

#### `access_grants`
```
id                    UUID PK
grantee_user_id       UUID FK users(id) NOT NULL
target_person_id      UUID FK persons(id) NOT NULL
categories            text[] NOT NULL
granted_by_user_id    UUID FK users(id) NOT NULL
granted_at            timestamptz NOT NULL
expires_at            timestamptz NULL                 -- null = permanente
revoked_at            timestamptz NULL
reason                text NULL
source_request_id     UUID FK access_requests(id) NULL -- se deriva da una request
```

### Dominio medical

#### `medical_records`
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
condition_code        text NOT NULL                    -- da enum chiuso in apps/medical/choices.py
condition_category    enum('cardiovascular','oncological','metabolic','neurological','psychiatric','autoimmune','genetic_disorder','ophthalmological','orthopedic','dermatological','other')
custom_condition_note text NULL                        -- max 200 char, solo se condition_code='other'
onset_age             int NULL
onset_age_precision   enum('exact','decade','unknown')
status                enum('active','resolved','chronic','in_remission','cause_of_death')
resolution_age        int NULL
source                enum('self_reported','family_memory','medical_document','unknown')
confidence            enum('certain','probable','possible','rumored')
consent_record_id     UUID FK medical_consents(id) NOT NULL
added_by_user_id      UUID FK users(id) NOT NULL
added_at              timestamptz NOT NULL
archived_at           timestamptz NULL
```

#### `medical_record_versions`
```
id                    UUID PK
medical_record_id     UUID FK medical_records(id) NOT NULL
version_number        int NOT NULL
condition_code        text
condition_category    text
custom_condition_note text NULL
onset_age             int NULL
status                text
source                text
confidence            text
edited_by_user_id     UUID FK users(id) NOT NULL
edited_at             timestamptz NOT NULL
edit_reason           text NULL
UNIQUE (medical_record_id, version_number)
```

#### `medical_consents`
```
id                    UUID PK
person_id             UUID FK persons(id) NOT NULL
granted_by_user_id    UUID FK users(id) NOT NULL
consent_type          enum('self_input','family_input_for_deceased','family_input_for_minor')
legal_basis           enum('explicit_consent','legitimate_interest_family_health','documented_medical_record')
consent_text_version  text NOT NULL                    -- versione testo consenso accettato
consent_text_hash     text NOT NULL                    -- hash del testo versione
granted_at            timestamptz NOT NULL
revoked_at            timestamptz NULL
```

### Dominio communication

#### `in_app_messages`
```
id                    UUID PK
sender_user_id        UUID FK users(id) NOT NULL
recipient_user_id     UUID FK users(id) NOT NULL
body                  text NOT NULL
context_person_id     UUID FK persons(id) NULL         -- se il msg è "su" un nodo
sent_at               timestamptz NOT NULL
read_at               timestamptz NULL
archived_at           timestamptz NULL
```

#### `contact_unlocks`
```
id                    UUID PK
user_a_id             UUID FK users(id) NOT NULL
user_b_id             UUID FK users(id) NOT NULL
unlock_type           enum('email','phone','both')
initiated_by_user_id  UUID FK users(id) NOT NULL
status                enum('pending_mutual','unlocked','revoked')
initiated_at          timestamptz NOT NULL
completed_at          timestamptz NULL
UNIQUE (user_a_id, user_b_id)
```

Vincoli: `user_a_id < user_b_id` per normalizzazione.

#### `notifications`
```
id                    UUID PK
recipient_user_id     UUID FK users(id) NOT NULL
type                  enum('claim_request','curatorship_request','access_request','merge_proposal','new_content_on_curated','new_comment','content_tag_proposed','message_received','vote_required','other')
payload               JSONB NOT NULL
read_at               timestamptz NULL
created_at            timestamptz NOT NULL
```

### Dominio governance

#### `merge_proposals`
```
id                    UUID PK
person_a_id           UUID FK persons(id) NOT NULL     -- sopravvive
person_b_id           UUID FK persons(id) NOT NULL     -- assorbito
proposed_by_user_id   UUID FK users(id) NOT NULL
reason                text NULL
confidence_score      float NULL                       -- se proposto da matching automatico
status                enum('pending','approved','rejected','applied','cancelled')
proposed_at           timestamptz NOT NULL
resolved_at           timestamptz NULL
```

#### `merge_votes`
Voti dei curatori di entrambi i nodi sulla proposta:
```
id                    UUID PK
proposal_id           UUID FK merge_proposals(id) NOT NULL
voter_user_id         UUID FK users(id) NOT NULL
side                  enum('person_a','person_b')       -- quale curatela rappresenta
ballot                enum('approve','reject') NOT NULL
cast_at               timestamptz NOT NULL
UNIQUE (proposal_id, voter_user_id)
```

#### `audit_log`
Append-only. Nessun UPDATE, nessun DELETE (enforced via DB grant o trigger).
```
id                    UUID PK
actor_user_id         UUID FK users(id) NULL            -- null se azione sistema
action_type           text NOT NULL                     -- enum esteso
entity_type           text NOT NULL                     -- nome tabella
entity_id             UUID NOT NULL
changes_diff          JSONB NULL                        -- diff prima/dopo
context               JSONB DEFAULT '{}'                -- IP, device, session_id
created_at            timestamptz NOT NULL
```

Valori di `action_type` (non esaustivo):
- `create_person`, `update_person`, `archive_person`, `gdpr_delete_person`
- `create_relationship`, `update_relationship`, `archive_relationship`
- `create_content`, `update_content`, `archive_content`
- `create_medical_record`, `update_medical_record`, `revoke_consent`
- `change_privacy_policy`, `create_node_override`
- `create_curatorship`, `approve_curatorship_request`
- `propose_merge`, `vote_merge`, `apply_merge`
- `approve_access_request`, `revoke_access_grant`
- `send_message`, `unlock_contact`
- `create_affinity`, `create_social_connection`

### Dominio social

#### `social_connections`
Grafo guanxi, separato dall'albero:
```
id                    UUID PK
person_a_id           UUID FK persons(id) NOT NULL
person_b_id           UUID FK persons(id) NOT NULL
type                  enum('friend','colleague','mentor','classmate','neighbor','acquaintance','business_partner','other')
strength              int CHECK (strength BETWEEN 1 AND 5)
started_at            date NULL
ended_at              date NULL
context               text NULL
is_reciprocal         boolean DEFAULT false
created_by_user_id    UUID FK users(id) NOT NULL
created_at            timestamptz NOT NULL
archived_at           timestamptz NULL
```

Vincoli:
- `person_a_id != person_b_id`
- Nota: le connessioni sono **soggettive** di default. `created_by_user_id` è la vista di chi l'ha dichiarata. Se l'altro conferma, `is_reciprocal = true`.

## Indici consigliati

Elenco non esaustivo, da consolidare alla prima migration:

**identity**
- `users(email)` UNIQUE (già da constraint)
- `users(person_id)` UNIQUE (già da constraint)
- `persons(user_id)` UNIQUE WHERE NOT NULL
- `persons(is_living)` — filtri frequenti
- `persons(archived_at)` WHERE archived_at IS NULL — soft delete filter

**tree**
- `relationships(person_a_id)`, `relationships(person_b_id)` — traversal
- `relationships(person_a_id, person_b_id, type)` UNIQUE
- `person_distances(person_a_id, person_b_id)` già PK
- `family_affinities(from_person_id)`, `family_affinities(to_person_id)`

**content**
- `contents(uploaded_by_user_id)`, `contents(reference_date)` per timeline queries
- `content_subjects(person_id)` — trova tutti i contenuti di una persona

**curatorship**
- `curatorships(person_id, status)` WHERE status='active' — trova curatori attivi

**permissions**
- `access_grants(grantee_user_id, target_person_id)` WHERE revoked_at IS NULL
- `access_requests(target_person_id, status)` WHERE status='pending'

**audit**
- `audit_log(entity_type, entity_id, created_at DESC)` — cronologia di un'entità
- `audit_log(actor_user_id, created_at DESC)` — azioni di un utente

## Trigger e vincoli complessi

Alcuni vincoli non si esprimono bene con sole FK/CHECK e richiedono trigger:

1. **No cicli in parent_child**: trigger BEFORE INSERT/UPDATE su `relationships` che rifiuta cicli (un figlio non può essere antenato del suo genitore).

2. **Invalidazione cache distanze**: trigger AFTER INSERT/UPDATE/DELETE su `relationships` che cancella righe in `person_distances` che coinvolgono le person toccate.

3. **Audit log append-only**: REVOKE UPDATE, DELETE su `audit_log` da tutti i ruoli applicativi, oppure trigger `BEFORE UPDATE/DELETE RAISE EXCEPTION`.

4. **At-most-one primary curator**: `CREATE UNIQUE INDEX ... ON curatorships(person_id) WHERE role='primary' AND status='active'`.

5. **Versioning automatico**: trigger BEFORE UPDATE su entità versionate (`contents`, `persons`, `relationships`, `medical_records`) che copia lo stato precedente nella tabella `_versions`.

## Conteggio tabelle

Totale: **33 tabelle** (incluse versioning shadow). Core operazioni quotidiane toccano ~8-10 tabelle: `users`, `persons`, `relationships`, `contents`, `content_subjects`, `curatorships`, `access_grants`, `notifications`, `audit_log`.
