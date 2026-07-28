"""Campaign weather table and roll, ported from the Elder `tempo` event list.

The Elder project stored the six weather states as `Evento` rows with a d100
range in `numeri` and rolled them from `generate_event`. ReDjango keeps the same
table and the same two biases, but as backend-owned data instead of editable
event rows: the roll is a rule, not content.

The two biases the master relies on are preserved exactly:

* half of every reroll keeps the weather that is already in play, so a storm
  lasts more than one turn of the clock;
* the fresh roll itself is weighted towards `Soleggiato`, which alone covers
  half of the d100 table.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# Hours of the campaign clock that ask the master for a fresh weather roll.
WEATHER_REMINDER_HOURS = (0, 6, 12, 18)


@dataclass(frozen=True)
class WeatherEntry:
    label: str
    effects: str
    low: int
    high: int

    @property
    def name(self) -> str:
        """The stored form, identical to the Elder `Evento.nome`."""
        return f"{self.label} - {self.effects}"


WEATHER_TABLE: tuple[WeatherEntry, ...] = (
    WeatherEntry("Soleggiato", "No cambiamenti", 1, 50),
    WeatherEntry(
        "Pioggia",
        "Costo movimento in combat +25%, Attacco -3",
        51,
        70,
    ),
    WeatherEntry(
        "Grande Pioggia",
        "Costo movimento in combat +50%, Attacco -5, Ogni casella dopo la prima: "
        "possibilità di mancare atk o cast a distanza +10%, Danno da fuoco -25%, "
        "Danno elettro +25%, Costo movimento in viaggio +50%",
        71,
        80,
    ),
    WeatherEntry(
        "Nebbia",
        "Ogni casella dopo la prima: possibilità di mancare atk o cast a distanza +20%, "
        "Danno da gelo +25%, Costo movimento in viaggio +50%",
        81,
        90,
    ),
    WeatherEntry(
        "Temporale",
        "Attacco -7, Costo movimento in combat +50%, Ogni casella dopo la prima: "
        "possibilità di mancare atk o cast a distanza +20%, Costo movimento in viaggio +100%",
        91,
        95,
    ),
    WeatherEntry(
        "Tempesta",
        "Attacco -10, Costo movimento in combat +100%, Ogni casella dopo la prima: "
        "possibilità di mancare atk o cast a distanza +33%, Costo movimento in viaggio +200%",
        96,
        100,
    ),
)

DEFAULT_WEATHER = WEATHER_TABLE[0]


def split_weather(stored: str) -> tuple[str, str]:
    """Split a stored weather string into its name and its rule effects."""
    label, _, effects = str(stored or "").partition(" - ")
    return label.strip(), effects.strip()


def entry_for(stored: str) -> WeatherEntry | None:
    """Find the table row a stored weather string belongs to.

    Matching uses only the name, so a campaign whose effect text was edited by
    hand still counts as the same weather when the roll decides to prolong it.
    """
    label = split_weather(stored)[0].casefold()
    if not label:
        return None
    return next((entry for entry in WEATHER_TABLE if entry.label.casefold() == label), None)


def roll_weather(current: str, rng: random.Random | None = None) -> tuple[WeatherEntry, bool]:
    """Roll the next weather, returning the entry and whether it was prolonged.

    A campaign with no recorded weather, or one holding a name that is no longer
    in the table, is treated as `Soleggiato` — the same fallback the Elder view
    used for an empty `meteo`.
    """
    source = rng or random.Random()
    if source.randint(1, 2) == 1:
        return entry_for(current) or DEFAULT_WEATHER, True
    roll = source.randint(1, 100)
    matches = [entry for entry in WEATHER_TABLE if entry.low <= roll <= entry.high]
    return source.choice(matches) if matches else DEFAULT_WEATHER, False


def current_hour(stored: str) -> int:
    """Read the campaign clock as an hour, tolerating free text and blanks."""
    try:
        return int(str(stored or "").strip()) % 24
    except ValueError:
        return 0
