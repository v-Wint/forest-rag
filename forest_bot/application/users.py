"""Animals who upload documents: their real name is shown next to their advice.
Each function owns its transaction, like ingestion's."""

from sqlalchemy.dialects.postgresql import insert

from forest_bot.domain import User
from forest_bot.infrastructure import db
from forest_bot.settings import settings


class InvalidName(ValueError):
    pass


async def get_user(telegram_id: int) -> User | None:
    async with db.sessions() as session:
        return await session.get(User, telegram_id)


async def register_user(telegram_id: int, real_name: str) -> User:
    """Remember the animal's real name; registering again changes it.
    Raises InvalidName for an empty or too long name."""
    name = clean_name(real_name)
    async with db.sessions.begin() as session:
        user = await session.scalars(
            insert(User)
            .values(telegram_id=telegram_id, real_name=name)
            .on_conflict_do_update(index_elements=[User.telegram_id], set_={"real_name": name})
            .returning(User)
        )
        return user.one()


def clean_name(text: str) -> str:
    name = " ".join(text.split())
    if not name or len(name) > settings.max_name_chars:
        raise InvalidName(f"a name is 1 to {settings.max_name_chars} characters")
    return name
