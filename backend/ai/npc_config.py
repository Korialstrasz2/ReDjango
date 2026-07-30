"""Configurazione della generazione personaggi, letta da un'unica riga JSON.

Vive in `SettingDefinition` come le regole del Mercato: è configurazione di
gioco amministrata da una pagina di gestione, non una preferenza personale.
"""

from __future__ import annotations

import re
from copy import deepcopy

from django.core.exceptions import ValidationError

from backend.core.models import SettingDefinition


NPC_GENERATION_KEY = "ai.npc_generation"

# Vincoli pubblicati da OpenAI per gpt-image-2: lato massimo 3840px, entrambi i
# lati multipli di 16, rapporto massimo 3:1 e un intervallo di pixel totali.
# Validarli qui evita di scoprire un formato illegale al momento della spesa.
MINIMUM_PIXELS = 655_360
MAXIMUM_PIXELS = 8_294_400
MAXIMUM_EDGE = 3840
EDGE_MULTIPLE = 16
MAXIMUM_ASPECT_RATIO = 3
PORTRAIT_QUALITIES = ("low", "medium", "high")
MAXIMUM_STYLE_CHARACTERS = 400

_SIZE_RE = re.compile(r"^(\d{2,4})x(\d{2,4})$")


def _italian_thousands(value: int) -> str:
    """655.360, non 655,360: il messaggio finisce in un'interfaccia italiana."""

    return f"{value:,}".replace(",", ".")

DEFAULT_NPC_GENERATION = {
    # 640x1024 è il minimo fatturabile e ha già l'inquadratura giusta per un busto.
    "portraitSize": "640x1024",
    "portraitQuality": "medium",
    "portraitStyle": "Ritratto a mezzo busto, pittura a olio fantasy, luce naturale morbida, sfondo neutro.",
    # Il Master può togliere del tutto l'opzione «contesto della campagna» senza
    # dover disabilitare l'intero strumento.
    "allowCampaignContext": True,
}


def parse_size(raw: object) -> tuple[int, int]:
    match = _SIZE_RE.match(str(raw or "").strip().lower())
    if match is None:
        raise ValidationError({"portraitSize": "Il formato deve essere tipo 640x1024."})
    return int(match.group(1)), int(match.group(2))


def validate_size(raw: object) -> str:
    """Rifiuta i formati che l'API non accetterebbe, spiegando il perché."""

    width, height = parse_size(raw)
    if width % EDGE_MULTIPLE or height % EDGE_MULTIPLE:
        raise ValidationError({"portraitSize": f"Entrambi i lati devono essere multipli di {EDGE_MULTIPLE}."})
    if max(width, height) > MAXIMUM_EDGE:
        raise ValidationError({"portraitSize": f"Il lato più lungo non può superare {MAXIMUM_EDGE} pixel."})
    pixels = width * height
    if pixels < MINIMUM_PIXELS:
        raise ValidationError(
            {"portraitSize": f"Troppo piccola: servono almeno {_italian_thousands(MINIMUM_PIXELS)} pixel totali (640x1024 è il minimo)."}
        )
    if pixels > MAXIMUM_PIXELS:
        raise ValidationError({"portraitSize": f"Troppo grande: massimo {_italian_thousands(MAXIMUM_PIXELS)} pixel totali."})
    if max(width, height) / min(width, height) > MAXIMUM_ASPECT_RATIO:
        raise ValidationError({"portraitSize": "Il rapporto fra i lati non può superare 3:1."})
    return f"{width}x{height}"


def validate_npc_generation(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValidationError({"values": "La configurazione deve essere un oggetto."})
    quality = str(raw.get("portraitQuality") or DEFAULT_NPC_GENERATION["portraitQuality"]).strip().lower()
    if quality not in PORTRAIT_QUALITIES:
        raise ValidationError({"portraitQuality": f"Qualità non valida: usa {', '.join(PORTRAIT_QUALITIES)}."})
    style = str(raw.get("portraitStyle") or "").strip()
    if len(style) > MAXIMUM_STYLE_CHARACTERS:
        raise ValidationError({"portraitStyle": f"Massimo {MAXIMUM_STYLE_CHARACTERS} caratteri."})
    return {
        "portraitSize": validate_size(raw.get("portraitSize") or DEFAULT_NPC_GENERATION["portraitSize"]),
        "portraitQuality": quality,
        "portraitStyle": style,
        "allowCampaignContext": bool(raw.get("allowCampaignContext", True)),
    }


def npc_generation_config() -> dict:
    """La configurazione effettiva, con i default per le chiavi mai salvate."""

    setting = SettingDefinition.objects.filter(
        key=NPC_GENERATION_KEY, active=True, archived_at__isnull=True
    ).first()
    config = deepcopy(DEFAULT_NPC_GENERATION)
    if setting is None:
        return config
    stored = setting.default_value if setting.value is None else setting.value
    if isinstance(stored, dict):
        config.update({key: stored[key] for key in config if key in stored})
    return config
