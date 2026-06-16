LOCAL_PLAYER_NAME = "local_master"
DEFAULT_CAMPAIGN_NAME = "Campagna principale"


PERSONAGGIO_FLOAT_TOTAL_KEYS = [
    "stanchezza",
    "modificatore_generale",
    "fortuna",
    "forza",
    "resistenza",
    "velocita",
    "agilita",
    "intelligenza",
    "concentrazione",
    "personalita",
    "saggezza",
    "pf",
    "mana",
    "energia",
    "potere",
    "pa",
    "attacco",
    "difesa",
    "attacco_npc",
    "difesa_npc",
    "rd_fis",
    "res_contundente",
    "res_taglio",
    "res_perforante",
    "res_fuoco",
    "res_gelo",
    "res_elettro",
    "rd_fuoco",
    "rd_gelo",
    "rd_elettro",
    "ap",
    "ap_percento",
    "slot_magici",
    "slot_non_magici",
    "monete_per_slot",
    "tier",
    "sifone_di_mana",
    "en_per_mana_ordine",
    "pa_per_mana_ordine",
    "en_per_mana_caos",
    "pa_per_mana_caos",
    "ogni_en_x_mana_ordine",
    "ogni_pa_x_mana_ordine",
    "ogni_en_x_mana_caos",
    "ogni_pa_x_mana_caos",
    "sconto_mana_per_potere",
    "sconto_pa_per_potere",
    "mod_carico",
    "mod_peso_equip",
    "orecchini_max",
    "anelli_max",
    "sacchi_max",
    "atk_skill_taglio",
    "atk_skill_contundente",
    "atk_skill_perforante",
]


V2_GLOBAL_MODIFIERS_DEFAULTS = [
    {
        "name": "Formule_base",
        "value_float": {key: 0 for key in PERSONAGGIO_FLOAT_TOTAL_KEYS},
        "value_string": {
            "crit_min": "",
            "crit_nor": "",
            "crit_mag": "",
            "formula_profile": "base",
        },
        "rule_notes": (
            "Default v2 formula/modifier profile. This is the canonical seed record for "
            "base values moved out of Personaggio; import exact old Formule values here "
            "before wiring calculation services."
        ),
    }
]


V2_SKILL_FAMILY_DEFAULTS = [
    {"nome": "Generale", "gruppo": "generale", "ordine": 10},
    {"nome": "Combattimento", "gruppo": "combattimento", "ordine": 20},
    {"nome": "Magia", "gruppo": "magia", "ordine": 30},
    {"nome": "Crafting", "gruppo": "crafting", "ordine": 40},
    {"nome": "Alchimia", "gruppo": "alchimia", "ordine": 50},
    {"nome": "Sociale", "gruppo": "sociale", "ordine": 60},
    {"nome": "Esplorazione", "gruppo": "esplorazione", "ordine": 70},
    {"nome": "Classe", "gruppo": "classe", "ordine": 80, "is_classe": True},
    {"nome": "Religione", "gruppo": "religione", "ordine": 90, "is_religione": True},
    {"nome": "Perk", "gruppo": "perk", "ordine": 100, "is_perk": True},
]


V2_EFFECT_CATEGORY_DEFAULTS = [
    {"tipo": "effetto", "nome": "Categoria effetto", "icon": "sparkles"},
    {"tipo": "malattia", "nome": "Categoria malattia", "icon": "biohazard"},
    {"tipo": "ferita", "nome": "Categoria ferita", "icon": "heart-crack"},
    {"tipo": "maledizione", "nome": "Categoria maledizione", "icon": "skull"},
    {"tipo": "benedizione", "nome": "Categoria benedizione", "icon": "sun"},
    {"tipo": "ambientale", "nome": "Categoria ambientale", "icon": "cloud"},
]


V2_PLACEHOLDER_ITEMS = [
    {"nome": "Slot vuoto", "icona": "circle", "tipo_1": "placeholder"},
    {"nome": "Nessuna arma", "icona": "sword", "tipo_1": "placeholder", "tipo_2": "arma"},
    {"nome": "Nessuna armatura", "icona": "shield", "tipo_1": "placeholder", "tipo_2": "armatura"},
    {"nome": "Nessuno scudo", "icona": "shield-off", "tipo_1": "placeholder", "tipo_2": "scudo"},
    {"nome": "Nessun accessorio", "icona": "gem", "tipo_1": "placeholder", "tipo_2": "accessorio"},
]


V2_EMPTY_OBJECT_NAMES = {
    "zaino": "Template - Zaino vuoto",
    "faretra": "Template - Faretra vuota",
    "equip": "Template - Equip vuoto",
    "note": "Template - Note vuote",
    "borsa_reagenti": "Template - Borsa reagenti vuota",
    "personaggio": "Template - Personaggio vuoto",
    "personaggio_internal": "template_personaggio_vuoto",
}
