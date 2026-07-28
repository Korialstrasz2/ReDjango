"""Generazione e modifica di immagini.

Due backend dietro la stessa interfaccia: l'API immagini di OpenAI e un server
Stable Diffusion locale (AUTOMATIC1111 o compatibile). Entrambi restituiscono PNG
in base64, che il servizio archivia poi come normale `UploadedImage`.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from backend.core.api import ApiError

from .base import post_json


class OpenAIImageProvider:
    """`/images/generations` e `/images/edits` dell'API compatibile OpenAI."""

    supports_editing = True

    def __init__(self, provider):
        self.provider = provider

    def _headers(self) -> dict[str, str]:
        secret = self.provider.read_secret()
        if not secret:
            raise ApiError("ai.secret_missing", "Configura la chiave API del provider immagini.", status=409)
        return {"Authorization": f"Bearer {secret}"}

    def generate(self, *, prompt: str, size: str, quality: str, source_image_base64: str = "") -> str:
        base = (self.provider.base_url or "").rstrip("/")
        if not base:
            raise ApiError("ai.base_url_missing", "Configura l'indirizzo del provider immagini.", status=409)
        payload: dict[str, Any] = {
            "model": self.provider.model or "gpt-image-1",
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        if quality:
            payload["quality"] = quality
        if source_image_base64:
            # L'endpoint di modifica accetta l'immagine di partenza in base64.
            payload["image"] = [source_image_base64]
            endpoint = f"{base}/images/edits"
        else:
            endpoint = f"{base}/images/generations"

        body = post_json(endpoint, payload, self._headers())
        entries = body.get("data") or []
        image = (entries[0] if entries else {}).get("b64_json") or ""
        if not image:
            raise ApiError("ai.image_missing", "Il provider non ha restituito un'immagine.", status=502)
        return image


class StableDiffusionImageProvider:
    """API di AUTOMATIC1111: `txt2img` per creare, `img2img` per modificare."""

    supports_editing = True

    def __init__(self, provider):
        self.provider = provider

    def generate(self, *, prompt: str, size: str, quality: str, source_image_base64: str = "") -> str:
        base = (self.provider.base_url or "").rstrip("/")
        if not base:
            raise ApiError("ai.base_url_missing", "Configura l'indirizzo del server Stable Diffusion.", status=409)
        options = self.provider.options if isinstance(self.provider.options, dict) else {}
        width, _, height = size.partition("x")
        steps = {"low": 15, "medium": 25, "high": 40}.get(quality, 25)
        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": str(options.get("negativePrompt") or ""),
            "width": int(width or 1024),
            "height": int(height or 1024),
            "steps": steps,
            "cfg_scale": float(options.get("cfgScale") or 7),
        }
        if self.provider.model:
            payload["override_settings"] = {"sd_model_checkpoint": self.provider.model}
        if source_image_base64:
            payload["init_images"] = [source_image_base64]
            payload["denoising_strength"] = float(options.get("denoisingStrength") or 0.6)
            endpoint = f"{base}/sdapi/v1/img2img"
        else:
            endpoint = f"{base}/sdapi/v1/txt2img"

        body = post_json(endpoint, payload, {})
        images = body.get("images") or []
        if not images:
            raise ApiError("ai.image_missing", "Il server non ha restituito un'immagine.", status=502)
        return str(images[0])


def decode_image(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ApiError("ai.image_invalid", "L'immagine restituita non è leggibile.", status=502) from error
