from __future__ import annotations


COMPETENCE_TAG_KEYS = (
    "core_fisico",
    "core_magico",
    "focus_combat",
    "range_skill",
    "area_e_multi_target",
    "natura_magica",
    "difesa",
    "attacco",
    "sociale",
    "supporto_party",
    "esplorazione_infiltrazione",
    "tecnica_crafting",
    "controllo_situazionale",
)


_RAW_COMPETENCE_DEFINITIONS = (
    (
        "scalare", "Scalare", "forza",
        "(1) Scivoli immediatamente e non riesci nemmeno a iniziare la scalata. (3) Riesci a salire solo di pochi metri prima di perdere la presa e dover rinunciare. (7) Scali con qualche difficoltà, superando ostacoli minori ma rallentando spesso. (11) Scali agilmente pareti medie, superando ostacoli con facilità e mantenendo un buon ritmo. (15) Affronti superfici difficili con destrezza, come pareti ripide o rocciose. (19) Scali superfici quasi impossibili, come pareti lisce o verticali, con eccezionale abilità.",
        (3, -1, 1, -1, -1, -1, 1, -1, -1, 1, 5, -1, 2),
    ),
    (
        "manovrare_veicoli", "Manovrare veicoli", "forza",
        "(1) Perdi il controllo di carri, navi o altri macchinari, causando incidenti o danni. (3) Hai difficoltà a manovrare veicoli complessi, effettuando movimenti imprecisi. (7) Manovri carri, navi o macchinari adeguatamente, affrontando situazioni normali senza problemi. (11) Gestisci veicoli complessi con abilità, affrontando condizioni difficili come mare mosso o terreni accidentati. (15) Esegui manovre avanzate su carri, navi o macchinari, come manovre evasive o operazioni complesse. (19) Dimostri maestria assoluta nel manovrare qualsiasi tipo di veicolo o macchinario, compiendo azioni spettacolari e precise.",
        (1, -1, 1, -1, 2, -1, 2, -1, -1, 3, 4, 3, 3),
    ),
    (
        "nuotare", "Nuotare", "resistenza",
        "(1) Non riesci a restare a galla e rischi di affogare. (3) Nuoti con difficoltà, avanzando lentamente e stancandoti rapidamente. (7) Nuoti con competenza, attraversando distanze moderate senza affaticarti troppo. (11) Nuoti agilmente, affrontando correnti moderate e nuotando a velocità sostenuta. (15) Affronti correnti forti e acque agitate con facilità, mantenendo alto il ritmo. (19) Eccelli nel nuoto in condizioni estreme, come acque gelide o lunghe immersioni in apnea.",
        (3, -1, 1, -1, -1, -1, 2, -1, -1, 1, 5, -1, 1),
    ),
    (
        "rapidita_di_mano", "Rapidità di mano", "velocita",
        "(1) Ogni tentativo di furto o manipolazione fallisce clamorosamente, attirando attenzione. (3) Riesci a compiere azioni semplici come lanciare un oggetto o aprire una finestra leggermente chiusa. (7) Esegui furti discreti e scassi di base senza destare sospetti. (11) Manipoli oggetti complessi o scassi serrature avanzate con agilità e precisione. (15) Le tue azioni rapide includono il disinnescare trappole e il lanciare oggetti con grande efficacia. (19) La tua maestria nella rapidità di mano ti permette di eseguire gesti impossibili, influenzando il corso degli eventi con la tua destrezza.",
        (1, -1, 1, -1, -1, -1, 1, 1, 1, 1, 4, 3, 2),
    ),
    (
        "suonare", "Suonare", "agilita",
        "(1) Produci suoni discordanti, rendendo sgradevole qualsiasi performance. (3) Esegui strumenti, canto o danza con errori evidenti, ma riconoscibili. (7) Suoni, canti o balli correttamente pezzi semplici, intrattenendo piacevolmente. (11) Esegui brani complessi con espressività, impressionando il pubblico con musica o danza. (15) Incanti gli ascoltatori con esecuzioni magistrali di strumenti, canto o danza, suscitando forti emozioni. (19) La tua performance musicale o di danza è trascendente, capace di commuovere profondamente e ispirare chi ti ascolta o ti osserva.",
        (-1, -1, -1, 1, 3, -1, -1, -1, 5, 2, 2, -1, 3),
    ),
    (
        "cavalcare", "Cavalcare", "agilita",
        "MALUS DI 3 SE IN SELLA CON ALTRI. (1) Perdi il controllo dell'animale, rischiando di cadere o essere disarcionato. (3) Cavalchi con poca sicurezza; l'animale potrebbe non rispondere ai comandi. (7) Cavalchi adeguatamente, gestendo l'animale in situazioni normali. (11) Cavalchi con abilità, affrontando terreni difficili e controllando l'animale in situazioni stressanti. (15) Esegui manovre avanzate come galoppi prolungati o salti, mantenendo perfetto controllo. (19) Dimostri una sintonia perfetta con l'animale, eseguendo azioni incredibili come acrobazie o comunicazione quasi telepatica.",
        (2, -1, 3, 1, -1, -1, 2, 2, 1, 1, 4, -1, 3),
    ),
    (
        "furtivita", "Furtività", "agilita",
        "(1) Vieni immediatamente scoperto mentre tenti di nasconderti o muoverti furtivamente. (3) Fai rumore o ti esponi accidentalmente, rischiando di essere individuato. (7) Ti nascondi e ti muovi senza farti notare in ambienti poco sorvegliati. (11) Riesci a eludere la sorveglianza in ambienti controllati, muovendoti silenziosamente. (15) Ti muovi invisibile anche in aree altamente sorvegliate, evitando guardie e trappole. (19) Sei praticamente un'ombra, impossibile da rilevare anche dai sistemi più avanzati o da creature con sensi acuti.",
        (-1, -1, 2, -1, -1, -1, 2, 2, 1, 2, 5, -1, 3),
    ),
    (
        "sapienza_magica", "Sapienza magica", "intelligenza",
        "(1) Non riesci a comprendere nemmeno i concetti magici più elementari. (3) Hai una comprensione limitata, riconosci solo incantesimi o effetti semplici. (7) Conosci bene la teoria magica, identifichi incantesimi comuni e i loro effetti. (11) Hai una profonda conoscenza, comprendi incantesimi complessi e puoi dedurre effetti nascosti. (15) Sei un esperto, capace di riconoscere magie rare e comprendere antichi rituali. (19) La tua conoscenza è enciclopedica, sai tutto ciò che c'è da sapere sulla magia e potresti scoprire nuovi incantesimi.",
        (-1, 1, 1, -1, -1, 4, 2, 1, 1, 2, 2, 2, 2),
    ),
    (
        "ingegneria", "Ingegneria", "intelligenza",
        "(1) Non comprendi i principi base, rischi di causare danni manipolando macchinari. (3) Riesci a effettuare semplici riparazioni o comprendere meccanismi basilari. (7) Progetti e ripari strutture o dispositivi comuni con competenza. (11) Crei progetti complessi, migliori macchinari esistenti e risolvi problemi tecnici avanzati. (15) Inventi nuove tecnologie o costruisci opere ingegneristiche di grande portata. (19) La tua genialità ingegneristica è leggendaria, capace di realizzare meraviglie tecniche mai viste.",
        (-1, -1, 1, -1, 1, -1, 2, 2, -1, 3, 4, 5, 3),
    ),
    (
        "strategia_militare", "Strategia militare", "intelligenza",
        "(1) Proponi tattiche inefficaci che potrebbero portare a disastri sul campo. (3) Hai idee basilari, ma manchi di visione strategica, rischiando errori tattici. (7) Elabori strategie solide per scontri comuni, prevedendo le mosse nemiche. (11) Pianifichi campagne complesse, anticipando le tattiche avversarie e adattandoti. (15) Sei un brillante stratega, capace di ribaltare le sorti di una guerra con le tue decisioni. (19) Le tue strategie sono studiate nei secoli, capaci di vittorie impossibili e di farti diventare una leggenda militare.",
        (2, -1, 5, 1, 4, -1, 3, 3, 1, 4, 1, -1, 4),
    ),
    (
        "conoscenze_naturaegeografia", "Conoscenze Natura e Geografia", "concentrazione",
        "(1) Non riconosci piante o animali comuni, né comprendi le caratteristiche del territorio. (3) Hai conoscenze limitate, puoi identificare elementi naturali basilari. (7) Conosci bene flora, fauna e caratteristiche geografiche tipiche. (11) Hai una profonda comprensione degli ecosistemi e delle peculiarità geografiche avanzate. (15) Sei un esperto naturalista, in grado di scoprire nuove specie o luoghi inesplorati. (19) La tua conoscenza è tale da prevedere fenomeni naturali e capire i segreti più profondi della natura.",
        (-1, -1, 1, -1, 2, -1, 2, -1, 1, 3, 5, 1, 2),
    ),
    (
        "conoscenze_religioni", "Conoscenze Religioni", "concentrazione",
        "(1) Hai una comprensione minima delle divinità, confondendo Aedra e Daedra. (3) Conosci alcune divinità minori e i loro domini, ma la tua conoscenza è superficiale. (7) Comprendi bene le principali Aedra e Daedra, le loro caratteristiche e i loro culti. (11) Possiedi una conoscenza approfondita delle religioni di Tamriel, inclusi riti e tradizioni. (15) Sei in grado di interpretare testi sacri e di guidare cerimonie religiose complesse. (19) La tua sapienza religiosa ti permette di decifrare antichi testi, evocare benedizioni divine e comprendere i piani delle divinità a un livello superiore.",
        (-1, -1, -1, -1, -1, -1, 1, -1, 4, 2, 2, -1, 2),
    ),
    (
        "conoscenze_storiaenobilta", "Conoscenze Storia e Nobiltà", "concentrazione",
        "(1) Non conosci eventi storici o linee di successione nobiliari basilari. (3) Hai nozioni generiche su eventi storici e casate nobili. (7) Conosci dettagli su periodi storici importanti e genealogie nobiliari. (11) Hai una comprensione profonda della storia, inclusi eventi meno noti e intrecci politici. (15) Sei uno storico rinomato, con accesso a informazioni rare e documenti antichi. (19) La tua conoscenza storica è incomparabile, potresti riscrivere la storia o svelare verità nascoste.",
        (-1, -1, -1, -1, -1, -1, 1, -1, 4, 2, 2, -1, 2),
    ),
    (
        "percezione", "Percezione", "concentrazione",
        "(1) Non noti dettagli evidenti nell'ambiente circostante. (3) Percepisci solo elementi evidenti e potresti mancare indizi importanti. (7) Noti dettagli comuni, sei attento a ciò che ti circonda. (11) Individui dettagli nascosti, come trappole o indizi sottili. (15) Hai sensi acuti, percepisci minime anomalie o suoni impercettibili. (19) La tua percezione è quasi sovrumana: nulla sfugge ai tuoi sensi.",
        (-1, -1, 2, 1, 1, -1, 3, 1, 1, 3, 5, -1, 3),
    ),
    (
        "diplomazia", "Diplomazia", "personalita",
        "(1) I tuoi tentativi di dialogo risultano goffi e non riesci a trasmettere chiaramente le tue intenzioni. (3) Convinci una persona già propensa ad accettare una piccola richiesta o proposta. (7) Allinei le opinioni di individui indecisi verso una direzione che supporta i tuoi obiettivi. (11) Persuadi una persona con esperienza negoziale a mettere da parte i propri interessi per favorirti, senza andare direttamente contro sé stessa. (15) Riesci a convincere gruppi di gente comune a fare il tuo volere, minimizzando le loro obiezioni; anche diplomatici esperti sono fortemente influenzati da ciò che dici. (19) La tua abilità riuscirebbe a convincere quasi chiunque a scendere a patti con te; a parte situazioni fuori da ogni logica, quasi tutto ti è concesso.",
        (-1, -1, -1, -1, 2, -1, 1, -1, 5, 3, 2, -1, 4),
    ),
    (
        "intimidire", "Intimidire", "personalita",
        "(1) Le tue minacce sono inefficaci e suscitano derisione. (3) Non incuti particolare timore; l'interlocutore rimane indifferente. (7) Riesci a intimidire persone comuni, ottenendo collaborazione. (11) Incuti timore anche in individui coriacei, influenzandone le azioni. (15) La tua presenza è così minacciosa da far desistere gruppi o avversari potenti. (19) Sei temuto universalmente: la sola tua fama può mettere in fuga intere armate.",
        (1, -1, 2, -1, 1, -1, 1, 1, 5, 2, 1, -1, 4),
    ),
    (
        "camuffare", "Camuffare", "personalita",
        "(1) Il travestimento è mal realizzato e facilmente riconoscibile. (3) Il tuo camuffamento potrebbe ingannare solo a un primo sguardo distratto. (7) Riesci a camuffarti adeguatamente, senza attirare attenzioni indesiderate. (11) Il tuo travestimento è convincente e puoi impersonare altre persone senza destare sospetti. (15) Puoi trasformarti in chiunque, ingannando anche chi conosce bene la persona imitata. (19) I tuoi camuffamenti sono perfetti, quasi magici: nessuno può scoprire la tua vera identità.",
        (-1, -1, -1, -1, -1, -1, 1, -1, 4, 2, 5, 2, 3),
    ),
    (
        "raggirare", "Raggirare", "personalita",
        "(1) Le tue bugie sono evidenti e facilmente smascherate. (3) Le tue menzogne sono poco credibili e l'interlocutore è sospettoso. (7) Riesci a mentire convincendo la maggior parte delle persone. (11) Sei un abile manipolatore e puoi ingannare esperti o persone diffidenti. (15) Le tue truffe sono sofisticate e inganni gruppi o organizzazioni intere. (19) Sei un maestro dell'inganno, capace di orchestrare complesse macchinazioni senza essere scoperto.",
        (-1, -1, -1, -1, 1, -1, 1, -1, 5, 2, 4, -1, 4),
    ),
    (
        "sopravvivenza", "Sopravvivenza", "saggezza",
        "(0) Ti perdi facilmente e non hai alcun senso dell'orientamento, rendendo difficile anche tornare sui tuoi passi. (1) Hai il 50% di probabilità di trovare cibo in un'ora e riesci a orientarti solo con punti di riferimento evidenti. (2) Riduci leggermente i malus alla percezione durante il sonno, diminuisci di 1 gli incontri casuali, riconosci il nord di giorno e puoi accendere un fuoco senza strumenti. (3) Diminuisci di un ulteriore punto gli incontri casuali e mantieni una direzione per ore anche in zone poco conosciute. (4) Anche senza sacco a pelo recuperi fino a -1 stanchezza, sfrutti elementi naturali per orientarti e trovi il nord anche di notte. (5) Hai il 100% di probabilità di trovare cibo in 30 minuti e viaggi con sicurezza per ore nelle zone selvagge durante il giorno. (6) Diminuisci ancora di 1 gli incontri casuali e puoi seguire tracce o sentieri nascosti senza perderti di notte. (7) Anche senza sacco a pelo recuperi fino a 0 stanchezza, puoi dormire 4 ore senza stanchezza aggiuntiva e trovi sempre un luogo sicuro e nascosto dove accamparti.",
        (2, -1, 1, -1, 2, -1, 3, 1, -1, 3, 5, 2, 3),
    ),
    (
        "gestione_risorse", "Gestione risorse", "saggezza",
        "(1) Sprechi risorse e organizzi male il gruppo, causando perdite critiche durante viaggi o accampamenti. (3) Gestisci le risorse in modo inefficiente, con scarsa pianificazione che può portare a carenze. (7) Organizzi adeguatamente gruppi e risorse, mantenendo un equilibrio tra consumo e disponibilità; gestisci bene piccoli gruppi. (11) Ottimizzi l'uso delle risorse e coordini bene il gruppo, aumentando l'efficienza e riducendo gli sprechi; puoi tenere organizzata una piccola cittadina. (15) Sei un eccellente amministratore, capace di moltiplicare le risorse disponibili, organizzare spedizioni complesse e gestire una città. (19) La tua gestione crea abbondanza anche nella scarsità, permettendo viaggi lunghi e accampamenti autosufficienti; sapresti gestire Skingrad da solo.",
        (2, -1, 1, -1, 3, -1, 2, -1, 1, 4, 4, 2, 3),
    ),
    (
        "intuizione", "Intuizione", "saggezza",
        "(1) Interpreti male le intenzioni altrui, trai conclusioni errate e agisci in modo inadeguato. (3) Hai difficoltà a leggere tra le righe e potresti non cogliere segnali importanti o capire se qualcuno mente. (7) Comprendi le motivazioni di base degli altri e riesci a capire se qualcuno mente basandoti sui dati disponibili. (11) Intuisci le vere intenzioni altrui, anche quando sono ben nascoste, e riconosci le menzogne con maggiore facilità. (15) Leggi con facilità pensieri ed emozioni nascoste, anticipando le mosse degli altri e discernendo menzogne complesse. (19) La tua intuizione è quasi telepatica: comprendi profondamente l'animo altrui e riconosci le menzogne anche nelle situazioni più intricate.",
        (-1, -1, -1, -1, -1, -1, 2, -1, 5, 2, 2, -1, 3),
    ),
)


# These strings intentionally preserve the legacy catalogue verbatim, including
# its punctuation and wording. In the new UI they are presented as narrative
# nuances, not executable thresholds.
LEGACY_COMPETENCE_DESCRIPTIONS = {
    "scalare": "(1) Scivoli immediatamente e non riesci nemmeno a iniziare la scalata.(3) Riesci a salire solo di pochi metri prima di perdere la presa e dover rinunciare.(7) Scala con qualche difficoltà, superando ostacoli minori ma rallentando spesso.(11) Scala agilmente pareti medie, superando ostacoli con facilità e mantenendo un buon ritmo.(15) Affronti superfici difficili con destrezza, come pareti ripide o rocciose(19) Scala superfici quasi impossibili, come pareti lisce o verticali, con eccezionale abilità.",
    "manovrare_veicoli": "(1) Perdi il controllo di carri, navi o altri macchinari, causando incidenti o danni(3) Hai difficoltà a manovrare veicoli complessi, effettuando movimenti imprecisi.(7) Manovri carri, navi o macchinari adeguatamente, affrontando situazioni normali senza problemi(11) Gestisci veicoli complessi con abilità, affrontando condizioni difficili come mare mosso o terreni accidentati.(15) Esegui manovre avanzate su carri, navi o macchinari, come manovre evasive o operazioni complesse.(19) Dimostri maestria assoluta nel manovrare qualsiasi tipo di veicolo o macchinario, compiendo azioni spettacolari e precise.",
    "nuotare": "(1) Non riesci a restare a galla e rischi di affogare(3) Nuoti con difficoltà, avanzando lentamente e stancandoti rapidamente(7) Nuoti con competenza, attraversando distanze moderate senza affaticarti troppo.(11) Nuoti agilmente, affrontando correnti moderate e nuotando a velocità sostenuta.(15) Affronti correnti forti e acque agitate con facilità, mantenendo alto il ritmo.(19) Eccelli nel nuoto in condizioni estreme, come acque gelide o lunghe immersioni in apnea.",
    "rapidita_di_mano": "(1) Ogni tentativo di furto o manipolazione fallisce clamorosamente, attirando attenzione.(3) Riesci a compiere azioni semplici come lanciare un oggetto o aprire una finestra leggermente chiusa.(7) Esegui furti discreti e scassi di base senza destare sospetti.(11) Manipoli oggetti complessi o scassi serrature avanzate con agilità e precisione.(15) Le tue azioni rapide includono il disinnescare trappole e il lanciare oggetti con grande efficacia.(19) La tua maestria nella rapidità di mano ti permette di eseguire gesti impossibili, influenzando il corso degli eventi con la tua destrezza.",
    "suonare": "(1) Produci suoni discordanti, rendendo sgradevole qualsiasi performance.(3) Esegui strumenti, canto o danza con errori evidenti, ma riconoscibili.(7) Suoni, canti o balli correttamente pezzi semplici, intrattenendo piacevolmente.(11) Esegui brani complessi con espressività, impressionando il pubblico con musica o danza.(15) Incanti gli ascoltatori con esecuzioni magistrali di strumenti, canto o danza, suscitando forti emozioni.(19) La tua performance musicale o di danza è trascendente, capace di commuovere profondamente e ispirare chi ti ascolta o ti osserva.",
    "cavalcare": "MALUS DI 3 SE IN SELLA CON ALTRI(1) Perdi il controllo dell'animale, rischiando di cadere o essere disarcionato.(3) Cavalchi con poca sicurezza, l'animale potrebbe non rispondere ai comandi.(7) Cavalchi adeguatamente, gestendo l'animale in situazioni normali.(11) Cavalchi con abilità, affrontando terreni difficili e controllando l'animale in situazioni stressanti.(15) Esegui manovre avanzate come galoppi prolungati o salti, mantenendo perfetto controllo.(19) Dimostri una sintonia perfetta con l'animale, eseguendo azioni incredibili come acrobazie o comunicazione quasi telepatica.",
    "furtivita": "(1) Veni immediatamente scoperto mentre tenti di nasconderti o muoverti furtivamente(3) Fai rumore o ti esponi accidentalmente, rischiando di essere individuato.(7) Ti nascondi e ti muovi senza farti notare in ambienti poco sorvegliati.(11) Riesci a eludere la sorveglianza in ambienti controllati, muovendoti silenziosamente.(15) Ti muovi invisibile anche in aree altamente sorvegliate, evitando guardie e trappole(19) Sei praticamente un'ombra, impossibile da rilevare anche dai sistemi più avanzati o creature con sensi acuti.",
    "sapienza_magica": "(1) Non riesci a comprendere nemmeno i concetti magici più elementari.(3) Hai una comprensione limitata, riconosci solo incantesimi o effetti semplici.(7) Conosci bene la teoria magica, identifichi incantesimi comuni e i loro effetti.(11) Hai una profonda conoscenza, comprendi incantesimi complessi e puoi dedurre effetti nascosti(15) Sei un esperto, capace di riconoscere magie rare e comprendere antichi rituali.(19) La tua conoscenza è enciclopedica, sai tutto ciò che c'è da sapere sulla magia e potresti scoprire nuovi incantesimi.",
    "ingegneria": "(1) Non comprendi i principi base, rischi di causare danni manipolando macchinari.(3) Riesci a effettuare semplici riparazioni o comprendere meccanismi basilari(7) Progetti e ripari strutture o dispositivi comuni con competenza.(11) Crea progetti complessi, migliori macchinari esistenti e risolvi problemi tecnici avanzati.(15) Inveni nuove tecnologie o costruisci opere ingegneristiche di grande portata.(19) La tua genialità ingegneristica è leggendaria, capace di realizzare meraviglie tecniche mai viste.",
    "strategia_militare": "(1) Proponi tattiche inefficaci che potrebbero portare a disastri sul campo.(3) Hai idee basilari, ma manca di visione strategica, rischiando errori tattici(7) Elabora strategie solide per scontri comuni, prevedendo le mosse nemiche(11) Pianifichi campagne complesse, anticipando le tattiche avversarie e adattandoti.(15) Sei un brillante stratega, capace di ribaltare le sorti di una guerra con le tue decisioni.(19) Le tue strategie sono studiate nei secoli, capace di vittorie impossibili e di diventare una leggenda militare.",
    "conoscenze_naturaegeografia": "(1) Non riconosci piante o animali comuni, né comprendi le caratteristiche del territorio.(3) Hai conoscenze limitate, puoi identificare elementi naturali basilari.(7) Conosci bene flora, fauna e caratteristiche geografiche tipiche.(11) Hai una profonda comprensione degli ecosistemi e delle peculiarità geografiche avanzate.(15) Sei un esperto naturalista, in grado di scoprire nuove specie o luoghi inesplorati.(19) La tua conoscenza è tale da prevedere fenomeni naturali e capire i segreti più profondi della natura.",
    "conoscenze_religioni": "(1) Hai una comprensione minima delle divinità, confondendo Aedra e Daedra.(3) Conosci alcune divinità minori e i loro domini, ma la tua conoscenza è superficiale.(7) Comprendi bene le principali Aedra e Daedra, le loro caratteristiche e i loro culti.(11) Possiedi una conoscenza approfondita delle religioni di Tamriel, inclusi riti e tradizioni.(15) Sei in grado di interpretare testi sacri e di guidare cerimonie religiose complesse.(19) La tua sapienza religiosa ti permette di decifrare antichi testi, evocare benedizioni divine e comprendere i piani delle divinità a un livello superiore.",
    "conoscenze_storiaenobilta": "(1) Non conosci eventi storici o linee di successione nobiliari basilari.(3) Hai nozioni generiche su eventi storici e casate nobili.(7) Conosci dettagli su periodi storici importanti e genealogie nobiliari.(11) Hai una comprensione profonda della storia, inclusi eventi meno noti e intrecci politici.(15) Sei uno storico rinomato, con accesso a informazioni rare e documenti antichi.(19) La tua conoscenza storica è incomparabile, potresti riscrivere la storia o svelare verità nascoste.",
    "percezione": "(1) Non noti dettagli evidenti nell'ambiente circostante.(3) Percepisci solo elementi evidenti, potresti mancare indizi importanti.(7) Noti dettagli comuni, sei attento a ciò che ti circonda.(11) Individui dettagli nascosti, come trappole o indizi sottili.(15) Hai sensi acuti, percepisci minime anomalie o suoni impercettibili.(19) La tua percezione è quasi sovrumana, nulla sfugge ai tuoi sensi.",
    "diplomazia": "(1) I tuoi tentativi di dialogo risultano goffi e non riesci a trasmettere chiaramente le tue intenzioni. (3) Convincere una persona che è già propensa ad accettare una piccola richiesta o proposta. (7) Allineare le opinioni di individui indecisi verso una direzione specifica che supporta i tuoi obiettivi. (11) Persuadere una persona con una certa esperienza negoziale a mettere da parte i propri interessi per favoreggiarti, senza andare direttamente contro sé stesso.(15) Riesci a convingere gruppi di gente comune a fare il tuo volere, minimizzando le loro obiezioni. Diplomatici esperti sono fortemente influenzati da quello che dici.(19) La tua abilità riuscirebbe a convincere chiunque a scendere a patti con te. A parte situazioni fuori da ogni logica, quasi tutto ti è concesso.",
    "intimidire": "(1) Le tue minacce sono inefficaci, suscitando derisione.(3) Non incuti particolare timore, l'interlocutore rimane indifferente.(7) Riesci a intimidire persone comuni, ottenendo collaborazione.(11) Incuti timore anche in individui coriacei, influenzandone le azioni.(15) La tua presenza è così minacciosa da far desistere gruppi o avversari potenti.(19) Sei temuto universalmente, la sola tua fama può mettere in fuga intere armate.",
    "camuffare": "(1) Il travestimento è mal realizzato e facilmente riconoscibile.(3) Il tuo camuffamento potrebbe ingannare solo a un primo sguardo distratto(7) Riesci a camuffarti adeguatamente, non attirando attenzioni indesiderate.(11) Il tuo travestimento è convincente, puoi impersonare altre persone senza destare sospetti.(15) Puoi trasformarti in chiunque, ingannando anche chi conosce bene la persona imitata.(19) I tuoi camuffamenti sono perfetti, quasi magici, nessuno può scoprire la tua vera identità.",
    "raggirare": "(1) Le tue bugie sono evidenti e facilmente smascherate.(3) Le tue menzogne sono poco credibili, l'interlocutore è sospettoso.(7) Riesci a mentire convincendo la maggior parte delle persone.(11) Sei un abile manipolatore, puoi ingannare esperti o persone diffidenti.(15) Le tue truffe sono sofisticate, inganni gruppi o organizzazioni intere.(19) Sei un maestro dell'inganno, capace di orchestrare complesse macchinazioni senza essere scoperto.",
    "sopravvivenza": "(0) Ti perdi facilmente e non hai alcun senso dell'orientamento, rendendo difficile anche tornare sui tuoi passi.(1) Hai il 50% di probabilità di trovare cibo in un'ora e riesci a orientarti solo con l’aiuto di punti di riferimento evidenti.(2) Riduci leggermente i malus alla percezione durante il sonno, diminuisci di 1 il numero di incontri casuali, e inizi a conoscere dov’è il nord, di giorno. Puoi accendere un fuoco senza strumenti.(3) Diminuisci di 1 ulteriore il numero di incontri casuali e riesci a trovare la direzione giusta anche in zone leggermente sconosciute seguendo una direzione per un paio d’ore.(4) Anche senza sacco a pelo, recuperi fino a -1 punto di stanchezza e sai sfruttare elementi naturali per orientarti meglio. Trovi il nord anche di notte.(5) Hai il 100% di probabilità di trovare cibo in 30 minuti e riesci a orientarti facilmente anche in zone selvagge, viaggiando con sicurezza per ore e ore di giorno.(6) Diminuisci ancora di 1(totale 3) il numero di incontri casuali e puoi seguire tracce o sentieri nascosti senza perderti di notte.(7) Anche senza sacco a pelo, recuperi fino a 0 punti di stanchezza e puoi dormire solo 4 ore per notte senza soffrire di stanchezza aggiuntiva, trovando sempre un luogo sicuro e nascosto dove accamparti.",
    "gestione_risorse": "(1) Sprechi risorse e organizzi male il gruppo, causando perdite critiche durante i viaggi o negli accampamenti.(3) Gestisci le risorse in modo inefficiente, con scarsa pianificazione che può portare a carenze.(7) Organizzi adeguatamente gruppi e risorse, mantenendo un equilibrio tra consumo e disponibilità durante i viaggi o negli accampamenti. Gestisci bene piccoli gruppi.(11) Ottimizzi l'uso delle risorse e coordinati bene il gruppo, aumentando l'efficienza e riducendo gli sprechi. Sei un ottimo amministratore, capace di tenere organizzato una piccola cittadina.(15) Sei un eccellente amministratore, capace di moltiplicare le risorse disponibili e organizzare spedizioni complesse con successo. Puoi gestire una città con successo, da solo.(19) La tua gestione è così efficace da creare abbondanza anche in condizioni di scarsità, permettendo viaggi lunghi e accampamenti autosufficienti senza problemi. Saresti capace di gestire Skingrad da solo.",
    "intuizione": "(1) Interpreti male le intenzioni altrui, traendo conclusioni errate e agendo in modo inadeguato(3) Hai difficoltà a leggere tra le righe, potresti non cogliere segnali importanti o capire se qualcuno mente.(7) Comprendi le motivazioni base degli altri e riesci a capire se qualcuno sta mentendo basandoti sui tuoi dati(11) Intuisci le vere intenzioni altrui, anche quando ben nascoste, e riconosci menzogne con maggiore facilità.(15) Leggi con facilità pensieri ed emozioni nascoste, anticipando le mosse degli altri e discernendo menzogne complesse.(19) La tua intuizione è quasi telepatica, comprendendo profondamente l'animo umano e riconoscendo menzogne anche nelle situazioni più intricate.",
}


ATTRIBUTE_LABELS = {
    "forza": "Forza",
    "resistenza": "Resistenza",
    "velocita": "Velocità",
    "agilita": "Agilità",
    "intelligenza": "Intelligenza",
    "concentrazione": "Concentrazione",
    "personalita": "Personalità",
    "saggezza": "Saggezza",
}


COMPETENCE_DEFINITIONS = tuple(
    {
        "key": key,
        "name": name,
        "attribute": attribute,
        "category": ATTRIBUTE_LABELS[attribute],
        "description": LEGACY_COMPETENCE_DESCRIPTIONS.get(key, description),
        "mapping_tag": dict(zip(COMPETENCE_TAG_KEYS, tag_values, strict=True)),
        "order": order,
    }
    for order, (key, name, attribute, description, tag_values) in enumerate(_RAW_COMPETENCE_DEFINITIONS, start=1)
)

COMPETENCE_DEFINITION_BY_KEY = {definition["key"]: definition for definition in COMPETENCE_DEFINITIONS}


def default_competence_state() -> dict[str, dict[str, int]]:
    return {
        definition["key"]: {"barra1": 0, "barra2": 0, "extra": 0}
        for definition in COMPETENCE_DEFINITIONS
    }
