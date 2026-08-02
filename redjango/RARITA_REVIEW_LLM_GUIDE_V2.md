# Guida LLM V2 — Revisione semantica della rarità degli oggetti 2, 3 e 4

## Mandato

Agisci come il Master che conosce l'intero sistema di ReDjango, il catalogo
completo e il ruolo pratico di ogni oggetto durante il gioco. Non comportarti
come un classificatore statistico e non applicare una formula universale. Per
ogni oggetto devi formulare lo stesso giudizio editoriale che formulerebbe il
Master sapendo che cosa fa l'oggetto, quanto è ordinario nel mondo, quali
alternative esistono e quale effetto avrebbe la sua presenza frequente nei
negozi.

La revisione riguarda tutti gli `Oggetto` con `rarita__in=[2, 3, 4]`. Il
risultato è esclusivamente una proposta: **non modificare il database**, non
rigenerare negozi e non alterare nessun campo. Un umano approverà in seguito le
modifiche tramite l'editor o una migrazione esplicita.

## Principio fondamentale

`rarita` misura la reperibilità desiderata sul mercato, non il livello di loot,
il valore, la quantità di bonus o la potenza considerati isolatamente.

Il livello risponde a «quando questo oggetto è appropriato?». La rarità risponde
a «quanto spesso un personaggio appropriato dovrebbe riuscire a comprarlo o
trovarlo?». Sono assi indipendenti.

Esempi vincolanti:

- Una pozione di cura di livello alto può restare comune o non comune: è una
  versione più potente di una risorsa ordinaria, destinata a personaggi di
  livello alto.
- Una pozione di invisibilità dello stesso livello può essere rara: offre
  accesso a infiltrazione, fuga e aggiramento degli incontri, quindi una sua
  disponibilità frequente cambia il gioco.
- Un'arma normale di materiale avanzato non diventa automaticamente rara solo
  perché appartiene a un livello alto o costa molto. Può essere merce normale
  nei negozi adatti a quel livello.
- Un oggetto debole può essere raro per ragioni di identità, produzione,
  cultura o accesso; un oggetto potente può essere comune nel proprio contesto
  se costituisce l'equipaggiamento standard di quel livello.

## Scala editoriale

| Rarità | Giudizio del Master |
|---:|---|
| 0 | `Unico`: premio o oggetto singolare assegnato manualmente; non appartiene al mercato casuale. |
| 1 | Merce ordinaria per il suo contesto: un negozio pertinente e del livello giusto dovrebbe averla spesso. |
| 2 | Merce non comune: normale e acquistabile, ma non garantita in ogni assortimento pertinente. |
| 3 | Merce rara: capacità, identità o manifattura distintiva; la sua comparsa deve essere saltuaria. |
| 4 | Merce molto rara: accesso fortemente limitato per impatto, origine, valore strategico o identità. |
| 5 | Eccezionale ma ancora acquistabile: il mercato può offrirla, però come evento insolito nei negozi/loot più adatti. |

Non usare `0` o `5` come contenitori per dati incompleti. Proponi `0` solo se il
Master dovrebbe assegnare personalmente quello specifico oggetto. Proponi `5`
solo se deve restare realmente acquistabile.

## Dati obbligatori

Leggi tutte le righe in scope, senza paginazione o campionamento. Per ogni riga
leggi e conserva almeno:

`id`, `nome`, `rarita`, `modello`, `temporaneo`, `archiviato`, `archived_at`,
`speciale`, `valore`, `peso`, `tipo_1`–`tipo_4`, `tipo_arma`,
`pa_per_attacco`, `lv_loot`, `regione_loot`, `peso_regione`, `descrizione`,
`effetto_1`–`effetto_8`, `regole_speciali`, `effects`, `weapon_profile` e
`metadata`.

Leggi anche gli oggetti fuori scope, comprese rarità 0, 1 e 5, quando servono a
capire una famiglia o a trovare punti di riferimento. Non proporre modifiche
per questi comparabili, ma usali per ricostruire il linguaggio editoriale già
presente nel catalogo.

Leggi la configurazione corrente del Mercato: probabilità per rarità, tipi di
negozio, `itemTypeRanks`, livelli, regioni, peso regionale, regole di prezzo e
copie massime. Un oggetto è vendibile oggi soltanto se è un `modello`, non è
archiviato, non è `speciale`, possiede almeno un livello di loot valido e il suo
`tipo_1` ha rank inferiore a 5 in almeno un tipo di negozio abilitato. Segnala
gli oggetti non vendibili; non affermare che un cambio di rarità li renderebbe
vendibili.

## Metodo obbligatorio

### 1. Comprendi l'identità prima dei numeri

Per ogni oggetto determina in linguaggio naturale:

- che cosa è nel mondo: merce quotidiana, versione di qualità superiore,
  manufatto specializzato, oggetto culturale, oggetto magico, premio narrativo,
  artefatto, componente o placeholder;
- che cosa permette di fare al tavolo;
- se il suo effetto è ordinario per la categoria oppure introduce una capacità
  qualitativamente diversa;
- chi dovrebbe produrlo e venderlo e quanto normalmente sarebbe difficile
  trovarlo nel negozio appropriato.

Il nome, il testo descrittivo e le regole hanno priorità sulla semplice somma
dei valori numerici. Non confondere un maggior numero di righe in `effects` con
maggiore rarità: più righe possono soltanto descrivere il normale profilo di
un'arma.

### 2. Costruisci famiglie semantiche reali

Prima di giudicare i singoli record, raggruppa l'intero catalogo per funzione e
modalità d'uso. `tipo_1` è un indizio, non una classificazione sufficiente.

Esempi di famiglie corrette:

- cure istantanee, cure nel tempo, recupero di mana/energia;
- invisibilità, fuga, teletrasporto, controllo mentale o del campo;
- resistenze comuni, immunità, resurrezione, effetti permanenti;
- armi ordinarie in progressione di materiale;
- armi con proprietà tattiche speciali;
- armature ordinarie, set culturali, set magici e artefatti;
- pergamene consumabili, libri che concedono apprendimento e grimori
  riutilizzabili;
- accessori con un singolo bonus standard e accessori con combinazioni rare;
- contenitori, strumenti professionali, trappole, munizioni e oggetti di
  utilità narrativa.

Non confrontare due oggetti soltanto perché condividono `tipo_1`. Una pozione di
cura deve essere confrontata prima con altre cure; una pozione di invisibilità
con altre forme di invisibilità, fuga e aggiramento. Quando la funzione coincide
ma il tipo differisce, il confronto funzionale è più importante del confronto
di colonna.

### 3. Identifica la progressione interna

Dentro ogni famiglia separa la progressione quantitativa dalla differenza
qualitativa.

- Un aumento di cura, danno, difesa o capacità che accompagna il livello è di
  norma una progressione quantitativa. Non richiede automaticamente una rarità
  maggiore.
- Una nuova capacità — invisibilità, resurrezione, immunità, azioni aggiuntive,
  controllo, teletrasporto, effetti permanenti o aggiramento di un costo
  centrale — è una differenza qualitativa e può giustificare maggiore rarità.
- Una durata più lunga o un uso ripetibile possono trasformare un effetto
  ordinario in uno strategico. Valutali semanticamente, non contando cifre o
  campi.
- Le varianti `+1/+2`, i materiali e i livelli devono formare una progressione
  coerente. Una discontinuità è ammessa soltanto quando cambia davvero la
  funzione o la disponibilità nel mondo.

### 4. Formula il giudizio di disponibilità

Chiediti, come Master:

1. Se questo oggetto apparisse spesso, renderebbe banale una sfida, una
   specializzazione o una scelta di risorse?
2. È merce standard per un venditore competente e del livello appropriato?
3. Richiede conoscenze, componenti, cultura o istituzioni difficili da trovare?
4. La sua reperibilità frequente è coerente con gli altri oggetti che offrono la
   stessa capacità?
5. Ha identità narrativa individuale oppure appartiene a una classe ripetibile
   di prodotti?

Usa il livello di loot per stabilire il contesto nel quale porre queste domande,
non come tabella di conversione verso la rarità.

### 5. Considera il mercato effettivo

La rarità agisce insieme alla pressione commerciale:

- un `tipo_1` con rank basso in molti negozi ha già molta esposizione;
- un tipo presente soltanto in negozi specialistici ha una limitazione
  naturale e può non aver bisogno di una rarità estrema;
- una corrispondenza regionale e un `peso_regione` alto rendono l'oggetto più
  frequente nella sua regione;
- il livello restringe i negozi appropriati, ma questa restrizione non equivale
  a rarità;
- prezzo e copie massime modificano costo e quantità, ma non sostituiscono il
  giudizio sulla reperibilità.

Quando proponi una rarità, immagina il risultato combinato di tutti questi
fattori. Evita di «correggere due volte» un oggetto già limitato dal tipo di
negozio, dalla regione o da un range di livello stretto.

### 6. Usa valore, potenza e statistiche come prove, non come formula

Valore, peso, danno, PA, durata, capacità ed effetti devono essere letti
insieme. Non usare soglie universali, somme di effetti, medie automatiche o una
conversione `lv_loot → rarita`.

Il prezzo è una prova utile quando differenzia oggetti semanticamente simili;
non può da solo trasformare una normale versione di alto livello in un oggetto
raro. Analogamente, cinque effetti tecnici non valgono necessariamente più di
un singolo effetto di invisibilità: conta ciò che quelle regole fanno durante il
gioco.

### 7. Confronta e poi decidi ogni record

Per ogni proposta cita almeno due comparabili reali quando esistono. I
comparabili devono essere scelti in quest'ordine:

1. stessa funzione, stessa modalità d'uso e fascia di livello simile;
2. stessa funzione in un'altra categoria;
3. stessa famiglia in una fascia di livello adiacente;
4. stesso `tipo_1` soltanto se ha anche un ruolo di gioco simile.

Spiega la differenza semantica: non limitarti a elencare ID o a dire «valore
simile». Una ragione valida è, per esempio, «come le cure ID 10 e 12 aumenta
soltanto la quantità ripristinata; a differenza dell'invisibilità ID 20 non
introduce un mezzo di fuga». Una ragione non valida è «livello 8, quindi rarità
4».

Ogni record deve ricevere una decisione consapevole, anche quando appartiene a
una grande progressione. È consentito applicare la stessa decisione a una
famiglia solo dopo averne compreso la funzione e verificato che nessun membro
introduca una differenza qualitativa.

## Indicazioni per categoria

### Consumabili e pozioni

Valuta l'effetto primario, la durata, l'immediatezza, la possibilità di
accumulo e il modo in cui altera una scena. Cura, mana ed energia sono
normalmente risorse di routine; le versioni più forti possono rimanere comuni o
non comuni al proprio livello. Invisibilità, resurrezione, immunità, controllo,
teletrasporto e capacità equivalenti richiedono maggiore cautela perché aprono
soluzioni altrimenti non disponibili. Non rendere rara una pozione soltanto
perché il numero curato è alto.

### Armi, armature e munizioni

Distingui qualità/materiale standard, forma d'arma specializzata, proprietà
magica e identità narrativa. Un materiale avanzato può essere normale nei
negozi di alto livello. Una forma esotica può essere meno reperibile senza
essere più potente. Proprietà che cambiano economia delle azioni, penetrazione,
controllo, danno eccezionale o possibilità tattiche possono giustificare rarità
superiore. I set culturali non sono automaticamente unici: valuta se sono
prodotti ripetibili della fazione oppure esemplari individuali.

### Accessori e abbigliamento

Considera lo slot occupato, la cumulabilità e la disponibilità di alternative.
Un singolo bonus quantitativo in progressione può essere merce standard; una
combinazione di bonus normalmente separati, una capacità qualitativa o un
effetto cumulabile con forte impatto può essere rara. Non usare il numero di
effetti strutturati come scorciatoia.

### Pergamene, libri, grimori e oggetti magici

Distingui uso singolo, apprendimento permanente e uso ripetibile. Valuta anche
la rarità della capacità concessa: una pergamena consumabile di un effetto
comune può essere ordinaria, mentre apprendere permanentemente o ripetere un
effetto strategico richiede maggiore limitazione.

### Strumenti, contenitori, gemme e oggetti vari

Valuta quanto l'oggetto rimuove limiti centrali come capacità, slot, peso,
accesso professionale o costo di una procedura. Un normale strumento migliore
non è automaticamente raro; un oggetto che elimina stabilmente una limitazione
può esserlo. Le pietre preziose possono essere costose senza essere
meccanicamente rare: considera commercio, origine e uso, non soltanto valore.

## Ambiguità e revisione umana

Se descrizione, effetto o regola non permettono di capire con affidabilità che
cosa accade al tavolo:

- imposta `needsHumanReview=true`;
- conserva la rarità attuale, salvo una prova semantica forte e indipendente;
- descrivi esattamente quale informazione manca o quale interpretazione è
  incerta;
- non inventare regole;
- non usare l'ambiguità per proporre automaticamente `0` o `5`.

Un oggetto non vendibile deve essere segnalato, ma non deve essere marcato per
revisione umana soltanto perché è fuori mercato se la sua identità e rarità sono
comunque comprensibili. `marketEligible` e `needsHumanReview` descrivono due
problemi diversi.

## Automazione consentita e vietata

È consentito usare codice per estrarre tutte le righe, normalizzare testo,
individuare duplicati, costruire famiglie candidate, calcolare la reale
eleggibilità di mercato, trovare possibili comparabili e verificare completezza
e ordinamento.

È vietato lasciare che il codice assegni la rarità tramite punteggi, soglie,
numero di effetti, livello medio, prezzo relativo o altre euristiche. Il codice
può preparare le prove; la decisione deve essere semantica e formulata
esplicitamente dal modello per ogni famiglia e per ogni eccezione.

Non presentare come «revisione del Master» un report generato soltanto da regole
automatiche.

## Controlli finali obbligatori

Prima della consegna verifica che:

- ogni ID con rarità corrente 2, 3 o 4 compaia una sola volta;
- gli ID siano ordinati e nessuna riga sia stata campionata o omessa;
- ogni comparabile esista e sia semanticamente pertinente;
- progressioni quantitative equivalenti abbiano disponibilità coerente;
- differenze qualitative siano motivate esplicitamente;
- nessuna proposta derivi direttamente dal solo livello, prezzo o conteggio
  degli effetti;
- `0` identifichi soltanto assegnazioni manuali e `5` soltanto oggetti ancora
  acquistabili;
- `marketEligible` rifletta la configurazione corrente del Mercato;
- il database e i negozi non siano stati modificati.

Esegui inoltre controlli mirati su almeno queste coppie: cura contro
invisibilità, arma standard contro arma tattica/magica, accessorio a bonus
singolo contro combinazione di bonus, consumabile contro apprendimento
permanente, oggetto regionale contro equivalente non regionale.

## Formato di consegna

Prima del JSON scrivi al massimo un paragrafo con i principali pattern
semantici osservati e le decisioni che richiedono conferma umana. Restituisci un
record per ogni oggetto in scope, ordinato per `id`, senza omettere gli
invariati.

```json
{
  "scope": {
    "currentRarities": [2, 3, 4],
    "reviewedCount": 0
  },
  "summary": {
    "proposedCounts": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    "changedCount": 0,
    "needsHumanReviewCount": 0,
    "marketIneligibleCount": 0
  },
  "proposals": [
    {
      "id": 123,
      "name": "Nome esatto",
      "currentRarity": 3,
      "proposedRarity": 2,
      "confidence": "high",
      "needsHumanReview": false,
      "marketEligible": true,
      "semanticFamily": "pozione/cura istantanea",
      "identity": "Versione quantitativamente superiore di un consumabile ordinario",
      "gameplayRole": "Ripristina salute senza introdurre una nuova capacità tattica",
      "comparables": [456, 789],
      "reasons": [
        "Rispetto alle cure 456 e 789 cambia la quantità ripristinata, non la funzione.",
        "Il livello alto limita già il contesto di comparsa; nel negozio appropriato deve restare una risorsa normale."
      ],
      "warnings": [],
      "source": {
        "id": 123,
        "nome": "Nome esatto",
        "rarita": 3
      }
    }
  ]
}
```

`source` deve contenere tutti i campi obbligatori elencati sopra, non soltanto
quelli abbreviati nell'esempio. `confidence` può essere `high`, `medium` o
`low`. Le ragioni devono dimostrare comprensione della funzione dell'oggetto e
del confronto; riferimenti puramente numerici o frasi generiche non sono
sufficienti.
