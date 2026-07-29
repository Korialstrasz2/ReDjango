from __future__ import annotations

from copy import deepcopy
from typing import Any

import elder_unit_calibration_v2 as base
import elder_unit_batch2_v2 as toolkit
import elder_unit_batch3_v2 as previous


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-batch-4-v2" / "authored"
toolkit.BATCH_LABEL = "Batch 4 v2"


def covered_equipment(source_file: str) -> list[dict[str, Any]]:
    return previous.covered_equipment(source_file)


def unique_skills(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return previous.unique_skills(*pools)


COMMANDER = [
    base.skill(321, "archetype", 7),
    base.skill(330, "archetype", 8),
    base.skill(328, "archetype", 7),
    base.skill(324, "archetype", 6, 4),
    base.skill(333, "archetype", 6, 5),
    base.skill(1010, "archetype", 6, 7),
    base.skill(1011, "archetype", 5, 11),
    base.skill(891, "archetype", 8, 4),
    base.skill(892, "archetype", 6, 10),
    base.skill(894, "archetype", 7, 6),
]

BATTLE_MAGE = [
    base.skill(331, "archetype", 7),
    base.skill(328, "archetype", 6, 4),
    base.skill(324, "archetype", 5, 6),
    base.skill(439, "archetype", 8),
    base.skill(440, "archetype", 8, 4),
    base.skill(444, "archetype", 6, 6),
    base.skill(1314, "archetype", 5, 10),
    base.skill(1315, "archetype", 6, 12),
    base.skill(445, "archetype", 5, 14),
]

TELVANNI_ELITE = [
    base.skill(1444, "archetype", 9),
    base.skill(426, "archetype", 9),
    base.skill(427, "archetype", 8),
    base.skill(1210, "archetype", 6, 4),
    base.skill(1168, "archetype", 7, 6),
    base.skill(431, "archetype", 7, 6),
    base.skill(1445, "archetype", 7, 8),
    base.skill(1446, "archetype", 7, 12),
    base.skill(1447, "archetype", 6, 14),
    base.skill(1448, "archetype", 5, 16),
    base.skill(440, "archetype", 7, 5),
]

SUPPORT_CORE = [
    base.skill(71, "core", 8),
    base.skill(72, "core", 5, 4),
    base.skill(81, "core", 8),
    base.skill(82, "core", 5, 4),
    base.skill(403, "core", 9),
    base.skill(404, "core", 6, 5),
    base.skill(395, "core", 8),
    base.skill(396, "core", 6, 4),
    base.skill(397, "core", 6, 6),
    base.skill(1302, "core", 6, 7),
]

RECOVERY = [
    base.skill(417, "archetype", 10),
    base.skill(1310, "archetype", 9),
    base.skill(1309, "archetype", 8),
    base.skill(419, "archetype", 10, 4),
    base.skill(420, "archetype", 7, 6),
    base.skill(424, "archetype", 7, 8),
    base.skill(425, "archetype", 8, 10),
    base.skill(1452, "archetype", 5, 5),
    base.skill(1442, "archetype", 5, 8),
]


def humanoid_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    candidate = toolkit.humanoid_candidate(spec)
    candidate["rejectedCandidates"].extend(deepcopy(spec.get("extra_rejected") or []))
    candidate["deviations"].extend(deepcopy(spec.get("extra_deviations") or []))
    return candidate


def creature_candidate(spec: dict[str, Any]) -> dict[str, Any]:
    candidate = toolkit.creature_candidate(spec)
    candidate["rejectedCandidates"].extend(deepcopy(spec.get("extra_rejected") or []))
    candidate["deviations"].extend(deepcopy(spec.get("extra_deviations") or []))
    return candidate


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Alto Stregone Telvanni", "source": "937", "ids": [937],
        "category": "Dunmer", "core": "mage", "core_share": 0.4, "magic": "any",
        "skills": deepcopy(base.MAGE_CORE) + TELVANNI_ELITE, "races": ["Dunmer"],
        "subraces": ["Retaggio Mago", "Nobile di Vvardenfell"],
        "equipment": covered_equipment("937"),
        "fantasy": "Maestro Telvanni che considera magia, rango e conoscenza strumenti dello stesso dominio.",
        "combat": "Controlla volontà e spazio con Illusione e teletrasporto, usando staff o fioretto soltanto come focus di prestigio.",
        "archetype": "Incantatore Telvanni d'élite con Illusione avanzata, mobilità e dotazione iconica.",
        "tags": {"core_magico": 5, "natura_magica": 5, "controllo_situazionale": 5, "area_e_multi_target": 3, "core_fisico": -4},
        "competences": {"sapienza_magica": 5, "conoscenze_storiaenobilta": 5, "intimidire": 4, "intuizione": 3, "sopravvivenza": -4},
        "siblings": [("Mago Telvanni", "nearest", "Capstone Illusione, rango e armatura Telvanni sostituiscono lo specialista ordinario."), ("Spadaccino Telvanni", "same-house", "Controllo arcano invece di duello."), ("Mago (standard)", "contrast", "Identità di Casata e dominio mentale, non generalismo.")],
        "axes": [("autorità Telvanni", "Dunmer, equipaggiamento iconico e competenze di rango"), ("dominio mentale", "Illusione avanzata e Teleport")],
        "must": ["Dunmer", "Telvanni", "Illusione", "staff"], "must_not": ["cura primaria", "scudo", "religione", "azioni innate"],
        "variation": "staff o fioretto daedrico con rami Illusione diversi", "legacy_range": "15-20",
        "range_reason": "La dotazione iconica resta fissa; ai livelli bassi cambia soltanto la profondità delle Skill.",
        "checkpoints": ["stregone Telvanni completo", "controllo mentale", "teletrasporto", "Malia e Comando", "maestro di Mindscape"],
        "at_least_one": ["una Skill Illusione entro il livello 1"],
    },
    {
        "name": "Buoyant Armiger", "source": "932-933", "ids": [932, 933],
        "category": "Dunmer", "core": "warrior", "core_share": 0.48, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, previous.DUELIST, toolkit.WARRIOR),
        "races": ["Dunmer"], "subraces": ["Retaggio Guerriero", "Servo del Tribunale"],
        "equipment": covered_equipment("932-933"),
        "fantasy": "Campione errante di Vivec che unisce servizio religioso, eleganza e audacia personale.",
        "combat": "Combatte mobile con spada lunga o Zweihander, cerca l'apertura e rifiuta la postura statica dell'Ordinatore.",
        "archetype": "Spadaccino Dunmer d'élite con armatura dreugh e stile offensivo mobile.",
        "tags": {"core_fisico": 4, "focus_combat": 5, "attacco": 5, "difesa": 2, "sociale": 2, "core_magico": -5},
        "competences": {"strategia_militare": 4, "conoscenze_religioni": 4, "percezione": 4, "diplomazia": 3, "furtivita": -3},
        "siblings": [("Ordinatore", "nearest", "Mobilità e lama a due mani invece di scudo e bastione."), ("Cavaliere Redoran", "same-culture", "Servizio a Vivec e duello invece di difesa di Casata."), ("Duellante", "contrast", "Campione religioso corazzato, non professionista urbano.")],
        "axes": [("campione di Vivec", "Dunmer, religione e armatura Armiger"), ("offesa mobile", "spada/Zweihander e Affondo")],
        "must": ["Dunmer", "Buoyant Armiger", "spada", "mobilità"], "must_not": ["magia", "scudo", "furtività", "azioni innate"],
        "variation": "spada lunga o Zweihander di vetro/ebano", "legacy_range": "10-20",
        "range_reason": "Il set dreugh resta identitario; la fascia vetro viene estesa ai livelli bassi.",
        "checkpoints": ["Armiger completo", "affondo mobile", "lama di vetro", "arsenale d'ebano", "campione di Vivec"],
        "at_least_one": ["Affondo o Carica entro il livello 5"],
    },
    {
        "name": "Comandante della Legione Imperiale", "source": "847", "ids": [847],
        "category": "Imperiale", "core": "warrior", "core_share": 0.56, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, COMMANDER), "classes": ["Cavaliere"],
        "races": ["Imperiale"], "subraces": ["Di Città", "Di Campagna"],
        "equipment": covered_equipment("847"),
        "fantasy": "Ufficiale veterano che tiene la Legione unita attraverso disciplina, presenza e lettura del campo.",
        "combat": "Guida dalla prima linea con arma pesante, scudo e manovre che premiano posizione e cooperazione.",
        "archetype": "Comandante Imperiale pesante con formazione, arma a due mani e autorità tattica.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "difesa": 4, "attacco": 4, "sociale": 4, "core_magico": -5},
        "competences": {"strategia_militare": 5, "intimidire": 4, "diplomazia": 4, "percezione": 3, "furtivita": -5},
        "siblings": [("Soldato Imperiale", "nearest", "Comando e arma pesante sostituiscono ruolo di linea standard."), ("Bandito Capo", "same-role", "Disciplina istituzionale invece di paura criminale."), ("Signore della Guerra Orco", "contrast", "Formazione legionaria invece di autorità di clan.")],
        "axes": [("comando legionaro", "strategia/diplomazia e Skill Cavaliere"), ("prima linea pesante", "armatura di servizio, scudo e arma a due mani")],
        "must": ["Imperiale", "Legione", "comando", "armatura di servizio"], "must_not": ["magia", "furtività", "bottino casuale", "azioni innate"],
        "variation": "spadone o martello nordico con dotazione legionaria fissa", "legacy_range": "15-20",
        "range_reason": "Rango e uniforme non vengono degradati; la crescita 1-20 passa dalle Skill.",
        "checkpoints": ["ufficiale completo", "manovre di comando", "cooperazione", "maestro d'arme", "comandante veterano"],
        "at_least_one": ["una manovra offensiva entro il livello 5"],
    },
    {
        "name": "Combattente Ashlander", "source": "966", "ids": [966],
        "category": "Dunmer", "core": "warrior", "core_share": 0.52, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + toolkit.WARRIOR, "races": ["Dunmer"],
        "subraces": ["Retaggio Guerriero"],
        "equipment": covered_equipment("966"),
        "fantasy": "Difensore nomade delle terre di cenere, temprato da caccia, viaggio e faide tribali.",
        "combat": "Mantiene la distanza con la lancia, passa all'ascia quando chiuso e usa il terreno invece della corazza pesante.",
        "archetype": "Guerriero Ashlander leggero con lancia, ascia e forte sopravvivenza.",
        "tags": {"core_fisico": 4, "focus_combat": 4, "attacco": 4, "esplorazione_infiltrazione": 4, "difesa": 2, "core_magico": -5},
        "competences": {"sopravvivenza": 5, "conoscenze_naturaegeografia": 5, "percezione": 4, "strategia_militare": 2, "diplomazia": -3},
        "siblings": [("Saggia Ashlander", "nearest", "Difesa fisica della tribù invece di guida spirituale."), ("Guerriero Forsworn", "same-role", "Lancia e cultura delle ceneri invece di imboscata della Reach."), ("Soldato Imperiale", "contrast", "Terreno e autonomia invece di formazione.")],
        "axes": [("nomade delle ceneri", "sopravvivenza/geografia e armatura Ashlander"), ("lancia tribale", "lancia o ascia con manovre melee")],
        "must": ["Dunmer", "Ashlander", "lancia", "sopravvivenza"], "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "lancia Ashlander o ascia d'acciaio", "legacy_range": "5-9",
        "range_reason": "Il singolo set tribale è identitario e viene mantenuto lungo 1-20.",
        "checkpoints": ["combattente nomade", "manovra di lancia", "veterano delle ceneri", "difensore tribale", "campione Ashlander"],
        "at_least_one": ["una manovra melee entro il livello 5"],
    },
    {
        "name": "Guardia Carovana", "source": "907-908-909", "ids": [907, 908, 909],
        "category": "Khajiit", "core": "warrior", "core_share": 0.56, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, base.SHIELD_ARCHETYPE, toolkit.WARRIOR),
        "races": ["Khajiit"], "subraces": ["Carovana"],
        "equipment": covered_equipment("907-908-909"),
        "fantasy": "Professionista delle rotte che protegge merci e viaggiatori da assalti, bestie e truffatori.",
        "combat": "Tiene il lato esposto della carovana con arma e scudo, legge il terreno e privilegia sopravvivenza e continuità.",
        "archetype": "Guardia Khajiit versatile con scudo, materiali progressivi e competenze di viaggio.",
        "tags": {"core_fisico": 4, "focus_combat": 4, "difesa": 5, "attacco": 3, "esplorazione_infiltrazione": 3, "core_magico": -5},
        "competences": {"percezione": 5, "sopravvivenza": 5, "gestione_risorse": 4, "strategia_militare": 3, "sapienza_magica": -4},
        "siblings": [("Mercenario", "nearest", "Protezione continuativa e scudo invece di contratto offensivo."), ("Soldato Imperiale", "same-role", "Rotte e sopravvivenza invece di Legione."), ("Esploratore Imperiale", "contrast", "Difende il convoglio, non opera davanti alla linea.")],
        "axes": [("protezione della rotta", "percezione/sopravvivenza e scudo"), ("adattamento al viaggio", "tre fasce complete di armi e armature")],
        "must": ["Khajiit", "carovana", "scudo", "sopravvivenza"], "must_not": ["magia", "arma a distanza", "fazione militare", "azioni innate"],
        "variation": "spada, ascia o mazza con percorso ferro-acciaio-nordico", "legacy_range": "1-15",
        "range_reason": "La fascia nordica finale viene estesa fino al 20 mantenendo la matrice originale.",
        "checkpoints": ["guardia operativa", "scudo e strada", "materiale d'acciaio", "set nordico", "veterano delle rotte"],
        "at_least_one": ["una Skill difensiva e una melee entro il livello 5"],
    },
    {
        "name": "Giustiziere Thalmor", "source": "958", "ids": [958],
        "category": "Altmer", "core": "mage", "core_share": 0.46, "magic": "any",
        "skills": unique_skills(base.MAGE_CORE, previous.DUELIST, previous.ILLUSION),
        "races": ["Altmer"], "subraces": ["Sangue Nobile"],
        "equipment": covered_equipment("958"),
        "fantasy": "Esecutore pubblico del Dominion che combina autorità, duello e magia di coercizione.",
        "combat": "Acceca o terrorizza il bersaglio, poi chiude con armblade o katana; non si comporta come una spia.",
        "archetype": "Giustiziere Altmer ibrido Illusione-lama con equipaggiamento Thalmor d'élite.",
        "tags": {"core_magico": 4, "focus_combat": 4, "controllo_situazionale": 5, "attacco": 4, "sociale": 3},
        "competences": {"intimidire": 5, "sapienza_magica": 4, "strategia_militare": 4, "percezione": 3, "furtivita": -3},
        "siblings": [("Agente Thalmor", "nearest", "Esecuzione pubblica e duello invece di infiltrazione."), ("Duellante", "same-weapon", "Coercizione arcana e autorità politica invece di onore privato."), ("Mago da Battaglia Imperiale", "contrast", "Illusione e lama leggera, non evocazione corazzata.")],
        "axes": [("autorità del Dominion", "Altmer, intimidire e dotazione Thalmor"), ("condanna arcana", "Illusione seguita da Affondo/Parata")],
        "must": ["Altmer", "Thalmor", "Illusione", "lama"], "must_not": ["furtività primaria", "scudo", "cura", "azioni innate"],
        "variation": "armblade o katana con diversa coercizione Illusione", "legacy_range": "15-20",
        "range_reason": "Il rango e il set d'élite restano fissi; le Skill scalano da 1 a 20.",
        "checkpoints": ["giustiziere completo", "Acceca o Paura", "duello arcano", "controllo avanzato", "esecutore del Dominion"],
        "at_least_one": ["una Skill Illusione entro il livello 1"],
    },
    {
        "name": "Mago da Battaglia Imperiale", "source": "845-846", "ids": [845, 846],
        "category": "Imperiale", "core": "specialist", "core_share": 0.5, "magic": "any",
        "skills": deepcopy(base.MAGE_CORE) + BATTLE_MAGE, "races": ["Imperiale"],
        "subraces": ["Apprendista"],
        "equipment": covered_equipment("845-846"),
        "fantasy": "Incantatore militare della Legione addestrato a mantenere la formula sotto il peso dell'armatura.",
        "combat": "Alterna spada e staff, usa sigilli e teletrasporto per sostenere la linea e banna minacce evocate.",
        "archetype": "Battlemage Imperiale corazzato con Evocazione tattica e arma secondaria.",
        "tags": {"core_magico": 4, "core_fisico": 3, "focus_combat": 4, "controllo_situazionale": 4, "difesa": 3},
        "competences": {"sapienza_magica": 5, "strategia_militare": 5, "percezione": 3, "furtivita": -5},
        "siblings": [("Mago da Battaglia", "nearest", "Dottrina e armatura Imperiale sostituiscono neutralità."), ("Comandante della Legione Imperiale", "same-faction", "Sigilli e mobilità arcana invece di comando puro."), ("Giustiziere Thalmor", "contrast", "Evocazione corazzata invece di Illusione leggera.")],
        "axes": [("dottrina battlemage", "Imperiale, strategia e armatura di servizio"), ("Evocazione tattica", "Sigilli, Teleport e Banna")],
        "must": ["Imperiale", "battlemage", "Evocazione", "armatura di servizio"], "must_not": ["furtività", "cura primaria", "azioni innate", "veste senza armatura"],
        "variation": "spada o staff di Evocazione per fascia", "legacy_range": "10-20",
        "range_reason": "La prima fascia viene estesa ai livelli bassi mantenendo l'uniforme.",
        "checkpoints": ["battlemage completo", "Sigilli", "Teleport", "Banna", "Forma Elementale"],
        "at_least_one": ["Sigilli o Affondo entro il livello 1"],
    },
    {
        "name": "Sacerdote del Tribunale", "source": "929-930", "ids": [929, 930],
        "category": "Dunmer", "core": "support", "core_share": 0.46, "magic": "any",
        "skills": SUPPORT_CORE + RECOVERY, "races": ["Dunmer"],
        "subraces": ["Servo del Tribunale"],
        "equipment": covered_equipment("929-930"),
        "fantasy": "Custode della fede del Tribunale che sostiene comunità e fedeli attraverso rito, cura e autorità.",
        "combat": "Stabilizza, cura e rimuove condizioni dalla seconda linea, usando staff e veste come segni liturgici.",
        "archetype": "Sacerdote Dunmer di supporto con Recupero, medicina e dotazione rituale.",
        "tags": {"supporto_party": 5, "core_magico": 4, "sociale": 5, "difesa": 2, "attacco": -4},
        "competences": {"conoscenze_religioni": 5, "diplomazia": 5, "sapienza_magica": 4, "intuizione": 4, "intimidire": -3},
        "siblings": [("Guaritore", "nearest", "Autorità religiosa Dunmer e rito sostituiscono neutralità clinica."), ("Ordinatore", "same-faith", "Cura e parola invece di scudo e repressione."), ("Mago Telvanni", "contrast", "Servizio comunitario invece di ambizione personale.")],
        "axes": [("voce del Tribunale", "Dunmer, religioni e diplomazia"), ("rito di Recupero", "staff/veste e Skill di cura")],
        "must": ["Dunmer", "Tribunale", "Recupero", "supporto"], "must_not": ["magia offensiva", "armatura", "assassinio", "azioni innate"],
        "variation": "staff qualificato o maestro con cure diverse", "legacy_range": "10-20",
        "range_reason": "La dotazione rituale iniziale viene estesa senza aggiungere armi offensive.",
        "checkpoints": ["sacerdote completo", "stabilizzazione", "Cura", "rimozione status", "alto officiante"],
        "at_least_one": ["Stabilizza o Cicatrizza entro il livello 1"],
    },
    {
        "name": "Signore della Guerra Orco", "source": "921", "ids": [921],
        "category": "Orsimer", "core": "warrior", "core_share": 0.58, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, COMMANDER), "classes": ["Cavaliere"],
        "races": ["Orsimer"], "subraces": ["Della Tribù"],
        "equipment": covered_equipment("921"),
        "fantasy": "Capo militare di roccaforte che converte forza personale in disciplina del clan.",
        "combat": "Guida dalla prima linea con ascia o martello a due mani e coordina alleati invece di cedere alla furia.",
        "archetype": "Comandante Orsimer pesante con armi dwemer e autorità di clan.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 4, "sociale": 3, "core_magico": -5},
        "competences": {"strategia_militare": 5, "intimidire": 5, "sopravvivenza": 4, "diplomazia": 2, "raggirare": -5},
        "siblings": [("Berserker Orco", "nearest", "Comando e disciplina sostituiscono Ira e Bloodlust."), ("Comandante della Legione Imperiale", "same-role", "Codice del clan e arma dwemer invece di formazione legionaria."), ("Bandito Capo", "contrast", "Autorità legittima della roccaforte, non paura criminale.")],
        "axes": [("comando del clan", "strategia/intimidire e Skill Cavaliere"), ("campione dwemer", "armatura e arma pesante dwemer")],
        "must": ["Orsimer", "comando", "arma a due mani", "armatura dwemer"], "must_not": ["magia", "furia berserker", "scudo", "azioni innate"],
        "variation": "ascia o martello dwemer", "legacy_range": "18-20",
        "range_reason": "Rango e set dwemer restano iconici; la progressione dipende dalle Skill.",
        "checkpoints": ["signore della guerra completo", "manovre", "comando cooperativo", "maestro d'arme", "capo della roccaforte"],
        "at_least_one": ["una manovra offensiva entro il livello 5"],
    },
    {
        "name": "Principe Dremora", "source": "970", "ids": [970],
        "category": "Dremora", "core": "warrior", "core_share": 0.56, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, COMMANDER), "classes": ["Cavaliere"],
        "races": ["Dremora"], "subraces": ["Valkynaz"],
        "equipment": [entry for entry in covered_equipment("970") if entry["slot"] != "scudo"],
        "kind_reason": "Impugna armi, porta armatura e segue una gerarchia marziale: Dremora/Valkynaz è il contratto humanoid corretto.",
        "fantasy": "Principe guerriero al vertice della gerarchia Dremora, incarnazione di rango e disciplina daedrica.",
        "combat": "Avanza con spadone o martello daedrico, coordina i subordinati e domina la prima linea senza trucchi da creatura.",
        "archetype": "Valkynaz pesante con arma a due mani daedrica e comando d'élite.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 4, "sociale": 3, "core_magico": -5},
        "competences": {"intimidire": 5, "strategia_militare": 5, "percezione": 3, "diplomazia": -4, "raggirare": -5},
        "siblings": [("Soldato Dremora", "nearest", "Rango Valkynaz, arma a due mani e comando sostituiscono ruolo di linea."), ("Signore Dremora", "same-race", "Principe guerriero apicale, non ufficiale intermedio."), ("Signore della Guerra Orco", "contrast", "Gerarchia daedrica e set daedrico invece di clan mortale.")],
        "axes": [("rango Valkynaz", "razza/sottorazza bloccate e comando"), ("arsenale daedrico", "spadone o martello con armatura fissa")],
        "must": ["Dremora", "Valkynaz", "arma daedrica", "comando"], "must_not": ["magia", "scudo con arma a due mani", "azioni innate", "razza mortale"],
        "variation": "spadone o martello daedrico", "legacy_range": "solo livello 20",
        "range_reason": "Il rango Valkynaz e il set daedrico sono front-loaded e non vengono degradati.",
        "checkpoints": ["Valkynaz completo", "manovre pesanti", "comando", "maestro d'arme", "principe guerriero"],
        "at_least_one": ["razza Dremora/Valkynaz in ogni variante"],
        "extra_rejected": [{
            "candidate": {"slot": "scudo", "itemId": 622, "name": "Scudo (daedrico)"},
            "decision": "reject",
            "reasonCode": "two-handed-loadout-conflict",
            "reason": "Il Principe usa esclusivamente spadone o martello a due mani; equipaggiare anche lo scudo produrrebbe un loadout incoerente.",
        }],
        "extra_deviations": [{
            "what": "scudo legacy",
            "from": "Scudo (daedrico) presente nella riga 970",
            "to": "rimosso dal pool",
            "why": "Conflitto esplicito con entrambe le armi a due mani preservate.",
        }],
    },
]


SPECTRAL_BLADE = {
    "key": "batch4-lama-spettrale",
    "name": "Lama Spettrale",
    "description": "Bersaglio adiacente. La lama incorporata nella manifestazione infligge danni da Taglio ed è parte dello Spettro: non può essere disarmata o raccolta.",
    "minLevel": 1, "maxLevel": 20,
    "costs": {"pa": 4, "energia": 2},
    "trigger": "Azione", "duration": "Istantanea", "icon": "lama",
}

STEAM_MACE = {
    "key": "batch4-mazza-vapore-integrata",
    "name": "Mazza a Vapore Integrata",
    "description": "Bersaglio adiacente. Il Centurione scarica il pistone e colpisce con la mazza incorporata, infliggendo danni Contundenti; l'arma non può essere disarmata.",
    "minLevel": 1, "maxLevel": 20,
    "costs": {"pa": 5, "energia": 3},
    "trigger": "Azione", "duration": "Istantanea", "icon": "martello",
}


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Operaio Kwama", "source": "980", "ids": [980], "category": "Animale",
        "fantasy": "Casta laboriosa della colonia Kwama, costruita per scavare, trasportare e sopravvivere.",
        "combat": "Non cerca lo scontro: resiste grazie alla pelle rigenerativa e protegge il percorso verso il nido.",
        "archetype": "Creatura da nido resistente ma poco offensiva con rigenerazione naturale.",
        "siblings": [("Guerriero Kwama", "nearest", "Lavoro e sopravvivenza invece di carica e veleno."), ("Regina Kwama", "same-colony", "Casta subordinata senza controllo della covata."), ("Scrib", "contrast", "Più robusto e operaio, non giovane raccoglitore.")],
        "axes": [("casta operaia", "attacco basso e chassis resistente"), ("pelle rigenerativa", "unica azione identitaria")],
        "must": ["Kwama", "rigenerazione", "nido", "Mana zero"], "must_not": ["veleno", "evocazione", "carica"],
        "checkpoints": ["operaio riconoscibile", "rigenerazione", "tenacia del nido", "operaio maturo", "guardiano dei tunnel"],
        "range_reason": "La riga 20 viene linearizzata senza aggiungere azioni da Guerriero.", "at_least_one": ["solo Pelle Rigenerativa come azione"],
    },
    {
        "name": "Orso delle Caverne", "source": "984", "ids": [984], "category": "Animale",
        "fantasy": "Grande onnivoro territoriale che difende tana e cuccioli con massa e ferocia.",
        "combat": "Carica, entra in Furia e recupera dalle ferite; vince attraverso pressione frontale prolungata.",
        "archetype": "Orso massiccio da carica e Furia con rigenerazione.",
        "siblings": [("Orso delle Nevi", "nearest", "Furia e carica continua invece di pestone e adattamento al gelo."), ("Kagouti", "same-role", "Più resistente e rigenerante, meno rapido."), ("Troll", "contrast", "Animale territoriale, non mostro rigenerante intelligente.")],
        "axes": [("massa della caverna", "PF/forza e Carica"), ("ferocia territoriale", "Furia e Pelle Rigenerativa")],
        "must": ["orso", "carica", "Furia", "Mana zero"], "must_not": ["gelo offensivo", "pestone"],
        "checkpoints": ["orso territoriale", "carica", "Furia", "rigenerazione", "dominatore della tana"],
        "range_reason": "Gli endpoint 20 diventano una progressione lineare mantenendo Mana zero.", "at_least_one": ["Furia presente e nessun Pestone Tonante"],
    },
    {
        "name": "Orso delle Nevi", "source": "983", "ids": [983], "category": "Animale",
        "fantasy": "Orso artico enorme, adattato a valanghe, gelo e prede capaci di reagire.",
        "combat": "Carica per chiudere, usa il pestone per controllare l'area e rigenera senza entrare in Furia.",
        "archetype": "Orso artico da controllo ravvicinato con carica, pestone e resistenza al gelo.",
        "siblings": [("Orso delle Caverne", "nearest", "Pestone e gelo sostituiscono Furia."), ("Lupo delle Nevi", "same-biome", "Massa e controllo invece di balzo di branco."), ("Troll del Gelo", "contrast", "Animale senza pelle di pietra o soffio.")],
        "axes": [("massa artica", "PF e Pestone Tonante"), ("adattamento al gelo", "res/rd_gelo e assenza di Furia")],
        "must": ["orso", "gelo", "pestone", "Mana zero"], "must_not": ["Furia", "soffio gelido"],
        "checkpoints": ["orso artico", "carica", "pestone", "resistenza glaciale", "signore delle nevi"],
        "range_reason": "La riga 20 viene estesa preservando la firma di controllo.", "at_least_one": ["Pestone Tonante presente e Furia assente"],
    },
    {
        "name": "Scamp", "source": "997", "ids": [997], "category": "Daedra",
        "fantasy": "Daedra minore dispettoso che compensa fragilità con fuoco e sabotaggio delle risorse.",
        "combat": "Resta a media distanza, lancia fuoco, brucia Mana e usa Furia soltanto quando viene chiuso.",
        "archetype": "Caster Daedra minore con Palla di Fuoco e Bruciatura di Mana.",
        "siblings": [("Atronach di Fuoco", "nearest", "Più fragile e opportunista, con sabotaggio Mana invece di aura."), ("Clannfear", "same-rank", "Caster minore invece di predatore fisico."), ("Hunger", "contrast", "Fuoco e disturbo, non drenaggio sostenuto.")],
        "axes": [("piromante minore", "Palla di Fuoco e Mana"), ("sabotatore", "Bruciatura di Mana")],
        "must": ["Daedra", "fuoco", "Bruciatura di Mana", "fragilità"], "must_not": ["volo", "armatura elementale"],
        "checkpoints": ["Scamp riconoscibile", "fuoco", "bruciatura Mana", "Furia d'emergenza", "Scamp veterano"],
        "range_reason": "Gli endpoint vengono linearizzati senza elevarlo al rango di Atronach.", "at_least_one": ["Palla di Fuoco e Bruciatura di Mana presenti"],
    },
    {
        "name": "Segugio di Xivilai", "source": "1005", "ids": [1005], "category": "Daedra",
        "fantasy": "Predatore daedrico allevato per inseguire, balzare e ricomparire alle spalle della preda.",
        "combat": "Usa Balzo e Passo d'Ombra per negare distanza, poi entra in Furia; non possiede magia offensiva.",
        "archetype": "Segugio Daedra mobile con balzo, ombra e Furia.",
        "siblings": [("Clannfear", "nearest", "Ombra e inseguimento invece di carica e coda."), ("Lupo delle Nevi", "same-role", "Teletrasporto daedrico invece di adattamento naturale."), ("Crepuscolo Alato", "contrast", "Terrestre e fisico, non volante e mentale.")],
        "axes": [("caccia d'ombra", "Passo d'Ombra e Balzo Predatorio"), ("ferocia daedrica", "Furia e chassis fisico")],
        "must": ["Daedra", "balzo", "ombra", "Furia"], "must_not": ["volo", "incantesimi a distanza"],
        "checkpoints": ["segugio daedrico", "balzo", "Passo d'Ombra", "Furia", "cacciatore di Xivilai"],
        "range_reason": "La riga 20 viene estesa mantenendo Mana zero e mobilità innata.", "at_least_one": ["Balzo Predatorio e Passo d'Ombra presenti"],
    },
    {
        "name": "Spettro", "source": "1017", "ids": [1017], "category": "Non morto",
        "fantasy": "Spirito guerriero aggressivo che conserva una lama come parte della propria manifestazione.",
        "combat": "Alterna forma eterea e fase per entrare in mischia, colpisce con la lama e drena lo spirito.",
        "archetype": "Non morto incorporeo offensivo con lama innata, fase e drenaggio.",
        "actions": toolkit.source_actions("1017") + [deepcopy(SPECTRAL_BLADE)],
        "siblings": [("Fantasma", "nearest", "Lama e aggressione melee sostituiscono difesa legata al luogo."), ("Drago Spettrale", "same-state", "Scala umanoide senza volo o soffio."), ("Draugr Signore della Morte", "contrast", "Incorporeo senza equipaggiamento o Skill.")],
        "axes": [("guerriero incorporeo", "Lama Spettrale e PF superiori al Fantasma"), ("fase predatoria", "Forma Eterea, Spostamento e drenaggio")],
        "must": ["forma eterea", "lama spettrale", "drenaggio", "gelo"], "must_not": ["equipment", "corpo osseo"],
        "checkpoints": ["spettro armato", "fase", "drenaggio", "assalto incorporeo", "spettro maggiore"],
        "range_reason": "La spada legacy diventa azione innata; curve e resistenze restano lineari.", "at_least_one": ["Lama Spettrale presente"],
        "extra_rejected": [{
            "candidate": {"slot": "arma", "name": "Spada lunga (vetro)"},
            "decision": "reject",
            "reasonCode": "creature-equipment-contract",
            "reason": "Lo Spettro è creature: la lama viene incorporata nell'azione innata e non equipaggiata.",
        }],
    },
    {
        "name": "Spriggan Bruciato", "source": "1019", "ids": [1019], "category": "Natura",
        "fantasy": "Spirito arboreo consumato dal fuoco che ora usa le fiamme contro chi invade il territorio.",
        "combat": "Blocca con radici, sottrae vita e punisce la distanza con Palla di Fuoco; non evoca alleati.",
        "archetype": "Controllore naturale corrotto con radici, drenaggio e fuoco.",
        "siblings": [("Spriggan", "nearest", "Fuoco e aggressione sostituiscono evocazione della natura."), ("Atronach di Fuoco", "same-element", "Radici e drenaggio organico invece di puro elemento."), ("Hunger", "contrast", "Controllo del terreno, non predazione mobile.")],
        "axes": [("natura bruciata", "Palla di Fuoco e resistenze alterate"), ("radici affamate", "Radici Intrappolanti e Sottrai Vita")],
        "must": ["radici", "fuoco", "drenaggio", "Mana"], "must_not": ["Evoca Minion", "volo"],
        "checkpoints": ["Spriggan bruciato", "radici", "drenaggio", "fuoco", "spirito incendiato"],
        "range_reason": "Gli endpoint preservano il profilo superiore e la corruzione elementale.", "at_least_one": ["Palla di Fuoco presente e Evoca Minion assente"],
    },
    {
        "name": "Steam Centurion", "source": "1030", "ids": [1030], "category": "Costrutto",
        "fantasy": "Automa Dwemer mosso da pistoni e pressione, progettato per sfondare corridoi fortificati.",
        "combat": "Avanza lentamente e scarica una mazza integrata alimentata a vapore; non usa Mana o equipaggiamento.",
        "archetype": "Costrutto pesante con mazza a vapore, riduzione fisica costante e grande massa.",
        "curve_overrides": {"mana": (0, 0)},
        "actions": [deepcopy(STEAM_MACE)],
        "siblings": [("Centurione Nanico", "nearest", "Pistone e mazza compatta invece di colosso da guerra completo."), ("Sfera Dwemer", "same-origin", "Massa e impatto invece di mobilità e lama."), ("Ogrim", "contrast", "Costrutto disciplinato, non bruto daedrico.")],
        "axes": [("pressione a vapore", "energia e Mazza a Vapore Integrata"), ("corazza Dwemer", "rd_fis costante e PF elevati")],
        "must": ["Dwemer", "vapore", "mazza integrata", "Mana zero"], "must_not": ["equipment", "Skill", "magia"],
        "checkpoints": ["automa a vapore", "mazza integrata", "corazza", "pistoni veterani", "Steam Centurion d'élite"],
        "range_reason": "La mazza legacy diventa azione innata e Mana viene azzerato per il costrutto.", "at_least_one": ["Mazza a Vapore Integrata presente"],
        "extra_rejected": [{
            "candidate": {"slot": "arma", "name": "Mazza (dwemer)"},
            "decision": "reject",
            "reasonCode": "creature-equipment-contract",
            "reason": "Il costrutto non può equipaggiare oggetti: la mazza è parte del telaio.",
        }],
    },
    {
        "name": "Troll", "source": "1022", "ids": [1022], "category": "Natura",
        "fantasy": "Mostro cavernicolo ostinato che trasforma ogni pausa dell'avversario in rigenerazione.",
        "combat": "Preme in mischia, usa Furia e Pestone e deve essere abbattuto rapidamente prima che recuperi.",
        "archetype": "Bruto rigenerante con Furia, pestone e forte vulnerabilità al fuoco.",
        "siblings": [("Troll del Gelo", "nearest", "Pestone e massa neutrale invece di pietra e soffio gelido."), ("Ogrim", "same-scale", "Rigenerazione biologica e debolezza al fuoco, non pelle daedrica."), ("Orso delle Caverne", "contrast", "Mostro persistente con pestone, non animale territoriale.")],
        "axes": [("rigenerazione troll", "Pelle Rigenerativa e PF"), ("bruto cavernicolo", "Furia e Pestone Tonante")],
        "must": ["rigenerazione", "Furia", "pestone", "Mana zero"], "must_not": ["gelo offensivo", "pelle di pietra"],
        "checkpoints": ["Troll riconoscibile", "rigenerazione", "Furia", "pestone", "Troll antico"],
        "range_reason": "La riga 20 viene linearizzata mantenendo la debolezza al fuoco.", "at_least_one": ["res_fuoco negativa e Soffio Gelido assente"],
    },
    {
        "name": "Troll del Gelo", "source": "1021", "ids": [1021], "category": "Natura",
        "fantasy": "Troll artico corazzato dal gelo, più resistente e controllato del cugino cavernicolo.",
        "combat": "Indurisce la pelle, rigenera, entra in Furia e usa il soffio gelido per impedire la fuga.",
        "archetype": "Bruto artico con pelle di pietra, rigenerazione e soffio gelido.",
        "siblings": [("Troll", "nearest", "Gelo, pelle di pietra e soffio sostituiscono pestone."), ("Orso delle Nevi", "same-biome", "Mostro rigenerante con soffio, non animale da carica."), ("Atronach del Gelo", "contrast", "Bruto biologico senza armatura elementale o tormenta.")],
        "axes": [("corazza glaciale", "Pelle di Pietra e res_gelo"), ("predazione artica", "Soffio Gelido e rigenerazione")],
        "must": ["gelo", "rigenerazione", "pelle di pietra", "soffio"], "must_not": ["Pestone Tonante", "Mana"],
        "checkpoints": ["Troll artico", "rigenerazione", "pelle di pietra", "soffio gelido", "Troll del Gelo antico"],
        "range_reason": "Gli endpoint conservano la superiorità artica senza trasformarlo in Atronach.", "at_least_one": ["Soffio Gelido presente e Pestone Tonante assente"],
    },
]


BATCH_CANDIDATES = [humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"batch4-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-batch4"


if __name__ == "__main__":
    base.main()
