"""Registration: name cleanup offline, then get/register against the real PostgreSQL
(see the run_in_db fixture)."""

import pytest

from forest_bot.application.users import InvalidName, clean_name, get_user, register_user
from forest_bot.settings import settings

TELEGRAM_ID = 999_000_000_001


def test_name_whitespace_is_collapsed():
    assert clean_name("  Ведмідь   Михайло \n") == "Ведмідь Михайло"


@pytest.mark.parametrize("name", ["", "   ", "Я" * (settings.max_name_chars + 1)])
def test_empty_or_too_long_name_is_rejected(name):
    with pytest.raises(InvalidName):
        clean_name(name)


async def _register_and_rename() -> tuple:
    before = await get_user(TELEGRAM_ID)
    first = await register_user(TELEGRAM_ID, " Лисичка ")
    renamed = await register_user(TELEGRAM_ID, "Лисичка-сестричка")
    after = await get_user(TELEGRAM_ID)
    return before, first, renamed, after


def test_register_then_register_again_renames(run_in_db):
    before, first, renamed, after = run_in_db(_register_and_rename)
    assert before is None
    assert first.real_name == "Лисичка"
    assert renamed.real_name == after.real_name == "Лисичка-сестричка"
