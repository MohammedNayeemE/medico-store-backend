import redis.asyncio as aioredis
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

"""
POSTGRES
"""
engine = create_async_engine(settings.DB_URL, echo=True, future=True)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

otp_store = {}

"""
MONGO
"""

client = AsyncIOMotorClient(settings.MONGO_DB_URL)
mongo_db = client[settings.MONGO_DB_NAME]
bucket = AsyncIOMotorGridFSBucket(mongo_db)

"""
REDIS
"""
redis_client = None


async def init_redis():
    global redis_client
    redis_client = await aioredis.from_url(
        "redis://localhost", encoding="utf-8", decode_responses=True
    )
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
