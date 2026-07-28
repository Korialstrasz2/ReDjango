"""Cifratura a riposo delle credenziali dei provider.

La chiave deriva da `SECRET_KEY`: un backup del database non basta per leggere una
chiave API, ma ruotare `SECRET_KEY` rende illeggibili le credenziali salvate. È una
scelta deliberata — la decifratura fallita non solleva, restituisce stringa vuota,
così l'interfaccia può chiedere di reinserire la chiave invece di rompersi.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"redjango-ai::{settings.SECRET_KEY}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return ""
