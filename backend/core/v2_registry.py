from django.apps import apps


V2_MODEL_LABELS = [
    "core.GlobalModifiers",
    "core.FamigliaSkill",
    "core.Skill",
    "core.Effetto",
    "core.EffettiSkill",
    "core.EffettiEMalattie",
    "core.Competenze",
    "core.TipoArma",
    "core.OpzioneTipoOggetto",
    "core.Oggetto",
    "core.ReagenteAlchemico",
    "characters.Zaino",
    "characters.Faretra",
    "characters.ContenitoreInventario",
    "characters.VoceContenitoreInventario",
    "characters.EffettiPersonaggio",
    "characters.Equip",
    "characters.Note",
    "characters.Personaggio",
    "characters.TiroCompetenza",
    "core.Giocatore",
    "core.DatiCampagna",
    "media_library.ImageCategory",
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
    "core.SettingDefinition",
    "core.SettingOverride",
    "core.Theme",
    "dice_tools.DiceSet",
    "dice_tools.DiceTexture",
]


def get_v2_models(selected_labels: list[str] | None = None):
    labels = selected_labels or V2_MODEL_LABELS
    return [apps.get_model(label) for label in labels]
