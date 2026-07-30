from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
import uuid


class IdentityError(ValueError):
    """Raised when a participant identity is incomplete."""


class AccessCodeError(IdentityError):
    """Raised when a personal journey code is missing or invalid."""


ACCESS_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
ACCESS_CODE_LENGTH = 12


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
    """Return the private lookup hash for a normalized name.

    New participant records use a random participant ID so homonyms can have
    separate journeys. Existing records whose ID was derived from the name
    remain compatible with this lookup value.
    """
    normalized = normalize_full_name(first_name, last_name)
    digest = hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def new_participant_id() -> str:
    return uuid.uuid4().hex


def generate_access_code() -> str:
    """Return a readable code whose plaintext is shown only to the participant."""
    compact = "".join(
        secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(ACCESS_CODE_LENGTH)
    )
    return "-".join(compact[index : index + 4] for index in range(0, 12, 4))


def normalize_access_code(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").upper()
    compact = re.sub(r"[\s-]+", "", normalized)
    if (
        len(compact) != ACCESS_CODE_LENGTH
        or any(char not in ACCESS_CODE_ALPHABET for char in compact)
    ):
        raise AccessCodeError(
            "Il codice percorso deve avere 12 caratteri, per esempio "
            "ABCD-EFGH-JKLM."
        )
    return compact


def access_code_hash(code: str, participant: str, salt: str) -> str:
    compact = normalize_access_code(code)
    return hmac.new(
        salt.encode("utf-8"),
        f"{participant}:{compact}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_access_code(
    code: str,
    participant: str,
    salt: str,
    expected_hash: str,
) -> bool:
    try:
        supplied_hash = access_code_hash(code, participant, salt)
    except AccessCodeError:
        return False
    return hmac.compare_digest(supplied_hash, expected_hash or "")
