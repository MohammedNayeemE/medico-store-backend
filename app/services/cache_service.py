import json
from typing import Any

from app.core import database as db

CACHE_TTL = 600


class CacheService:
    def __init__(self) -> None:
        self.cache = db.redis_client

    async def get_cache(self, key: str):
        if not self.cache:
            return None
        data = await self.cache.get(key)
        return json.loads(data) if data else None

    async def set_cache(self, key: str, value: Any, ttl: int = CACHE_TTL):
        if not self.cache:
            return
        await self.cache.set(key, json.dumps(value, default=str), ex=ttl)

    async def invalidate_pattern(self, pattern: str):
        if not self.cache:
            return
        async for key in self.cache.scan_iter(match=pattern):
            await self.cache.delete(key)
