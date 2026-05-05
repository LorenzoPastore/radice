# ADR-005: Separazione User e Person nel data model

**Status**: Accepted
**Date**: 2026-04-20
**Decision makers**: Lorenzo Pastore

## Contesto

Radice deve rappresentare sia persone che hanno un account nell'app sia persone che non lo hanno (defunti, antenati remoti, bambini, anziani non digitali, cugini mai contattati). La maggior parte delle persone nel sistema **non avrà mai un account** — i nostri nonni non useranno l'app.

La tentazione iniziale sarebbe di avere un solo modello `User` che rappresenta tutti — ma un defunto del 1920 non è un "utente", non ha email, non effettua login. Forzare questa concettualizzazione porta a schema degeneri (email fittizie, utenti "disabilitati per morte").

## Opzioni valutate

### Opzione 1: Un solo modello User (anche per i non-registrati)
Unica tabella con flag `is_registered`. I non-registrati hanno email null o placeholder.

Pro:
- Uno schema solo, meno join
- Relazioni dirette (es: "figlio di" → User to User)

Contro:
- Semantica confusa: gli utenti registrati e i defunti convivono nella stessa tabella
- Campi applicabili solo a registrati (email, password_hash, preferences) sono sparsi e confondono
- Auth framework (django-allauth) assume che ogni User sia loggabile
- Proliferazione di `is_registered=True` in query di auth

### Opzione 2: Due modelli separati con relazione opzionale
Due tabelle: `users` (account) e `persons` (persone reali). `User.person_id` FK obbligatoria unica. `Person.user_id` FK opzionale unica.

Pro:
- Semantica cristallina: User = account, Person = persona reale
- Auth framework lavora solo su `users` senza contaminazioni
- Campi auth-specific restano in `users`, campi persona-specific in `persons`
- Import di GEDCOM o altri formati genealogici è naturale: importano `Person`, non `User`
- Una Person può esistere per decenni senza mai diventare User

Contro:
- Un join in più per molte query (es: trova il display_name dell'autore di un contenuto)
- Più attenzione richiesta nel distinguere contesti (chi modifica? → User. Di chi parliamo? → Person)

### Opzione 3: User come sottoclasse di Person (table inheritance)
Usa Django multi-table inheritance: `Person` base, `User` la estende.

Pro:
- Conciliare unità concettuale con specializzazione
- Query polimorfiche possibili

Contro:
- Multi-table inheritance in Django ha performance implicazioni
- Confusione su quale tabella interrogare per cosa
- Non risolve il problema: un defunto del 1920 non è un User "disabled"

## Decisione

**Opzione 2: due modelli separati `User` e `Person` con relazione opzionale**.

Questa scelta è **fondativa del data model** e non è negoziabile. È il pilastro 3 del progetto (CLAUDE.md principale).

Ragionamento:

1. **Semantica pulita**: User è account, Person è persona. Due concetti diversi, due tabelle. Nessuna ambiguità in query, serializer, business logic.

2. **La realtà del dominio**: la maggior parte delle Person non avrà mai User. Far convivere le due entità nello stesso modello distorce lo schema per un caso minoritario.

3. **Tutti i flussi si reggono su questa separazione**:
   - **Claim**: un User che si registra reclama una Person preesistente
   - **Invitation**: un User invita un futuro-User a reclamare una specifica Person
   - **Curatorship**: un User (non una Person) gestisce Person che non sono se stesso
   - **Authorship**: azioni sono fatte da User (chi ha caricato questo contenuto?), ma riguardano Person (chi è taggato?)

4. **Import futuro**: GEDCOM e formati genealogici importano persone, non account. La separazione rende l'import uno-a-uno con `Person` senza toccare `User`.

## Conseguenze

### Positive
- Schema semanticamente pulito e autoesplicativo
- Business logic riflette la realtà del dominio
- Estendibilità naturale: aggiungere campi a Person (dati storici, biografia, medical) senza toccare User
- Auth framework isolato e inalterato

### Negative / Trade-off
- Ogni view che mostra "chi ha fatto X" deve fare il join User → Person per prendere display_name
- Nel codice, richiede attenzione: distinguere `request.user` (User autenticato) da `request.user.person` (Person associata)
- Potenziale confusione per nuovi contributor / agenti AI che assumono User == Person

### Trigger per riconsiderazione
**Non riconsiderabile senza riscrivere il sistema.** Questa è una decisione di schema irreversibile. L'unico modo di cambiarla sarebbe rifare completamente il data model, il che implica un nuovo progetto.

## Note per implementazione

Convenzioni di naming per chiarezza:
- Parametri di funzione: `viewer_user`, `target_person`, `actor_user` — mai `user` ambiguo se il contesto coinvolge anche Person
- In DRF serializer, quando si serializza una Person mostrando chi l'ha creata: usare `created_by_user` nel payload, non `created_by` ambiguo
- Nei test: fixture separate `user_factory()` e `person_factory()`, con helper `registered_user_with_person()` per i casi dove servono entrambi collegati
