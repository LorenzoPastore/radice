# `apps/medical` — Contesto dominio

## Responsabilità

Gestisce i **dati medici** di `Person`: condizioni mediche ereditarie, età di insorgenza, relazioni familiari di rilevanza medica. È il dominio più **legalmente delicato** del progetto: GDPR Art. 9 classifica i dati sanitari come "categoria speciale" che richiede consenso esplicito documentato.

Il valore del dominio è reale: sapere che un antenato ha avuto condizioni cardiovascolari a 50 anni ha valore preventivo per i discendenti. Ma la gestione deve essere impeccabile.

## Entità principali

- **`MedicalRecord`** — singola condizione medica associata a una `Person`, con codice chiuso, età, status, fonte, confidence.
- **`MedicalRecordVersion`** — shadow versioning (critico per motivi legali: modifiche a dati medici devono avere traccia immutabile).
- **`MedicalConsent`** — record di consenso esplicito per ogni inserimento/visualizzazione. Include versione del testo di consenso accettato.

## Dipendenze

- Dipende da: `core`, `identity`, `permissions`, `tree` (per consanguinei calcolati strutturalmente)
- Chiamato da: `curatorship` (voto unanimità per decisioni mediche), `governance` (audit)

## Vincoli critici (NON NEGOZIABILI)

### Vincolo 1: Lista chiusa di `condition_code`
Nessun testo libero nelle condizioni mediche. `condition_code` deve essere un valore dall'enum chiuso definito in `choices.py`. Solo quando `condition_code='other'`, il campo `custom_condition_note` (max 200 char) può contenere testo libero.

Motivi:
- Evita inserimento di informazioni imbarazzanti o non rilevanti
- Rende i dati queryabili e aggregabili ("chi in famiglia ha condition_code='diabetes_type_2'?")
- Protegge la dignità di persone defunte (curatore non può scrivere cose indiscrete)

La lista parte con ~80-100 condizioni maggiori (cardiovascolari, oncologiche, metaboliche, neurologiche, psichiatriche, autoimmuni, genetiche, ecc.) ed è estendibile via migration con review.

### Vincolo 2: Consenso esplicito obbligatorio
Ogni `MedicalRecord` ha `consent_record_id` FK NOT NULL a `MedicalConsent`. Creare un record senza consenso è impossibile a livello DB.

Consent types:
- `self_input`: l'utente stesso inserisce propri dati, consenso implicito nel login + accettazione esplicita del testo
- `family_input_for_deceased`: familiare inserisce dati di defunto, basato su legitimate_interest + dichiarazione di buona fede
- `family_input_for_minor`: rappresentante legale del minore inserisce dati

`legal_basis` è enum chiuso con corrispondenza GDPR Art. 9.

### Vincolo 3: Consenso versionato
`MedicalConsent.consent_text_version` è la versione del testo di consenso accettato. `consent_text_hash` è il SHA-256 del testo. Se un giorno aggiorni il testo di consenso, i consensi vecchi **non vengono revocati automaticamente**: restano validi per la versione vecchia. Per la nuova serve ri-consenso.

I testi di consenso versionati sono committati in `apps/medical/consent_texts/v1.md`, `v2.md`, ecc.

### Vincolo 4: Visibilità esclusiva ai consanguinei
I dati medici sono visibili **solo** a `Person` che condividono DNA potenzialmente rilevante:
- Ascendenti biologici diretti (genitori, nonni, bisnonni) – eredità ereditaria up
- Discendenti biologici diretti (figli, nipoti) – eredità down
- Fratelli biologici (subtype='full_biological' o 'half_biological')
- Coniugi **NO** (non condividono DNA)
- Step-parent, adoptive, de_facto **NO** (non condividono DNA)

Il check viene fatto via `tree.services.distance_service` seguendo SOLO i path con subtype consanguineo. È una logica specializzata che vive in `medical/services/consanguinity_service.py`.

### Vincolo 5: Revoca consenso = soft delete immediato
Se un utente vivente revoca il consenso sui propri dati (`MedicalConsent.revoked_at = now()`):
- Tutti i `MedicalRecord` associati a quel consent vengono immediatamente archiviati (`archived_at = now()`)
- Non più visibili a nessuno (neanche via query ai versioni shadow)
- Il hard delete dal DB avviene entro 30 giorni via Celery cleanup (con audit trail di revoca mantenuto)

Il hard delete dopo 30 giorni è compliance GDPR "right to erasure".

### Vincolo 6: Unanimità per defunti
Per Person defunte con curatela condivisa, inserire/modificare un `MedicalRecord` richiede **voto unanime** dei co-curatori (vedi `curatorship/services/voting_service.py`). Un singolo rifiuto o abstain blocca l'inserimento.

Motivo: un record medico inserito in mala fede su un defunto potrebbe danneggiare i discendenti (visibilità a consanguinei). Serve consenso forte.

### Vincolo 7: Confidence tracciato sempre
Il campo `confidence` (certain/probable/possible/rumored) è obbligatorio. Evita che "si dice che bisnonna avesse un tumore" venga ricevuto come certezza. UI mostra confidence prominentemente.

### Vincolo 8: Source tracciato sempre
Il campo `source` (self_reported/family_memory/medical_document/unknown) permette di distinguere:
- Inserimento basato su documento medico reale (alta affidabilità)
- Memoria familiare (media affidabilità)
- Sconosciuto (bassa affidabilità)

## Flussi principali

### Inserimento self (utente vivente)

```
1. User naviga a proprio profilo medico
2. Vede il testo di consenso corrente (v_current)
3. Accetta esplicitamente (checkbox + conferma)
4. Transaction:
   - Crea MedicalConsent(person=self, granted_by=self, consent_type='self_input', text_version=v_current, text_hash=...)
   - Crea MedicalRecord con consent_record_id, condition_code, onset_age, confidence, source
5. Audit log
6. Notifica consanguinei che ora possono vedere il record (opzionale, settings utente)
```

### Inserimento su defunto

```
1. Co-curator propone aggiunta MedicalRecord → CuratorshipVote(proposal_type='approve_medical_entry')
2. Tutti i co-curatori attivi ricevono notifica
3. Regola: UNANIMITÀ richiesta. Ogni co-curator deve votare 'approve'.
4. Se passa:
   - Transaction: crea MedicalConsent(consent_type='family_input_for_deceased', legal_basis='legitimate_interest_family_health')
   - Crea MedicalRecord
5. Audit log con lista votanti
6. Se non passa (anche un reject): proposal rejected, nessun inserimento
```

### Revoca consenso

```
1. User vivente naviga a proprio consenso medico
2. Click "Revoca consenso"
3. Conferma (modal con avviso: "tutti i tuoi dati medici verranno archiviati immediatamente e cancellati entro 30 giorni")
4. Transaction:
   - MedicalConsent.revoked_at = now()
   - Tutti MedicalRecord con consent_record_id → archived_at = now()
5. Celery task schedulato a +30 giorni per hard delete
6. Audit log con motivo revoca (opzionale)
7. Notifica consanguinei (informativa, non il contenuto)
```

### Query di familiarità medica (lato utente)

```python
# Esempio: "qual è la familiarità per condizioni cardiovascolari dei miei antenati diretti?"
# Query in service:
consanguineous_ancestors = get_consanguineous_ancestors(viewer.person, max_depth=3)
records = MedicalRecord.objects.filter(
    person__in=consanguineous_ancestors,
    condition_category='cardiovascular',
    archived_at__isnull=True,
)
# Filtro pipeline permessi standard
filtered = [r for r in records if check_medical_visibility(r, viewer)]
```

Il servizio espone metodi come `get_family_history_by_category(viewer, category)` per usi UI standard.

## Servizi chiave

### `services/consent_service.py`
- `grant_self_consent(user, text_version)` → MedicalConsent
- `grant_family_consent(granter, for_person, consent_type, legal_basis)` → MedicalConsent
- `revoke_consent(consent, revoker)` → MedicalConsent + archiviazione record associati
- `get_current_consent_text()` → str (current version)

### `services/medical_record_service.py`
- `create_record(consent, condition_code, **kwargs)` → MedicalRecord
- `update_record(record, **changes, editor)` → MedicalRecord (+ version entry)
- `archive_record(record, reason)` → MedicalRecord

### `services/consanguinity_service.py`
- `get_consanguineous_descendants(person, max_depth=10)` → list[Person]
- `get_consanguineous_ancestors(person, max_depth=10)` → list[Person]
- `get_consanguineous_siblings(person)` → list[Person]
- `is_consanguineous(a, b)` → bool (equivalente a distanza con solo path biologici)

### `services/family_history_service.py`
- `get_family_history_by_category(viewer, category)` → structured dict with records visible to viewer
- `get_inheritance_pattern(condition_code)` → ascendenti/discendenti con quella condizione

## File attesi

```
medical/
├── __init__.py
├── apps.py
├── CLAUDE.md
├── models.py
├── choices.py                    # CONDITION_CODES (lista chiusa), enum categorie
├── consent_texts/
│   ├── v1.md                     # Testo consenso v1
│   └── CURRENT → v1.md           # Symlink a versione corrente
├── serializers.py
├── views.py
├── urls.py
├── admin.py
├── services/
│   ├── __init__.py
│   ├── consent_service.py
│   ├── medical_record_service.py
│   ├── consanguinity_service.py
│   └── family_history_service.py
├── tasks.py                      # hard_delete_revoked_consents (after 30 days)
├── factories.py
└── tests/
    ├── test_consent_lifecycle.py
    ├── test_record_crud.py
    ├── test_consanguinity.py      # Test matrice con famiglie allargate
    ├── test_visibility.py         # Verifica coniugi/step NON vedono
    ├── test_unanimity_for_deceased.py
    ├── test_revocation_cascade.py
    └── test_versioning.py
```

## Test density richiesta

**85%+**. Compliance GDPR Art. 9 dipende dalla correttezza di questo modulo. Test obbligatori:

- Inserimento senza consenso **fallisce**
- Revoca consenso **archivia** tutti i record associati istantaneamente
- Cleanup dopo 30gg hard-deleta i record archiviati
- Coniugi NON vedono dati medici del partner
- Step-parent NON vede dati medici dei figliastri
- Fratelli biologici SÌ vedono, fratellastri adottivi NO
- Unanimità su defunto: un abstain basta a rejectare
- Versioning preserva stato pre-modifica
- Testo di consenso vecchio rimane valido per record creati sotto quella versione

## Note legali (non implementative, ma da tenere presente)

- GDPR Art. 9 richiede documented consent per dati sanitari
- Alcune giurisdizioni (Italia compresa) hanno limiti sulla "memoria dei defunti" — il GDPR tecnicamente non si applica ai defunti in tutti gli Stati UE, ma alcuni li proteggono comunque
- Il campo `legal_basis` è per audit legale; in caso di richiesta autorità, i record mostrano base giuridica
- Un'eventuale futura feature "export medico per medico" (esportare la storia familiare per consulto specialistico) va progettata con ulteriori cautele
