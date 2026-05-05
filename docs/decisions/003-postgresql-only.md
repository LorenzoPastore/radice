# ADR-003: PostgreSQL puro, nessuna estensione grafo

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

Le relazioni familiari e il grafo guanxi sono naturalmente strutture a grafo. Il cuore della logica dei permessi si basa sul calcolo della **distanza di parentela** tra due `Person`: "viewer è a distanza ≤2 dal target?" determina l'archetipo, che determina la visibilità.

Calcolare distanze su un grafo è un'operazione naturale su database grafo (Neo4j, Apache AGE), mentre su SQL richiede query ricorsive (CTE) con costi potenzialmente alti su grafi grandi.

Tre strategie principali erano sul tavolo:
- **B**: PostgreSQL puro con CTE ricorsive + tabella di cache `person_distances` popolata lazy
- **C**: PostgreSQL + Apache AGE (estensione grafo Postgres, Cypher su stesso DB)
- **C-bis**: PostgreSQL + Neo4j separati (best-of-breed, due DB)

## Opzioni valutate

### Opzione 1: PostgreSQL puro + cache lazy (strategia B)
Un solo database. Le distanze si calcolano on-demand con CTE ricorsive su `relationships`, i risultati vengono memorizzati in una tabella `person_distances` che funge da cache. Trigger invalidano la cache quando cambiano le relazioni.

Pro:
- Un solo sistema da gestire, backuppare, monitorare
- Ecosistema Django ORM nativo, no astrazioni esotiche
- Semplice in dev, semplice in produzione
- Costi gestiti bassi (Railway single Postgres)

Contro:
- Query di distanza su alberi molto grandi (10k+ nodi) può diventare lenta
- Invalidazione cache su relationship mutation richiede attenzione (ma gestibile con trigger)
- Query di tipo "percorso più breve tra A e B" sono complesse da scrivere

### Opzione 2: PostgreSQL + Apache AGE (strategia C)
Un database fisico con due paradigmi. AGE è un'estensione che aggiunge capacità grafo a Postgres, supporta Cypher.

Pro:
- Distanze calcolate nativamente come operazione grafo
- Un solo DB fisico (backup unificato)
- Query di percorso naturali in Cypher

Contro:
- Ecosistema AGE molto più piccolo di Neo4j
- Django non ha integrazione nativa, servirebbe codice custom per serializzare query Cypher
- Supporto in hosted providers (Railway, Supabase) non esistente — servirebbe Postgres self-hosted con AGE pre-installato
- Meno maturità → bug più probabili, meno documentazione
- Per una famiglia di 200-500 persone è **over-engineered**

### Opzione 3: PostgreSQL + Neo4j separati (strategia C-bis)
Due database specializzati, ognuno per il suo paradigma.

Pro:
- Neo4j è il più maturo dei grafi
- Cypher molto espressivo
- Best-of-breed per entrambi i casi d'uso

Contro:
- Sincronizzazione tra i due DB è un problema serio (transazioni distribuite, eventual consistency, outbox pattern)
- Costi raddoppiati (2 hosting)
- Complessità operazionale (2 backup, 2 monitoring, 2 upgrade path)
- Overhead di sviluppo significativo per un progetto single-developer

## Decisione

**Opzione 1: PostgreSQL puro + cache lazy su `person_distances`**.

Motivazioni concrete:

1. **Scala realistica**: Radice parte come app familiare (100-300 nodi). A questa scala, le CTE ricorsive su Postgres restano sotto i 50ms tranquillamente. Il paradigma grafo vince in modo tangibile solo sopra i 5000-10000 nodi.

2. **Semplicità operazionale**: un solo DB fisico, un backup, un monitoring, un upgrade path. Valore enorme per un progetto single-developer che deve durare decenni.

3. **Ecosistema Django nativo**: tutto funziona con ORM standard + alcune `RawSQL` per le CTE. Gli agenti AI hanno contesto pieno sullo stack senza dover imparare Cypher.

4. **Costo zero aggiuntivo**: Railway Postgres hobby copre il caso d'uso. Aggiungere AGE richiederebbe self-hosting Postgres con estensione custom. Aggiungere Neo4j richiederebbe un secondo hosting a pagamento.

La strategia B è "good enough" per almeno 3-5 anni di vita del progetto. Il percorso di migrazione a un paradigma grafo, se mai servisse, è chiaro.

## Conseguenze

### Positive
- Un solo database, un solo sistema, complessità operativa minima
- Ecosistema ORM completo
- Query di dominio (non solo distanze) semplici e testabili
- Cache lazy è un pattern ben conosciuto, implementabile in ore

### Negative / Trade-off
- CTE ricorsive richiedono attenzione: vanno scritte con LIMIT di profondità per evitare runaway
- Cache invalidation è un problema classico: trigger su `relationships` + chiavi TTL opzionali
- Query "percorso più breve" o "tutti i percorsi tra A e B" sono difficili
- La logica di calcolo distanze va testata con attenzione su casi edge (matrimoni tra cugini, cicli impossibili in parent_child)

### Trigger per riconsiderazione
- Se le query di distanza superano i 100ms di media in produzione
- Se una famiglia istanza supera i 5000 nodi
- Se aggiungiamo feature di "ricerca percorsi" (es: "come sono collegato a questa persona nel guanxi?")
- Se scaliamo a migliaia di famiglie distinte con dataset aggregati complessi

In tal caso, la migrazione più probabile è verso **Apache AGE** (resta un solo DB fisico) piuttosto che Neo4j separato.
