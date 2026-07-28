"""Vocabolario dei tag della colonna sonora.

È dato di regola del backend, come la tabella del meteo: la picklist dell'interfaccia
non accetta valori liberi, così i filtri restano prevedibili e le tracce importate
non moltiplicano etichette quasi identiche. Aggiungere un tag significa aggiungere
una voce qui: i valori restano stabili, le etichette sono in italiano.
"""

AUDIO_TAG_CHOICES = [
    {"value": "musica", "label": "Musica"},
    {"value": "ambient", "label": "Ambient"},
    {"value": "combattimento", "label": "Combattimento"},
    {"value": "esplorazione", "label": "Esplorazione"},
    {"value": "taverna", "label": "Taverna"},
    {"value": "citta", "label": "Città"},
    {"value": "natura", "label": "Natura"},
    {"value": "dungeon", "label": "Dungeon"},
    {"value": "tensione", "label": "Tensione"},
    {"value": "boss", "label": "Scontro epico"},
    {"value": "riposo", "label": "Riposo"},
    {"value": "viaggio", "label": "Viaggio"},
    {"value": "effetti", "label": "Effetti sonori"},
]

AUDIO_TAG_VALUES = frozenset(entry["value"] for entry in AUDIO_TAG_CHOICES)

AUDIO_TAG_LABELS = {entry["value"]: entry["label"] for entry in AUDIO_TAG_CHOICES}
