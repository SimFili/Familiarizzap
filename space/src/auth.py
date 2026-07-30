from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata


class IdentityError(ValueError):
    """Raised when a participant identity is incomplete."""


def clean_name_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_name(value: str) -> str:
    """Normalize the single display name used by the small pilot group."""
    name = clean_name_part(value)
    if len(name) < 2:
        raise IdentityError("Inserisci il tuo nome.")
    if any(char.isdigit() for char in name):
        raise IdentityError("Il nome non può contenere numeri.")
    return name.casefold()


def display_name_only(value: str) -> str:
    normalize_name(value)
    return clean_name_part(value)


def participant_name_id(value: str, salt: str) -> str:
    """Return the deterministic private identifier for a display name."""
    normalized = normalize_name(value)
    return hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
