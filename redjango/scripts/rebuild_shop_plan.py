"""Rebuild the reviewed Mercato naming plan from immutable shop slots.

This script deliberately never touches SQLite or the Elder source workbook.  It
rewrites only the diffable JSON content plan after validating the source facts.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "reference" / "approved_shop_plan.json"

REGIONAL = {
    "Altro": {
        "tradition": "Imperial",
        "first": ["Aurelia", "Cassian", "Livia", "Marcellus", "Neria", "Sextus", "Valeria", "Teren"],
        "last": ["Varro", "Crispin", "Merula", "Salvius", "Cato", "Vibia", "Rufinus", "Laro"],
        "anchors": ["del Ponte Basso", "della Riva Chiara", "delle Cisterne", "del Cortile Vecchio", "del Vicolo Largo", "del Molo Secco"],
    },
    "Black Marsh": {
        "tradition": "Argonian/Tamrielic",
        "first": ["Keeps-the-Reed", "Hears-the-Rain", "Walks-in-Mist", "Nura", "Vekka", "Talen", "Sings-to-Stones", "Mira"],
        "last": ["Reed-Watcher", "of-Deepwater", "Tzel", "Voss", "Maro", "Lifts-the-Net", "Sathasa", "Nereel"],
        "anchors": ["delle Passerelle", "del Canale Lento", "della Darsena Verde", "dei Piloni", "della Riva Bassa", "della Chiusa"],
    },
    "Cyrodiil": {
        "tradition": "Imperial",
        "first": ["Aurelia", "Cassian", "Livia", "Marcellus", "Neria", "Sextus", "Valeria", "Teren"],
        "last": ["Varro", "Crispin", "Merula", "Salvius", "Cato", "Vibia", "Rufinus", "Laro"],
        "anchors": ["del Foro Minore", "della Porta Est", "delle Terme Vecchie", "del Ponte di Pietra", "del Portico", "della Via delle Candele"],
    },
    "Elsweyr": {
        "tradition": "Khajiit/Tamrielic",
        "first": ["Ra'jirra", "Miziba", "Kharjo", "S'vasha", "J'zara", "Nirni", "Do'rashi", "Ma'khar"],
        "last": ["Sabi", "Daro", "Vasha", "Rin", "Kesh", "Mara", "Zirr", "Haj"],
        "anchors": ["del Mercato Basso", "dei Muri d'Argilla", "della Via dei Carri", "del Cortile delle Stoffe", "della Porta Sud", "della Fonte"],
    },
    "Hammerfell": {
        "tradition": "Redguard",
        "first": ["Nadira", "Faris", "Zahra", "Rashid", "Samira", "Hakeem", "Yasmin", "Khalid"],
        "last": ["al-Rihad", "Bint-Sahir", "Daro", "Nafis", "Sadaq", "Kavari", "Mazin", "Tavari"],
        "anchors": ["della Banchina Bianca", "del Cortile del Vento", "della Porta del Mare", "dei Gradini di Calce", "del Pozzo Comune", "della Via delle Vele"],
    },
    "High Rock": {
        "tradition": "Breton",
        "first": ["Eliane", "Gaston", "Mariette", "Renaud", "Celene", "Olivier", "Ysabel", "Thibaut"],
        "last": ["Aubry", "Vannier", "Corbeau", "Montclair", "Bellamy", "Roche", "Duvall", "Leroux"],
        "anchors": ["della Piazza Piccola", "del Ponte dei Mugnai", "del Vicolo delle Campane", "della Porta Ovest", "del Molo Vecchio", "della Corte del Grano"],
    },
    "Morrowind": {
        "tradition": "Dunmer",
        "first": ["Dralasa", "Ravyn", "Vevrana", "Dralor", "Nerethi", "Uveran", "Mavon", "Ralen"],
        "last": ["Hlaalu", "Redoran", "Drenim", "Sarandas", "Telvanni", "Arenim", "Vendu", "Dralas"],
        "anchors": ["del Cortile di Cenere", "della Scalinata Bassa", "del Canale Nero", "della Strada dei Mercanti", "della Corte del Tempio", "del Molo di Basalto"],
    },
    "Skyrim": {
        "tradition": "Nord",
        "first": ["Hjolda", "Bjarne", "Runa", "Torsten", "Astrid", "Eirik", "Signe", "Vidar"],
        "last": ["Stone-Hand", "Hearth-Born", "Haldorsen", "Frostvein", "Raven-Brand", "Keld", "Morn", "Oak-Shield"],
        "anchors": ["della Via del Fabbro", "del Ponte Nord", "della Corte del Jarl", "del Mercato Alto", "della Riva Fredda", "della Porta di Quercia"],
    },
    "Summerset Isles": {
        "tradition": "Altmer",
        "first": ["Calion", "Elenwen", "Tirion", "Niranye", "Aranwe", "Liriel", "Caldor", "Vanya"],
        "last": ["Aurelin", "Elenor", "Seyrane", "Calindil", "Mirel", "Tavaro", "Larethor", "Valandor"],
        "anchors": ["del Colonnato", "della Terrazza Marina", "dei Gradini Bianchi", "del Giardino d'Acqua", "della Galleria", "della Porta di Vetro"],
    },
    "Valenwood": {
        "tradition": "Bosmer/Tamrielic",
        "first": ["Erdal", "Falinwe", "Miraen", "Talan", "Sarethi", "Virel", "Nimel", "Orin"],
        "last": ["Leaf-Thread", "Everwake", "Harin", "Selaro", "Mestrel", "Taviel", "Dalen", "Rinna"],
        "anchors": ["della Passerella", "del Sentiero Alto", "della Piazza delle Corde", "del Ponte Vivo", "della Radura", "del Mercato di Corteccia"],
    },
}

CATEGORY = {
    "alchimista": ("distilleria", ["infuso", "ampolla", "resina", "fiala", "crogiolo"], "prepara reagenti in piccoli lotti e annota ogni miscela sul banco di pietra"),
    "arcieria": ("arceria", ["corda", "penna", "tacca", "arco", "faretra"], "tende le corde a mano e fa provare l'equilibrio dell'arco nel cortile"),
    "armaiolo": ("armeria", ["giuntura", "rivetto", "lamina", "bordo", "maglia"], "adatta protezioni su misura e conserva i modelli di taglia dietro il banco"),
    "abbigliamento": ("sartoria", ["orlo", "trama", "bottone", "fodera", "telaio"], "taglia e ripara capi robusti, con campioni di stoffa appesi alla parete"),
    "carovana-khajiit": ("carovana", ["bastio", "tenda", "carico", "stuoia", "lanterna"], "cambia merce con le stagioni e tratta con viaggiatori davanti ai carri coperti"),
    "contenitori": ("magazzino", ["cassa", "giara", "cesto", "botte", "scrigno"], "sceglie chiusure e rivestimenti pratici per mercanti, pescatori e carovanieri"),
    "generale": ("emporio", ["scaffale", "misura", "cordame", "campione", "bilancia"], "tiene merci d'uso quotidiano su scaffali segnati e rifornisce chi parte all'alba"),
    "fabbricante-armi": ("officina d'armi", ["tempera", "guardia", "filo", "pomolo", "incastro"], "rifinisce lame e impugnature su commissione, senza promettere meriti che non può provare"),
    "fabbro": ("fucina", ["incudine", "martello", "brace", "tenaglia", "cuneo"], "lavora ferro e riparazioni leggere con una fucina visibile dalla strada"),
    "oggetti-magici": ("gabinetto arcano", ["sigillo", "cristallo", "runa", "vetro", "inchiostro"], "verifica sigilli e provenienza davanti al cliente prima di esporre ogni pezzo"),
    "taverna": ("taverna", ["focolare", "panca", "brocca", "cucina", "soglia"], "serve pasti semplici e offre tavoli puliti a viaggiatori, marinai e gente del posto"),
}

FORMS = ["Casa", "Bottega", "Officina", "Corte", "Portico", "Dispensa", "Galleria", "Sala"]
INHERIT_FORMS = ["L'Eredità", "La Concessione", "Il Banco Antico", "La Chiave di Bottega", "La Licenza Vecchia", "La Sala Ereditata", "Il Registro di Famiglia", "La Porta Custodita"]
METAPHORS = ["Lampada Ferma", "Nodo Paziente", "Soglia Chiara", "Ramo Silente", "Mano Misurata", "Pietra Asciutta", "Vento di Ritorno", "Coppa Quietta", "Corda Tesa", "Ago Stabile", "Specchio Opaco", "Marea Lenta", "Passo Sicuro", "Vetro Calmo", "Tavola Larga", "Riva Gentile"]
MIDDLES = ["Aelius", "Belyn", "Corvin", "Dareth", "Eris", "Faren", "Galon", "Hadril", "Ivar", "Joran", "Kalen", "Lethan"]
UNIQUE_TAILS = ["del Vicolo", "della Scala", "della Riva", "del Cortile", "del Portone", "della Sala", "del Ponte", "della Loggia", "della Fonte", "del Campanile", "della Darsena", "della Stadera"]


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def owner(region: str, plan_id: int, category: str) -> str:
    source = REGIONAL[region]
    # Caravans retain a Khajiit keeper without forcing that convention on every shop.
    if category == "carovana-khajiit":
        first = ["Ri'jirr", "Ma'zaka", "S'virr", "Daro'ji", "Kha'zir", "J'naasha"][plan_id % 6]
        last = ["of the Open Road", "Sabi", "Daro", "Rin", "Kesh", "Vasha"][(plan_id // 6) % 6]
        middle = MIDDLES[(plan_id // 36) % len(MIDDLES)] + ["ra", "zi", "ne", "ko", "va", "shi"][(plan_id // 432) % 6]
        return f"{first} {middle} {last}"
    first = source["first"][plan_id % len(source["first"])]
    last = source["last"][(plan_id // len(source["first"])) % len(source["last"])]
    middle = MIDDLES[(plan_id // (len(source["first"]) * len(source["last"])) + plan_id) % len(MIDDLES)]
    return f"{first} {middle} {last}"


def candidate(record: dict, local_index: int) -> tuple[str, str]:
    region = record["region"]
    source = REGIONAL[region]
    category = record["categoryKey"]
    kind, objects, _ = CATEGORY[category]
    pid = record["planId"]
    style = local_index % 5
    anchor = source["anchors"][(pid // 5) % len(source["anchors"])]
    obj = objects[(pid + local_index) % len(objects)]
    founder = source["last"][(pid * 3 + 1) % len(source["last"])]
    form = FORMS[(pid + local_index) % len(FORMS)]
    place = record["locationKey"].split("/", 1)[1].replace("-", " ").title()
    if style == 0:  # Tamriel canon sobrio
        return f"{form} di {founder}", "family-and-workshop"
    if style == 1:  # civic-mercantile
        return f"{kind.capitalize()} {anchor} di {place}", "civic-landmark"
    if style == 2:  # artigianale e materico
        return f"{obj.title()} di {anchor.removeprefix('del ').removeprefix('della ').removeprefix('dei ').removeprefix('delle ')}", "craft-and-material"
    if style == 3:  # family, casate e insegne ereditate
        return f"{INHERIT_FORMS[(pid + local_index) % len(INHERIT_FORMS)]} di {founder}", "inherited-lease"
    return f"{METAPHORS[(pid + local_index) % len(METAPHORS)]} {anchor}", "restrained-metaphor"


def description(record: dict, pattern: str, local_index: int) -> str:
    _, objects, service = CATEGORY[record["categoryKey"]]
    object_word = objects[(record["planId"] * 2 + local_index) % len(objects)]
    variants = [
        f"{record['name']} {service}; il responsabile cura anche {object_word} e ordini riservati per la clientela abituale.",
        f"Dietro l'insegna di {record['name']}, {service}; gli avventori apprezzano tempi chiari e materiali controllati.",
        f"{record['name']} ha un ingresso modesto ma ordinato: {service}, dando priorità a chi conosce già il quartiere.",
        f"Nel locale di {record['name']}, {service}; la merce più richiesta resta vicina alla porta per chi viaggia leggero.",
        f"{record['name']} lavora senza clamore: {service}; gli ordini vengono raccolti con cura e consegnati quando sono pronti.",
    ]
    return variants[(record["planId"] + local_index) % len(variants)]


def rebuild() -> dict:
    original = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    rows = original["records"]
    seen_names: set[str] = set()
    seen_owners: set[str] = set()
    locality_indices: defaultdict[str, int] = defaultdict(int)
    rebuilt = []
    reviews: dict[str, dict] = {}

    for source in rows:
        if source.get("status") == "needs_review" or not source.get("locationKey"):
            rebuilt.append(source)
            continue
        record = {key: source[key] for key in ("planId", "locationKey", "categoryKey", "level", "seed")}
        record["region"] = source["locationKey"].split("/", 1)[0].replace("-", " ").title()
        # Preserve the project spelling for compound region keys.
        record["region"] = next(key for key in REGIONAL if norm(key) == norm(record["region"]))
        locality = source["locationKey"]
        local_index = locality_indices[locality]
        locality_indices[locality] += 1
        name, pattern = candidate(record, local_index)
        base_name = name
        disambiguator = 0
        while norm(name) in seen_names:
            disambiguator += 1
            place = record["locationKey"].split("/", 1)[1].replace("-", " ").title()
            if disambiguator == 1:
                name = f"{base_name} presso {place}"
            else:
                tail = UNIQUE_TAILS[(record["planId"] + disambiguator) % len(UNIQUE_TAILS)]
                name = f"{base_name} presso {place} {tail}"
        record["name"] = name
        record["owner"] = owner(record["region"], record["planId"], record["categoryKey"])
        if norm(record["owner"]) in seen_owners:
            raise ValueError(f"duplicate owner: {record['owner']}")
        record["description"] = description(record, pattern, local_index)
        record["status"] = "approved"
        seen_names.add(norm(record["name"]))
        seen_owners.add(norm(record["owner"]))
        del record["region"]
        rebuilt.append(record)

    # Validation and compact locality reports.
    approved = [r for r in rebuilt if r.get("status") == "approved"]
    if len(approved) != len(seen_names) or len(approved) != len(seen_owners):
        raise ValueError("global uniqueness validation failed")
    for locality, group in _group_by(approved, "locationKey").items():
        patterns = Counter(_pattern_for_name(r["name"]) for r in group)
        reviews[locality] = {
            "rows": len(group), "approved": len(group), "needs_review": 0,
            "duplicate_names": 0, "duplicate_owners": 0,
            "naming_patterns": dict(patterns),
        }
    original["records"] = rebuilt
    original["localityReview"] = [reviews[key] | {"locationKey": key} for key in sorted(reviews)]
    original["generation"] = {
        "method": "reviewed-content-rebuild", "batchSize": 30,
        "approaches": ["canon-sobrio", "civico-mercantile", "artigianale-materico", "eredita-familiare", "atmosferico-contenuto"],
        "approved": len(approved), "needsReview": len(rebuilt) - len(approved),
    }
    return original


def _group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def _pattern_for_name(name: str) -> str:
    if name.startswith(tuple(INHERIT_FORMS)):
        return "inherited-lease"
    if name.split()[0] in {entry.split()[0] for entry in METAPHORS}:
        return "restrained-metaphor"
    if any(name.lower().startswith(CATEGORY[key][0]) for key in CATEGORY):
        return "civic-landmark"
    if name.startswith(tuple(FORMS)):
        return "family-and-workshop"
    if " di " in name:
        return "craft-and-material"
    return "family-and-workshop"


if __name__ == "__main__":
    plan = rebuild()
    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(plan['records'])} planned records to {PLAN_PATH}")
