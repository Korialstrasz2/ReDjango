# Generazione rapida delle Unit

La generazione rapida usa `core.Unit` come blueprint e crea un vero
`characters.Personaggio`. Non copia più statistiche casuali e non cerca
equipaggiamento in tutto il catalogo quando un pool non produce risultati.

## Tipi di Unit

`Unit.generation_rules.kind` è obbligatorio:

- `animal`: niente `SkillPersonaggio`, `Equip`, zaino o faretra; può avere
  abilità innate biologiche;
- `creature`: come `animal`, con abilità innate anche soprannaturali;
- `humanoid`: usa Skill, PE, perk ed equipaggiamento.

Le azioni innate vivono in `Unit.skill_actions` e vengono copiate in
`Personaggio.abilita.known`. Non sono Skill e quindi possono rappresentare
Soffio elementale, Volo, Morso, Rigenerazione e altre capacità biologiche.

Esempio non umanoide:

```json
{
  "generation_rules": {
    "kind": "creature",
    "minimumLevel": 1,
    "maximumLevel": 20
  },
  "stat_profiles": {
    "curves": [
      {
        "key": "pf",
        "profile": "high",
        "level1": 25,
        "level20": 150,
        "curve": "exponential"
      },
      {
        "key": "res_fuoco",
        "profile": "custom",
        "level1": 2,
        "level20": 5,
        "curve": "hi_hi"
      }
    ]
  },
  "skill_actions": [
    {
      "key": "soffio",
      "name": "Soffio elementale",
      "description": "Cono di energia elementale.",
      "minLevel": 1,
      "costs": {"energia": 2}
    },
    {
      "key": "volo",
      "name": "Volo",
      "description": "Prende quota e ignora il terreno.",
      "minLevel": 5
    }
  ]
}
```

`animal` e `creature` rifiutano configurazioni che contengono
`skill_unlocks`, pool di equipaggiamento o progressione Competenze. Solo
gli Umanoidi usano il catalogo Skill e non accettano `skill_actions`.
Animali e Creature possono invece usare `skill_actions` come abilità innate,
senza prezzi, PE, prerequisiti o record `SkillPersonaggio`. In questo modo una configurazione errata
non può trasformare silenziosamente uno skeever in un guerriero o assegnare
un Soffio a un umanoide.

## Progressione degli umanoidi

Un umanoide ripercorre tutti i livelli da 1 al livello richiesto. Per ogni
livello il generatore:

1. accredita i PE del livello;
2. sceglie fra Core e archetipo secondo la quota configurata, usando un unico
   conto di PE generali riportato fra i livelli;
3. rispetta prezzo dinamico, prerequisiti e requisiti strutturati delle Skill;
4. sceglie indipendentemente a ogni livello, con probabilità 50/50, fra la
   tappa perk originale e una scelta pesata coerente con la Unit;
5. materializza separatamente ogni miglioramento di caratteristica ripetibile;
6. materializza gli effetti passivi e ricalcola il personaggio.

Di default il livello 1 parte da 0 PE. Dal livello 2 la formula è
`20 + livello - 1`, la stessa progressione già usata dalla creazione
assistita. La ripartizione predefinita è 50% Core e 50% archetipo e guida la
selezione, non divide artificialmente la valuta. Dopo l'ultimo livello il
generatore esegue passaggi finali configurabili; conserva PE soltanto quando
nessuna Skill valida e configurata è acquistabile.

```json
{
  "kind": "humanoid",
  "coreKey": "warrior",
  "coreShare": 0.5,
  "minimumLevel": 1,
  "maximumLevel": 20,
  "xpPerLevel": {"base": 20, "growth": 1},
  "startingXp": 0,
  "finalSpendingPasses": 4
}
```

La progressione perk non espone modalità selezionabili. Per ogni livello viene
effettuata una sola scelta casuale: al 50% usa la tappa di `ai_pg_creation`,
risolta per nome senza conservare ID Elder, e al 50% usa i perk compatibili
pesati. Se il livello concede sia un perk minore sia uno maggiore, la scelta
vale per entrambi. I miglioramenti di caratteristica previsti dalle tappe sono
ripetibili e diventano effetti permanenti del personaggio.

I cinque Core predefiniti sono `warrior`, `mage`, `stealth`, `support` e
`specialist`. Ogni Unit umanoide deve avere una whitelist esplicita per
entrambi gli insiemi: il Core raccoglie soprattutto passivi, PF/energia,
mobilità, difese e utilità generali, mentre gli attacchi caratterizzanti
appartengono all'archetipo. Non esiste ampliamento automatico dal catalogo:
solo le Skill curate e i loro prerequisiti reali possono essere acquistati.
Questo impedisce, per esempio, che un arciere riceva tecniche melee soltanto
per un alto `core_fisico`.

`allowedRaces` limita le razze primarie ammesse. `allowedSubraces` può
restringere ulteriormente le sottorazze appartenenti alla razza estratta; se è
vuoto, il generatore usa l'intero catalogo della razza. Per esempio, il
`Soldato Dremora` ammette soltanto `Churl`, `Caitiff` e `Kynval`, evitando che
una Unit di fanteria venga generata come ufficiale o principe Dremora.
Una Unit umanoide non morta può usare `allowedRaces: ["Non morto"]` e limitare
la sottorazza al suo modello reale, per esempio `Scheletro` o `Draugr`. Le
Creature senza equipaggiamento e senza Skill restano invece nel contratto
`creature`, anche quando sono non morte.
Gli Xivilai usano `allowedRaces: ["Xivilai"]`: sono Daedra umanoidi distinti
dai Dremora e non possiedono ranghi-sottorazza.

Un Core di campagna può essere definito direttamente sulla Unit senza cambiare
il database:

```json
{
  "kind": "humanoid",
  "coreKey": "monk",
  "coreProfile": {
    "core_fisico": 3,
    "controllo_situazionale": 3,
    "natura_magica": 1
  }
}
```

Una singola Skill può anche dichiarare appartenenze Core esplicite dentro i
tag profilo:

```json
{
  "generation": {
    "cores": {"warrior": 8, "stealth": 3},
    "minLevel": 2,
    "maxLevel": 20,
    "weight": 4
  }
}
```

## Metà personalizzata dell'archetipo

La metà archetipo può essere calcolata dal vettore numerico
`Unit.archetipo_tags` oppure definita con una whitelist in
`Unit.skill_unlocks`. Se esiste almeno una Skill normale esplicita, la
whitelist vince: non viene allargata automaticamente.

```json
[
  {
    "skillId": 123,
    "weight": 8,
    "minLevel": 1,
    "maxLevel": 20,
    "requiredAtLevel": 2
  },
  {
    "skillId": 456,
    "weight": 3,
    "minLevel": 5
  }
]
```

I prerequisiti delle Skill in pool vengono aggiunti al percorso quando sono
Skill normali. I perk restano una quota separata. Per restringere i perk di
un archetipo si possono aggiungere entry con `perkTier: "minor"` o
`perkTier: "major"`; altrimenti il generatore usa le famiglie canoniche
`Perk Minori` e `Perk Maggiori`, pesandole con Core più profilo archetipo.

## Statistiche

Per Animali e Creature, `stat_profiles.curves` assegna a ogni variabile un
valore finale esatto al livello 1 e al livello 20. Il livello intermedio è
calcolato con una curva scelta per quella specifica variabile:
`linear`, `quadratic`, `exponential`, `logarithmic` oppure `hi_hi` (raggiunge
il massimo al livello 15). Gli estremi restano sempre esatti.

L'editor offre i profili `very_low`, `low`, `medium`, `high` e `very_high`
come valori iniziali riutilizzabili, più `custom`. Per esempio i profili PF
propongono rispettivamente `10→50`, `14→75`, `18→100`, `25→150` e
`35→225`. Cambiare manualmente uno dei due estremi converte la riga in
`custom`.

Esempio:

```json
{
  "curves": [
    {
      "key": "pf",
      "profile": "low",
      "level1": 14,
      "level20": 75,
      "curve": "exponential"
    },
    {
      "key": "pa",
      "profile": "high",
      "level1": 9,
      "level20": 32,
      "curve": "linear"
    }
  ]
}
```

`baseModifiers`, `perLevelModifiers`, `milestones` e le fasce
`Unit.levels` restano leggibili per compatibilità con le Unit già migrate.
Negli umanoidi la crescita arriva da Skill, perk, equipaggiamento e formule
che leggono il livello; qualsiasi crescita diretta, comprese le curve, richiede
`generation_rules.allowHumanoidStatGrowth: true`.

## Equipaggiamento

Gli umanoidi usano solo `Unit.equipment_profiles`. Ogni entry indica un
oggetto preciso, una fascia di livello e un peso. Non esiste fallback verso
oggetti fuori pool.

```json
{
  "slots": {
    "armatura": [
      {"itemId": 10, "minLevel": 1, "maxLevel": 5, "weight": 5},
      {"itemId": 11, "minLevel": 6, "maxLevel": 12, "weight": 5},
      {"itemId": 12, "minLevel": 13, "maxLevel": 20, "weight": 3}
    ],
    "arma": [
      {"itemId": 30, "minLevel": 1, "maxLevel": 20, "weight": 4},
      {"itemId": 31, "minLevel": 8, "maxLevel": 20, "weight": 2}
    ]
  },
  "groups": [
    {
      "slots": ["orecchino_1", "orecchino_2"],
      "minCount": 1,
      "maxCount": 3,
      "emptyChance": 0,
      "items": [
        {"itemId": 40, "minLevel": 1, "maxLevel": 20, "weight": 3, "chance": 1},
        {"itemId": 41, "minLevel": 1, "maxLevel": 20, "weight": 1, "chance": 0.8}
      ]
    }
  ],
  "accessoryCountByLevel": [
    {"minLevel": 1, "maxLevel": 1, "minCount": 2, "maxCount": 4},
    {"minLevel": 4, "maxLevel": 5, "minCount": 5, "maxCount": 7},
    {"minLevel": 10, "maxLevel": 12, "minCount": 8, "maxCount": 10}
  ]
}
```

I gruppi permettono più varietà controllata per orecchini, anelli e accessori:
variano quantità, slot e possibilità di restare vuoti. La curva globale
sceglie il totale per livello dopo aver garantito i `minCount` dei gruppi;
`chance` rende facoltativa una singola opzione.

Armi e armature non usano una gerarchia unica. Il percorso leggero è
legno/pelle → chitina → elfico → ossa → dreugh → vetro → adamantio; quello
pesante è ferro → acciaio → nordico → orchesco → dwemer → ebano → daedrico.
Ogni Unit deve dichiarare percorso preferito, periodo di possibile
sovrapposizione e tier massimo. L'Arciere Bandito ammette entrambi i percorsi
soltanto ai livelli 1-6, usa esclusivamente il leggero dal 7, sovrappone elfico
e ossa ai livelli 9-11 e dal 12 usa soltanto ossa. I dettagli operativi e la
tabella dei tier sono in `Builder_docs/UNIT_AUTHORING_GUIDE_FOR_LLM.md`.

## Ripetibilità e diagnosi

La schermata Combattimento espone la tab `Unità rapide`, un selettore di
livello su ogni Unit e una chiave Variante. `auto` o il valore vuoto genera
una variante nuova a ogni importazione. La stessa Unit con la stessa Variante
nominata produce la stessa scelta pesata di Skill, perk, miglioramenti,
armatura e accessori.

Ogni personaggio generato conserva in `Personaggio.metadata.unitGeneration`
il seed, i PE allocati e residui, la Skill comprata a ogni livello, i perk,
i miglioramenti ripetibili, l'equipaggiamento e gli eventuali avvisi. Questo rende una build ricostruibile
e permette di correggere il pool invece di ritoccare a mano il risultato.

## Gestione e Unit Elder pronte

`/tools/units` è la postazione master/admin per cercare, creare, modificare,
archiviare e provare le Unit. L'editor separa Profilo, Progressione,
Equipaggiamento e Anteprima; i selettori interrogano i cataloghi Skill e
Oggetti correnti. L'anteprima invoca il generatore di Combattimento dentro una
transazione annullata, quindi mostra il risultato reale senza lasciare
personaggi, zaini o equipaggiamenti temporanei nel database.

Il seed crea due blueprint quando il catalogo Elder importato è disponibile:

- `Arciere Bandito`, ricostruito dalle Unit Elder 951 e 952, umanoide
  Guerriero/Ranger con metà PE Core, metà archetipo, Competenze pesate,
  progressione perk completa e fasce di equipaggiamento da pelle/ferro a
  elfico senza accesso all'adamantio;
- `Lupo`, ricostruito dalla Unit Elder 986, Animale privo di Skill,
  equipaggiamento e Competenze, con curve fisiche deterministiche e le
  abilità innate Elder `Balzo Predatorio` e `Furia`.

Quando un master o amministratore usa `Prendi il controllo`, il personaggio
generato viene associato al suo elenco, diventa immediatamente il personaggio
attivo sia per la mappa sia per la sessione e può essere aperto nella scheda
completa per modificare equipaggiamento e altri dati.

Per creare nuovi blueprint seguire
`Builder_docs/UNIT_AUTHORING_GUIDE_FOR_LLM.md`, che contiene schema, esempi,
criteri di varietà e checklist di verifica per LLM.

Il seed conserva gli ID sorgente in `Unit.metadata` e aggiorna soltanto record
ancora posseduti dal seed quando cambia `seed_version`; le modifiche autoriali
non vengono sovrascritte a ogni avvio.
