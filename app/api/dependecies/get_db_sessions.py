from app.core.database import async_session


async def get_postgres():
    async with async_session() as session:
        yield session


async def get_mongo():
    pass
