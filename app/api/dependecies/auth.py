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

from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.core.database import async_session
from app.models.user_management_models import (
    Permission,
    RevokedToken,
    Role,
    Session,
    User,
)
from app.services.auth_service import AuthService
from app.services.cache_service import CacheService

auth_manager = AuthService()


async def load_scopes_from_db():
    async with async_session() as db:
        result = await db.execute(select(Permission))
        permissions = result.scalars().all()
        return {perm.name: perm.description for perm in permissions}


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/admin/token",
    scopes={
        "admin:read": "Read roles",
        "admin:write": "Write roles",
        "user:read": "Read admin profile",
        "user:write": "Write admin profile",
    },
)


async def get_permissions_for_role(db: AsyncSession, role_id: int):
    """
    Fetch permissions for a given role. Cache in Redis for performance.
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
        token_scopes = payload.get("scopes", [])
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
    granted_scopes = set(token_scopes) | set(db_permissions)
    missing_scopes = required_scopes - granted_scopes
    if missing_scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required permissions: {', '.join(missing_scopes)}",
        )
    return user
