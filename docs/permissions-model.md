# Radice — Modello dei permessi

Questo documento descrive il sistema di permessi di Radice in dettaglio. È il documento più importante del progetto: i permessi determinano cosa gli utenti vedono e possono fare, e sbagliarli significa violare la privacy degli utenti.

**Principio fondativo**: nessun dato sensibile viene mai restituito senza che la pipeline dei permessi abbia esplicitamente approvato la visibilità per il viewer specifico. Non esistono "dati di default visibili".

## Le 6 categorie di campo

Ogni campo dato su una `Person` è classificato in esattamente una di queste 6 categorie. La visibilità è determinata a livello di categoria, non di singolo campo.

### 1. `existence_structure`
Il minimo informativo per mantenere l'estensione dell'albero visibile a tutti i familiari.
- Esistenza del nodo
- `given_names`, `surname` (primo nome e cognome)
- `is_living`
- Anno di nascita (solo anno, anche con precisione "decade")
- Anno di morte (solo anno, se defunto)
- Relazioni strutturali (chi è genitore/figlio/coniuge di chi)

### 2. `extended_identity`
Dettagli identitari oltre il minimo.
- Nomi completi (inclusi secondi nomi, nicknames)
- `surname_at_birth`
- Date complete di nascita/morte con precisione esatta
- Luoghi di nascita/morte
- `gender`
- Foto profilo principale (`profile_photo_content_id`)

### 3. `biography`
La parte "directory" — chi è questa persona oggi.
- `short_bio`
- Professione, istruzione (se inserite come contenuti strutturati)
- Residenza attuale a livello di città (non indirizzo preciso)
- Interessi, lingue parlate
- Per i defunti: storia professionale, istruzione, luoghi di residenza principali

### 4. `contactability`
**Non sono i contatti reali.** È un flag binario "questo utente accetta di essere contattato da [categoria di archetipo]?". I contatti veri (email, telefono) non sono **mai** esposti direttamente. La comunicazione passa via messaggistica in-app; lo sblocco di contatti reali avviene solo per mutuo consenso esplicito in una singola conversazione.

### 5. `memory`
Il cuore del memoriale. I contenuti (foto, storie, audio, documenti) taggati con questa `Person`.

Per i contenuti multi-soggetto, la visibilità è calcolata per **intersezione restrittiva** delle policy di tutti i soggetti taggati (vedi sezione dedicata).

### 6. `medical_sensitive`
I record medici della persona. Trattamento speciale:
- Consenso esplicito obbligatorio per ogni record
- Lista chiusa di `condition_code`, no testo libero
- Visibilità esclusiva a **consanguinei** calcolati strutturalmente (solo rami di discendenza/ascendenza biologica, non acquisiti)
- Unanimità dei co-curatori richiesta per modifiche su defunti

## Gli 8 archetipi di utente

Dato un `viewer` (utente autenticato) e un `target` (Person), il viewer appartiene a esattamente uno di questi archetipi rispetto al target. Calcolato dinamicamente.

### `self`
L'utente viewer È il target. `viewer.person_id == target.id`. Vede tutto, modifica quasi tutto (eccetto struttura relazionale, che richiede accordo dell'altro).

### `primary_curator`
Il viewer è curatore primario del target. Ha `curatorships` row con `curator_user_id=viewer`, `person_id=target`, `role='primary'`, `status='active'`.

### `co_curator`
Come sopra ma con `role='co_curator'`.

### `close_family` (distanza ≤ 2)
Il viewer è a distanza di parentela ≤ 2 dal target, calcolata via `person_distances`. Esempi: genitori, figli, fratelli, coniuge, nonni, nipoti, zii.

### `extended_family` (distanza 3-5)
Distanza 3, 4, o 5. Esempi: cugini primi (dist 4), pronipoti, cognati acquisiti, zii di secondo grado.

### `distant_family` (distanza > 5)
Qualsiasi distanza superiore a 5 ma con percorso esistente nell'albero. Cugini secondi, parenti molto lontani.

### `external_connected`
Viewer registrato nell'app ma senza percorso di parentela calcolabile verso il target. Può comparire nel guanxi di qualcuno, ma non nell'albero.

### `external_unknown`
Viewer registrato ma senza nessun collegamento visibile al target. Di default non vede nemmeno l'esistenza del target.

## Configurabilità delle soglie

Le soglie numeriche di distanza (≤2, 3-5, >5) **NON sono configurabili a runtime**. Sono definite in `apps/permissions/constants.py` come costanti applicative. Modificabili solo via codice + deploy dal maintainer.

Motivazioni:
- Stabilità semantica del sistema
- Impossibilità di avere policy consistenti tra famiglie con soglie diverse
- Un "account admin" che può modificare soglie per conto di altri utenti è un antipattern di sicurezza

## Matrice default per archetipo (viventi con account)

La matrice base, prima di override personali e di nodo:

| Archetipo             | existence_structure | extended_identity | biography | contactability | memory   | medical_sensitive |
|-----------------------|---------------------|-------------------|-----------|----------------|----------|-------------------|
| self                  | ✓                   | ✓                 | ✓         | ✓              | ✓        | ✓                 |
| primary_curator       | ✓                   | ✓                 | ✓         | ✓              | ✓        | ✓ (con consenso)  |
| co_curator            | ✓                   | ✓                 | ✓         | ✓              | ✓        | solo se primary approva |
| close_family          | ✓                   | ✓                 | ✓         | on_request     | ✓        | ✗ (salvo consanguinei) |
| extended_family       | ✓                   | ✓                 | ✓         | on_request     | parziale | ✗ (salvo consanguinei) |
| distant_family        | ✓                   | ✓                 | on_request| ✗              | ✗        | ✗                 |
| external_connected    | ✗                   | ✗                 | ✗         | ✗              | ✗        | ✗                 |
| external_unknown      | ✗                   | ✗                 | ✗         | ✗              | ✗        | ✗                 |

Legenda:
- `✓` — visibile di default
- `✗` — non visibile di default
- `on_request` — non visibile di default, ma il viewer può inoltrare `access_request`
- `parziale` — alcuni contenuti sì (es: foto di gruppo), altri no (es: foto recenti intime); decisione lasciata al content-level tagging

## Matrice default per defunti

Per Person con `is_living=false`, la matrice cambia:

| Archetipo             | existence_structure | extended_identity | biography | memory   | medical_sensitive |
|-----------------------|---------------------|-------------------|-----------|----------|-------------------|
| primary_curator       | ✓                   | ✓                 | ✓         | ✓        | ✓ (con consenso)  |
| co_curator            | ✓                   | ✓                 | ✓         | ✓        | unanimità richiesta |
| close_family          | ✓                   | ✓                 | ✓         | ✓ + può aggiungere | solo consanguinei |
| extended_family       | ✓                   | ✓                 | ✓         | ✓ + può aggiungere | solo consanguinei |
| distant_family        | ✓                   | ✓                 | parziale  | parziale | ✗                 |
| external_connected    | ✗                   | ✗                 | ✗         | ✗        | ✗                 |
| external_unknown      | ✗                   | ✗                 | ✗         | ✗        | ✗                 |

Differenza fondamentale: per i defunti, `close_family` e `extended_family` possono **contribuire** contenuti di memoria (foto, storie). Per i viventi, contribuire è limitato al soggetto stesso e al curatore.

`contactability` non compare per i defunti (non ha senso).

## Preset di policy personali

Ogni utente ha un `privacy_preset` nel proprio profilo, applicato alle proprie informazioni come soggetto:

### `reserved`
Restringe la matrice default:
- `memory` visibile solo a `close_family` (non `extended_family`)
- `biography` on_request per `extended_family`
- `contactability` solo a `close_family`

### `balanced` (default alla registrazione)
Usa la matrice default come scritta sopra.

### `open`
Apre la matrice:
- `biography` visibile anche a `external_connected` (es: amici, colleghi nel guanxi degli altri)
- `memory` con approccio più aperto a contenuti non intimi

### `custom`
Usa `privacy_custom_overrides` JSONB per override granulari per archetipo/categoria.

## Override per nodo (NodePolicyOverride)

Per ogni nodo gestito da un curatore, è possibile definire override espliciti:
- "Per mio nonno Giuseppe, tutti i contenuti di memoria sono visibili a tutto l'albero, override del default"
- "Per questa zia vivente, contactability aperta anche a extended_family"

Precedenza (dal più forte al più debole):
1. `access_grants` espliciti (viewer ha grant specifico → vede)
2. `node_policy_overrides` sul target
3. `privacy_custom_overrides` dell'utente soggetto (se vivente)
4. Matrice default per preset (`reserved`/`balanced`/`open`)

## La pipeline dei permessi in 3 livelli

Implementata in `apps/permissions/services/`. Ogni richiesta dati attraversa questi 3 livelli in ordine.

### Livello 1 — Archetype resolution

Input: `(viewer_user, target_person)`
Output: `Archetype` enum

Pseudocodice:

```python
def resolve_archetype(viewer_user, target_person) -> Archetype:
    # Self check
    if viewer_user.person_id == target_person.id:
        return Archetype.SELF

    # Curatorship check
    curatorship = get_active_curatorship(viewer_user, target_person)
    if curatorship:
        if curatorship.role == 'primary':
            return Archetype.PRIMARY_CURATOR
        return Archetype.CO_CURATOR

    # Distance check
    distance = get_cached_distance(viewer_user.person, target_person)
    if distance is None:
        # Nessun percorso nell'albero
        if is_connected_via_guanxi(viewer_user, target_person):
            return Archetype.EXTERNAL_CONNECTED
        return Archetype.EXTERNAL_UNKNOWN

    if distance <= 2:
        return Archetype.CLOSE_FAMILY
    if distance <= 5:
        return Archetype.EXTENDED_FAMILY
    return Archetype.DISTANT_FAMILY
```

Questa funzione è **pura** e va **memoizzata per request** — viene chiamata molte volte in una singola page view.

### Livello 2 — Visibility calculation

Input: `(archetype, target_person, viewer_user)`
Output: `set[Category]`

Pseudocodice:

```python
def calculate_visible_categories(
    archetype: Archetype,
    target_person: Person,
    viewer_user: User,
) -> set[Category]:
    # Check access grants espliciti (precedenza massima)
    granted = get_active_access_grants(viewer_user, target_person)
    if granted:
        return granted.categories  # grant è esplicito, sovrascrive tutto

    # Check node override
    node_override = get_active_node_override(target_person)
    if node_override:
        rules = node_override.override_rules
        if archetype in rules.by_archetype:
            return set(rules.by_archetype[archetype])

    # Check personal policy del target (se vivente)
    if target_person.user_id:
        target_user = target_person.user
        if target_user.privacy_preset == 'custom':
            rules = target_user.privacy_custom_overrides
            if archetype in rules.by_archetype:
                return set(rules.by_archetype[archetype])
        else:
            return get_preset_defaults(target_user.privacy_preset, archetype, target_person.is_living)

    # Fallback: preset 'balanced' per nodi senza account
    return get_preset_defaults('balanced', archetype, target_person.is_living)
```

### Livello 3 — Field serialization

Data una Person e un set di `visible_categories`, costruisce il dict serializzato filtrando i campi.

```python
def serialize_person_for_viewer(person: Person, viewer_user: User) -> dict:
    archetype = resolve_archetype(viewer_user, person)
    visible = calculate_visible_categories(archetype, person, viewer_user)

    if not visible:
        # External unknown → il nodo non esiste per lui
        raise PermissionDenied()

    result = {}

    if Category.EXISTENCE_STRUCTURE in visible:
        result['id'] = person.id
        result['given_names'] = person.given_names
        result['surname'] = person.surname
        result['is_living'] = person.is_living
        if person.birth_date:
            result['birth_year'] = person.birth_date.year
        if person.death_date:
            result['death_year'] = person.death_date.year

    if Category.EXTENDED_IDENTITY in visible:
        result['nicknames'] = person.nicknames
        result['surname_at_birth'] = person.surname_at_birth
        result['birth_date'] = person.birth_date
        result['birth_date_precision'] = person.birth_date_precision
        result['birth_place'] = person.birth_place
        result['death_date'] = person.death_date
        result['death_place'] = person.death_place
        result['gender'] = person.gender
        result['profile_photo'] = serialize_content(person.profile_photo) if person.profile_photo else None

    if Category.BIOGRAPHY in visible:
        result['short_bio'] = person.short_bio
        # Altri dati biografici...

    # ... ecc. per le altre categorie

    return result
```

## Contenuti multi-soggetto — intersezione restrittiva

Un `Content` può essere taggato con N `Person` (tramite `content_subjects`). La sua visibilità è calcolata come intersezione delle visibilità di ciascun soggetto.

```python
def is_content_visible_to(content: Content, viewer_user: User) -> bool:
    if not content.subjects:
        # Caso degenere: contenuto orfano, non dovrebbe esistere
        return False

    # Per ciascun soggetto confermato, calcola se il viewer può vedere 'memory' di quel soggetto
    for subject in content.confirmed_subjects:
        archetype = resolve_archetype(viewer_user, subject)
        visible = calculate_visible_categories(archetype, subject, viewer_user)
        if Category.MEMORY not in visible:
            return False  # Intersezione restrittiva: basta un "no" per nascondere

    # Override del curatore del contenuto
    if content.visibility_override:
        return apply_override(content.visibility_override, viewer_user)

    return True
```

**Ottimizzazioni per query di lista** (es: tutti i contenuti di una pagina):
- Caching di `resolve_archetype` per request
- Pre-filter a livello SQL: EXCLUDE contenuti i cui subjects hanno policy più restrittiva del viewer
- Valutare materialized view `content_visibility_for_user` se le query superano i 100ms

## Flussi di governance dei permessi

### Richiesta di accesso (AccessRequest)

Quando un viewer è in archetype `extended_family`, `distant_family` o simili, e vede un campo `on_request`:
1. Il frontend mostra "Richiedi accesso a [categoria]"
2. Il viewer compila una richiesta con `message` opzionale
3. Riga in `access_requests` con `status='pending'`
4. Notifica al `primary_curator` del target (o all'utente stesso se vivente con account)
5. Curatore/utente approva/rifiuta
6. Se approvato, crea `access_grant` collegato con `source_request_id`

### Richiesta di curatela (CuratorshipRequest)

1. Un familiare stretto vede "Richiedi co-curatela" su un nodo defunto
2. Compila la richiesta, `auto_approve_at = now + 14 days`
3. Notifica al `primary_curator` esistente
4. Se il primary approva entro 14 giorni → `status='approved'`
5. Se non risponde → `status='auto_approved'` alla scadenza (cron task)
6. In entrambi i casi, creazione di riga `curatorships` con `role='co_curator'`

### Voto su decisioni straordinarie

Per curatele condivise, alcune azioni richiedono voto:
- Cambio di visibility policy del nodo
- Approvazione di merge con altro nodo
- Archiviazione del nodo
- Revoca di un curatore

Flusso:
1. Un co-curatore propone → riga in `curatorship_votes` con `proposal_payload`
2. Tutti i co-curatori attivi ricevono notifica
3. Hanno tempo fino a `voting_deadline` (default 7 giorni) per votare
4. A scadenza (o quando tutti hanno votato): valuta maggioranza
5. **Maggioranza semplice** (>50% di `approve` su chi ha votato) per la maggior parte delle decisioni
6. **Unanimità** richiesta per decisioni su dati medici
7. Applica decisione o segnala conflitto

### Claim di un nodo esistente

Un utente che si registra può reclamare un nodo già esistente nell'albero (es: tuo cugino vede il suo nodo creato da te):
1. User si registra o fa login
2. Ricerca nel proprio albero potenziale un nodo che rappresenta se stesso
3. Invia `person_claim` con `status='pending'`
4. Il `created_by_user_id` del nodo riceve notifica
5. Approvazione → `persons.user_id = claiming_user_id`, `persons.is_claimed = true`
6. La curatela preesistente del creatore viene automaticamente terminata (l'utente è ora curatore di se stesso implicito)

## Considerazioni di sicurezza aggiuntive

### Nessun leak via error messages

Gli errori 403/404 devono essere **indistinguibili**. Se un viewer è `external_unknown` rispetto a un target, non deve ricevere "403 Permission denied" (che rivelerebbe che il nodo esiste): deve ricevere "404 Not Found".

### Nessun leak via paginazione/counting

Liste e conteggi devono applicare i permessi a livello di query SQL. Mai fare `COUNT(*)` di tutti i nodi e poi filtrare in Python — i totali rivelerebbero informazione.

### Rate limiting sulle richieste

`access_requests`, `curatorship_requests`, `in_app_messages` sono rate-limitati per utente per prevenire harassment o enumeration attack.

### Audit di tutte le grant

Ogni `access_grant` creato/revocato è tracciato in `audit_log`. Un utente può sempre vedere chi gli ha dato/tolto accesso a cosa.
