from backend.characters.models import Personaggio, default_personaggio_tot
from backend.core.models import DatiCampagna, Giocatore, Oggetto, SettingDefinition, Skill, Unit

from .models import CharacterTemplate, CombatModifier, HexType, MapType


HEX_TYPE_DEFAULTS = (
    ("Strada", "strada", 0.75, "#b8a27c", False, "Terreno battuto e rapido."),
    ("Sentiero", "sentiero", 0.90, "#9f8b68", False, "Traccia stretta ma percorribile."),
    ("Erba", "erba", 1.00, "#6f9559", False, "Terreno aperto."),
    ("Terra", "terra", 1.00, "#8b6d4d", False, "Suolo compatto."),
    ("Fango", "fango", 1.50, "#66594b", False, "Rallenta il passo."),
    ("Sabbia", "sabbia", 1.35, "#c3a85f", False, "Cede sotto i piedi."),
    ("Neve", "neve", 1.40, "#d8e2e3", False, "Neve profonda."),
    ("Ghiaccio", "ghiaccio", 1.30, "#8dc5d3", False, "Scivoloso e instabile."),
    ("Acqua bassa", "acqua-bassa", 1.50, "#4b91b0", False, "Acqua fino al ginocchio."),
    ("Acqua profonda", "acqua-profonda", 2.50, "#245b82", False, "Richiede nuoto o grande sforzo."),
    ("Salita", "salita", 1.50, "#937861", False, "Pendenza sfavorevole."),
    ("Discesa", "discesa", 0.90, "#a48970", False, "Pendenza favorevole."),
    ("Roccia", "roccia", 1.35, "#777b7b", False, "Fondo sconnesso."),
    ("Macerie", "macerie", 1.75, "#665f58", False, "Detriti e ostacoli."),
    ("Bosco", "bosco", 1.50, "#3d6a42", False, "Vegetazione fitta."),
    ("Rovi", "rovi", 2.00, "#4d6736", False, "Vegetazione spinosa."),
    ("Palude", "palude", 2.25, "#536646", False, "Terreno cedevole e acquitrinoso."),
    ("Lava", "lava", 4.00, "#c54a2c", False, "Terreno estremamente pericoloso."),
    ("Muro", "muro", 1.00, "#57595d", True, "Ostacolo non attraversabile."),
    ("Baratro", "baratro", 1.00, "#20252b", True, "Spazio non attraversabile."),
)

ELDER_UNIT_SEED_VERSION = "14"


def _seed_elder_units() -> int:
    item_names = {
        "Armatura (pelle)",
        "Armatura (chitina)",
        "Armatura (elfico)",
        "Armatura (ossa)",
        "Armatura (ferro)",
        "Armatura (acciaio)",
        "Armatura (nordico)",
        "Arco corto (legno)",
        "Arco corto (chitina)",
        "Arco corto (elfico)",
        "Arco corto (ossa)",
        "Arco corto (ferro)",
        "Arco corto (acciaio)",
        "Arco corto (nordico)",
        "Mantello da città",
        "Mantello da viaggio",
        "Mantello del cacciatore",
        "Orecchino + attacco lv. 1 (1)",
        "Orecchino + attacco lv. 2 (2)",
        "Orecchino + attacco lv. 3 (3)",
        "Orecchino + attacco lv. 4 (4)",
        "Orecchino + pf lv. 1 (4)",
        "Orecchino + pf lv. 2 (6)",
        "Orecchino + pf lv. 3 (9)",
        "Orecchino + pf lv. 4 (13)",
    }
    for label in ("Anello", "Amuleto", "Cintura", "Fascia", "Spilla"):
        for item_level, attack, health in ((1, 1, 4), (2, 2, 6), (3, 3, 9), (4, 4, 13)):
            item_names.add(f"{label} + attacco lv. {item_level} ({attack})")
            item_names.add(f"{label} + pf lv. {item_level} ({health})")
    skill_names = {
        "Tiro Rapido",
        "Tiro Attento",
        "Doppio Missile",
        "Triplo Missile",
        "Focus 1",
        "Focus 2",
        "Bersaglio mobile",
        "Bruciapelo 1",
        "Bruciapelo 2",
        "Rimbalzo",
        "Tiro d'effetto",
        "Frammentazione",
        "Colpo furtivo",
        "Cacciatore",
        "Guerriglia",
        "Guerriglia aggressiva 1",
        "Guerriglia aggressiva 2",
        "Guerriglia aggressiva 3",
        "Cecchino",
        "Mira rapida",
        "Schiva 1",
        "Leggero 1",
        "Inafferrabile 1",
        "Inafferrabile 2",
        "Attaccante 1",
        "Attaccante 2",
        "Critico 1",
        "Colpo abile",
        "Punto Debole",
        "Efficiente",
    }
    skill_names.update(f"Vitale {level}" for level in range(1, 11))
    skill_names.update(f"Energico {level}" for level in range(1, 8))
    skill_names.update(f"Svelto {level}" for level in range(1, 4))
    skill_names.update({"Difensore 1", "Difensore 2"})
    skill_names.update(f"Roccia {level}" for level in range(1, 6))
    skill_names.update(f"Recupero Vita {level}" for level in range(1, 5))
    skill_names.update(f"Leggero {level}" for level in range(1, 8))
    skill_names.update(f"Schiva {level}" for level in range(1, 4))
    skill_names.update(f"Più Danno {level}" for level in range(1, 6))
    skill_names.update(f"Critico {level}" for level in range(1, 4))
    skill_names.update(
        {
            "Padrone del terreno 1",
            "Padrone del terreno 2",
            "Inafferrabile 1",
            "Inafferrabile 2",
            "Veterano 1",
            "Veterano 2",
            "Cardio",
            "Scattino",
            "19 critico 1",
            "19 critico 2",
            "18 critico 1",
            "18 critico 2",
            "20 critico",
            "Critico fortunato 1",
            "Critico fortunato 2",
            "Critico fortunato 3",
            "Fortuna cieca 1",
            "Fortuna cieca 2",
            "Fagotto 1",
            "Fagotto 2",
            "Peso distribuito 1",
            "Peso distribuito 2",
            "Peso distribuito 3",
            "Seconda Pelle 1",
            "Seconda Pelle 2",
            "Casa nella Natura 1",
            "Casa nella Natura 2",
            "A tuo agio fuori",
            "Guerriglia Attiva",
            "Guerriglia Difensiva",
            "Guerriglia Efficiente 1",
            "Guerriglia Efficiente 2",
            "Nomade",
            "Esperto di cibo",
        }
    )
    items = {
        item.nome: item
        for item in Oggetto.objects.filter(
            nome__in=item_names,
            archived_at__isnull=True,
            archiviato=False,
        )
    }
    skills = {
        skill.nome: skill
        for skill in Skill.objects.filter(
            nome__in=skill_names,
            archived_at__isnull=True,
        )
    }
    # The two production Units depend on the deliberately imported Elder
    # catalog. A clean install without that catalog remains valid and the next
    # seed run after import creates them.
    if set(items) != item_names or set(skills) != skill_names:
        return 0

    def item_entry(name, minimum, maximum, weight=1, chance=1):
        return {
            "itemId": items[name].id,
            "minLevel": minimum,
            "maxLevel": maximum,
            "weight": weight,
            "chance": chance,
        }

    accessory_types = {
        "Orecchino": "orecchino",
        "Anello": "anello",
        "Amuleto": "amuleto",
        "Cintura": "cintura",
        "Fascia": "fascia",
        "Spilla": "spilla",
    }
    archer_accessory_presets = {
        # Elder pg_da_archetipo.py repeats these archer Core presets, then
        # mixes one physical/utility preset to keep copies distinct.
        "pf_item",
        "attacco_item",
        "velocita_extra",
        "agilita_extra",
        "concentrazione_extra",
        "difesa_item",
        "energia_item",
        "resistenza_extra",
        "stanchezzabase",
        "rigenerazionepf",
        "fortuna_extra",
        "reroll",
        "darkvision",
    }
    accessory_catalog = list(
        Oggetto.objects.filter(
            tipo_1__in=accessory_types.values(),
            tipo_2__in=archer_accessory_presets,
            tipo_4__startswith="Livello ",
            archived_at__isnull=True,
            archiviato=False,
        )
    )

    def accessory_entries(label):
        item_type = accessory_types[label]
        result = []
        for item in accessory_catalog:
            if item.tipo_1 != item_type:
                continue
            try:
                item_level = int(str(item.tipo_4).split()[-1])
            except (TypeError, ValueError):
                continue
            result.append(
                {
                    "itemId": item.id,
                    "minLevel": max(1, item_level * 2 - 5),
                    "maxLevel": min(20, item_level * 2 + 5),
                    "weight": 4 if item.tipo_2 in {
                        "pf_item",
                        "attacco_item",
                        "velocita_extra",
                        "agilita_extra",
                        "concentrazione_extra",
                    } else 1,
                    "chance": 1,
                }
            )
        return result

    core_skill_plan = tuple(
        [(f"Vitale {level}", "core", 1, 20, 9) for level in range(1, 11)]
        + [(f"Energico {level}", "core", 1, 20, 8) for level in range(1, 8)]
        + [(f"Svelto {level}", "core", 1, 20, 7) for level in range(1, 4)]
        + [
            ("Difensore 1", "core", 1, 20, 6),
            ("Difensore 2", "core", 1, 20, 6),
            ("Attaccante 1", "core", 1, 20, 6),
            ("Attaccante 2", "core", 1, 20, 6),
            ("Leggero 1", "core", 1, 20, 6),
        ]
        + [(f"Roccia {level}", "core", 6, 20, 6) for level in range(1, 6)]
        + [(f"Recupero Vita {level}", "core", 6, 20, 6) for level in range(1, 5)]
        + [(f"Leggero {level}", "core", 6, 20, 6) for level in range(2, 8)]
        + [(f"Schiva {level}", "core", 6, 20, 6) for level in range(1, 4)]
        + [(f"Più Danno {level}", "core", 8, 20, 5) for level in range(1, 6)]
        + [(f"Critico {level}", "core", 8, 20, 5) for level in range(1, 4)]
        + [
            ("Padrone del terreno 1", "core", 7, 20, 6),
            ("Padrone del terreno 2", "core", 7, 20, 6),
            ("Inafferrabile 1", "core", 7, 20, 6),
            ("Inafferrabile 2", "core", 7, 20, 6),
            ("Veterano 1", "core", 8, 20, 5),
            ("Veterano 2", "core", 8, 20, 5),
            ("Cardio", "core", 8, 20, 5),
            ("Scattino", "core", 8, 20, 5),
            ("Critico fortunato 1", "core", 10, 20, 4),
            ("Critico fortunato 2", "core", 10, 20, 4),
            ("Critico fortunato 3", "core", 10, 20, 4),
            ("Fortuna cieca 1", "core", 10, 20, 4),
            ("Fortuna cieca 2", "core", 10, 20, 4),
            ("19 critico 1", "core", 12, 20, 4),
            ("19 critico 2", "core", 12, 20, 4),
            ("18 critico 1", "core", 14, 20, 4),
            ("18 critico 2", "core", 14, 20, 4),
            ("20 critico", "core", 16, 20, 4),
            ("Fagotto 1", "core", 6, 20, 4),
            ("Fagotto 2", "core", 6, 20, 4),
            ("Peso distribuito 1", "core", 6, 20, 4),
            ("Peso distribuito 2", "core", 6, 20, 4),
            ("Peso distribuito 3", "core", 6, 20, 4),
            ("Seconda Pelle 1", "core", 7, 20, 5),
            ("Seconda Pelle 2", "core", 7, 20, 5),
        ]
    )
    archetype_skill_plan = (
        ("Tiro Rapido", "archetype", 1, 20, 10),
        ("Tiro Attento", "archetype", 1, 20, 10),
        ("Focus 1", "archetype", 2, 20, 9),
        ("Doppio Missile", "archetype", 2, 20, 8),
        ("Bersaglio mobile", "archetype", 2, 20, 8),
        ("Bruciapelo 1", "archetype", 3, 20, 7),
        ("Rimbalzo", "archetype", 3, 20, 7),
        ("Colpo furtivo", "archetype", 3, 20, 6),
        ("Tiro d'effetto", "archetype", 4, 20, 7),
        ("Bruciapelo 2", "archetype", 4, 20, 6),
        ("Frammentazione", "archetype", 5, 20, 6),
        ("Cacciatore", "archetype", 5, 20, 8),
        ("Cecchino", "archetype", 6, 20, 7),
        ("Guerriglia", "archetype", 8, 20, 7),
        ("Casa nella Natura 1", "archetype", 8, 20, 5),
        ("A tuo agio fuori", "archetype", 8, 20, 5),
        ("Focus 2", "archetype", 9, 20, 7),
        ("Triplo Missile", "archetype", 10, 20, 6),
        ("Casa nella Natura 2", "archetype", 10, 20, 5),
        ("Guerriglia Attiva", "archetype", 10, 20, 5),
        ("Guerriglia Difensiva", "archetype", 10, 20, 5),
        ("Guerriglia Efficiente 1", "archetype", 11, 20, 5),
        ("Guerriglia aggressiva 1", "archetype", 12, 20, 6),
        ("Nomade", "archetype", 12, 20, 5),
        ("Esperto di cibo", "archetype", 12, 20, 4),
        ("Mira rapida", "archetype", 14, 20, 6),
        ("Guerriglia Efficiente 2", "archetype", 14, 20, 5),
        ("Guerriglia aggressiva 2", "archetype", 16, 20, 5),
        ("Guerriglia aggressiva 3", "archetype", 19, 20, 4),
    )
    skill_plan = core_skill_plan + archetype_skill_plan
    bandit_values = {
        "categoria": "Banditi",
        "archetipo_tags": {
            "core_fisico": 3,
            "core_magico": -1,
            "focus_combat": 5,
            "range_skill": 5,
            "area_e_multi_target": 1,
            "natura_magica": -1,
            "difesa": 2,
            "attacco": 4,
            "sociale": 0,
            "supporto_party": 1,
            "esplorazione_infiltrazione": 2,
            "tecnica_crafting": 0,
            "controllo_situazionale": 2,
        },
        "archetipo_descrizione": (
            "Predone disciplinato a distanza: apre lo scontro dall'imboscata, "
            "usa il terreno e ripiega se viene raggiunto. Non usa magia."
        ),
        "profilo_competenze": {
            "camuffare": -2,
            "cavalcare": 1,
            "conoscenze_naturaegeografia": 1,
            "conoscenze_religioni": -2,
            "conoscenze_storiaenobilta": -1,
            "diplomazia": -1,
            "furtivita": 1,
            "gestione_risorse": 1,
            "ingegneria": -2,
            "intimidire": 1,
            "intuizione": 1,
            "manovrare_veicoli": 0,
            "nuotare": 0,
            "percezione": 3,
            "raggirare": -2,
            "rapidita_di_mano": 2,
            "sapienza_magica": -5,
            "scalare": 1,
            "sopravvivenza": 1,
            "strategia_militare": 2,
            "suonare": -4,
        },
        "levels": [],
        "equipment_profiles": {
            "slots": {
                "armatura": [
                    # Levels 1-6 may mix light and heavy loot. From level 7
                    # the archer stays on the light path; tier 4 overlaps tier
                    # 3 at 9-11 and becomes exclusive from level 12.
                    item_entry("Armatura (pelle)", 1, 3, 4),
                    item_entry("Armatura (ferro)", 1, 3, 2),
                    item_entry("Armatura (chitina)", 2, 6, 5),
                    item_entry("Armatura (acciaio)", 2, 6, 2),
                    item_entry("Armatura (elfico)", 4, 11, 5),
                    item_entry("Armatura (nordico)", 4, 6, 2),
                    item_entry("Armatura (ossa)", 9, 20, 4),
                ],
                "arma": [
                    item_entry("Arco corto (legno)", 1, 3, 4),
                    item_entry("Arco corto (ferro)", 1, 3, 2),
                    item_entry("Arco corto (chitina)", 2, 6, 5),
                    item_entry("Arco corto (acciaio)", 2, 6, 2),
                    item_entry("Arco corto (elfico)", 4, 11, 5),
                    item_entry("Arco corto (nordico)", 4, 6, 2),
                    item_entry("Arco corto (ossa)", 9, 20, 4),
                ],
                "mantello": [
                    item_entry("Mantello da città", 1, 20, 3, 0.85),
                    item_entry("Mantello da viaggio", 3, 20, 2, 0.85),
                    item_entry("Mantello del cacciatore", 5, 20, 2, 0.75),
                ],
            },
            "groups": [
                {
                    "name": "Orecchini del predone",
                    "slots": [f"orecchino_{index}" for index in range(1, 7)],
                    "minCount": 1,
                    "maxCount": 3,
                    "emptyChance": 0,
                    "items": accessory_entries("Orecchino"),
                },
                {
                    "name": "Anelli del predone",
                    "slots": [f"anello_{index}" for index in range(1, 9)],
                    "minCount": 1,
                    "maxCount": 3,
                    "emptyChance": 0,
                    "items": accessory_entries("Anello"),
                },
                *[
                    {
                        "name": f"{label} del predone",
                        "slots": [slot],
                        "minCount": 0,
                        "maxCount": 1,
                        "emptyChance": 0.6,
                        "items": accessory_entries(label),
                    }
                    for label, slot in (
                        ("Amuleto", "amuleto"),
                        ("Cintura", "cintura"),
                        ("Fascia", "fascia"),
                        ("Spilla", "spilla"),
                    )
                ],
                ],
            "accessoryCountByLevel": [
                {"minLevel": 1, "maxLevel": 1, "minCount": 2, "maxCount": 4},
                {"minLevel": 2, "maxLevel": 2, "minCount": 3, "maxCount": 5},
                {"minLevel": 3, "maxLevel": 3, "minCount": 4, "maxCount": 6},
                {"minLevel": 4, "maxLevel": 5, "minCount": 5, "maxCount": 7},
                {"minLevel": 6, "maxLevel": 7, "minCount": 6, "maxCount": 8},
                {"minLevel": 8, "maxLevel": 9, "minCount": 7, "maxCount": 9},
                {"minLevel": 10, "maxLevel": 12, "minCount": 8, "maxCount": 10},
                {"minLevel": 13, "maxLevel": 15, "minCount": 9, "maxCount": 10},
                {"minLevel": 16, "maxLevel": 20, "minCount": 10, "maxCount": 10},
            ],
            "allowDuplicates": False,
        },
        "stat_profiles": {
            "baseModifiers": {
                "velocita": 1,
                "agilita": 1,
                "concentrazione": 1,
            },
            "perLevelModifiers": {},
            "milestones": [],
        },
        "skill_actions": [],
        "skill_unlocks": [
            {
                "skillId": skills[name].id,
                "pool": pool,
                "weight": weight,
                "minLevel": minimum,
                "maxLevel": maximum,
            }
            for name, pool, minimum, maximum, weight in skill_plan
        ],
        "lore_description": (
            "Gli Arcieri Banditi si annidano lungo le strade isolate, nei rifugi "
            "montani e nei campi nascosti dei fuorilegge. Preferiscono vedere i "
            "viaggiatori senza essere visti: per loro la strada è una trappola, "
            "non un passaggio. Aprono lo scontro da lontano e sfruttano terreno "
            "e compagni più robusti per evitare il duello."
        ),
        "generation_rules": {
            "kind": "humanoid",
            "coreKey": "warrior",
            "coreShare": 0.5,
            "startingXp": 0,
            "xpPerLevel": {"base": 20, "growth": 1},
            "competenceXp": {"starting": 5, "base": 15, "growth": 0},
            "finalSpendingPasses": 4,
            "magicPolicy": "none",
            "allowedClassFamilies": ["Ranger"],
            "allowedReligionFamilies": [],
            "allowHumanoidStatGrowth": False,
        },
        "notes": (
            "Ricostruzione deterministica delle Unit Elder #951 e #952. "
            "Armi e armature seguono i percorsi materiale leggero/pesante: "
            "misto fino al livello 6, solo leggero dal 7, ossa esclusivo dal 12."
        ),
        "metadata": {
            "seed_kind": "elder_unit",
            "seed_version": ELDER_UNIT_SEED_VERSION,
            "sourceProject": "the_elder_django",
            "sourceTable": "django_slim_unit",
            "sourceIds": [951, 952],
            "sourceArchetype": "Arciere Soldato",
        },
    }
    wolf_values = {
        "categoria": "Animali",
        "archetipo_tags": {},
        "archetipo_descrizione": (
            "Predatore naturale da branco, rapido e resistente. Non possiede "
            "Skill, magie o equipaggiamento."
        ),
        "profilo_competenze": {},
        "levels": [],
        "equipment_profiles": {},
        "stat_profiles": {
            "baseModifiers": {},
            "perLevelModifiers": {},
            "milestones": [],
            "curves": [
                {"key": "pf", "profile": "medium", "level1": 18, "level20": 100},
                {"key": "pa", "profile": "high", "level1": 9, "level20": 32},
                {"key": "energia", "profile": "medium", "level1": 6, "level20": 30},
                {"key": "potere", "profile": "custom", "level1": 0, "level20": 0},
                {"key": "forza", "profile": "high", "level1": 11, "level20": 30},
                {"key": "resistenza", "profile": "medium", "level1": 8, "level20": 22},
                {"key": "velocita", "profile": "high", "level1": 11, "level20": 30},
                {"key": "agilita", "profile": "high", "level1": 11, "level20": 30},
                {"key": "intelligenza", "profile": "low", "level1": 6, "level20": 16},
                {"key": "concentrazione", "profile": "low", "level1": 6, "level20": 16},
                {"key": "personalita", "profile": "custom", "level1": 0, "level20": 0},
                {"key": "saggezza", "profile": "low", "level1": 6, "level20": 16},
                {"key": "fortuna", "profile": "high", "level1": 11, "level20": 30},
                {"key": "attacco", "profile": "medium", "level1": 10, "level20": 55},
                {"key": "difesa", "profile": "medium", "level1": 10, "level20": 55},
                {"key": "tier", "profile": "high", "level1": 5, "level20": 15},
                {"key": "rd_fis", "profile": "medium", "level1": 1, "level20": 3},
                {"key": "res_contundente", "profile": "custom", "level1": 0, "level20": 0},
                {"key": "res_taglio", "profile": "custom", "level1": -1, "level20": -1},
                {"key": "res_perforante", "profile": "custom", "level1": -1, "level20": -1},
                {"key": "res_fuoco", "profile": "custom", "level1": 0, "level20": 0},
                {"key": "res_gelo", "profile": "custom", "level1": 0, "level20": 0},
                {"key": "res_elettro", "profile": "custom", "level1": 0, "level20": 0},
            ],
        },
        "skill_actions": [
            {
                "key": "balzo-predatorio",
                "name": "Balzo Predatorio",
                "description": "Salta fino a 3 esagoni su una casella adiacente al bersaglio ed esegue un attacco con +3 Attacco e un reroll.",
                "minLevel": 1,
                "maxLevel": 20,
                "costs": {"pa": 7, "energia": 2},
                "trigger": "Azione",
                "duration": "Istantanea",
                "icon": "artiglio",
            },
            {
                "key": "furia",
                "name": "Furia",
                "description": "Per 3 turni ottiene +4 Forza e +3 Attacco, ma -2 Difesa.",
                "minLevel": 6,
                "maxLevel": 20,
                "costs": {"pa": 4, "energia": 4},
                "trigger": "Azione",
                "duration": "3 turni",
                "icon": "runa",
            },
        ],
        "skill_unlocks": [],
        "lore_description": (
            "I Lupi vivono nelle foreste, nelle colline e nelle pianure di "
            "Tamriel. Non sono mostri: sono predatori sociali, guidati "
            "dall'istinto del branco, con sensi acuti, morso forte e grande "
            "resistenza sulle lunghe distanze."
        ),
        "generation_rules": {
            "kind": "creature",
        },
        "notes": (
            "Ricostruzione deterministica della Unit Elder #986. Balzo Predatorio "
            "e Furia sono abilità innate, non Skill acquistate con PE."
        ),
        "metadata": {
            "seed_kind": "elder_unit",
            "seed_version": ELDER_UNIT_SEED_VERSION,
            "sourceProject": "the_elder_django",
            "sourceTable": "django_slim_unit",
            "sourceIds": [986],
        },
    }

    touched = 0
    for name, values in (("Arciere Bandito", bandit_values), ("Lupo", wolf_values)):
        unit, created = Unit.objects.get_or_create(nome=name, defaults=values)
        touched += int(created)
        if created:
            continue
        metadata = unit.metadata if isinstance(unit.metadata, dict) else {}
        if metadata.get("seed_kind") != "elder_unit" or metadata.get("seed_version") == ELDER_UNIT_SEED_VERSION:
            continue
        for field, value in values.items():
            setattr(unit, field, value)
        unit.archived_at = None
        unit.save()
        touched += 1
    return touched


def ensure_combat_defaults():
    touched = 0
    active_campaign = DatiCampagna.objects.filter(attiva=True, archived_at__isnull=True).first()
    campaign_by_character_id: dict[int, int] = {}
    for player in Giocatore.objects.filter(active_campaign__isnull=False).only("active_campaign_id", "character_ids"):
        for raw_character_id in player.character_ids if isinstance(player.character_ids, list) else []:
            try:
                campaign_by_character_id.setdefault(int(raw_character_id), player.active_campaign_id)
            except (TypeError, ValueError):
                continue
    for character in Personaggio.objects.all().only("id", "campagna_id", "metadata"):
        metadata = character.metadata if isinstance(character.metadata, dict) else {}
        if not metadata.get("generatedFromUnitId") or metadata.get("unitCampaignResolved"):
            continue
        target_campaign_id = campaign_by_character_id.get(character.id)
        if target_campaign_id is None and character.campagna_id is None and active_campaign:
            target_campaign_id = active_campaign.id
        metadata["unitCampaignResolved"] = True
        character.metadata = metadata
        character.campagna_id = target_campaign_id or character.campagna_id
        character.save(update_fields=["campagna", "metadata", "updated_at"])
        touched += 1
    for order, (name, slug, multiplier, color, impassable, description) in enumerate(HEX_TYPE_DEFAULTS):
        _entry, created = HexType.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "movement_multiplier": multiplier, "color": color, "impassable": impassable, "description": description, "order": order},
        )
        touched += int(created)
    map_type, created = MapType.objects.get_or_create(
        slug="scontro",
        defaults={"name": "Scontro", "description": "Mappa tattica standard.", "default_orientation": "pointy", "default_rows": 24, "default_columns": 32},
    )
    touched += int(created)
    for order, values in enumerate((
        {"name": "Attacco accurato", "scope": "attack", "attack_bonus": 2, "damage_bonus": -1, "description": "Più precisione a costo di impatto.", "color": "#6686a7"},
        {"name": "Attacco potente", "scope": "both", "attack_bonus": -2, "damage_bonus": 3, "description": "Meno precisione, più danno.", "color": "#9e5c48"},
        {"name": "Bersaglio esposto", "scope": "attack", "attack_bonus": 2, "description": "Il difensore offre un'apertura.", "color": "#a5814c"},
    )):
        _entry, created = CombatModifier.objects.get_or_create(name=values["name"], defaults={**values, "order": order})
        touched += int(created)
    totals = default_personaggio_tot()
    totals.update({"pf": 24, "mana": 0, "energia": 8, "potere": 0, "pa": 6, "attacco": 4, "difesa": 3, "forza": 3, "resistenza": 2, "velocita": 2, "tier": 1, "rd_fis": 1})
    _template, created = CharacterTemplate.objects.get_or_create(
        slug="bandito",
        defaults={
            "name": "Bandito",
            "description": "Template dimostrativo completo e pronto per future espansioni automatiche.",
            "blueprint": {
                "version": 1,
                "profile": {"nome": "Bandito", "tipologia": "nemico", "razza_1": "Umano", "livello": 2, "dettagli_personaggio": "Predone opportunista armato alla leggera."},
                "totals": totals,
                "competencies": {},
                "abilities": {"known": [], "skills": []},
                "skills": [],
                "equipment": [],
                "inventory": [],
                "quiver": [],
                "effects": [],
                "notes": {"combat": "Preferisce accerchiare e colpire bersagli isolati."},
                "reagents": {"capacity": 0, "ingredients": {}, "multipliers": {}},
            },
        },
    )
    touched += int(created)
    _setting, created = SettingDefinition.objects.get_or_create(
        key="combat.base_movement_ap",
        defaults={
            "label": "Costo base movimento per esagono",
            "category": "Combattimento",
            "description": "PA di base per ogni esagono; i tag terreno moltiplicano questo valore.",
            "minimum_role": "master",
            "value_type": "int",
            "default_value": 1,
            "master_customizable": False,
            "order": 10,
            "metadata": {
                "minimum": 1,
                "maximum": 20,
                "step": 1,
                "admin_managed": True,
            },
        },
    )
    touched += int(created)
    metadata = _setting.metadata if isinstance(_setting.metadata, dict) else {}
    desired_metadata = {**metadata, "admin_managed": True}
    update_fields = []
    if _setting.master_customizable:
        _setting.master_customizable = False
        update_fields.append("master_customizable")
    if metadata != desired_metadata:
        _setting.metadata = desired_metadata
        update_fields.append("metadata")
    if update_fields:
        _setting.save(update_fields=[*update_fields, "updated_at"])
        touched += 1
    touched += _seed_elder_units()
    return touched
