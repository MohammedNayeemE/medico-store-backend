import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependecies.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    oauth2_scheme,
    verify_password,
)
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.core.database import otp_store
from app.models.user_management_models import RevokedToken, Session, User
from app.schemas.user_schemas import (
    AdminCreate,
    AdminResponse,
    OtpRequest,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/dev")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post("/admin-login")
async def login_admin(
    request: Request, admin: AdminCreate, db: AsyncSession = Depends(get_postgres)
):
    try:
        result = await db.execute(select(User).filter(User.email == admin.email))
        admin_obj = result.scalar_one_or_none()
        if admin_obj is None:
            raise HTTPException(status_code=404, detail="this email doesn't exists")
        if 1 == admin_obj.role_id:
            raise HTTPException(
                status_code=403, detail="this page forbidden for you: uwu"
            )
        admin_hashed_password: str = str(admin_obj.password_hash)
        if not verify_password(admin.password, admin_hashed_password):
            raise HTTPException(status_code=401, detail="the password is wrong")
        access_token = create_access_token(admin_obj)
        refresh_token, expires_at = create_refresh_token(admin_obj)
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        session = Session(
            user_id=admin_obj.user_id,
            refresh_token=refresh_token,
            device_info=user_agent,
            ip_address=client_ip,
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()
        return JSONResponse(
            status_code=200,
            content={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": admin_obj.user_id,
                "email": admin_obj.email,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[login_admin] Internal error: {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : login_admin route"
        )


@router.post("/admin-logout")
async def admin_logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
):
    try:
        try:
            payload = jwt.decode(
                token, settings.ACCESS_SECRET_TOKEN, algorithms=[settings.ALGORITHM]
            )
            jti = payload.get("jti")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
        revoked_entry = RevokedToken(jti=jti, revoked_at=datetime.now(timezone.utc))
        db.add(revoked_entry)
        await db.commit()
        return JSONResponse(
            status_code=200, content={"message": "Admin successfully logged out"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[admin-logout] error : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error: admin-logout"
        )


@router.post("/admin-forgot-password")
async def admin_forgot_password():
    pass


@router.post("/get-otp")
async def get_otp(data: OtpRequest):
    otp = random.randint(100000, 999999)
    expiry = datetime.utcnow() + timedelta(minutes=5)
    otp_store[data.phone_number] = {"otp": str(otp), "expires": expiry}
    print(f"otp : {otp} sent")
    return JSONResponse(status_code=200, content={"msg": "otp sent successfully"})


@router.post("/login")
async def user_login(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_postgres)
):
    try:
        if user_data.phone_number not in otp_store:
            raise HTTPException(
                status_code=404, detail="number is not found for sending otp"
            )
        if otp_store[user_data]["otp"] != user_data.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        if otp_store[user_data]["expires"] < datetime.utcnow():
            raise HTTPException(status_code=400, detail="otp expired")
        result = await db.execute(
            select(User).filter(User.phone_number == user_data.phone_number)
        )
        user_obj = result.scalar_one_or_none()
        if not user_obj:
            new_user = User(
                phone_number=user_data.phone_number,
                password_hash="default@password",
                role_id=user_data.role_id,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user_obj = new_user
        access_token = create_access_token(user_obj)
        refresh_token, expires_at = create_refresh_token(user_obj)
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        session = Session(
            user_id=user_obj.user_id,
            refresh_token=refresh_token,
            device_info=user_agent,
            ip_address=client_ip,
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()
        del otp_store[user_data.phone_number]
        return JSONResponse(
            status_code=200,
            content={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user_obj.user_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[user-login] : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [user_login]"
        )


@router.post("/user-logout")
async def user_logout(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_postgres)
):
    try:
        try:
            payload = jwt.decode(
                token, settings.ACCESS_SECRET_TOKEN, algorithms=[settings.ALGORITHM]
            )
            jti = payload.get("jti")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
        revoked_entry = RevokedToken(jti=jti, revoked_at=datetime.now(timezone.utc))
        db.add(revoked_entry)
        await db.commit()
        return JSONResponse(
            status_code=200, content={"message": "User successfully logged out"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[user-logout] error : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error: admin-logout"
        )
