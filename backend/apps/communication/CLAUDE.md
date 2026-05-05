# `apps/communication` — Contesto dominio

## Responsabilità

Gestisce la **messaggistica in-app** tra utenti (senza esporre contatti reali), lo **sblocco reciproco di contatti veri** (email/telefono) dopo mutuo consenso, e il sistema di **notifiche** applicative.

Questo dominio implementa concretamente il pilastro "Contatti veri mai esposti": tutta la comunicazione passa via proxy in-app finché entrambe le parti non acconsentono esplicitamente allo scambio di contatti reali.

## Entità principali

- **`InAppMessage`** — messaggio tra due `User` via proxy applicativo. Può essere contestualizzato a una Person (`context_person_id`: "sto scrivendo a te riguardo mio nonno").
- **`ContactUnlock`** — stato dello sblocco reciproco di email/telefono tra due User. Flusso mutuo consenso.
- **`Notification`** — notifica applicativa (read/unread) con payload strutturato.

## Dipendenze

- Dipende da: `core`, `identity`, `permissions` (per check contactability)
- Chiamato da: tutti gli altri domini che emettono notifiche (identity, tree, curatorship, content, medical, permissions, governance)

## Vincoli critici

### Vincolo 1: Contactability via pipeline permessi
Per iniziare una conversazione con un utente X, il viewer deve avere `contactability` visibile per X (secondo la pipeline permessi standard). Se `contactability` è `✗` o `on_request` non approvato, l'endpoint di invio messaggio ritorna 403/404.

In pratica: il check di "posso mandare messaggio a X?" è un check di permessi standard (archetype → visibility), non una logica separata.

### Vincolo 2: Email e telefono reali NON esposti in InAppMessage
I messaggi sono contenuto testo tra due User via sistema. Il payload del messaggio è body (testo), sender_user_id, recipient_user_id, timestamps. **Mai** scrivere email/telefono di alcun utente nel body serializzato se il recipient non ha sblocco attivo.

Eccezione: l'utente stesso può scrivere i propri contatti nel body se vuole. Il sistema non filtra i messaggi (non vogliamo filtrare contenuto user-generated). Ma il *sistema* non espone contatti senza consenso.

### Vincolo 3: Contact unlock è mutuo e per-pair
`ContactUnlock` ha UNIQUE constraint su `(user_a_id, user_b_id)` con normalizzazione `a < b`. Un unlock attivo vale in entrambi i sensi (A vede contatti di B, B vede contatti di A). Non esistono sblocchi asimmetrici.

Flusso:
1. A chiede sblocco → ContactUnlock(user_a, user_b, initiated_by=A, status='pending_mutual')
2. B accetta → status='unlocked', completed_at=now()
3. Ora A e B possono vedere rispettivi contatti reali (via endpoint `/api/contacts/{user_id}/` che verifica unlock)
4. O entrambi possono revocare → status='revoked'

Dopo revoca, l'unlock resta in DB per audit ma status revoked. Un nuovo unlock richiederebbe nuova riga (o riattivazione esplicita).

### Vincolo 4: Rate limiting sui messaggi
Prevenire spam/harassment: 50 messaggi inviati/giorno per utente (configurabile in settings). Oltre, rate limit con errore utile. Applicato via `django-ratelimit` sulla view.

Inoltre, un utente non può inviare messaggi a **utenti che non hanno mai risposto** oltre N messaggi non-letti (3 di default). Questo blocca stalking/spam: se B non risponde e non legge, A non può continuare a bombardarlo.

### Vincolo 5: Notifiche non espongono dati oltre il permesso del recipient
Il `payload` di una `Notification` può contenere informazioni come "tuo cugino ha aggiunto una foto al nonno Giuseppe". Questo payload deve rispettare i permessi del recipient: se il recipient non potrebbe vedere quel contenuto via pipeline standard, la notifica **non deve essere creata** o deve essere sanitized.

Pattern corretto: quando un service emette notifica, **prima** verifica visibilità del recipient rispetto all'evento, poi costruisce payload con solo dati visibili.

### Vincolo 6: Soft-delete per messaggi archiviati
Un utente può archiviare (hard delete soft) i propri messaggi ricevuti. Il messaggio non è visibile a lui, ma resta nel DB per il sender (l'audit trail della sua interazione). Solo hard delete via GDPR rimuove davvero.

## Flussi principali

### Invio messaggio

```
1. Sender cerca recipient (solo utenti con contactability visibile)
2. POST /api/messages/ con recipient_user_id, body, context_person_id opzionale
3. Check: contactability del recipient visibile al sender? Else 403.
4. Check rate limit
5. Check "recipient ha già ricevuto 3+ messaggi non letti da sender"? Else 403 con errore "il destinatario non ha risposto ai tuoi messaggi precedenti, aspetta una risposta"
6. Crea InAppMessage
7. Crea Notification per recipient
8. Audit log (lightweight, solo metadata)
```

### Richiesta sblocco contatti

```
1. In conversazione, A clicca "Richiedi scambio contatti"
2. POST /api/contact-unlocks/ con user_b_id, unlock_type='email'|'phone'|'both'
3. Transaction:
   - Crea ContactUnlock(initiated_by=A, status='pending_mutual')
   - Notification a B con azione "Accetta/Rifiuta scambio contatti"
4. B accetta:
   - ContactUnlock.status='unlocked', completed_at=now
   - Entrambi ora accedono a /api/contacts/{other_user_id}/ con i contatti reali
5. B rifiuta:
   - ContactUnlock archiviato (status='revoked')
6. Audit log
```

### Notifica

```
1. Service di dominio X (es: content service al tag) chiama notify_user(recipient, type, payload, context)
2. notify_user verifica: il recipient può vedere l'evento? (via pipeline permessi)
3. Se sì: crea Notification(recipient_user_id, type, payload, created_at=now)
4. Push opzionale via PWA (se subscription attiva e settings utente lo permette)
5. Inbox digest opzionale (email daily/weekly per notifiche non lette)
```

## Servizi chiave

### `services/messaging_service.py`
- `send_message(sender, recipient, body, context_person=None)` → InAppMessage
- `can_message(sender, recipient)` → bool (verifica permessi + rate + unread count)
- `mark_read(message, reader)` → InAppMessage
- `archive_message(message, archiver)` → InAppMessage

### `services/contact_unlock_service.py`
- `request_unlock(initiator, other_user, unlock_type)` → ContactUnlock
- `accept_unlock(unlock, acceptor)` → ContactUnlock
- `reject_unlock(unlock, rejector, reason=None)` → ContactUnlock
- `revoke_unlock(unlock, revoker)` → ContactUnlock
- `get_visible_contacts(requesting_user, other_user)` → dict | None (None se non sbloccato)

### `services/notification_service.py`
- `notify_user(recipient, notif_type, payload, context=None, sanitize=True)` → Notification
- `bulk_notify(recipients_filter, notif_type, payload)` → int (batch)
- `mark_read(notification, user)` → Notification
- `get_unread_count(user)` → int

## File attesi

```
communication/
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
│   ├── messaging_service.py
│   ├── contact_unlock_service.py
│   └── notification_service.py
├── tasks.py                     # Email digest, push notifications
├── push/
│   └── webpush_client.py        # Web Push Protocol client
├── factories.py
└── tests/
    ├── test_messaging.py
    ├── test_rate_limiting.py
    ├── test_unread_threshold.py
    ├── test_contact_unlock_flow.py
    ├── test_notification_sanitization.py
    └── test_notification_permissions.py
```

## Test density richiesta

65%+. Test obbligatori:
- Contact unlock asimmetrico impossibile (uno solo sblocca → l'altro non vede)
- Rate limit messaggi funziona
- Spam threshold (3 non-letti) blocca sender ulteriori
- Notifica non esposta se recipient non ha permesso sull'evento
- ContactUnlock revocato → endpoint `/api/contacts/` torna 404
