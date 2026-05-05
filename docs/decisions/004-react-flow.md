# ADR-004: Visualizzazione albero con react-flow + layout genealogico custom

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

La visualizzazione dell'albero genealogico è il componente frontend più visibile del prodotto. Gli alberi genealogici reali non sono alberi in senso matematico (rooted trees) ma **grafi diretti aciclici con cross-links**: matrimoni tra cugini, secondi matrimoni con figli da entrambe le parti, adozioni, famiglie allargate con step-parents.

Serve una libreria/approccio che gestisca:
- Rendering performante di 200-1000+ nodi
- Zoom, pan, focus su un nodo
- Relazioni non solo parent-child (coniugi, fratelli, affinity simboliche)
- Interazioni: click per dettaglio, drag per rearrange, hover per preview
- Estetica moderna con micro-animazioni
- Adattamento mobile (responsive + touch)

## Opzioni valutate

### Opzione 1: d3-hierarchy + rendering custom
La libreria d3 fornisce algoritmi di layout per alberi. Rendering totalmente custom via SVG/Canvas.

Pro:
- Controllo totale
- Performance ottimizzabile al massimo
- Nessun lock-in

Contro:
- Solo alberi puri (rooted tree), no cross-links nativi
- Settimane di lavoro per implementare interazioni basilari (pan, zoom, drag)
- Gestione topologia genealogica reale (matrimoni, step-parents) da costruire da zero
- Mantenibilità a lungo termine: codice lungo da capire quando si torna sul progetto

### Opzione 2: react-flow (xyflow)
Libreria moderna per grafi interattivi in React, molto attiva come community.

Pro:
- Zoom, pan, drag, selezioni, gruppi — tutto gratis
- Performance ottime con viewport culling (fino a ~10k nodi)
- Estetica pulita, customizable
- Estende naturalmente al grafo guanxi (stesso engine)
- Community ricca, esempi, documentazione

Contro:
- Non è specializzata in genealogia: layout algoritmico per alberi familiari va costruito
- Performance degrada sopra ~500 nodi visibili contemporaneamente (gestibile con culling)

### Opzione 3: family-chart
Libreria specializzata in alberi genealogici.

Pro:
- Topologia familiare nativa (matrimoni, figli multipli, step-parents)
- Layout algoritmico pensato apposta
- Implementazione immediata

Contro:
- Community piccola, manutenzione incerta
- DX meno moderna (vanilla JS, non React-first)
- Customizzazione limitata: difficile fare qualcosa di distintivo visivamente
- Estetica di default datata

### Opzione 4: BALKAN FamilyTreeJS
Libreria commerciale, molto completa.

Pro:
- Specializzata, gestisce tutti i casi edge
- Estetica professionale out-of-the-box
- Matura

Contro:
- **Licenza commerciale** per uso non-personale (~500-1000€ una tantum)
- Lock-in su una libreria proprietaria
- Contrasta con il pilastro "no vendor lock-in, longevità decennale"

## Decisione

**react-flow + layout genealogico custom**.

Ragionamento:

1. **Controllo senza rifare da zero**: react-flow fornisce tutte le primitive interattive (pan, zoom, drag, selezione, edge rendering). Non serve reinventare la ruota per queste cose.

2. **Layout custom è investimento mirato**: implementare il layout genealogico (posizionamento automatico di generations, gestione coniugi side-by-side, gestione cross-links per matrimoni tra cugini) è 2-3 settimane di lavoro focalizzato su un algoritmo pulito, testabile. Il risultato si possiede, non dipende da librerie che potrebbero essere abbandonate.

3. **Estensione naturale al guanxi**: lo stesso engine react-flow renderizza il grafo guanxi (senza layout gerarchico, con layout force-directed o manuale). Uniformità di codice frontend.

4. **Longevità**: react-flow è open source, activamente sviluppato da una azienda seria (xyflow), con ampia adozione. Probabilità di esistere tra 5 anni: molto alta. In ogni caso, il layout custom che scriviamo è portabile.

5. **Libertà di estetica**: il progetto vuole essere visivamente distintivo (micro-animazioni, elementi che si spostano). react-flow dà il controllo necessario; family-chart e balkan impongono loro stili.

## Conseguenze

### Positive
- Stack frontend uniforme (stessa libreria per albero e guanxi)
- Controllo estetico pieno
- Performance scalabile con viewport culling
- Nessun lock-in su libreria commerciale

### Negative / Trade-off
- Layout genealogico custom è investimento significativo (2-3 settimane)
- Il layout custom deve gestire tutti i casi edge di famiglie moderne (step, adozioni, de-facto, multipli matrimoni)
- Test del layout richiede fixture di dati complessi (viene consegnato come milestone dedicata)

### Trigger per riconsiderazione
- Se il layout custom si rivela impossibile da mantenere dopo prima implementazione
- Se react-flow abbandonasse lo sviluppo (improbabile)
- Se un giorno il progetto avesse budget per balkan.js con ROI giustificato
