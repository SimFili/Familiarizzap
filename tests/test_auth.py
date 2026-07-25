from __future__ import annotations

import pytest

from src.auth import IdentityError, normalize_full_name, participant_id


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
