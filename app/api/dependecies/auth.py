import uuid
from datetime import datetime, timedelta
from typing import Tuple

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependecies.get_db_sessions import get_postgres, get_redis_client
from app.core.config import settings
from app.core.database import async_session
from app.models.user_management_models import (
    Permission,
    RevokedToken,
    Role,
    Session,
    User,
)
from app.services.auth_management.auth_service import AuthService
from app.services.cache_service import CacheService

auth_manager = AuthService()


async def load_scopes_from_db():
    """
    Load all permissions (scopes) from the database.
    
    Fetches all permission records from the database and returns them as a dictionary
    mapping permission names to their descriptions. This is used for OAuth2 scope
    validation and documentation.
    
    Returns:
        dict: A dictionary where keys are permission names (str) and values are
              permission descriptions (str). Example:
              {"medicine:read": "Permission to read medicines", ...}
    
    Note:
        This function creates a new database session and should be called when
        initializing the OAuth2 security scheme or when refreshing permission
        definitions.
    """
    async with async_session() as db:
        result = await db.execute(select(Permission))
        permissions = result.scalars().all()
        return {perm.name: perm.description for perm in permissions}


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/admin/token",
)


async def get_permissions_for_role(db: AsyncSession, role_id: int):
    """
    Fetch permissions for a given role from the database with Redis caching.
    
    Retrieves all permissions associated with a specific role. The results are
    cached in Redis to improve performance on subsequent requests. If the
    permissions are found in cache, they are returned immediately without
    querying the database.
    
    Args:
        db (AsyncSession): The database session to use for querying permissions.
        role_id (int): The unique identifier of the role to fetch permissions for.
    
    Returns:
        list[str]: A list of permission names (strings) associated with the role.
                   Returns an empty list if the role is not found.
                   Example: ["medicine:read", "medicine:write", "order:read"]
    
    Cache Behavior:
        - Cache key format: "permissions:role:{role_id}"
        - Cache is checked first before database query
        - Results are cached after database fetch for future requests
        - Cache persists until manually invalidated or expired
    
    Raises:
        No explicit exceptions, but database errors may propagate.
    """
    CACHE_PREFIX = "permissions:role:"
    cache = CacheService()
    cache_key = f"{CACHE_PREFIX}{role_id}"
    cached = await cache.get_cache(cache_key)
    if cached:
        return cached
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.role_id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        return []
    permissions = [perm.name for perm in role.permissions]
    await cache.set_cache(cache_key, permissions)
    return permissions


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
):
    """
    Dependency function to get the current authenticated user and validate permissions.
    
    This is a FastAPI dependency that extracts and validates the JWT access token
    from the Authorization header. It verifies the token signature, checks if the
    token has been revoked, loads the user from the database, and validates that
    the user has all required permissions (scopes) for the requested operation.
    
    Args:
        security_scopes (SecurityScopes): FastAPI SecurityScopes object containing
                                          the required permissions for the endpoint.
                                          This is automatically injected by FastAPI
                                          based on the endpoint's Security dependency.
        token (str): The JWT access token extracted from the Authorization header
                     using OAuth2PasswordBearer. Defaults to Depends(oauth2_scheme).
        db (AsyncSession): Database session dependency for querying user and
                           permission data. Defaults to Depends(get_postgres).
    
    Returns:
        User: The authenticated user object with loaded role and permissions.
              The user object includes all user attributes and related role
              information.
    
    Raises:
        HTTPException (401): If the token is invalid, expired, malformed, or revoked.
                            Also raised if the user_id or jti (JWT ID) is missing
                            from the token payload.
        HTTPException (403): If the user does not have all required permissions
                            (scopes) for the requested operation. The error detail
                            includes a list of missing permissions.
        HTTPException (404): If the user_id from the token does not exist in the
                            database (though this typically results in 401).
    
    Token Validation:
        - Verifies JWT signature using the configured secret key and algorithm
        - Checks if token has been revoked by querying the RevokedToken table
        - Validates that user_id and jti (JWT ID) are present in token payload
    
    Permission Validation:
        - Fetches all permissions associated with the user's role
        - Compares required scopes (from security_scopes) with granted permissions
        - Raises 403 if any required scope is missing from the user's permissions
    
    Example Usage:
        ```python
        @router.get("/protected")
        async def protected_route(
            current_user: User = Depends(get_current_user),
            security_scopes: SecurityScopes = Security(get_current_user, scopes=["medicine:read"])
        ):
            return {"user_id": current_user.user_id}
        ```
    
    Note:
        The function eagerly loads the user's role and permissions using SQLAlchemy
        selectinload to avoid N+1 query problems. Token revocation status is checked
        to support logout functionality.
    """
    authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = jwt.decode(
            token, auth_manager.A_SECRET_KEY, algorithms=[auth_manager.ALGORITHM]
        )
        user_id = payload.get("sub")
        # token_scopes = payload.get("scopes", [])
        jti = payload.get("jti")
        role_id = payload.get("role_id")
        if user_id is None or jti is None:
            raise credentials_exception
        user_id = int(user_id)
    except JWTError:
        raise credentials_exception
    if await auth_manager.is_token_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )
    if not jti:
        raise credentials_exception
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .filter(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception
    db_permissions = await get_permissions_for_role(db=db, role_id=role_id)
    required_scopes = set(security_scopes.scopes)
    granted_scopes = set(db_permissions)
    missing_scopes = required_scopes - granted_scopes
    if missing_scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required permissions: {', '.join(missing_scopes)}",
        )
    return user
