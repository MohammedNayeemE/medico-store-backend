from app.core.database import async_session, client, get_redis, mongo_db


async def get_postgres():
    async with async_session() as session:
        yield session


async def get_mongo_db():
    return mongo_db


async def get_redis_client():
    return get_redis()
