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

A_SECRET_KEY = settings.ACCESS_SECRET_TOKEN
R_SECRET_KEY = settings.REFRESH_SECRET_TOKEN
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRES
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


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


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user: User) -> str:
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user.user_id),
        "scopes": [perm.name for perm in user.role.permissions],
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": jti,
    }
    return jwt.encode(payload, A_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: User) -> Tuple[str, datetime]:
    jti = str(uuid.uuid4())
    expiration_dt = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user.user_id),
        "scopes": [perm.name for perm in user.role.permissions],
        "exp": expiration_dt,
        "jti": jti,
    }
    encoded_jwt = jwt.encode(payload, R_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expiration_dt


async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
    result = await db.execute(select(RevokedToken).filter(RevokedToken.jti == jti))
    obj = result.scalars().all()
    if not obj:
        return False
    return True


async def revoke_token(db: AsyncSession, jti: str):
    if not await is_token_revoked(db, jti):
        db.add(RevokedToken(jti=jti))
        await db.commit()


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
        payload = jwt.decode(token, A_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_scopes = payload.get("scopes", [])
        jti = payload.get("jti")
        if user_id is None or jti is None:
            raise credentials_exception
        user_id = int(user_id)
    except JWTError:
        raise credentials_exception

    if await is_token_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .filter(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    db_permissions = [perm.name for perm in user.role.permissions]
    required_scopes = set(security_scopes.scopes)
    granted_scopes = set(token_scopes) | set(db_permissions)

    missing_scopes = required_scopes - granted_scopes
    if missing_scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required permissions: {', '.join(missing_scopes)}",
        )

    return user


async def rotate_refresh_token(old_token: str, db: AsyncSession) -> str:
    # result = await db.execute(
    #     select(RefreshToken)
    #     .where(RefreshToken.token == old_token)
    #     .where(RefreshToken.revoked == False)
    # )
    # db_token = result.scalar_one_or_none()
    #
    # if not db_token:
    #     raise HTTPException(status_code=401, detail="Invalid refresh token")
    #
    # if db_token.expires_at < datetime.utcnow():
    #     raise HTTPException(status_code=401, detail="Refresh token expired")
    #
    # # revoke old token
    # db_token.revoked = True
    # await db.commit()
    #
    # # issue a new one
    # result = await db.execute(select(User).where(User.user_id == db_token.user_id))
    # user = result.scalar_one()
    # new_token = await create_refresh_token(user, db)
    # return new_token
    pass
