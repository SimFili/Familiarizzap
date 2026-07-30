from __future__ import annotations

import pytest

from src.auth import (
    AccessCodeError,
    IdentityError,
    access_code_hash,
    generate_access_code,
    normalize_access_code,
    normalize_full_name,
    participant_id,
    verify_access_code,
)


def test_name_variants_produce_same_identifier():
    salt = "test-secret"
    first = participant_id("  FÀBIO ", " Zanda  ", salt)
    second = participant_id("fàbio", "zanda", salt)
    assert first == second


@pytest.mark.parametrize(
    ("first_name", "last_name"),
    [("", "Rossi"), ("A", "Rossi"), ("Anna", ""), ("Anna2", "Rossi")],
)
def test_incomplete_or_invalid_names_are_rejected(first_name, last_name):
    with pytest.raises(IdentityError):
        normalize_full_name(first_name, last_name)


def test_personal_code_is_readable_hashed_and_verifiable():
    code = generate_access_code()

    assert len(code.split("-")) == 3
    assert all(len(part) == 4 for part in code.split("-"))
    stored = access_code_hash(code, "participant", "secret")
    assert code.replace("-", "") not in stored
    assert verify_access_code(
        code.lower(), "participant", "secret", stored
    )
    assert not verify_access_code(
        code, "different-participant", "secret", stored
    )


def test_personal_code_normalization_rejects_ambiguous_or_short_values():
    with pytest.raises(AccessCodeError):
        normalize_access_code("ABC")
    with pytest.raises(AccessCodeError):
        normalize_access_code("OOOO-OOOO-OOOO")
