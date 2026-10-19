"""Registration: the name an animal types."""

import pytest

from forest_bot.application.users import InvalidName, clean_name
from forest_bot.settings import settings


def test_name_whitespace_is_collapsed():
    assert clean_name("  Ведмідь   Михайло \n") == "Ведмідь Михайло"


@pytest.mark.parametrize("name", ["", "   ", "Я" * (settings.max_name_chars + 1)])
def test_empty_or_too_long_name_is_rejected(name):
    with pytest.raises(InvalidName):
        clean_name(name)
