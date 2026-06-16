from django.apps import apps


V2_MODEL_LABELS = [
    "core.GlobalModifiers",
    "core.FamigliaSkill",
    "core.Skill",
    "core.EffettiSkill",
    "core.EffettiEMalattie",
    "core.Competenze",
    "core.TipoArma",
    "core.Oggetto",
    "characters.Zaino",
    "characters.Faretra",
    "characters.Equip",
    "characters.Note",
    "characters.BorsaReagenti",
    "characters.Personaggio",
    "core.Giocatore",
    "core.DatiCampagna",
    "media_library.UploadedImage",
    "media_library.DatiMappa",
    "core.CampaignLoreEntry",
    "core.CampaignLoreRelation",
    "core.Unit",
    "core.Negozio",
    "core.Guida",
    "core.Curiosita",
    "media_library.AudioFile",
    "core.TimelineEvent",
    "core.HallOfFameCharacter",
    "core.Messaggio",
    "core.NomiRazzeInfo",
]


def get_v2_models(selected_labels: list[str] | None = None):
    labels = selected_labels or V2_MODEL_LABELS
    return [apps.get_model(label) for label in labels]
