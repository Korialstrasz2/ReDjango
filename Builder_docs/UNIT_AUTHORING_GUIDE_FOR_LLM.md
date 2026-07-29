# Guida per LLM: creare e modificare una Unit

Questa guida è il contratto operativo per un LLM che deve creare una nuova
`core.Unit` in ReDjango. Prima di proporre valori, leggere anche
`Builder_docs/UNIT_GENERATION.md` e verificare nel catalogo corrente gli ID
di Skill e Oggetti. Non inventare ID, nomi di slot, variabili statistiche o
famiglie. La Unit è un blueprint: il personaggio vero viene creato soltanto
dal generatore condiviso usato da Combattimento e dall'anteprima di Gestione
Unit.

## 1. Scegliere il contratto

Ogni Unit dichiara esattamente un `generation_rules.kind`.

- `creature`: Animali, mostri, costrutti e creature soprannaturali. Non
  configurare Skill, perk, Competenze o equipaggiamento. Usare curve
  statistiche e `skill_actions` innate.
- `humanoid`: persone e avversari che seguono la progressione dei personaggi.
  Configurare Core, profilo archetipo, Competenze, pool Skill ed
  equipaggiamento.

Non aggirare il contratto. Un lupo non diventa più forte attraverso una Skill
umana; un bandito non riceve un Morso innato al posto di una Skill.

## 2. Definire l'identità prima dei numeri

Scrivere:

1. `nome` e `categoria`;
2. una `archetipo_descrizione` breve che descriva ruolo, distanza, difesa,
   magia e comportamento;
3. `lore_description` separata dalle regole;
4. `notes` con decisioni di authoring e provenienza;
5. `metadata.sourceProject`, `sourceTable` e `sourceIds` quando la fonte è
   Elder Django.

Ogni scelta successiva deve poter essere giustificata dalla descrizione
dell'archetipo.

## 3. Progressione di un Umanoide

Scegliere un Core fra `warrior`, `mage`, `stealth`, `support` e `specialist`.
Usare `archetipo_tags` da -5 a +5 per differenziare la metà specifica della
Unit. Un valore positivo aumenta l'affinità, zero è neutro, un valore negativo
esclude o penalizza.

Configurazione raccomandata:

```json
{
  "kind": "humanoid",
  "coreKey": "warrior",
  "coreShare": 0.5,
  "startingXp": 0,
  "xpPerLevel": {"base": 20, "growth": 1},
  "finalSpendingPasses": 4,
  "magicPolicy": "none",
  "allowedClassFamilies": ["Ranger"],
  "allowedReligionFamilies": [],
  "allowedRaces": ["Bosmer"],
  "allowedSubraces": ["Cacciatore", "Esploratore"]
}
```

Lasciare `allowedRaces` vuoto significa consentire tutte le razze. Quando una
Unit richiede una razza precisa, dichiararla esplicitamente. Usare
`allowedSubraces` per escludere sottorazze o ranghi che contraddicono il Charter;
i valori devono appartenere ad almeno una delle razze consentite.
Non sostituire specie daedriche distinte per comodità: una Unit Xivilai usa
`allowedRaces: ["Xivilai"]`, non `Dremora` e non una razza mortale.

La progressione perk è unica e non configurabile. A ogni livello il generatore
sceglie con probabilità 50% una tappa della progressione originale di
`ai_pg_creation` e con probabilità 50% una scelta pesata coerente con la Unit.
La scelta è indipendente per ciascun livello; quando il livello concede sia un
perk minore sia uno maggiore, entrambi seguono la stessa scelta. Le tappe di
caratteristica restano ripetibili e vengono materializzate come miglioramenti
del personaggio. I nomi della tabella sono risolti nel catalogo corrente, mai
tramite ID Elder.

Il generatore mantiene un unico conto di PE generali riportati di livello in
livello, come il wizard Elder, ma acquista ogni Skill tramite il prezzo
dinamico e il servizio di sblocco ReDjango. Dopo l'ultimo livello esegue
`finalSpendingPasses` tentativi aggiuntivi. I PE restano soltanto se nessuna
Skill configurata è acquistabile; il motivo deve comparire nel report.

Core e archetipo sono sempre whitelist curate nella `skill_unlocks` della
singola Unit. Il generatore non cerca riempitivi nel catalogo e non amplia
automaticamente le liste in base ai tag. Questo impedisce che l'aggiunta futura
di una Skill o la modifica dei suoi tag alteri una Unit già pubblicata. L'unica
aggiunta automatica ammessa è un prerequisito reale di una Skill curata:
l'autore deve comunque controllare che l'intera catena sia coerente col ruolo.

## 4. Creare pool Skill con varietà controllata

Non usare una lista lineare obbligatoria per ogni livello. Inserire più scelte
coerenti con fasce sovrapposte e pesi diversi:

```json
[
  {
    "skillId": 123,
    "pool": "core",
    "weight": 8,
    "minLevel": 1,
    "maxLevel": 10,
    "requiredAtLevel": 3
  },
  {
    "skillId": 456,
    "pool": "archetype",
    "weight": 5,
    "minLevel": 2,
    "maxLevel": 12
  }
]
```

Regole:

- verificare che gli ID esistano e che le Skill non siano archiviate;
- separare semanticamente i pool: il `core` contiene soprattutto passivi,
  PF/energia, mobilità, difese e bonus generali riutilizzabili; `archetype`
  contiene gli attacchi, le stance e le capacità che definiscono il ruolo;
- non usare una famiglia di armi o una tecnica d'attacco come riempitivo Core.
  Per un arciere, `Carica`, `Finta`, `Doppio attacco` e simili sono errati
  anche se hanno un punteggio `core_fisico` alto;
- prima di inserire una Skill Core controllare `azioni_attive`,
  `effetti_passivi`, famiglia, descrizione e prerequisiti. Per un Core fisico
  privilegiare catene come PF, energia, difesa, movimento e inventario;
- per l'archetipo arciere usare soltanto attacchi a distanza, difese/mobilità
  coerenti e la Classe Ranger autorizzata;
- inserire i prerequisiti oppure lasciare che il generatore li espanda;
- usare `requiredAtLevel` solo per una capacità identitaria indispensabile;
- offrire almeno tre alternative acquistabili nelle fasce 1-5, 6-10,
  11-15 e 16-20;
- sovrapporre alcune fasce per evitare che tutte le copie dello stesso livello
  abbiano la medesima build;
- rispettare `magicPolicy`, massimo due famiglie Classe e una Religione;
- non inserire perk nei pool normali;
- per perk personalizzati usare `perkTier: "minor"` o `"major"`; la
  progressione unica li considera automaticamente nella sua scelta pesata.

La varietà non deve distruggere il ruolo: almeno metà dei candidati deve
rafforzare direttamente l'identità descritta.

## 5. Configurare Competenze

`profilo_competenze` usa le chiavi canoniche e valori da -5 a +5. Impostare
almeno tre priorità positive, alcune neutrali e le incompatibilità reali come
negative. I PE sono spesi con il costo triangolare. Non scrivere direttamente
`barra1` e `barra2` salvo migrazione fedele di uno stato fisso.

Esempio:

```json
{
  "percezione": 4,
  "furtivita": 3,
  "sopravvivenza": 2,
  "strategia_militare": 1,
  "sapienza_magica": -5
}
```

## 6. Equipaggiamento per fascia, percorso materiale e variante

Ogni oggetto deve essere esplicito. Non esiste fallback al catalogo globale.
Per uno slot fisso offrire alternative sovrapposte:

```json
{
  "slots": {
    "arma": [
      {"itemId": 10, "minLevel": 1, "maxLevel": 8, "weight": 4, "chance": 1},
      {"itemId": 11, "minLevel": 4, "maxLevel": 13, "weight": 2, "chance": 0.9}
    ]
  }
}
```

`chance` va da 0 a 1 e rende l'opzione facoltativa. Per armatura e arma
identitarie usare normalmente `1`; per mantelli, scudi secondari o oggetti
situazionali usare valori inferiori.

### Percorsi canonici dei materiali

Armi e armature hanno due percorsi indipendenti. Non alternare leggero e
pesante soltanto perché il numero di tier cresce.

| Tier | Leggero | Pesante | Livello loot |
|---:|---|---|---|
| 1 | legno per armi, pelle per armature | ferro | 1-2 |
| 2 | chitina | acciaio | 2-3 |
| 3 | elfico | nordico | 3-4 |
| 4 | ossa | orchesco | 4-5-6 |
| 5 | dreugh | dwemer | 6-7 |
| 6 | vetro | ebano | 8-9 |
| 7 | adamantio | daedrico | 10 |

`lv_loot` descrive il tier del catalogo e non va copiato direttamente nel
livello del personaggio. La Unit deve dichiarare il proprio ritmo narrativo,
il percorso preferito e un tier massimo. Per un arciere bandito il tetto è
tier 4 e la progressione raccomandata è:

- livelli 1-3: tier 1-2 leggeri con alternative pesanti comuni;
- livelli 4-6: tier 2-3, ancora sia leggeri sia pesanti;
- livelli 7-8: soltanto elfico, tier 3 leggero;
- livelli 9-11: elfico e ossa sovrapposti, con ossa che entra intorno al 10;
- livelli 12-20: soltanto ossa, tier 4 leggero.

Applicare lo stesso percorso all'arma: arco corto di legno/chitina/elfico/ossa
come linea leggera, con ferro/acciaio/nordico/orchesco ammessi soltanto fino
al livello 6. Prima di consegnare, costruire una matrice livello × oggetti e
verificare che nessuna fascia vuota o materiale fuori percorso sia possibile.

Gli accessori usano gruppi con quantità variabile:

```json
{
  "name": "Anelli del predone",
  "slots": ["anello_1", "anello_2", "anello_3", "anello_4"],
  "minCount": 1,
  "maxCount": 3,
  "emptyChance": 0,
  "items": [
    {"itemId": 40, "minLevel": 1, "maxLevel": 7, "weight": 3, "chance": 1},
    {"itemId": 41, "minLevel": 5, "maxLevel": 12, "weight": 2, "chance": 1}
  ]
}
```

Creare gruppi separati per tipi incompatibili: anelli negli slot anello,
orecchini negli slot orecchino, amuleti in amuleto e così via. Aumentare
gradualmente `maxCount` e qualità, non assegnare automaticamente tutti gli
slot disponibili. In ogni fascia offrire almeno due effetti o materiali
alternativi e non superare il tetto narrativo dell'archetipo.

Per riprodurre `pg_da_archetipo.py`, configurare anche un totale globale
variabile. Il generatore soddisfa prima i `minCount` dei gruppi e poi riempie
casualmente gli altri slot fino al totale scelto:

```json
{
  "accessoryCountByLevel": [
    {"minLevel": 1, "maxLevel": 1, "minCount": 2, "maxCount": 4},
    {"minLevel": 4, "maxLevel": 5, "minCount": 5, "maxCount": 7},
    {"minLevel": 10, "maxLevel": 12, "minCount": 8, "maxCount": 10},
    {"minLevel": 16, "maxLevel": 20, "minCount": 10, "maxCount": 10}
  ]
}
```

Per un umanoide equipaggiato non lasciare anelli e orecchini entrambi
facoltativi: usare almeno `minCount: 1` per ciascuno. I pool devono includere
molti effetti coerenti, non solo PF e attacco. L'arciere Elder privilegia
PF, attacco, velocità, agilità e concentrazione e mescola difesa, energia,
resistenza, rigenerazione, fortuna, reroll e utilità esplorativa. La qualità
degli accessori deve avere fasce sovrapposte e crescere col livello.
Quando `accessoryCountByLevel` è presente, le fasce devono coprire una sola
volta tutti i livelli 1-20; ogni totale minimo deve essere almeno la somma dei
`minCount` dei gruppi e ogni massimo non può superarne la capacità complessiva.

## 7. Seed e riproducibilità

La Variante `auto` o vuota produce un seed nuovo a ogni importazione. È la
scelta normale per avversari diversi. Una Variante nominata, per esempio
`sentinella-nord`, produce sempre le stesse Skill, Competenze, caratteristiche
e oggetti per quella Unit. Usare varianti nominate nelle anteprime, nei test,
per squadre uniformi e per riprodurre un bug.

Non salvare nel blueprint un seed casuale generato durante l'authoring. Il
seed appartiene al personaggio generato e viene registrato in
`metadata.unitGeneration`.

## 8. Creature non umanoidi

Una Creatura usa:

```json
{
  "generation_rules": {"kind": "creature"},
  "stat_profiles": {
    "curves": [
      {"key": "pf", "profile": "high", "level1": 25, "level20": 150},
      {"key": "pa", "profile": "medium", "level1": 7, "level20": 25}
    ]
  },
  "skill_actions": [
    {
      "key": "morso",
      "name": "Morso",
      "description": "Attacco naturale.",
      "minLevel": 1,
      "maxLevel": 20,
      "costs": {"pa": 3}
    }
  ]
}
```

Gli estremi delle curve sono esatti. Le azioni innate non spendono PE e non
creano `SkillPersonaggio`.

## 9. Verifica obbligatoria

Prima di consegnare una Unit:

1. salvare attraverso il servizio di Gestione Unit, non direttamente con ORM;
2. generare anteprime ai livelli 1, 5, 10, 15 e 20;
3. provare almeno otto Varianti automatiche allo stesso livello;
4. controllare PE guadagnati, spesi e residui;
5. controllare perk e miglioramenti per livello;
6. verificare che prerequisiti e passivi siano presenti;
7. confrontare numero, slot, tipo e livello degli accessori;
8. confermare che nessun oggetto fuori pool sia stato usato;
9. verificare la matrice dei materiali ai livelli 1, 3, 5, 6, 7, 9, 10,
   11 e 12 e il tetto di tier dell'archetipo;
10. classificare tutte le Skill ottenute: nessuna tecnica melee può comparire
    in un arciere salvo scelta esplicita documentata;
11. provare due volte una Variante nominata e confrontare le firme;
12. correggere il blueprint, mai il singolo personaggio generato.

Una Unit è pronta quando conserva l'identità in tutte le varianti, mostra
differenze reali fra copie automatiche e resta riproducibile con una Variante
nominata.
