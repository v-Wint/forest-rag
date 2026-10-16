"""The one database engine of the process. No connection is opened until the first query.

One session per unit of work (an upload, a file): `async with sessions.begin() as session`.
Call `await engine.dispose()` before the program exits.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from forest_bot.settings import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
sessions = async_sessionmaker(engine, expire_on_commit=False)
