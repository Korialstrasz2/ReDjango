from __future__ import annotations

from copy import deepcopy
from typing import Any

import elder_unit_calibration_v2 as base
import elder_unit_batch2_v2 as toolkit


OUTPUT_ROOT = base.WORKSPACE_ROOT / "elder-unit-batch-3-v2" / "authored"
toolkit.BATCH_LABEL = "Batch 3 v2"


def covered_equipment(source_file: str) -> list[dict[str, Any]]:
    """Extend the source's outer bands to 1 and 20 without changing its tier order."""
    entries = toolkit.source_equipment(source_file)
    slots = {str(entry["slot"]) for entry in entries}
    for slot in slots:
        slot_entries = [entry for entry in entries if entry["slot"] == slot]
        first = min(int(entry["minLevel"]) for entry in slot_entries)
        last = max(int(entry["maxLevel"]) for entry in slot_entries)
        for entry in slot_entries:
            if int(entry["minLevel"]) == first:
                entry["minLevel"] = 1
            if int(entry["maxLevel"]) == last:
                entry["maxLevel"] = 20
    return entries


def unique_skills(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for entry in (skill for pool in pools for skill in pool):
        by_id.setdefault(int(entry["skillId"]), deepcopy(entry))
    return list(by_id.values())


BARBARIAN = [
    base.skill(585, "archetype", 8),
    base.skill(586, "archetype", 7, 4),
    base.skill(587, "archetype", 6, 5),
    base.skill(588, "archetype", 8, 3),
    base.skill(589, "archetype", 7, 4),
    base.skill(591, "archetype", 6, 7),
    base.skill(592, "archetype", 5, 8),
    base.skill(593, "archetype", 6, 5),
    base.skill(594, "archetype", 5, 9),
    base.skill(1342, "archetype", 6, 10),
]

DUELIST = [
    base.skill(306, "archetype", 9),
    base.skill(321, "archetype", 7),
    base.skill(330, "archetype", 8),
    base.skill(331, "archetype", 9),
    base.skill(328, "archetype", 7, 4),
    base.skill(324, "archetype", 6, 5),
    base.skill(333, "archetype", 5, 8),
    base.skill(1010, "archetype", 5, 10),
]

ILLUSION = [
    base.skill(426, "archetype", 9),
    base.skill(427, "archetype", 8),
    base.skill(1210, "archetype", 6, 4),
    base.skill(1168, "archetype", 7, 6),
    base.skill(431, "archetype", 6, 8),
]

NECROMANCY = [
    base.skill(432, "archetype", 8),
    base.skill(435, "archetype", 9, 4),
    base.skill(437, "archetype", 6, 7),
    base.skill(1167, "archetype", 7, 5),
    base.skill(1311, "archetype", 6, 8),
    base.skill(1312, "archetype", 7, 10),
    base.skill(1449, "archetype", 8, 4),
]


HUMANOID_SPECS: list[dict[str, Any]] = [
    {
        "name": "Agente Hlaalu", "source": "938-939", "ids": [938, 939],
        "category": "Dunmer", "core": "stealth", "core_share": 0.5, "magic": "none",
        "skills": toolkit.STEALTH_CORE + toolkit.THIEF, "races": ["Dunmer"], "classes": ["Ladro"],
        "equipment": covered_equipment("938-939"),
        "fantasy": "Intermediario Hlaalu che trasforma cortesia, informazione e denaro in vantaggio.",
        "combat": "Evita la linea frontale, usa una lama corta quando la trattativa fallisce e conserva sempre una via di fuga.",
        "archetype": "Spia Hlaalu sociale e furtiva con lame corte ed equipaggiamento d'ossa.",
        "tags": {"esplorazione_infiltrazione": 5, "tecnica_crafting": 3, "attacco": 2, "difesa": 1, "core_magico": -5},
        "competences": {"raggirare": 5, "diplomazia": 5, "furtivita": 4, "rapidita_di_mano": 3, "intimidire": -4},
        "siblings": [("Agente Morag Tong", "nearest", "Influenza e fuga sostituiscono omicidio rituale."), ("Ladro (standard)", "same-role", "Rete politica Hlaalu e diplomazia sostituiscono furto neutrale."), ("Cavaliere Redoran", "contrast", "Sottigliezza urbana invece di onore marziale.")],
        "axes": [("influenza Hlaalu", "diplomazia/raggirare e abiti civili"), ("lama discreta", "coltelli Hlaalu e Core furtivo")],
        "must": ["Dunmer", "Hlaalu", "furtività", "diplomazia"], "must_not": ["magia", "armatura pesante", "azioni innate", "assassinio rituale"],
        "variation": "coltello o daga e veste sociale per fascia", "legacy_range": "5-14",
        "range_reason": "Le fasce esterne riusano gli stessi vincoli Hlaalu senza introdurre materiali estranei.",
        "checkpoints": ["agente riconoscibile", "fuga e contatti", "lama dwemer", "operatore esperto", "maestro d'influenza"],
        "at_least_one": ["una Skill da Ladro e raggirare 5 entro il livello 5"],
    },
    {
        "name": "Agente Thalmor", "source": "959", "ids": [959],
        "category": "Altmer", "core": "stealth", "core_share": 0.46, "magic": "any",
        "skills": toolkit.STEALTH_CORE + toolkit.THIEF + ILLUSION, "races": ["Altmer"], "classes": ["Ladro"],
        "equipment": covered_equipment("959"),
        "fantasy": "Operativo del Dominion che unisce privilegio politico, infiltrazione e coercizione arcana.",
        "combat": "Isola il bersaglio con Illusione, entra con armblade o katana e si ritira prima di uno scontro prolungato.",
        "archetype": "Agente Altmer ibrido furtivo-Illusione con equipaggiamento Thalmor.",
        "tags": {"esplorazione_infiltrazione": 5, "controllo_situazionale": 4, "core_magico": 3, "attacco": 3, "difesa": 1},
        "competences": {"intimidire": 5, "raggirare": 4, "furtivita": 4, "sapienza_magica": 4, "diplomazia": 2},
        "siblings": [("Giustiziere Thalmor", "nearest", "Infiltrazione e Illusione invece di autorità marziale pubblica."), ("Agente Hlaalu", "same-role", "Coercizione ideologica e magia invece di commercio."), ("Mago Telvanni", "contrast", "Operativo armato, non studioso arcano.")],
        "axes": [("coercizione Thalmor", "Altmer, intimidire e Illusione"), ("lama diplomatica", "armblade/katana e Core furtivo")],
        "must": ["Altmer", "Thalmor", "Illusione", "lama"], "must_not": ["scudo", "brutalità da berserker", "azioni innate", "magia di cura"],
        "variation": "armblade o katana con controllo Illusione", "legacy_range": "10-14",
        "range_reason": "La firma Thalmor è iconica e resta invariata; la progressione avviene nelle Skill.",
        "checkpoints": ["operativo completo", "prima coercizione", "infiltratore arcano", "agente veterano", "lama del Dominion"],
        "at_least_one": ["una Skill Illusione e una furtiva entro il livello 5"],
    },
    {
        "name": "Arciere Redoran", "source": "942-943", "ids": [942, 943],
        "category": "Dunmer", "core": "stealth", "core_share": 0.46, "magic": "none",
        "skills": toolkit.ARCHER_CORE + toolkit.ARCHERY + toolkit.PURE_ARCHERY_CEILING,
        "races": ["Dunmer"], "equipment": covered_equipment("942-943"),
        "fantasy": "Miliziano Redoran che porta disciplina, armatura d'ossa e tiro controllato nelle terre di cenere.",
        "combat": "Mantiene distanza con l'arco lungo, usa il coltello solo quando chiuso e non abbandona la posizione assegnata.",
        "archetype": "Arciere Dunmer di Casa Redoran con armatura d'ossa e arco lungo.",
        "tags": {"focus_combat": 4, "range_skill": 5, "difesa": 3, "attacco": 4, "core_magico": -5},
        "competences": {"percezione": 5, "strategia_militare": 4, "sopravvivenza": 3, "furtivita": 2, "raggirare": -4},
        "siblings": [("Arciere (standard)", "nearest", "Disciplina Redoran e armatura d'ossa sostituiscono neutralità."), ("Cavaliere Redoran", "same-house", "Tiro e mobilità invece di scudo e prima linea."), ("Cacciatore Bosmer", "contrast", "Milizia di casata invece di caccia nel bosco.")],
        "axes": [("milizia Redoran", "Dunmer, armatura Redoran e strategia"), ("tiro d'onore", "arco lungo e tecniche disciplinate")],
        "must": ["Dunmer", "Redoran", "arco lungo", "armatura d'ossa"], "must_not": ["magia", "scudo", "agguato banditesco", "azioni innate"],
        "variation": "arco lungo e coltello acciaio o dwemer", "legacy_range": "5-14",
        "range_reason": "Gli stessi materiali esterni preservano la divisa Redoran lungo 1-20.",
        "checkpoints": ["miliziano completo", "tiro disciplinato", "arsenale dwemer", "veterano Redoran", "tiratore di casata"],
        "at_least_one": ["una tecnica di tiro entro il livello 5"],
    },
    {
        "name": "Bandito Capo", "source": "949-950", "ids": [949, 950],
        "category": "Umano", "core": "warrior", "core_share": 0.54, "magic": "none",
        "skills": unique_skills(base.PHYSICAL_CORE, base.SHIELD_ARCHETYPE, toolkit.WARRIOR),
        "races": toolkit.MORTAL_RACES, "equipment": covered_equipment("949-950"),
        "fantasy": "Fuorilegge che ha trasformato forza, bottino e paura in una banda organizzata.",
        "combat": "Tiene il centro con arma e scudo, ordina l'imboscata e usa equipaggiamento rubato migliore dei sottoposti.",
        "archetype": "Capobanda tank con arsenale misto, scudo e comando intimidatorio.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "difesa": 4, "attacco": 4, "controllo_situazionale": 3, "core_magico": -5},
        "competences": {"intimidire": 5, "strategia_militare": 4, "sopravvivenza": 3, "raggirare": 2, "diplomazia": -4},
        "siblings": [("Arciere Bandito", "nearest", "Comando, scudo e prima linea invece di agguato a distanza."), ("Mercenario", "same-space", "Autorità criminale invece di contratto professionale."), ("Guerriero (standard)", "contrast", "Bottino irregolare e intimidazione sostituiscono neutralità.")],
        "axes": [("capobanda", "intimidire/strategia e Skill difensive"), ("bottino superiore", "armi, armature e scudi misti per fascia")],
        "must": ["comando", "scudo", "arma marziale", "intimidire"], "must_not": ["magia", "arco", "disciplina legionaria", "azioni innate"],
        "variation": "spada, ascia o mazza con set rubato", "legacy_range": "8-17",
        "range_reason": "Le fasce esterne mantengono il materiale più vicino senza inventare un terzo set.",
        "checkpoints": ["capobanda riconoscibile", "scudo e comando", "arsenale misto", "predone veterano", "signore del covo"],
        "at_least_one": ["una Skill difensiva e una offensiva entro il livello 5"],
    },
    {
        "name": "Berserker Nord", "source": "862-863", "ids": [862, 863],
        "category": "Nord", "core": "warrior", "core_share": 0.48, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + BARBARIAN, "races": ["Nord"], "classes": ["Barbaro"],
        "equipment": covered_equipment("862-863"),
        "fantasy": "Campione nordico che considera la furia uno stato sacro e il dolore una prova.",
        "combat": "Entra con spadone, accetta di esporsi e converte ferite e slancio in pressione crescente.",
        "archetype": "Berserker Nord con spadone, chainmail e furia offensiva.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 1, "core_magico": -5},
        "competences": {"intimidire": 5, "sopravvivenza": 4, "scalare": 3, "strategia_militare": 1, "diplomazia": -5},
        "siblings": [("Barbaro Nord", "nearest", "Furia e spadone fisso sostituiscono pressione più controllata."), ("Berserker Orco", "same-role", "Rapidità nordica e chainmail invece di massa orchesca."), ("Guerriero (standard)", "contrast", "Aggressione senza scudo invece di equilibrio.")],
        "axes": [("furia nordica", "Skill Barbaro e razza Nord"), ("lama pesante", "spadone/Zweihander e tenuta al gelo")],
        "must": ["Nord", "Berserker", "spadone", "furia"], "must_not": ["magia", "scudo", "ritirata prudente", "azioni innate"],
        "variation": "Zweihander o spadone nordico/ebano", "legacy_range": "10-20",
        "range_reason": "L'identità resta iconica ai bassi livelli; cambia soltanto la maturità delle Skill.",
        "checkpoints": ["berserker completo", "Ira online", "Bloodlust", "arma d'ebano", "campione della furia"],
        "at_least_one": ["Ira o Bloodlust entro il livello 6"],
    },
    {
        "name": "Berserker Orco", "source": "919-920", "ids": [919, 920],
        "category": "Orsimer", "core": "warrior", "core_share": 0.52, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + BARBARIAN, "races": ["Orsimer"], "classes": ["Barbaro"],
        "equipment": covered_equipment("919-920"),
        "fantasy": "Campione di roccaforte che segue il Codice di Malacath attraverso forza e sopportazione.",
        "combat": "Avanza con ascia o martello a due mani, assorbe lo scambio e diventa più pericoloso col prolungarsi dello scontro.",
        "archetype": "Berserker Orsimer corazzato con armi pesanti e resistenza superiore.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "attacco": 5, "difesa": 3, "core_magico": -5},
        "competences": {"intimidire": 5, "sopravvivenza": 4, "strategia_militare": 2, "scalare": 2, "raggirare": -5},
        "siblings": [("Berserker Nord", "nearest", "Armatura e tenuta orchesca invece di slancio nordico."), ("Signore della Guerra Orco", "same-culture", "Furia individuale invece di comando del clan."), ("Bandito Capo", "contrast", "Codice e arma pesante, non scudo e opportunismo.")],
        "axes": [("tenacia Orsimer", "razza, armatura orchesca e Core fisico"), ("impatto pesante", "ascia/martello e Skill Barbaro")],
        "must": ["Orsimer", "arma a due mani", "armatura orchesca", "furia"], "must_not": ["magia", "scudo", "furtività", "azioni innate"],
        "variation": "ascia o martello orchesco/dwemer", "legacy_range": "10-20",
        "range_reason": "La dotazione di roccaforte rimane coerente anche sotto il livello sorgente.",
        "checkpoints": ["campione Orsimer", "Ira controllata", "tenuta corazzata", "arma dwemer", "berserker del clan"],
        "at_least_one": ["una Skill Barbaro entro il livello 5"],
    },
    {
        "name": "Duellante", "source": "852-853-854", "ids": [852, 853, 854],
        "category": "Umano", "core": "warrior", "core_share": 0.48, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + DUELIST, "races": toolkit.MORTAL_RACES,
        "equipment": covered_equipment("852-853-854"),
        "fantasy": "Spadaccino urbano che costruisce reputazione con precisione, misura e sfide pubbliche.",
        "combat": "Controlla la distanza corta, para con la lama e punisce l'apertura con un affondo.",
        "archetype": "Duellante leggero con fioretto o rapier, parata e precisione.",
        "tags": {"core_fisico": 3, "focus_combat": 5, "attacco": 4, "difesa": 3, "controllo_situazionale": 4, "core_magico": -5},
        "competences": {"percezione": 5, "intuizione": 4, "diplomazia": 3, "intimidire": 2, "sopravvivenza": -4},
        "siblings": [("Guerriero (standard)", "nearest", "Precisione senza scudo invece di versatilità marziale."), ("Agente Hlaalu", "same-gear", "Confronto pubblico invece di fuga e intrigo."), ("Berserker Nord", "contrast", "Misura e parata invece di furia.")],
        "axes": [("misura del duello", "Parata/Affondo e percezione"), ("lama elegante", "solo fioretto o rapier")],
        "must": ["fioretto", "parata", "affondo", "armatura leggera"], "must_not": ["magia", "scudo", "arma pesante", "azioni innate"],
        "variation": "fioretto o rapier per fascia materiale", "legacy_range": "5-20",
        "range_reason": "La prima fascia viene estesa soltanto ai livelli 1-4.",
        "checkpoints": ["duellante completo", "parata e affondo", "lama d'acciaio", "precisione veterana", "maestro di rapier"],
        "at_least_one": ["Parata o Affondo entro il livello 5"],
    },
    {
        "name": "Guerriero Forsworn", "source": "955-956", "ids": [955, 956],
        "category": "Bretone", "core": "warrior", "core_share": 0.5, "magic": "none",
        "skills": deepcopy(base.PHYSICAL_CORE) + BARBARIAN + toolkit.WARRIOR[:4],
        "races": ["Bretone"], "classes": ["Barbaro"], "equipment": covered_equipment("955-956"),
        "fantasy": "Guerriero delle Reach che combina ferocia tribale, mobilità e conoscenza del terreno.",
        "combat": "Aggredisce con ascia o spada, sfrutta copertura naturale e rifiuta la pesante disciplina degli eserciti.",
        "archetype": "Guerriero Forsworn leggero con armatura d'ossa e aggressione da imboscata.",
        "tags": {"core_fisico": 4, "focus_combat": 5, "attacco": 5, "esplorazione_infiltrazione": 3, "difesa": 2, "core_magico": -5},
        "competences": {"sopravvivenza": 5, "conoscenze_naturaegeografia": 4, "intimidire": 4, "furtivita": 3, "diplomazia": -5},
        "siblings": [("Briarheart Forsworn", "nearest", "Guerriero mortale senza cuore rituale o magia."), ("Barbaro Nord", "same-role", "Mobilità della Reach e armatura d'ossa invece di forza nordica."), ("Soldato Imperiale", "contrast", "Terreno e imboscata invece di formazione.")],
        "axes": [("guerriglia della Reach", "sopravvivenza/furtività"), ("ferocia leggera", "Skill Barbaro e armatura d'ossa")],
        "must": ["Bretone", "Forsworn", "armatura d'ossa", "sopravvivenza"], "must_not": ["magia", "scudo", "armatura pesante", "azioni innate"],
        "variation": "ascia o spada acciaio/nordico", "legacy_range": "8-17",
        "range_reason": "Le fasce esterne riusano gli stessi materiali senza anticipare un artefatto.",
        "checkpoints": ["guerriero della Reach", "ferocia mobile", "arma nordica", "veterano Forsworn", "campione tribale"],
        "at_least_one": ["una Skill Barbaro entro il livello 5"],
    },
    {
        "name": "Mago Scheletro", "source": "1011", "ids": [1011],
        "category": "Non morto", "core": "mage", "core_share": 0.48, "magic": "any",
        "skills": deepcopy(base.MAGE_CORE) + toolkit.DESTRUCTION + NECROMANCY,
        "races": ["Non morto"], "subraces": ["Scheletro"],
        "equipment": covered_equipment("868-869-870-871"),
        "kind_reason": "È un incantatore senziente con focus, veste e progressione Skill; Non morto/Scheletro sostituisce il vecchio contratto creature.",
        "fantasy": "Scheletro animato che conserva formule di Distruzione e le alimenta con energia necromantica.",
        "combat": "Gestisce distanza con fuoco e ossa evocate, usa oscurità per proteggersi e non cerca mai lo scambio fisico.",
        "archetype": "Mago Scheletro di Distruzione e Negromanzia con grande dipendenza dal Mana.",
        "tags": {"core_magico": 5, "natura_magica": 5, "range_skill": 4, "area_e_multi_target": 4, "core_fisico": -5},
        "competences": {"sapienza_magica": 5, "intimidire": 4, "percezione": 2, "diplomazia": -5, "raggirare": -4},
        "siblings": [("Mago (standard)", "nearest", "Scheletro e Negromanzia sostituiscono generalismo mortale."), ("Arciere Scheletro", "same-race", "Mana e formule invece di tiro fisico."), ("Lich", "same-origin", "Servitore arcano più fragile, non maestro immortale.")],
        "axes": [("scheletro incantatore", "Non morto/Scheletro e veste"), ("fuoco necromantico", "Distruzione più Negromanzia")],
        "must": ["Non morto", "Scheletro", "Mana", "Negromanzia"], "must_not": ["armatura pesante", "scudo", "azioni innate", "razza mortale"],
        "variation": "staff e veste per grado con ramo fuoco/ossa", "legacy_range": "solo livello 20",
        "range_reason": "La reclassificazione rende disponibile una progressione Skill completa 1-20.",
        "checkpoints": ["mago scheletro completo", "fuoco o lancia d'ossa", "oscurità difensiva", "rianimazione", "arcanista non morto"],
        "at_least_one": ["razza Non morto/Scheletro e una Skill magica entro il livello 1"],
    },
    {
        "name": "Draugr Signore della Morte", "source": "1015", "ids": [1015],
        "category": "Non morto", "core": "warrior", "core_share": 0.52, "magic": "any",
        "skills": deepcopy(base.PHYSICAL_CORE) + toolkit.WARRIOR + NECROMANCY,
        "races": ["Non morto"], "subraces": ["Draugr"],
        "equipment": [base.item("arma", 354), base.item("arma", 312)],
        "kind_reason": "Impugna armi d'ebano, usa discipline marziali e comanda magia funebre: è un humanoid Non morto/Draugr.",
        "fantasy": "Antico signore nordico che conserva rango, forza e autorità sui morti del tumulo.",
        "combat": "Avanza con arma pesante d'ebano, incute paura e usa rianimazione soltanto dopo aver stabilito il controllo fisico.",
        "archetype": "Élite Draugr ibrido guerriero-negromante con armi pesanti d'ebano.",
        "tags": {"core_fisico": 5, "focus_combat": 5, "core_magico": 3, "attacco": 5, "difesa": 4},
        "competences": {"intimidire": 5, "strategia_militare": 5, "sapienza_magica": 3, "percezione": 3, "diplomazia": -5},
        "siblings": [("Draugr Guerriero", "nearest", "Rango, ebano e Negromanzia sostituiscono il guardiano semplice."), ("Lich", "same-origin", "Prima linea pesante invece di dominio arcano puro."), ("Berserker Nord", "contrast", "Autorità funebre e magia invece di furia viva.")],
        "axes": [("signore del tumulo", "Non morto/Draugr, intimidire e Negromanzia"), ("campione d'ebano", "spadone o martello d'ebano")],
        "must": ["Non morto", "Draugr", "arma d'ebano", "Negromanzia"], "must_not": ["arma leggera", "razza mortale", "azioni innate", "equipaggiamento casuale"],
        "variation": "spadone o martello d'ebano e ramo marziale/necromantico", "legacy_range": "solo livello 20",
        "range_reason": "Il rango resta iconico a ogni livello; la potenza cresce tramite Skill, non downgrade dell'equipaggiamento.",
        "checkpoints": ["signore Draugr completo", "pressione pesante", "aura funebre", "rianimazione", "Signore della Morte"],
        "at_least_one": ["razza Non morto/Draugr e una Skill marziale entro il livello 1"],
    },
]


CREATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Capra dei Ghiacciai", "source": "989", "ids": [989], "category": "Animale",
        "fantasy": "Capra alpina ostinata, adattata a ghiaccio, quota e pendii impossibili.",
        "combat": "Scatta tra le rocce, recupera dalle ferite superficiali e usa mobilità invece di massa.",
        "archetype": "Animale rapido del gelo con scatto e rigenerazione leggera.",
        "siblings": [("Cinghiale", "nearest", "Mobilità verticale invece di carica massiccia."), ("Lupo delle Nevi", "same-biome", "Fuga e tenacia invece di caccia di branco."), ("Guar", "contrast", "Piccola e agile, non bestia da soma.")],
        "axes": [("passo alpino", "velocità e Scatto Rapido"), ("tenacia glaciale", "Pelle Rigenerativa e res_gelo crescente")],
        "must": ["gelo", "scatto", "rigenerazione", "Mana zero"], "must_not": ["predazione", "magia"],
        "checkpoints": ["capra alpina", "scatto", "rigenerazione", "resistenza glaciale", "veterana delle vette"],
        "range_reason": "La riga 20 viene distribuita mantenendo Mana zero e chassis leggero.", "at_least_one": ["mana 0 a ogni livello"],
    },
    {
        "name": "Fantasma", "source": "1016", "ids": [1016], "category": "Non morto",
        "fantasy": "Spirito legato a un luogo o a una morte irrisolta, privo di corpo stabile.",
        "combat": "Nega il contatto con forma eterea e fase, poi sottrae spirito dalla media distanza.",
        "archetype": "Non morto incorporeo difensivo con drenaggio spirituale e alto Mana.",
        "siblings": [("Spettro", "nearest", "Più difensivo e legato al luogo, meno aggressivo."), ("Drago Spettrale", "same-state", "Chassis umanoide fragile senza volo draconico."), ("Mago Scheletro", "contrast", "Azioni innate incorporee, non Skill e focus.")],
        "axes": [("incorporeità", "Forma Eterea e Spostamento Fase"), ("fame spirituale", "Sottrazione Spirituale e Mana alto")],
        "must": ["forma eterea", "fase", "spirito", "gelo"], "must_not": ["corpo osseo", "equipment"],
        "checkpoints": ["presenza incorporea", "fase", "drenaggio", "fantasma persistente", "spirito maggiore"],
        "range_reason": "Gli endpoint vengono linearizzati senza rimuovere le resistenze costanti.", "at_least_one": ["Forma Eterea presente"],
    },
    {
        "name": "Guar", "source": "972", "ids": [972], "category": "Animale",
        "fantasy": "Bestia da soma di Morrowind, docile finché minacciata e sorprendentemente tenace.",
        "combat": "Carica per aprirsi spazio, spazza con la coda e recupera lentamente senza alcuna magia.",
        "archetype": "Animale resistente da carica e coda con rigenerazione naturale.",
        "siblings": [("Kagouti", "nearest", "Più docile e difensivo, meno predatorio."), ("Cinghiale", "same-role", "Coda e utilità da soma invece di furia."), ("Clannfear", "contrast", "Animale domestico, non Daedra.")],
        "axes": [("bestia da soma", "PF e resistenza"), ("difesa naturale", "Carica, coda e Pelle Rigenerativa")],
        "must": ["carica", "coda", "rigenerazione", "Mana zero"], "must_not": ["magia", "veleno"],
        "checkpoints": ["Guar riconoscibile", "carica", "coda", "tenacia", "grande bestia da soma"],
        "range_reason": "La riga 20 viene estesa mantenendo il profilo naturale.", "at_least_one": ["mana 0 a ogni livello"],
    },
    {
        "name": "Guerriero Kwama", "source": "981", "ids": [981], "category": "Animale",
        "fantasy": "Casta guerriera della colonia Kwama, nata per proteggere regina e nido.",
        "combat": "Carica l'intruso, inocula gelo debilitante e continua a combattere grazie alla pelle rigenerativa.",
        "archetype": "Difensore d'alveare corazzato con carica e veleno gelido.",
        "siblings": [("Regina Kwama", "nearest", "Guardia da prima linea, non controllo della covata."), ("Operaio Kwama", "same-colony", "Più forza, corazza e aggressione."), ("Ragno Frostbite", "contrast", "Carica frontale invece di ragnatele.")],
        "axes": [("casta guerriera", "forza/PF e Carica"), ("difesa del nido", "veleno gelido e rigenerazione")],
        "must": ["Kwama", "carica", "veleno gelido", "Mana zero"], "must_not": ["evocazione", "volo"],
        "checkpoints": ["guardia Kwama", "carica", "veleno gelido", "corazza del nido", "guerriero maturo"],
        "range_reason": "Gli endpoint 20 diventano una progressione leggibile della casta.", "at_least_one": ["Carica e Inietta veleno gelido presenti"],
    },
    {
        "name": "Hunger", "source": "998", "ids": [998], "category": "Daedra",
        "fantasy": "Daedra emaciato che trasforma ogni contatto in sottrazione di vita e spirito.",
        "combat": "Chiude rapidamente la distanza, morde e drena risorse per sostenere una pressione prolungata.",
        "archetype": "Predatore Daedra rapido con doppio drenaggio e morso infettivo.",
        "siblings": [("Daedroth", "nearest", "Drenaggio e velocità invece di massa e fuoco."), ("Clannfear", "same-origin", "Sostentamento soprannaturale invece di carica."), ("Fantasma", "contrast", "Predatore corporeo, non difesa incorporea.")],
        "axes": [("fame daedrica", "Sottrai Vita/Sottrazione Spirituale"), ("predatore emaciato", "velocità e Morso Infettivo")],
        "must": ["drenaggio", "morso", "Mana", "velocità"], "must_not": ["fuoco dominante", "volo"],
        "checkpoints": ["predatore famelico", "drenaggio vitale", "drenaggio spirituale", "pressione sostenuta", "Hunger maggiore"],
        "range_reason": "Le curve vengono linearizzate preservando velocità e risorse magiche.", "at_least_one": ["due azioni di sottrazione presenti"],
    },
    {
        "name": "Kagouti", "source": "974", "ids": [974], "category": "Animale",
        "fantasy": "Predatore territoriale delle terre di cenere, costruito per travolgere e lacerare.",
        "combat": "Carica, infetta col morso e usa Furia quando lo scontro non termina subito.",
        "archetype": "Bestia massiccia da carica, morso e furia senza Mana.",
        "siblings": [("Guar", "nearest", "Predazione e furia invece di utilità da soma."), ("Cinghiale", "same-role", "Morso infettivo e chassis alieno invece di zanne."), ("Clannfear", "contrast", "Fauna di Morrowind, non Daedra.")],
        "axes": [("carica territoriale", "forza/velocità e Carica"), ("ferocia ashlander", "Morso Infettivo e Furia")],
        "must": ["carica", "morso", "Furia", "Mana zero"], "must_not": ["magia", "volo"],
        "checkpoints": ["predatore delle ceneri", "carica", "morso", "Furia", "Kagouti dominante"],
        "range_reason": "La riga 20 viene estesa mantenendo Mana zero e debolezze elementali.", "at_least_one": ["mana 0 e res_gelo negativa"],
    },
    {
        "name": "Lupo delle Nevi", "source": "985", "ids": [985], "category": "Animale",
        "fantasy": "Predatore di branco adattato a neve, fame e inseguimenti nei passi settentrionali.",
        "combat": "Balza sulla preda isolata, entra in Furia e rigenera abbastanza da continuare la caccia.",
        "archetype": "Lupo artico d'élite con balzo, furia e rigenerazione.",
        "siblings": [("Lupo", "nearest", "Più robusto, rigenerante e resistente al gelo."), ("Capra dei Ghiacciai", "same-biome", "Predazione di branco invece di fuga alpina."), ("Kagouti", "contrast", "Mobilità e balzo invece di carica massiccia.")],
        "axes": [("caccia sulla neve", "Balzo e velocità"), ("adattamento artico", "Rigenerazione e res_gelo crescente")],
        "must": ["balzo", "Furia", "rigenerazione", "Mana zero"], "must_not": ["magia", "coda"],
        "checkpoints": ["lupo artico", "balzo", "Furia", "rigenerazione", "capobranco delle nevi"],
        "range_reason": "Gli endpoint mantengono la superiorità sul Lupo senza cambiare contratto.", "at_least_one": ["mana 0 e res_gelo positiva al livello 20"],
    },
    {
        "name": "Ogrim", "source": "1004", "ids": [1004], "category": "Daedra",
        "fantasy": "Daedra enorme e grottesco che usa massa e ostinazione come unica strategia.",
        "combat": "Occupa spazio, pesta un'area, indurisce la pelle e usa Furia per chiudere lo scontro.",
        "archetype": "Bruto Daedra lento con pestone, pelle di pietra e Furia.",
        "siblings": [("Daedroth", "nearest", "Più lento e difensivo, privo di fuoco a distanza."), ("Atronach di Carne", "same-scale", "Pietra e Furia invece di rigenerazione organica."), ("Colosso d’Ossa", "contrast", "Daedra vivo, non fortezza necromantica.")],
        "axes": [("massa grottesca", "PF/forza e Pestone Tonante"), ("ostinazione daedrica", "Pelle di Pietra e Furia")],
        "must": ["pestone", "pelle di pietra", "Furia", "Mana zero"], "must_not": ["volo", "magia a distanza"],
        "checkpoints": ["bruto Ogrim", "pestone", "pelle di pietra", "Furia", "Ogrim maggiore"],
        "range_reason": "La riga 20 viene linearizzata conservando lentezza e vulnerabilità elettrica.", "at_least_one": ["res_elettro negativa"],
    },
    {
        "name": "Ragno Frostbite", "source": "993", "ids": [993], "category": "Animale",
        "fantasy": "Predatore di caverna che prepara il terreno con ragnatele e chiude col veleno gelido.",
        "combat": "Riduce la mobilità da lontano, attacca da pareti e soffitti e punisce chi resta intrappolato.",
        "archetype": "Controllore animale con ragnatela, morso gelido e resistenza al gelo.",
        "siblings": [("Ragno Daedra", "nearest", "Animale e gelo invece di evocazione daedrica."), ("Guerriero Kwama", "same-space", "Controllo e imboscata invece di carica."), ("Lupo delle Nevi", "contrast", "Trappola statica invece di inseguimento.")],
        "axes": [("trappola di ragnatela", "riduzione PA e controllo del terreno"), ("veleno gelido", "morso e res_gelo costante")],
        "must": ["ragnatela", "veleno gelido", "gelo", "Mana zero"], "must_not": ["evocazione", "volo"],
        "checkpoints": ["predatore di caverna", "ragnatela", "morso gelido", "controllore maturo", "matriarca Frostbite"],
        "range_reason": "Gli endpoint vengono linearizzati mantenendo le polarità elementali.", "at_least_one": ["Trappola di Ragnatela presente"],
    },
    {
        "name": "Sfera Dwemer", "source": "1029", "ids": [1029], "category": "Costrutto",
        "fantasy": "Automa Dwemer compatto che si dispiega da sfera in sentinella armata.",
        "combat": "Chiude i corridoi con movimenti precisi e colpisce usando una lama integrata, senza equipaggiamento separato.",
        "archetype": "Costrutto mobile con lama Dwemer innata e corazza metallica.",
        "curve_overrides": {"mana": (0, 0)},
        "actions": [{
            "key": "batch3-lama-dwemer-integrata",
            "name": "Lama Dwemer Integrata",
            "description": "La Sfera si dispiega e colpisce con la lama incorporata, infliggendo danni da taglio; l'arma è parte del costrutto e non può essere disarmata.",
            "minLevel": 1, "maxLevel": 20,
            "costs": {"pa": 4, "energia": 2},
            "trigger": "Azione", "duration": "Istantanea", "icon": "lama",
        }],
        "siblings": [("Centurione Nanico", "nearest", "Mobilità e lama rapida invece di massa e martello."), ("Steam Centurion", "same-origin", "Precisione compatta invece di vapore pesante."), ("Draugr Guerriero", "contrast", "Costrutto senza Skill o arma equipaggiata.")],
        "axes": [("dispiegamento sferico", "velocità/agilità e chassis compatto"), ("lama integrata", "azione innata al posto dell'item sorgente")],
        "must": ["Dwemer", "costrutto", "lama integrata", "Mana zero"], "must_not": ["equipment", "Skill", "magia"],
        "checkpoints": ["sentinella dispiegabile", "lama integrata", "corazza dwemer", "automa veterano", "Sfera d'élite"],
        "range_reason": "La lama legacy viene re-autorizzata come azione innata; Mana è azzerato per il costrutto.", "at_least_one": ["Lama Dwemer Integrata presente"],
    },
]


BATCH_CANDIDATES = [toolkit.humanoid_candidate(spec) for spec in HUMANOID_SPECS] + [
    toolkit.creature_candidate(spec) for spec in CREATURE_SPECS
]

base.OUTPUT_ROOT = OUTPUT_ROOT
base.ALL_CANDIDATES = BATCH_CANDIDATES
base.VARIANTS = tuple(f"batch3-v2-{index}" for index in range(1, 9))
base.CONVERTER_VERSION = "elder-unit-charter-v2-batch3"


if __name__ == "__main__":
    base.main()
