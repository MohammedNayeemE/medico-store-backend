import json
from typing import Any

from app.core import database as db

CACHE_TTL = 600


async def get_cache(key: str):
    if not db.redis_client:
        return None
    data = await db.redis_client.get(key)
    return json.loads(data) if data else None


async def set_cache(key: str, value: Any, ttl: int = CACHE_TTL):
    if not db.redis_client:
        return
    await db.redis_client.set(key, json.dumps(value, default=str), ex=ttl)


async def invalidate_pattern(pattern: str):
    if not db.redis_client:
        return
    async for key in db.redis_client.scan_iter(match=pattern):
        await db.redis_client.delete(key)
