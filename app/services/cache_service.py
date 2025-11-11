import json
from typing import Any

from app.core import database as db

CACHE_TTL = 600


class CacheService:
    """
    Service class for managing Redis cache operations.
    
    Handles cache get/set operations, cache invalidation, and pattern-based cache clearing.
    """
    def __init__(self):
        pass

    async def get_cache(self, key: str):
        """
        Get a value from Redis cache.
        
        Args:
            key: Cache key to retrieve
        
        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        redis = db.redis_client
        if redis is None:
            print("[CacheService] Redis not initialized")
            return None
        data = await redis.get(key)
        return json.loads(data) if data else None

    async def set_cache(self, key: str, value: Any, ttl: int = CACHE_TTL):
        """
        Set a value in Redis cache with expiration time.
        
        Args:
            key: Cache key
            value: Value to cache (will be serialized to JSON)
            ttl: Time to live in seconds (default: 600)
        """
        redis = db.redis_client
        if redis is None:
            print("[CacheService] Redis not initialized")
            return
        await redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def invalidate_pattern(self, pattern: str):
        """
        Invalidate all cache keys matching a pattern.
        
        Args:
            pattern: Redis key pattern to match (e.g., "user:*")
        """
        redis = db.redis_client
        if redis is None:
            return
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)
