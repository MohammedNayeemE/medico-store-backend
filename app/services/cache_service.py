import json
from typing import Any

from app.core import database as db

CACHE_TTL = 600


class CacheService:
    def __init__(self):
        pass

    async def get_cache(self, key: str):
        redis = db.redis_client
        if redis is None:
            print("[CacheService] Redis not initialized")
            return None
        data = await redis.get(key)
        return json.loads(data) if data else None

    async def set_cache(self, key: str, value: Any, ttl: int = CACHE_TTL):
        redis = db.redis_client
        if redis is None:
            print("[CacheService] Redis not initialized")
            return
        await redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def invalidate_pattern(self, pattern: str):
        redis = db.redis_client
        if redis is None:
            return
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)
