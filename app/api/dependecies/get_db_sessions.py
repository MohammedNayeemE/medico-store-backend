from app.core.database import async_session, client, get_redis, mongo_db


async def get_postgres():
    """
    Dependency function to provide a PostgreSQL database session.
    
    This is a FastAPI dependency that creates and yields a database session
    for use in route handlers. The session is automatically closed after the
    request is complete. This follows the async generator pattern recommended
    by FastAPI for database connections.
    
    Yields:
        AsyncSession: An async SQLAlchemy session for PostgreSQL database operations.
                      The session is automatically closed when the request completes.
    
    Usage:
        ```python
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_postgres)):
            result = await db.execute(select(Item))
            return result.scalars().all()
        ```
    
    Note:
        - The session is created from the async_session factory
        - The session is automatically closed after the handler completes
        - This should be used as a dependency in FastAPI route handlers
        - All database operations should use this session within the handler scope
    """
    async with async_session() as session:
        yield session


async def get_mongo_db():
    """
    Dependency function to provide a MongoDB database instance.
    
    Returns the MongoDB database client that can be used for MongoDB operations.
    This is a singleton instance shared across all requests.
    
    Returns:
        Database: The MongoDB database instance for performing MongoDB operations.
                  This is the same instance throughout the application lifecycle.
    
    Usage:
        ```python
        @router.get("/documents")
        async def get_documents(db = Depends(get_mongo_db)):
            collection = db["documents"]
            documents = await collection.find().to_list(length=100)
            return documents
        ```
    
    Note:
        - Returns a singleton MongoDB database instance
        - The same database instance is reused across requests
        - Use this for MongoDB operations (as opposed to PostgreSQL)
    """
    return mongo_db


async def get_redis_client():
    """
    Dependency function to provide a Redis client instance.
    
    Returns the Redis client that can be used for caching, session storage,
    rate limiting, and other Redis operations. This is a singleton instance
    shared across all requests.
    
    Returns:
        Redis: The Redis client instance for performing Redis operations.
               This is the same instance throughout the application lifecycle.
    
    Usage:
        ```python
        @router.get("/cache")
        async def get_cache(redis: Redis = Depends(get_redis_client)):
            value = await redis.get("key")
            return {"value": value}
        ```
    
    Note:
        - Returns a singleton Redis client instance
        - The same client instance is reused across requests
        - Use this for caching, session management, and rate limiting
        - The client connection is managed by the core.database module
    """
    return get_redis()
