# `apps/content` — Contesto dominio

## Responsabilità

Gestisce i **contenuti multimediali e narrativi** del sistema: foto, storie testuali, audio, video, documenti, scansioni. È il **cuore distintivo di Radice** rispetto ai competitor: la qualità dell'esperienza di memoria collaborativa nasce qui.

Include il sistema di **tagging multi-soggetto** (un contenuto ritrae più `Person`), **commenti collaborativi** (più persone possono commentare/annotare un contenuto), e **collezioni** (album, corrispondenze, storie cronologiche).

## Entità principali

- **`Content`** — entità multimediale/testuale con metadata (data riferimento, luogo, uploader).
- **`ContentVersion`** — shadow versioning per Content (title, body, metadata, date, location).
- **`ContentSubject`** — tag many-to-many Content ↔ Person, con stato (proposed/confirmed/rejected).
- **`ContentComment`** — commento/annotazione sul contenuto (collaborativo, append-only con soft delete).
- **`ContentCollection`** — raggruppamento trasversale di contenuti (album, correspondence, event, chronological_story, custom).
- **`ContentCollectionItem`** — membership Content ↔ Collection con order_index.

## Dipendenze

- Dipende da: `core`, `identity`, `permissions` (per check di visibilità), `tree` (per distance-based permissioni multi-soggetto)
- Chiama: `curatorship` per determinare chi può approvare tag

## Vincoli critici

### Vincolo 1: Ogni Content ha almeno un Subject confermato
Non esistono contenuti orfani. La logica deve enforceare questa invariante:
- **Creation**: il servizio di upload richiede almeno un subject_person_id in payload
- **Deletion di subject**: l'ultimo subject non può essere rimosso; al suo posto il Content va archiviato

Enforced a service layer (non DB hard constraint, troppo rigido per transazioni multi-step), testato rigorosamente.

### Vincolo 2: Visibilità = intersezione restrittiva
Ricordato qui ma **implementato in `apps/permissions/services/content_visibility.py`**. Questo dominio non duplica la logica. Quando fai query di Content, passa sempre da `filter_visible_contents_queryset` di `permissions`.

### Vincolo 3: Tag Status flow
```
proposed (default) → confirmed (dal soggetto, se ha User)
                   → rejected (dal soggetto)

Il tag_status 'proposed' è visibile solo a:
- Uploader del contenuto
- Soggetto taggato (per poter confermare/rifiutare)
- Curatori del soggetto (se defunto)

Content con tutti i tag 'proposed' non ancora confermati ha visibilità ridotta: visibile solo a uploader e subject (o curator). Serve a prevenire tagging abusivo visibile ad altri prima di conferma.
```

### Vincolo 4: Upload flow via presigned URL
**Mai** caricare media passando dal backend Django. Flusso:
1. Frontend chiama `POST /api/contents/upload-intent/` con metadata
2. Backend risponde con presigned URL R2 (scadenza 15min) + content_id pendente
3. Frontend carica direttamente su R2 via PUT
4. Frontend conferma upload: `POST /api/contents/{id}/confirm-upload/`
5. Backend verifica che l'oggetto esista in R2, aggiorna `media_url`, status = confirmed
6. Celery task asincrono: resize, conversione WebP/AVIF, EXIF extraction

Se step 4 non avviene entro 1 ora, Celery cleanup task marca il Content come abandoned e cancella l'oggetto R2 parziale.

### Vincolo 5: URL firmati per accesso in lettura
I `media_url` in `Content` sono chiavi R2 (es: `raw/2026/04/abc-def-123.jpg`), **non URL pubblici**. Quando il frontend carica un Content visibile al viewer, il backend genera URL firmato a scadenza (~10 minuti) via `services/media_service.py`.

Questo evita che URL pubblici possano essere condivisi esternamente bypassando i permessi.

### Vincolo 6: Commenti sono append-only (con soft edit)
`ContentComment` ha `edited_at` nullable per tracciare modifiche, ma non si può cancellare hard (solo archive). La cronologia della discussione su un contenuto è preziosa per il memoriale; perderla è una regressione.

## Flussi principali

### Upload di una foto multi-soggetto

```
1. Utente (mobile) seleziona foto, apre UI di tagging
2. Indica subjects proposti (autocomplete di Person visibili nell'albero)
3. Inserisce title, body (caption), reference_date, reference_date_precision, reference_location
4. POST /api/contents/upload-intent/ → presigned URL R2 + content_id temporaneo
5. PUT foto direttamente su R2 (con progress bar)
6. POST /api/contents/{id}/confirm-upload/
7. Backend:
   - Transaction: crea Content, crea N ContentSubject (status='proposed' per viventi con account, 'confirmed' per viventi che sono self, defunti curati da uploader)
   - Celery: resize, webp/avif, exif extraction
   - Notifiche: ai soggetti viventi con account (per conferma tag)
   - Audit log
```

### Conferma tag

```
1. User riceve notifica "sei stato taggato in foto X"
2. Vede contenuto, subject_list, può:
   - Confermare: ContentSubject.tag_status='confirmed'
   - Rifiutare: ContentSubject.tag_status='rejected', rimosso dalla visibilità
   - Chiedere rimozione del Content intero (se la foto è inappropriata)
3. Audit log
```

### Creazione di una Collection

```
1. User crea ContentCollection con title, description, type
2. Aggiunge contenuti (drag & drop UI)
3. ContentCollectionItem creato per ogni aggiunta
4. Order_index auto-incrementato, modificabile con drag-riordino
5. Cover image opzionale (uno dei contenuti)
6. visibility_inherit=true (default): la Collection è visibile al viewer se almeno un contenuto è visibile
   visibility_inherit=false: la Collection ha sua policy propria (oggetto NodePolicyOverride-like, raro)
```

### Commento su un contenuto

```
1. Viewer con accesso a Content può commentare se archetype >= extended_family verso almeno un subject confermato
2. POST /api/contents/{id}/comments/ con body
3. Notifica a uploader + subject principali
4. Commenti mostrati cronologicamente nella pagina del Content
5. Modifica entro 15 minuti = edit senza mostrare "edited"; dopo = mostra "edited"
```

## Servizi chiave

### `services/upload_service.py`
- `create_upload_intent(uploader, metadata)` → (Content, presigned_url)
- `confirm_upload(content)` → Content (verifica R2 object, avvia processing task)
- `cleanup_abandoned_uploads()` → int (Celery beat task hourly)

### `services/media_processing.py` (Celery tasks)
- `process_image(content_id)` → generate thumb 400px, medium 1200px, webp/avif
- `extract_exif(content_id)` → popola `media_metadata` con data/luogo scatto (se presenti)
- `process_video(content_id)` → thumbnail poster, possibili transcodifiche future

### `services/tagging_service.py`
- `propose_tag(content, person, tagged_by_user)` → ContentSubject
- `confirm_tag(subject, confirmer)` → ContentSubject
- `reject_tag(subject, rejecter)` → ContentSubject
- `request_content_removal(content, requester, reason)` → RemovalRequest (porta a voto dei curatori se più subject)

### `services/collection_service.py`
- `create_collection(creator, title, type, **kwargs)` → ContentCollection
- `add_to_collection(collection, content, order_index=None)` → ContentCollectionItem
- `reorder_collection(collection, new_order: list[content_id])` → bulk update

### `services/media_service.py`
- `get_signed_url(content, variant='original'|'thumb'|'medium', ttl=600)` → str
- Called from serializer during serialization

## File attesi

```
content/
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
│   ├── upload_service.py
│   ├── media_processing.py
│   ├── media_service.py         # URL firmati R2
│   ├── tagging_service.py
│   └── collection_service.py
├── tasks.py                     # Celery tasks wrappers
├── r2_client.py                 # Cloudflare R2 client wrapper
├── factories.py
└── tests/
    ├── test_upload_flow.py
    ├── test_media_processing.py
    ├── test_tag_lifecycle.py
    ├── test_content_removal.py
    ├── test_collections.py
    ├── test_signed_urls.py
    └── fixtures/
        └── sample_contents.py
```

## Test density richiesta

65%+. Flussi di upload hanno molti rami (fail di upload R2, metadata invalidi, cleanup abandoned). Test obbligatori:
- Upload abbandonato viene cleanato dopo TTL
- Content senza subject confermato ha visibilità ridotta
- Signed URL scadono correttamente
- Processing task idempotente (re-run senza duplicare derived)
- Collection con contenuti misti (alcuni visibili, alcuni no) mostra solo visibili al viewer

## Note architetturali

**R2 bucket structure**:
```
radice-media/
├── raw/YYYY/MM/{content_id}.{ext}           # originale immutabile
├── thumb/YYYY/MM/{content_id}.webp          # 400px thumbnail
├── medium/YYYY/MM/{content_id}.webp         # 1200px medium
└── audio/YYYY/MM/{content_id}.{ext}         # audio e video restano in formato originale
```

Per backup: R2 ha replication interna. Aggiungere sync settimanale a Backblaze B2 via Celery task (milestone successiva).

**Export GDPR**: quando un user fa export del proprio dato, i Content dove è uploader vengono esportati con media originali. I Content dove è solo subject vengono esportati come references (no media download, rispettiamo la proprietà di chi ha uploadato).
