# `frontend/src/components/tree/` — Contesto visualizzazione albero

Questo documento fornisce contesto profondo per il lavoro sulla visualizzazione albero genealogico, il componente più distintivo e tecnicamente denso del frontend.

## Architettura ad alto livello

La visualizzazione è composta da 3 layer:

1. **Dati**: hook `useTreeData(focusPersonId)` carica da API (con fallback IndexedDB offline), normalizza in strutture typed
2. **Layout**: funzione pura `computeGenealogicalLayout(persons, relationships, focusPersonId)` calcola posizioni (x, y) per ogni nodo
3. **Rendering**: `TreeCanvas` wrappa react-flow con node types (`PersonNode`) e edge types (`ParentChildEdge`, `SpouseEdge`, `SiblingEdge`, `AffinityEdge`)

Separazione stretta: layout è pura (testabile senza DOM), rendering è solo presentazione.

## Struttura file

```
components/tree/
├── CLAUDE.md                       (questo file)
├── TreeCanvas.tsx                  # Entry point, wrappa react-flow
├── TreeSkeleton.tsx                # Loading state
├── nodes/
│   ├── PersonNode.tsx              # Node component con modalità adaptive
│   ├── FullPersonNode.tsx          # Modalità full (alto zoom, permessi ampi)
│   ├── StubPersonNode.tsx          # Modalità stub (solo existence_structure)
│   └── CompactPersonNode.tsx       # Modalità compact (zoom basso)
├── edges/
│   ├── ParentChildEdge.tsx
│   ├── SpouseEdge.tsx
│   ├── SiblingEdge.tsx
│   └── AffinityEdge.tsx
├── controls/
│   ├── TreeToolbar.tsx             # Zoom, fit, focus reset
│   ├── TreeMiniMap.tsx
│   └── FilterPanel.tsx             # Filtri per generation, living/deceased
├── layout/
│   ├── CLAUDE.md                   # Documento separato per l'algoritmo
│   ├── genealogical-layout.ts      # ALGORITMO — cuore del dominio
│   ├── constants.ts                # Spacing, dimensioni, ecc.
│   ├── types.ts                    # Internal types
│   └── genealogical-layout.test.ts # Test con fixture complesse
├── hooks/
│   ├── useTreeData.ts              # Fetch + normalize
│   ├── useReactFlowZoom.ts
│   └── useKeyboardNavigation.ts    # Arrow keys per accessibilità
└── types.ts                        # Types esportati del modulo tree
```

## L'algoritmo di layout genealogico

Il file `layout/CLAUDE.md` tratta in profondità l'algoritmo. Sintesi qui per context.

### Input e output

```typescript
type LayoutInput = {
  persons: Person[];                // Tutte le Person visibili al viewer
  relationships: Relationship[];     // Tutte le relazioni strutturali
  affinities: FamilyAffinity[];      // Affinità simboliche
  focusPersonId: string;             // Centro della visualizzazione
  viewport?: { width: number; height: number }; // Per scaling iniziale
};

type LayoutOutput = {
  nodes: Node<PersonData>[];         // react-flow nodes con position
  edges: Edge<EdgeData>[];           // react-flow edges tipizzati
  metadata: {
    generationRange: [number, number]; // Min/max generation level
    totalWidth: number;
    totalHeight: number;
  };
};
```

### Step principali

1. **Discovery BFS**: partendo da focusPersonId, esplora parent_child relationships per determinare generation levels (0 = focus, ±1 per adiacenti, ecc.)

2. **Spouse pairing**: per ogni persona visitata, identifica eventuali coniugi. Se coniuge ha un proprio sotto-albero (figli da precedente matrimonio), include quel sotto-albero assegnando generation levels relativi.

3. **Conflict resolution**: se una persona appare raggiungibile da più cammini (matrimoni tra cugini, cross-links), usa il cammino di minor distanza per assegnare generation.

4. **Horizontal positioning**:
   - Raggruppa siblings (figli della stessa coppia) adiacenti
   - Coniugi side-by-side orizzontale con spacing ridotto
   - Famiglie (couple + figli) come "blocchi" con spacing maggiore tra blocchi
   - Algoritmo Reingold-Tilford modificato per gestire i vincoli sopra

5. **Vertical positioning**: `y = generation_level * GENERATION_HEIGHT`. Piccoli jitter random (±5px) per evitare rigidity visiva.

6. **Cross-links**: relationships che collegano parti dell'albero non-adiacenti gerarchicamente (cugini sposati) generano edges "extra" con routing curvilineo per leggibilità.

7. **Affinity overlay**: FamilyAffinity genera edges tratteggiati, non influenzano posizioni strutturali.

### Complessità

- O(n) per discovery BFS
- O(n log n) per sorting siblings
- O(n²) worst case per conflict resolution su grafi densi, ma in pratica O(n · log d) dove d è la profondità media

Target performance: 500 nodi in < 500ms su mobile mid-range.

## Rendering adaptive (zoom levels)

`PersonNode.tsx` sceglie modalità in base a zoom corrente + dati disponibili:

```typescript
function PersonNode({ data }: NodeProps<PersonData>) {
  const zoom = useReactFlowZoom();
  const isStubData = !data.fullProfile; // viewer ha solo existence_structure

  if (zoom < 0.3) return <CompactPersonNode data={data} />;
  if (isStubData || zoom < 0.6) return <StubPersonNode data={data} />;
  return <FullPersonNode data={data} />;
}
```

### Full mode

Contiene:
- Avatar (signed URL, 80x80) — con fallback iniziale nome
- Nome completo + surname
- Date (nascita-morte o "living")
- Mini bio (2 righe max, truncated)
- Icone stato: is_living, is_self, has_content_available

Dimensione nodo: ~240x140px.

### Stub mode

Solo:
- Nome (forma breve)
- Anno nascita / morte
- Se defunto, piccolo indicator

Dimensione: ~160x80px.

### Compact mode

Solo:
- Iniziali del nome
- Colore del ramo (hash hue-based da surname)

Dimensione: ~40x40px, circle shape.

## Interazioni

### Tastiera (accessibilità)

- **Arrow keys**: naviga tra nodi adiacenti (up → genitore, down → figlio, left/right → sibling o coniuge)
- **Enter**: apri profilo del nodo focused
- **Escape**: chiudi modal/sidebar, ritorna a canvas
- **+/-**: zoom in/out
- **Home**: torna a focus_person (reset vista)

### Touch mobile

- **Tap su nodo**: apri sidebar con profilo
- **Double tap nodo**: focus change (ricentra albero su quel nodo)
- **Pinch**: zoom
- **Pan con uno dito**: scroll canvas

### Mouse desktop

Come mobile + hover preview:
- Hover su nodo → tooltip con quick info (2s delay)
- Right-click → context menu (opzioni: "Fai focus qui", "Vedi profilo", "Aggiungi parente")

## Micro-animazioni

Implementate con CSS transitions su transform/opacity (perf-safe) e Framer Motion solo per orchestrazioni complesse.

### Entry animation

Primo render:
```css
.person-node {
  animation: fade-scale-in 400ms ease-out backwards;
}
/* stagger 30ms per generation level, max 300ms totale */
```

### Focus change

Quando focusPersonId cambia:
1. Ricalcola layout (background)
2. Nodi che restano: transition smooth della position (500ms ease-in-out)
3. Nodi che escono: fade-out 300ms
4. Nodi nuovi: fade-in 300ms
5. Viewport: pan smooth verso nuovo focus (800ms)

### Add relationship (realtime)

Quando un'azione aggiunge una relationship:
1. Nuovo nodo fade-in nella posizione calculata
2. Nuovo edge: stroke-dashoffset animation (draws in)

## Performance considerations

### Viewport culling

react-flow lo fa nativamente. Verifica: nodi fuori viewport non sono nel DOM (usa browser devtools).

### Memoization

```tsx
const MemoizedPersonNode = React.memo(PersonNode, (prev, next) => {
  return prev.data.id === next.data.id &&
         prev.data.updatedAt === next.data.updatedAt &&
         prev.selected === next.selected;
});
```

Comparator custom perché react-flow passa nuovi oggetti `data` a ogni render.

### LOD rendering

Già descritto sopra: Full/Stub/Compact in base a zoom. In compact, non renderizzare texture avatar — solo colore e iniziali.

### Layout worker (se serve)

Se `computeGenealogicalLayout` supera 100ms main-thread, spostare in Web Worker. File `layout/genealogical-layout.worker.ts` con message passing.

## Testing

### Layout tests (unit, veloci)

`genealogical-layout.test.ts` con fixture da `apps/tree/tests/fixtures/sample_family.py` (replicati in JSON per test frontend):

```typescript
describe('genealogicalLayout', () => {
  test('lineare: nonno-padre-figlio a generazioni -2, -1, 0', () => {
    const result = computeGenealogicalLayout(LINEAR_FAMILY_FIXTURE, 'me');
    expect(result.nodes.find(n => n.id === 'grandfather').position.y).toBe(-2 * GENERATION_HEIGHT);
  });

  test('cugini sposati: cross-link renderizzato come edge extra', () => {
    const result = computeGenealogicalLayout(CROSS_LINK_FIXTURE, 'me');
    const crossLinkEdge = result.edges.find(e => e.type === 'spouse' && ...);
    expect(crossLinkEdge).toBeDefined();
  });

  // ... 7+ casi fixture
});
```

### Component tests (React Testing Library)

```typescript
test('PersonNode renders in stub mode when zoom < 0.6', () => {
  mockUseReactFlowZoom.mockReturnValue(0.5);
  render(<PersonNode data={mockData} />);
  expect(screen.getByTestId('stub-person-node')).toBeInTheDocument();
});
```

### Visual regression (Storybook)

Stories per ogni node type in ogni modalità. Chromatic o Percy per screenshot diff su PR.

### E2E (Playwright)

```typescript
test('user can navigate tree with keyboard', async ({ page }) => {
  await page.goto('/tree');
  await page.focus('[data-testid="person-node-me"]');
  await page.keyboard.press('ArrowUp');
  await expect(page.locator('[data-testid="person-node-parent"]')).toBeFocused();
});
```

## Anti-pattern da evitare

- **Layout nel render function**: deve essere pre-calcolato, non recompute durante render
- **Accesso a API nel node component**: i dati arrivano già enriched da `useTreeData`
- **Logica permessi**: dati già filtrati dal backend, nessun check client-side
- **CSS animations su position**: usare react-flow positioning system
- **Non-memoized inline styles**: React.memo viene bypassato se passi `style={{ ... }}` inline sempre nuovo

## Future extensions (non priorità)

- **Tree theming**: ogni ramo familiare con colore leggermente diverso (generato da surname hash)
- **Time slider**: scroll temporale per vedere chi era vivo in un dato anno ("1950")
- **Heatmap overlay**: mostrare density di contenuti per ramo ("ramo con più foto")
- **Minimap interactive**: click su minimap = pan
- **3D mode opzionale**: rendering 3D per "wow effect", disabilitato su mobile
