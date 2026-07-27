from __future__ import annotations

from typing import Any


# nome, lunghezza, potenza, pesantezza, danno, modo, banda, bonus 1, bonus 2
_PRESET_ROWS = (
    ("martello", "corta", "potente", "pesante", "contundente", "melee", "A", "Per ogni 10 DMG di un singolo attacco: -1 PA al nemico.", ""),
    ("tirapugni", "corta", "precisa", "leggera", "contundente", "melee", "A", "Non occupa slot; può essere nascosto.", ""),
    ("nunchaku", "corta", "media", "media", "contundente", "melee", "A", "1 reroll per turno.", ""),
    ("coltello", "corta", "precisa", "leggera", "taglio", "melee", "A", "Può essere tirato; +5 ATK al tiro.", ""),
    ("daga", "corta", "media", "media", "taglio", "melee", "A", "Danno contundente o perforante opzionale.", ""),
    ("armblade", "corta", "potente", "pesante", "taglio", "melee", "A", "1 attacco gratis per turno dopo aver ricevuto un attacco.", ""),
    ("stiletto", "corta", "media", "media", "perforante", "melee", "A", "Un attacco per turno ignora il 100% della RD nemica.", ""),
    ("shiv", "corta", "precisa", "leggera", "perforante", "melee", "A", "Non occupa slot; può essere nascosto.", ""),
    ("kriss", "corta", "potente", "pesante", "perforante", "melee", "A", "Danno da taglio opzionale.", ""),
    ("mazza", "media", "precisa", "leggera", "contundente", "melee", "B", "+1 ATK per ogni attacco sullo stesso nemico nel turno.", ""),
    ("mazzafrusta", "media", "potente", "pesante", "contundente", "melee", "B", "Può attaccare un nemico adiacente al bersaglio spendendo 1 PA.", ""),
    ("kusarigama", "media", "media", "media", "perforante", "melee", "B", "Danno contundente opzionale entro 9 m; recupero con 2 PA.", ""),
    ("spadalunga", "media", "media", "media", "taglio", "melee", "B", "Danno contundente o perforante opzionale.", ""),
    ("sciabola", "media", "potente", "pesante", "taglio", "melee", "B", "Per ogni 15 DMG di un singolo attacco: 1 Sanguinamento.", ""),
    ("katana", "media", "precisa", "leggera", "taglio", "melee", "B", "1 reroll per turno al tiro attacco o danno.", ""),
    ("fioretto", "media", "precisa", "leggera", "perforante", "melee", "B", "Un attacco per turno ignora il 100% della RD nemica.", ""),
    ("estoc", "media", "potente", "pesante", "perforante", "melee", "B", "+1 ATK per ogni attacco sullo stesso nemico nel turno.", ""),
    ("bastone", "lunga", "precisa", "leggera", "contundente", "melee", "C", "1 reroll per turno.", ""),
    ("martellodaguerra", "lunga", "potente", "pesante", "contundente", "melee", "C", "Per ogni 10 DMG di un singolo attacco: -1 PA al nemico.", ""),
    ("bastoneconpesi", "lunga", "media", "media", "contundente", "melee", "C", "Può attaccare un nemico adiacente al bersaglio spendendo 1 PA.", ""),
    ("asciaaduemani", "lunga", "media", "media", "taglio", "melee", "C", "Danno contundente opzionale.", ""),
    ("spadone", "lunga", "precisa", "leggera", "taglio", "melee", "C", "Danno contundente o perforante opzionale.", ""),
    ("zweihander", "lunga", "potente", "pesante", "taglio", "melee", "C", "Per ogni 15 DMG di un singolo attacco: 1 Sanguinamento.", ""),
    ("lancia", "lunga", "precisa", "leggera", "perforante", "melee", "C", "Può essere tirata; +8 ATK al tiro.", ""),
    ("picca", "lunga", "potente", "pesante", "perforante", "melee", "C", "Può attaccare a 2 celle di distanza.", ""),
    ("beccodicorvo", "lunga", "media", "media", "perforante", "melee", "C", "Danno contundente opzionale.", ""),
    ("coltellodalancio", "corta", "media", "media", "perforante", "throwable", "D", "+1 ATK per ogni attacco sullo stesso nemico nel turno.", ""),
    ("accettadalancio", "corta", "potente", "pesante", "taglio", "throwable", "D", "Per ogni 10 DMG di un singolo attacco: 1 Sanguinamento.", ""),
    ("shuriken", "corta", "precisa", "leggera", "perforante", "throwable", "D", "Dopo 2 attacchi, il successivo costa 1 PA in meno.", ""),
    ("balestra", "media", "precisa", "leggera", "perforante", "ranged", "C", "Nessun malus per il tiro in mischia.", "Ricarica: 3 PA."),
    ("balestraaripetizione", "media", "media", "media", "perforante", "ranged", "C", "Caricatore da 3 dardi.", "Ricarica: 3 PA fissi +3 PA per dardo."),
    ("arcocorto", "media", "media", "media", "perforante", "ranged", "B", "Nessun malus per il tiro in mischia.", ""),
    ("arcolungo", "lunga", "potente", "pesante", "perforante", "ranged", "C", "Gittata 18 m; +3 ATK tra 9 e 18 m.", ""),
    ("arcocomposito", "lunga", "precisa", "leggera", "perforante", "ranged", "C", "1 reroll per turno.", ""),
    ("chukonu", "lunga", "potente", "pesante", "perforante", "ranged", "C", "Caricatore da 5 dardi.", "Ricarica: 5 PA fissi +3 PA per dardo."),
    ("tonfa", "corta", "precisa", "leggera", "contundente", "melee", "A", "1 reroll per turno contro un attacco ricevuto.", ""),
    ("tridente", "lunga", "potente", "pesante", "perforante", "melee", "C", "Può essere tirato; +8 ATK al tiro.", ""),
    ("accetta", "corta", "potente", "pesante", "taglio", "melee", "A", "+1 ATK per ogni attacco sullo stesso nemico nel turno.", ""),
    ("ascia", "media", "potente", "pesante", "taglio", "melee", "B", "Per ogni 15 DMG di un singolo attacco: 1 Sanguinamento.", ""),
    ("maninude", "maninude", "maninude", "media", "contundente", "unarmed", "", "Categoria speciale: mani nude.", "2 PA per attacco."),
    ("natura1", "corta", "precisa", "leggera", "natura", "nature", "", "Preset per forma naturale corta.", ""),
    ("natura2", "media", "media", "media", "natura", "nature", "", "Preset per forma naturale media.", ""),
    ("natura3", "lunga", "potente", "pesante", "natura", "nature", "", "Preset per forma naturale lunga.", ""),
    ("bastonemagico", "lunga", "precisa", "leggera", "magico", "magic", "", "Arma magica con regole separate.", ""),
    ("rapier", "media", "media", "media", "perforante", "melee", "B", "Danno da taglio opzionale.", ""),
    ("grimorio", "corta", "media", "media", "magico", "magic", "", "Danno magico a scelta o contundente.", ""),
)


def _special_rules(name: str, mode: str) -> list[str]:
    rules: list[str] = []
    if mode == "throwable":
        rules.extend(("Gittata base 4 m.", "Oltre 4 m: -2 ATK per cella.", "Gittata massima: Forza in metri.", "In mischia: -4 ATK."))
    elif mode == "ranged":
        rules.extend(("Gittata base 9 m.", "Oltre 9 m: -2 ATK per cella.", "In mischia: -7 ATK salvo eccezioni."))
    if name in {"coltello", "lancia", "tridente"}:
        rules.append("Può usare le regole di lancio indicate nel bonus del tipo.")
    return rules


def _ranged_profile(name: str, mode: str) -> dict[str, Any]:
    if mode != "ranged":
        return {}
    if name == "balestra":
        return {"ammunitionType": "dardo", "magazineSize": 1, "reloadBaseCost": 3}
    if name == "balestraaripetizione":
        return {"ammunitionType": "dardo", "magazineSize": 3, "reloadBaseCost": 3, "reloadPerProjectileCost": 3}
    if name == "chukonu":
        return {"ammunitionType": "dardo", "magazineSize": 5, "reloadBaseCost": 5, "reloadPerProjectileCost": 3}
    return {"ammunitionType": "freccia"}


WEAPON_TYPE_PRESETS: tuple[dict[str, Any], ...] = tuple(
    {
        "name": name,
        "length": length,
        "power": power,
        "bonus1": bonus1,
        "bonus2": bonus2,
        "profile": {
            "heaviness": heaviness,
            "length": length,
            "power": power,
            "damageType": damage,
            "combatMode": mode,
            "costBand": band,
            "handling": "two_handed" if length == "lunga" else "one_handed" if length in {"corta", "media"} else "special",
            "baseRangeMeters": 4 if mode == "throwable" else 9 if mode == "ranged" else 0,
            "specialRules": _special_rules(name, mode),
            "bonusNotes": [note for note in (bonus1, bonus2) if note],
            **_ranged_profile(name, mode),
        },
    }
    for name, length, power, heaviness, damage, mode, band, bonus1, bonus2 in _PRESET_ROWS
)
