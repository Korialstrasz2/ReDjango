"""Regole pure del generatore di nomi: nessun accesso al database.

Il generatore Elder teneva queste regole sparse dentro la funzione di estrazione:
un `if race == "Orco"` in mezzo al codice (che produceva «Durok gro- Pugnoferro»,
con lo spazio di troppo) e un peso 1.5 sul primo elemento di ogni lista, cioè un
vantaggio deciso dall'ordine del file e non da una scelta di gioco. Qui le regole
sono dati e l'estrazione è uniforme.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, Sequence


GENDER_MALE = "maschile"
GENDER_FEMALE = "femminile"
GENDER_RANDOM = "casuale"
CONCRETE_GENDERS = (GENDER_MALE, GENDER_FEMALE)
GENDER_CHOICES = (
    {"value": GENDER_MALE, "label": "Maschile"},
    {"value": GENDER_FEMALE, "label": "Femminile"},
    {"value": GENDER_RANDOM, "label": "Casuale"},
)

# Elder accettava soltanto maschio/femmina e sollevava su tutto il resto, pur
# avendo bacini già unisex (gli Argoniani). «Casuale» è l'opzione che serve
# davvero quando si nomina una folla.
GENDER_ALIASES = {
    "m": GENDER_MALE, "maschio": GENDER_MALE, "maschile": GENDER_MALE, "male": GENDER_MALE,
    "f": GENDER_FEMALE, "femmina": GENDER_FEMALE, "femminile": GENDER_FEMALE, "female": GENDER_FEMALE,
    "casuale": GENDER_RANDOM, "random": GENDER_RANDOM, "indifferente": GENDER_RANDOM, "any": GENDER_RANDOM,
}


@dataclass(frozen=True)
class NameJoin:
    """Come il cognome si attacca al nome per una razza.

    `particle` sta davanti al cognome e non è mai separata da esso: è la parte
    che Elder sbagliava.
    """

    male_particle: str = ""
    female_particle: str = ""
    separator: str = " "

    def particle_for(self, gender: str) -> str:
        return self.male_particle if gender == GENDER_MALE else self.female_particle


# Il patronimico Orsimer è l'unica regola di composizione realmente diversa nei
# dati importati: i «cognomi» del bacino sono nomi di genitori (Burz, Ghor), non
# casate, quindi «Mog gro-Burz» è la forma corretta.
RACE_JOINS: dict[str, NameJoin] = {
    "Orsimer": NameJoin(male_particle="gro-", female_particle="gra-"),
}
DEFAULT_JOIN = NameJoin()

# Prefissi onorifici Khajiit: brevi, seguiti da apostrofo, mai staccati dal nome.
# Si normalizza soltanto la maiuscola del prefisso: dopo l'apostrofo la minuscola
# è la forma corretta («J'zargo», «M'aiq»), quindi non va toccata.
_APOSTROPHE_PREFIX = re.compile(r"\b([a-z]{1,3})'(?=\w)")


def normalize_gender(raw: object) -> str:
    """Restituisce un genere canonico, oppure stringa vuota se non riconosciuto."""

    return GENDER_ALIASES.get(str(raw if raw is not None else "").strip().lower(), "")


def resolve_gender(gender: str, *, rng: random.Random | None = None) -> str:
    """Trasforma «casuale» in un genere concreto; gli altri passano invariati."""

    if gender != GENDER_RANDOM:
        return gender
    return (rng or random).choice(CONCRETE_GENDERS)


def normalize_display(value: object) -> str:
    """Ripulisce un nome composto senza cambiarne la sostanza.

    Serve ai bacini scritti a mano dall'amministratore: uno spazio doppio o un
    «j'zargo» minuscolo non devono arrivare al tavolo.
    """

    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip()
    if not text:
        return ""
    text = _APOSTROPHE_PREFIX.sub(lambda match: f"{match.group(1).capitalize()}'", text)
    return text[:1].upper() + text[1:]


def join_name(first_name: str, surname: str, *, race: str = "", gender: str = GENDER_MALE) -> str:
    """Compone nome e cognome secondo la regola della razza."""

    first = str(first_name or "").strip()
    last = str(surname or "").strip()
    if not last:
        return normalize_display(first)
    join = RACE_JOINS.get(str(race or "").strip(), DEFAULT_JOIN)
    particle = join.particle_for(gender)
    return normalize_display(f"{first}{join.separator}{particle}{last}")


def pool_for_gender(names_male: Sequence[str], names_female: Sequence[str], gender: str) -> list[str]:
    """Il bacino del genere richiesto, con ricaduta sull'altro se è vuoto.

    I bacini unisex esistono già nei dati importati (Argoniani): un bacino
    femminile vuoto non è un errore, è una cultura che usa gli stessi nomi.
    """

    primary = list(names_female if gender == GENDER_FEMALE else names_male)
    if primary:
        return primary
    return list(names_male if gender == GENDER_FEMALE else names_female)


def pick(pool: Sequence[str], *, rng: random.Random | None = None, exclude: Iterable[str] = ()) -> str:
    """Estrazione uniforme: ogni voce del bacino ha lo stesso peso."""

    blocked = {str(entry).casefold() for entry in exclude}
    candidates = [str(entry).strip() for entry in pool if str(entry).strip()]
    available = [entry for entry in candidates if entry.casefold() not in blocked] or candidates
    if not available:
        return ""
    return (rng or random).choice(available)
