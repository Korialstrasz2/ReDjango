# ReDjango

Ricostruzione moderna, veloce e a pagina singola di **The Elder Django**. Django 5.2 è la fonte autorevole per dati e regole; React 19, TypeScript, Vite, TanStack Query e dnd-kit compongono l'interfaccia desktop.

## Funzioni disponibili

- SPA italiana con routing reale per dashboard, personaggi, scheda, Combattimento, immagini, guide e impostazioni.
- Scheda personaggio desktop con risorse modificabili e salvataggio esplicito, statistiche, combattimento, resistenze, ingombro ed effetti.
- Gestione effetti direttamente nella scheda: barra laterale con icone e nomi al passaggio, glow rosso pulsante per i temporanei `(t)`, area espansa con ricerca e ordinamento, e configuratore per nome, origine, descrizione, icona ricercabile e modifiche multiple. Il campo modificato usa autocomplete validato; formule, condizioni e operazioni hanno guide integrate con esempi e valori accettati. `Imposta` precede le correzioni rapide, mentre `Imposta forte` blocca il valore terminale anche dopo stanchezza e modificatore generale.
- Equipaggiamento completo, zaino con spazi normali e magici, faretre a capacità variabile e peso calcolato dal backend. La scheda include inoltre **Alchimia&Contenitori**, un contenitore personale senza peso da 15 spazi per reagenti, pozioni, pergamene e altre pile con quantità, e **Risorse gruppo**, un contenitore senza peso collegato alla campagna e condiviso tra i suoi personaggi.
- Le monete trasportate si salvano automaticamente dalla testata dell'equipaggiamento e occupano uno spazio protetto ogni `monete_per_slot` unità. L'interfaccia anticipa gli overflow, propone il massimo trasportabile e può trasferire esplicitamente l'eccedenza nella tesoreria della campagna; le **Monete condivise** restano una carta virtuale sempre presente in Risorse gruppo e non occupano spazi.
- Trascinamento e alternativa a clic per spostare o scambiare oggetti. Uno scambio avviene solo se entrambi gli oggetti sono compatibili con la destinazione; in caso contrario i dati non cambiano e viene mostrato un messaggio utile.
- Slot extra equipaggiati che accettano qualsiasi oggetto. Le faretre accettano soltanto munizioni e non possono essere rimosse se lascerebbero contenuti fuori capacità.
- Ricerca con completamento automatico dei nomi e inserimento diretto nello slot selezionato tramite **Equip**; **Svuota** rimuove il contenuto. Se uno slot occupato viene sostituito, il vecchio oggetto passa al primo spazio libero dello zaino, prima sbloccato e poi bloccato, con avviso esplicito se lo zaino è completamente pieno e l'oggetto viene perso.
- Modale completa per creare, modificare e archiviare oggetti, disponibile a master e amministratori e protetta anche dal backend.
- Temi Django modificabili, compresi colori delle quattro risorse, feedback degli slot e sfondo della scheda.
- Archivio immagini, guide strutturate e impostazioni gerarchiche `user < master < admin`. La pagina Impostazioni include un profilo Giocatore dedicato per alias, richieste di assegnazione dei personaggi e codici di promozione a Game Master/Game Admin; richieste e codici restano sotto il controllo dell'Amministrazione Django.
- Archivio immagini organizzato con categorie configurabili soltanto dall'Amministrazione Django e gruppi liberi, filtri per la navigazione e selettore visuale a miniature riutilizzato negli editor degli oggetti.
- Assistente AI con gestione protetta per Master/Amministratori, cataloghi modelli letti dai provider, controlli coerenti con le capacità del modello e indicatori di configurazione pronta. Chat e immagini lavorano in background con avanzamento, annullamento e limiti di tempo/token/strumenti; ogni utente conserva soltanto le ultime tre conversazioni.
- **Master AI** per Master e Amministratori: agenti in modalità Proposte possono cercare record e preparare una coda persistita per Item, Skill, Spell e, solo per Admin, Theme. Il modello non applica mai le modifiche: `/tools/master-ai` mostra campi, scelte server, diff, errori e avvisi; soltanto l'utente può convalidare, applicare atomicamente o scartare.
- Area **Gestione** per master e amministratori: editor organizzato di personaggi e record collegati con ricerca degli orfani e anteprima sicura dell'eliminazione; catalogo oggetti completo con filtri e confronto/copia affiancato; postazione **Gestione Skill** con panoramica, catalogo completo, gruppi e famiglie modificabili e coda persistente per correggere/importare le skill Elder escluse; postazione **Gestione Unit** per autore, validare e provare Animali, Creature e Umanoidi usati dalla generazione rapida in Combattimento; postazione amministrativa **Gestione Variabili** con controlli tipizzati, guide contestuali e convalida server-side obbligatoria prima del salvataggio del profilo globale. Il relativo **Tool Danno** modifica la matrice completa d20 × differenza Attacco/Difesa, le formule dei Tier e le percentuali di resistenza realmente lette dal motore di combattimento.
- **Gestione Negozi** è una postazione separata dal Mercato operativo: organizza e rinomina regioni, località e tipi senza cambiare le chiavi stabili, modifica ordine, icone, sfondi e assortimenti, e configura profili riutilizzabili per quantità, rarità e prezzi. Un profilo è predefinito per il mondo e può essere sostituito per ogni negozio; master e amministratori possono assegnarlo, mentre la definizione globale dei preset e delle regole del generatore resta amministrativa.
- Generazione Unit variabile e riproducibile senza LLM: gli Umanoidi ripercorrono PE, prerequisiti, Skill, la tabella perk dell'AI Elder e pool equipaggiamento per fascia; sette profili accessori condivisi riprendono i pool pesati, le eccezioni ai duplicati, la curva quantità e la variazione di livello oggetto di Elder senza copiare liste di oggetti in ogni Unit. `auto` crea una build diversa a ogni importazione, mentre una Variante nominata resta deterministica. Animali e Creature non hanno Skill a PE né equipaggiamento e usano curve configurabili con valori finali al livello 1/20 e abilità innate. Combattimento offre un selettore di livello per ogni Unit e master/admin possono prendere il controllo del risultato e aprirne la scheda completa. Il seed include l'Umanoide **Arciere Bandito** e l'Animale **Lupo**, ricostruiti dalle Unit Elder e pronti dal livello 1 al 20.
- Catalogo oggetti predisposto per l'importazione Elder: quattro tipi a scelta configurabili dall'Amministrazione Django, rarità `Unico/1-5` e otto testi effetto conservati separatamente dagli effetti strutturati eseguibili.
- Importatore oggetti Elder verificabile: `Vuoto` diventa blank, i bonus numerici sicuri vengono convertiti in effetti strutturati, le regole descrittive restano leggibili e marcano l'oggetto `Speciale`; la sostituzione atomica rimappa anche gli oggetti già assegnati. Gestione Oggetti supporta cataloghi completi, filtro Speciale, confronto/copia e clonazione esplicita.
- Pulsanti globali **Diario** e **Dadi**: il Diario è una superficie di scrittura più sottile e simile a un libro, con sezioni di testo libero e salvataggio automatico. Le note contestuali si aprono dal segnalibro in fondo alla barra laterale al passaggio del mouse o con il focus, e un clic le fissa: Zaino è collegato alla scheda, Combattimento alla relativa pagina e Competenze al suo atlante. Tutte e tre le sezioni sono anche nel Diario. Diario e Dadi si aprono al centro e possono essere spostati e ridimensionati. I dadi offrono tiri singoli animati, forme specifiche per d4–d100, modificatori del personaggio, formula completa del risultato e cronologia di sessione. Master e amministratori possono inoltre consultare, sia in Dadi sia in Competenze, gli ultimi 100 tiri persistenti del gruppo con giocatore, personaggio e orario; la scheda è controllata dall'impostazione di sessione dedicata.
- Il Diario include **Risorse speciali** subito dopo Condivise: schede dinamiche per doni, cariche, disponibilità e promemoria di campagna, con stato corrente molto visibile, ricerca, filtro per personaggio, evidenza, riordino e archivio. Master e amministratori scrivono direttamente; i giocatori inviano proposte firmate che il Master approva o rifiuta senza rischiare di sovrascrivere modifiche più recenti. I sette promemoria della campagna Sanguine provenienti da The Elder Django vengono importati soltanto se la raccolta ReDjango è ancora vuota.
- Stato di campagna sempre visibile a sinistra della barra rapida: nome della campagna, **Meteo**, **Giorno** e **Ora**. Il testo completo degli effetti del meteo resta nel suggerimento al passaggio del mouse. Solo master e amministratori vedono le frecce di giorno e ora e possono tirare di nuovo il tempo atmosferico con un doppio clic sul meteo; il tiro riprende la tabella Elder d100 con la doppia inclinazione verso `Soleggiato` e verso il prolungamento del meteo in corso. Ogni sei ore di campagna, e a ogni cambio di giorno, una finestra ricorda di tirare il tempo e permette di farlo subito.
- Scorciatoie personali configurabili nelle Impostazioni aprono tutte le destinazioni principali della SPA e gli strumenti rapidi con combinazioni `Alt + lettera`, con assegnazioni predefinite sicure, avviso immediato dei conflitti e convalida finale del backend.
- Catalogo `DiceSet` amministrabile sia dallo strumento Dadi sia dalle Impostazioni. Ogni dado può avere una texture immagine indipendente, preparata con controlli di posizione, scala e rotazione sulla stessa anteprima usata durante il tiro; numeri e bordi restano personalizzabili per la leggibilità. Creazione, modifica e archiviazione sono protette lato server come operazioni admin.
- Catalogo **Abilità** con gerarchia `gruppo di famiglie → famiglia → skill`: ogni carta contiene dettagli, requisiti, costo PE base e calcolato, profilo, effetti passivi strutturati e azioni attive promemoria. Una sezione Cerca Abilità interroga l'intero catalogo per nome o contenuto della carta e offre filtri avanzati per gruppo, famiglia, stato e variabile modificata. La pagina separa Skills, configurazione Azioni del PG e Analisi Skill PG. Lo sblocco è atomico, applica prerequisiti e sconti automatici (con bypass master/admin), richiede l'accettazione esplicita dei passivi e assegna i promemoria senza simulare l'esecuzione dell'azione. Master e amministratori usano lo stesso editor a schede della carta; `/tools/skills` offre la gestione completa di gruppi, famiglie, skill e casi Elder sospesi.
- Pagina **Competenze** dedicata e integrata nella SPA: atlante compatto delle 21 competenze legacy, due barre da 0 a 7, extra manuale permanente, bonus collegati a equipaggiamento/effetti/abilità, progressione atomica a costo triangolare e tiri server-side d6–d12. Le tecniche di Maestria spendono Energia, il grado 7 offre due rilanci giornalieri sullo stesso tiro e le descrizioni numeriche restano sfumature narrative, mai un verdetto automatico. Icone e atmosfere visive sono curate dagli asset originali dentro un layout nuovo.
- Pagina **Creazione** avviata con il banco Alchimia completo: le pile canoniche di reagenti Rossi, Verdi e Blu dal livello 1 al 4 vivono direttamente in **Alchimia&Contenitori**, insieme al catalogo dei 42 ingredienti Elder, estrazione atomica, miscela fino a quattro reagenti, anteprima trasparente della formula e distillazione server-side con consumo transazionale. Le soglie da 3 a 30 e i bonus di livello/colore restano collegati alle variabili calcolate del personaggio; Forgiatura e Incantamento hanno già una sede coerente per le prossime fasi.
- Pagina **Lore** con tre sezioni. **Fazioni** tiene le carte delle fazioni nella colonna principale e affianca una barra laterale con due schede: `Aggiungi` per registrare o correggere un evento e `Storico` per scorrere la cronologia e modificarne o rimuoverne le voci. Ogni fazione mostra la reputazione verso il gruppo su una scala da -100 a +100 con fascia narrativa, e il nome apre lo storico della singola fazione. La reputazione attuale non è mai salvata: nasce dal valore iniziale ripercorrendo tutti gli eventi in ordine di giorno, quindi rimuovere o retrodatare un evento ricalcola davvero il presente. Il master registra eventi con motivo obbligatorio, su una o più fazioni, in variazione o a valore imposto; una variazione si propaga di un solo passo alle fazioni collegate dalla matrice asimmetrica delle reazioni, mentre un valore imposto resta locale. I giocatori leggono fazioni, punteggi ed eventi, ma non vedono la matrice, i valori base, gli strumenti di modifica né gli eventi marcati come riservati, che continuano comunque a spostare i punteggi visibili. **Personaggi** è una galleria di ritratti con il solo nome: aprendo una carta compaiono descrizione, ruolo e appartenenza, e soltanto lì master e amministratori trovano i comandi per modificarla o archiviarla. **Timeline** porta la cronologia storica dentro la stessa pagina: ricerca, navigazione cronologica, dettaglio, immagini facoltative e authoring riservato a master/amministratori, con anni numerici ordinati rispetto alla caduta di Dagoth Ur. Le schede restano narrative e leggere, indipendenti dalle schede giocabili.
- Contratto OpenAPI versionato e tipi frontend generati.

## Master AI · proposte controllate

`/tools/ai` configura provider e agenti. Un agente `read_only` conserva il comportamento di sola consultazione; un agente `proposer`, disponibile da Master in su, può usare strumenti separati che scrivono esclusivamente `AIChangeSet` e `AIChangeOperation`.

La revisione avviene in `/tools/master-ai`:

1. il Master AI cerca e legge record accessibili;
2. crea operazioni di creazione, clone, modifica o archiviazione;
3. l'utente controlla il diff e può modificare i campi proposti;
4. la convalida server-side produce un token firmato e temporaneo;
5. un POST umano separato applica tutte le operazioni selezionate in una sola transazione, oppure nessuna;
6. scarto, applicazione e scadenza lasciano un riepilogo di audit in sola lettura.

I launcher contestuali sono presenti soltanto in Gestione Oggetti, Gestione Skill/Spell e, per gli Admin, Gestione Temi. I parametri URL sono suggerimenti: il backend rivalida tipo, record e ruolo. Non esiste un launcher generico per Unit, Negozi, Personaggi, Player, Variabili o impostazioni arbitrarie.

Endpoint principali:

```text
GET/POST         /api/ai/change-sets/
GET/PATCH/DELETE /api/ai/change-sets/<uuid>/
POST             /api/ai/change-sets/<uuid>/operations/
PATCH/DELETE     /api/ai/change-sets/<uuid>/operations/<id>/
POST             /api/ai/change-sets/<uuid>/validate/
POST             /api/ai/change-sets/<uuid>/apply/
GET              /api/ai/change-entities/
GET              /api/ai/change-entities/<type>/search/
```

Manutenzione manuale delle proposte abbandonate:

```bat
venv\Scripts\python.exe manage.py cleanup_ai_change_sets --dry-run
venv\Scripts\python.exe manage.py cleanup_ai_change_sets --review-days 14 --empty-days 2
```

La documentazione tecnica completa, inclusi sicurezza, token, concorrenza, osservabilità, estensione dei handler e verifica, è in `docs/MASTER_AI_PROPOSALS.md`. Il contratto degli endpoint legacy `/api/ai` è versionato separatamente in `Builder_docs/openapi-master-ai-proposals.json`; il contratto generato `Builder_docs/openapi-v1.json` continua a descrivere l'API Ninja `/api/v1`.

## Backup amministrativi

La pagina **Gestione Backup**, disponibile solo agli amministratori in `/tools/backups`, crea snapshot consistenti del database SQLite senza fermare il server. Permette di scegliere se eseguire un backup all'avvio, pianificare copie ogni 5-120 minuti di attività del server, impostare quante copie conservare, creare backup manuali e ispezionare personaggi, valori e inventari contenuti nelle copie precedenti.

Le copie gestite sono salvate nella cartella `backups/` con prefisso `redjango-backup-`. La conservazione automatica riguarda soltanto questi file e non elimina eventuali backup creati manualmente con altri nomi. Gli snapshot includono il database applicativo, ma non i file media caricati.

## Avvio

Da `C:\Users\alexo\PycharmProjects\ReDjango`:

```bat
start_server.bat
```

Lo script installa le dipendenze mancanti, costruisce il frontend, applica le migrazioni, aggiorna i dati minimi e avvia:

```text
http://127.0.0.1:8003/
```

Il launcher usa Uvicorn/ASGI in tutte le modalità. Gli aggiornamenti live del
Combattimento restano quindi connessioni asincrone e non occupano un worker per
giocatore mentre attendono un evento.

Al primo avvio il launcher richiede la creazione di un account amministratore se non ne esiste già uno. ReDjango non espone contenuti di gioco agli utenti anonimi: sono pubbliche soltanto la pagina di accesso, l'accesso Django Admin e le risorse statiche necessarie. Ogni account Django autenticato riceve un profilo Giocatore collegato; i permessi Django Admin e il ruolo di gioco restano separati.

La modalità globale si sceglie in **Impostazioni → Amministrazione → Sicurezza**:

- **Bloccata · solo questo computer** è il valore sicuro predefinito: il server ascolta su `127.0.0.1` e rifiuta anche a livello middleware ogni socket non locale.
- **Rete locale LAN** ascolta su tutte le interfacce (`0.0.0.0`) tramite HTTPS e continua a richiedere il login per ogni pagina, file multimediale e API.
- **Server online** ascolta su `127.0.0.1` per impostazione predefinita ed è pensata per un reverse proxy HTTPS. Richiede una chiave segreta e host espliciti.

Il cambio dalla UI mostra la conferma «Cambiare questa impostazione richiede il riavvio del server. Riavviare?». Quando l'app è stata avviata con `start_server.bat`, **Salva e riavvia** arresta il processo in modo controllato, il launcher lo riavvia nella nuova modalità e la pagina si riconnette automaticamente. Con un avvio manuale la modalità viene salvata, ma il riavvio deve essere eseguito manualmente.

È possibile scegliere e salvare una modalità anche dalla riga di comando:

```bat
start_server.bat locked
start_server.bat lan
```

Al primo avvio LAN, ReDjango genera in `.redjango\tls\` un'autorità di
certificazione locale e un certificato HTTPS con i nomi e gli indirizzi IP
correnti del computer. Copiare sui dispositivi client soltanto `lan-ca.pem`,
verificarne l'impronta SHA-256 stampata dal server e aggiungerlo all'archivio
delle autorità attendibili prima di inserire una password. `lan-ca-key.pem` e
`lan-key.pem` devono restare privati sul server. Se cambia l'indirizzo LAN,
il launcher rinnova il certificato server sotto la stessa CA, quindi i client
già configurati non devono importare un nuovo certificato.

Per la pubblicazione online, configurare almeno:

```bat
set REDJANGO_SECRET_KEY=una-chiave-casuale-di-almeno-50-caratteri
set REDJANGO_ALLOWED_HOSTS=gioco.example.it
set REDJANGO_CSRF_TRUSTED_ORIGINS=https://gioco.example.it
set REDJANGO_TRUSTED_PROXIES=127.0.0.1
start_server.bat online
```

`REDJANGO_TRUSTED_PROXIES` accetta indirizzi o reti CIDR separati da virgola
e deve contenere soltanto i reverse proxy che si collegano direttamente a
ReDjango; se viene omesso in modalità online sono attendibili soltanto gli
indirizzi di loopback. Gli header `X-Forwarded-*` provenienti da altri
indirizzi vengono eliminati. Il reverse proxy deve inoltrare anche
`/media/` a Django: non deve esporre direttamente la cartella `media`, perché
i file sono protetti dalla sessione e le immagini riservate dal ruolo di
gioco.

La modalità online abilita cookie sicuri, redirect HTTPS e HSTS. Il launcher
rifiuta il passaggio a `online` se `REDJANGO_SECRET_KEY` o una destinazione
pubblica (`REDJANGO_PUBLIC_ORIGIN`, oppure le liste avanzate di host/origini)
mancano. `DEBUG` è disattivato per impostazione
predefinita in tutte le modalità; `REDJANGO_DEBUG=1` va usato soltanto
durante lo sviluppo locale. Nelle modalità bloccata e LAN viene generata
anche una chiave Django privata persistente; online la chiave deve sempre
arrivare da `REDJANGO_SECRET_KEY`. La terminazione TLS online, gli aggiornamenti di
sicurezza, il firewall e i backup restano responsabilità del
server/reverse proxy.

### Accesso remoto privato con Tailscale

Tailscale Serve è un adattatore isolato della modalità `online`, non una quarta
modalità applicativa. Il launcher doppio clic richiede l'autorizzazione Windows
necessaria a Tailscale Serve, rileva il nome HTTPS privato `.ts.net` e lo passa a
Django tramite il contratto generico `REDJANGO_PUBLIC_ORIGIN`:

```bat
run_tailscale_plus_server.bat
```

Il launcher PowerShell resta disponibile per uso avanzato:

```powershell
powershell -ExecutionPolicy Bypass -File .\redjango\deployment\tailscale\start.ps1
```

Per controllare separatamente server locale, DNS e proxy:

```powershell
powershell -ExecutionPolicy Bypass -File .\redjango\deployment\tailscale\diagnose.ps1
```

Gli Amministratori di gioco trovano la procedura completa, una spiegazione
semplice, la guida da consegnare ai giocatori e il debug tecnico in
**Guide → Accesso remoto privato · Tailscale**. I dettagli dell'adattatore sono
anche in `redjango/deployment/tailscale/README.md`.

`REDJANGO_PUBLIC_ORIGIN` accetta una sola origine HTTPS senza percorso, per
esempio `https://gioco.example.it`. Quando è presente, configura automaticamente
l'host Django e l'origine CSRF; `REDJANGO_ALLOWED_HOSTS` e
`REDJANGO_CSRF_TRUSTED_ORIGINS` restano disponibili per configurazioni avanzate.

## Sviluppo frontend

```bat
cd frontend
npm ci
npm run generate:api
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Il bundle di produzione viene scritto in `frontend/static/frontend/dist/` e servito da Django. Le route SPA dirette, per esempio `/character/3`, usano il fallback Django alla shell React.

## Verifica backend

```bat
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py test
venv\Scripts\python.exe manage.py export_openapi_schema
```

## API

Il nuovo contratto tipizzato è in `/api/v1/`:

```text
GET  /api/v1/characters/<id>/sheet
GET  /api/v1/characters/<id>/notes
GET  /api/v1/characters/<id>/competencies
GET  /api/v1/dice-sets
GET  /api/v1/items
GET  /api/v1/skills
GET  /api/v1/lore
GET  /api/v1/management/units
GET  /api/v1/management/units/<id>
GET  /api/v1/management/units/options
GET  /api/v1/management/shops
POST /api/v1/actions
GET  /api/v1/openapi.json
```

Azioni supportate: spostamento/scambio e assegnazione oggetti, risorse, riposo, panoramica personaggio, creazione/modifica/riordino/rimozione degli effetti personali, applicazione compatibile degli effetti storici, CRUD controllato degli oggetti, anteprima e sblocco atomico delle abilità, anteprima non mutante degli incantesimi, configurazione di visibilità/ordine/note delle azioni del PG, authoring strutturato delle carte abilità e delle formule magiche, progressione/extra/tiri/rilanci delle competenze, aggiornamento delle sezioni di note, tiri server-side e gestione admin dei set di dadi. Gli endpoint precedenti sotto `/api/` restano disponibili per bootstrap, selezione personaggio, impostazioni e media.

L'importazione Elder parte sempre in dry-run e non importa personaggi o ownership:

```powershell
venv\Scripts\python.exe manage.py import_legacy_skills --dry-run --validate-write-path
# Solo dopo la revisione dei report:
venv\Scripts\python.exe manage.py import_legacy_skills --apply
```

La sostituzione del catalogo oggetti usa invece un dry-run predefinito e richiede `--apply` esplicito:

```powershell
venv\Scripts\python.exe manage.py import_legacy_items
venv\Scripts\python.exe manage.py import_legacy_items --apply
```

I ritratti delle Unit Elder vengono letti soltanto dalla radice
`django_slim/static/media/images/pgs` (le directory di duplicati e animazioni
sono escluse), copiati in staging e convertiti in WebP qualità 70. Il comando
scrive sempre un manifest verificabile; `--apply` è atomico e, per impostazione
predefinita, viene rifiutato finché una delle 131 Unit è priva di una
corrispondenza univoca e valida:

```powershell
venv\Scripts\python.exe manage.py import_legacy_unit_portraits
# Dopo aver risolto ogni bloccante riportato nel manifest:
venv\Scripts\python.exe manage.py import_legacy_unit_portraits --apply
# Modalità esplicita: importa i validi e lascia invariati i bloccati.
venv\Scripts\python.exe manage.py import_legacy_unit_portraits --apply --allow-partial
```

Le immagini importate usano categoria `Personaggi`, contesto
`character_portrait` e gruppo `Unit e NPC`. La Unit conserva il collegamento
canonico; ogni nuovo personaggio generato ne riceve il ritratto corrente come
snapshot, senza cambiare i personaggi creati in precedenza.
Gestione Unit usa lo stesso contratto: il selettore mostra soltanto ritratti
conformi, converte i nuovi caricamenti in WebP qualità 70 e mantiene il
collegamento precedente finché il salvataggio della Unit non riesce.

La guida Elder `Razze` e il mapping `EffettiSbloccabili`/`Attivabile` si importano
come gruppo di abilità `Razze/Sottorazze`, con una famiglia per razza. Il comando
è idempotente: senza `--apply` verifica soltanto la sorgente. ReDjango estende
il catalogo con le razze `Dremora`, `Xivilai` e `Non morto`. Dremora usa i sette
ranghi-sottorazza da Churl a Valkynaz; Xivilai è una razza daedrica autonoma
senza sottorazze; Non morto copre Scheletro, Draugr,
Revenant, Mummia, Vampiro, Lich e Spettro. I supplementi vengono aggiunti
anche alla guida `Razze`.

```powershell
venv\Scripts\python.exe manage.py import_legacy_races
venv\Scripts\python.exe manage.py import_legacy_races --apply
```

Prima di `--apply` creare sempre una copia di `db.sqlite3`. L'importatore legge il database Elder in sola lettura, salta soltanto i 13 placeholder `Vuoto`/`No …`, conserva la provenienza in `metadata` e non usa gli ID legacy come chiavi ReDjango.

## Struttura principale

```text
backend/api_v1/                 contratti Ninja/OpenAPI e action dispatcher
backend/ai/changes/              proposal kernel, handler espliciti, token e apply atomico
backend/ai/master_runtime.py     modalità proposer e strumenti AI isolati
frontend/src/features/master-ai/ workspace centrale e launcher contestuali
docs/MASTER_AI_PROPOSALS.md      sicurezza, uso, manutenzione ed estensione
backend/characters/services/    regole, calcoli e comandi atomici
backend/characters/competence_selectors.py proiezione delle competenze e bonus collegati
backend/dice_tools/              catalogo set, palette, validazione e tiri sicuri
backend/characters/selectors.py DTO della scheda e degli slot
backend/core/item_services.py   authoring oggetti e autorizzazione
backend/core/skill_services.py  authoring, validazione e sblocco abilità
backend/core/spell_services.py  definizioni e anteprime incantesimo senza spesa risorse
backend/core/legacy_skill_import.py staging, review queue e import massivo idempotente
backend/lore/selectors.py       replay della reputazione e proiezione per ruolo
backend/lore/services.py        authoring fazioni, matrice reazioni ed eventi
backend/combat/unit_generation.py generazione deterministica Unit usata da Gestione e Combattimento
Builder_docs/UNIT_AUTHORING_GUIDE_FOR_LLM.md contratto operativo per creare Unit variabili e verificabili
backend/combat/unit_management_services.py validazione e authoring Unit master/admin
frontend/src/                   SPA React/TypeScript
frontend/src/features/character workspace personaggio
frontend/src/features/notes     editor condiviso delle note contestuali
frontend/src/features/quick-tools diario, dadi e forgia dei set condivisa
frontend/src/features/skills    gruppi/famiglie, carte, azioni PG e analisi abilità
frontend/src/features/competencies atlante, progressione, extra e tavolo dei tiri
frontend/src/features/lore      fazioni, reputazione, eventi e personaggi narrativi
frontend/src/features/management/UnitManagementPage.tsx editor e anteprima delle Unit
Builder_docs/CONVERSION_MATRIX.md registro della conversione
Builder_docs/UNIT_GENERATION.md contratto completo di generazione delle Unit
Builder_docs/SKILL_MIGRATION_GUIDE_FOR_LLM.md procedura controllata per convertire le skill legacy
```

## Ritratti del personaggio

La modalità equipaggiamento **Sagoma** usa immagini locali in:

```text
frontend/static/frontend/images/characters/match/
```

Il formato preferito è WebP con nome `<primo-nome>_<armatura>.webp`; per esempio `livia_cuoio.webp`. Il fallback è `<primo-nome>_base.webp`, poi il segnaposto incluso. Sono supportati anche i PNG del progetto originale. Le regole complete e gli override disponibili sono documentati nel README della cartella.

Per creare in seguito un altro amministratore Django:

```bat
venv\Scripts\python.exe manage.py createsuperuser
```
