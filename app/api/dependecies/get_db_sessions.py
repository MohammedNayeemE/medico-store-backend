from app.core.database import async_session, get_redis


async def get_postgres():
    async with async_session() as session:
        yield session


async def get_mongo():
    pass


async def get_redis_client():
    return get_redis()
