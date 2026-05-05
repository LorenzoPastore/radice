# `apps/social` — Contesto dominio

## Responsabilità

Gestisce il **grafo delle connessioni sociali non familiari** dell'utente: amici, colleghi, mentori, compagni di scuola, vicini, conoscenti. Questo è il "guanxi" del progetto — una rete personale separata dall'albero genealogico.

Il grafo sociale è **soggettivo di default**: io dichiaro "Marco è mio amico" e questa è la mia vista. Marco può confermare (reciproco) o non pronunciarsi. Non serve consenso per dichiarare.

## Entità principali

- **`SocialConnection`** — edge soggettivo del grafo tra due `Person`, tipizzato (friend, colleague, mentor, classmate, neighbor, acquaintance, business_partner, other), con `strength` 1-5 e `context` opzionale.

## Dipendenze

- Dipende da: `core`, `identity`
- Usato da: `permissions` (per determinare archetype `external_connected` quando una Person è nel guanxi di un viewer pur non essendo nell'albero)

## Vincoli critici

### Vincolo 1: Connessioni soggettive
Le `SocialConnection` sono **dichiarazioni soggettive**, non proprietà oggettive. Se io dichiaro "Marco è mio amico":
- La connessione è visibile **solo a me** (nel mio grafo personale)
- Marco non vede questa dichiarazione finché non gli viene notificata
- Marco può accettare (reciproco = true, visibile a entrambi) o ignorare/rifiutare (resta solo lato mio)

Questo è diverso da `Relationship` (famiglia) che è oggettiva e condivisa.

### Vincolo 2: Privacy del guanxi per default
Il grafo guanxi di un User è **privato** per default. Nessun altro User può vedere "chi Lorenzo considera suoi amici" senza permesso esplicito.

Configurabile in `privacy_custom_overrides`:
```json
{
  "guanxi_visibility": "private" | "family_only" | "mutual_only" | "public_in_app"
}
```

- `private` (default): solo l'utente stesso
- `family_only`: close_family può vedere il proprio guanxi
- `mutual_only`: solo le connessioni reciproche sono visibili ad altri (una persona vedrà nel mio guanxi solo chi ha confermato la connessione con me)
- `public_in_app`: qualsiasi utente registrato può vedere il mio guanxi

### Vincolo 3: Nessun impatto strutturale sull'albero
Le `SocialConnection` **non influenzano le distanze di parentela**. Il mio guanxi con Marco è separato dall'albero genealogico; Marco non diventa automaticamente mio "extended_family" solo perché l'ho messo tra i miei amici.

L'unico modo in cui il guanxi influisce sui permessi dell'albero è l'archetipo `EXTERNAL_CONNECTED`: se una Person è nel mio guanxi (di cui sono owner), io ottengo archetype `EXTERNAL_CONNECTED` verso lei, pur non essendo nell'albero.

### Vincolo 4: Strength e context sono hint, non enforcement
I campi `strength` (1-5) e `context` (testo libero) sono puramente informativi per l'UI dell'utente. Non influenzano permessi o visibilità. Servono per:
- Filtrare il proprio guanxi per forza (es: "mostra solo friend con strength >= 4")
- Ricordarsi dove/quando si è conosciuta una persona

### Vincolo 5: Persone nel guanxi possono essere ovunque
Una `Person` referenziata in `SocialConnection` può essere:
- Un User registrato (caso comune: amico dell'utente)
- Una Person non-registrata creata ad hoc dall'utente (amico non sull'app)
- Una Person anche presente nell'albero genealogico (es: tuo cugino che è anche tuo amico stretto → può apparire in entrambi i grafi)

Le entità sono le stesse, i grafi separati. Una Person è unica nel sistema.

### Vincolo 6: Creazione di Person "guanxi-only"
Se l'utente aggiunge al guanxi una persona non-registrata e non nell'albero, crea una Person minimale (solo given_names, surname, nessuna relazione familiare). Questa Person ha `created_by_user_id = self` e di default solo l'utente la vede (`existence_structure` visibile solo a `self` via NodePolicyOverride automatico).

Se in futuro questa persona si registra, può fare claim come per qualsiasi Person.

## Flussi principali

### Aggiunta al guanxi

```
1. User apre "Aggiungi al mio guanxi"
2. Cerca Person esistente (nell'albero o guanxi-only) o crea nuova
3. Specifica type, strength, context, started_at
4. POST /api/social-connections/
5. Crea SocialConnection con is_reciprocal=false, created_by_user_id=self
6. Se la Person ha un User associato → notifica "A ti ha aggiunto come {type} nel suo guanxi, vuoi ricambiare?"
7. L'altro User può confermare (updates is_reciprocal=true) o ignorare
```

### Guanxi graph view

```
1. User naviga /guanxi
2. Frontend richiede /api/social-connections/mine/
3. Backend risponde con tutte le connections del User:
   - Proprie (create_by=self): sempre visibili
   - Reciproche altrui verso self: visibili
4. Frontend renderizza grafo force-directed con react-flow
5. Filtri per type, strength, reciprocity
```

### Query "external_connected" (per archetype)

```python
# apps/permissions/services/archetype_resolver.py chiama:
def is_connected_via_guanxi(viewer_user, target_person):
    return SocialConnection.objects.filter(
        created_by_user=viewer_user,
        to_person=target_person,
        archived_at__isnull=True,
    ).exists() or SocialConnection.objects.filter(
        from_person=target_person,
        to_person=viewer_user.person,
        is_reciprocal=True,
        archived_at__isnull=True,
    ).exists()
```

Se la query è hot, viene ottimizzata/cached.

## Servizi chiave

### `services/social_service.py`
- `create_connection(from_user, to_person, type, strength, context=None)` → SocialConnection
- `confirm_reciprocity(connection, confirming_user)` → SocialConnection
- `archive_connection(connection, archiver)` → SocialConnection
- `get_my_guanxi(user, filters=None)` → QuerySet[SocialConnection]
- `get_others_guanxi(viewing_user, owner_user)` → QuerySet (rispettando privacy_custom_overrides.guanxi_visibility)

### `services/guanxi_person_service.py`
- `create_guanxi_only_person(creator, given_names, surname, **minimal_data)` → Person
- Crea Person + automatic NodePolicyOverride che la rende visibile solo al creator

## File attesi

```
social/
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
│   ├── social_service.py
│   └── guanxi_person_service.py
├── factories.py
└── tests/
    ├── test_connection_lifecycle.py
    ├── test_reciprocity.py
    ├── test_guanxi_visibility.py    # Privacy settings per il grafo
    ├── test_archetype_external_connected.py
    └── test_guanxi_only_person.py
```

## Test density richiesta

60%+. Test obbligatori:
- Connessione non-reciproca visibile solo al creator
- Conferma reciprocità la rende bidirezionale
- `private` guanxi setting blocca tutti gli altri users
- `mutual_only` nasconde connessioni pending
- Archetype `external_connected` è derivato correttamente dal guanxi
- Guanxi-only Person ha visibility ristretta al creator

## Estensioni future (non MVP)

Non implementare ora, ma progettare per estendibilità:
- **Gruppi**: raggruppare connessioni in contesti ("compagni di liceo", "colleghi Menumal"). Tabella `SocialGroup` + M2M.
- **Eventi condivisi**: eventi che coinvolgono più persone del guanxi (matrimoni, reunions, trasferimenti).
- **Timeline guanxi**: nascita/morte/evoluzione delle relazioni ("conosciuto Marco nel 2012 al liceo, divenuti stretti nel 2018").
- **Strength dinamica**: ricalcolare automaticamente strength basandosi su recency of interaction (se mai avremo signal da messaggi).
