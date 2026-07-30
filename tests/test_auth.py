from __future__ import annotations

import pytest

from src.auth import (
    IdentityError,
    normalize_name,
    participant_name_id,
)


def test_single_name_variants_produce_same_identifier():
    salt = "test-secret"
    first = participant_name_id("  FÀBIO  ", salt)
    second = participant_name_id("fàbio", salt)
    assert first == second


@pytest.mark.parametrize("name", ["", "A", "Anna2"])
def test_invalid_single_names_are_rejected(name):
    with pytest.raises(IdentityError):
        normalize_name(name)
