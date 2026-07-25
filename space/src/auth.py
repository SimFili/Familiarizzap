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


def normalize_full_name(first_name: str, last_name: str) -> str:
    first = clean_name_part(first_name)
    last = clean_name_part(last_name)
    if len(first) < 2 or len(last) < 2:
        raise IdentityError("Inserisci nome e cognome completi.")
    if any(char.isdigit() for char in first + last):
        raise IdentityError("Nome e cognome non possono contenere numeri.")
    return f"{first} {last}".casefold()


def display_name(first_name: str, last_name: str) -> str:
    normalized = normalize_full_name(first_name, last_name)
    del normalized
    return f"{clean_name_part(first_name)} {clean_name_part(last_name)}"


def participant_id(first_name: str, last_name: str, salt: str) -> str:
    normalized = normalize_full_name(first_name, last_name)
    digest = hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]
