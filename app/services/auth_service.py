import uuid
from datetime import datetime, datetime_CAPI, timedelta
from typing import Tuple

import httpx
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.types import HTTPExceptionHandler

from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.core.database import otp_store
from app.models.user_management_models import (
    PasswordReset,
    RevokedToken,
    Role,
    Session,
    User,
)
from app.schemas.user_schemas import AdminCreate, OnBoardEmployee, UserCreate


class AuthService:
    def __init__(self) -> None:
        self.A_SECRET_KEY = settings.ACCESS_SECRET_TOKEN
        self.R_SECRET_KEY = settings.REFRESH_SECRET_TOKEN
        self.ALGORITHM = settings.ALGORITHM
        self.ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRES
        self.REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRES
        self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        self.PASSWORD_RESET_EXPIRE_MINUTES = 15
        self.CAPTCHA_BYPASS = settings.CAPTCHA_BYPASS
        self.RECAPTCHA_SECRET_KEY = settings.RECAPTCHA_SECRET_KEY

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self.pwd_context.verify(plain, hashed)

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def verify_token(self, token: str, secret_key: str, algorithm: str):
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload

    def create_access_token(self, user: User, refresh_token_jti: str) -> str:
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user.user_id),
            "scopes": [perm.name for perm in user.role.permissions],
            "exp": datetime.utcnow()
            + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": refresh_token_jti,
        }
        return jwt.encode(payload, self.A_SECRET_KEY, algorithm=self.ALGORITHM)

    def create_refresh_token(self, user: User) -> Tuple[str, str, datetime]:
        jti = str(uuid.uuid4())
        expiration_dt = datetime.utcnow() + timedelta(
            minutes=self.REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = {
            "sub": str(user.user_id),
            "scopes": [perm.name for perm in user.role.permissions],
            "exp": expiration_dt,
            "jti": jti,
        }
        encoded_jwt = jwt.encode(payload, self.R_SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt, jti, expiration_dt

    async def is_token_revoked(self, db: AsyncSession, jti: str) -> bool:
        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        return result.scalar_one_or_none() is not None

    async def revoke_token(self, db: AsyncSession, jti: str):
        if not await self.is_token_revoked(db, jti):
            revoked_at = datetime.utcnow()
            db.add(RevokedToken(jti=jti, revoked_at=revoked_at))
            await db.commit()

    async def verify_captcha(
        self, captcha_token: str, min_score: float | None = None
    ) -> bool:
        if self.CAPTCHA_BYPASS:
            if captcha_token == "false_token":
                return False
            return True
        if not self.RECAPTCHA_SECRET_KEY:
            raise HTTPException(status_code=404, detail="Missing reCaptcha key")
        url: str = "https://www.google.com/recaptcha/api/siteverify"
        data = {
            "secret": self.RECAPTCHA_SECRET_KEY,
            "response": captcha_token,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data)
                result = response.json()
        except Exception as e:
            print(f"[verify_captcha] Network error: {e}")
            raise HTTPException(status_code=500, detail="Failed to verify captcha")
        print(result)
        success = result.get("success", False)
        return success

    async def VERIFY_ONBOARDING(self, token: str):
        try:
            payload = jwt.decode(token, self.A_SECRET_KEY, self.ALGORITHM)
            email = payload.get("sub")
            if payload.get("type") != "onboarding":
                raise HTTPException(status_code=404, detail="Invalid Token")
            return {"email": email}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------")
            print(f"verify_onboarding: {e}")
            raise HTTPException(status_code=500, detail="internal server error")

    async def LOGIN_ADMIN(self, request: Request, admin: AdminCreate, db: AsyncSession):
        try:
            captcha_result = await self.verify_captcha(
                captcha_token=admin.captcha_token
            )
            if not captcha_result:
                raise HTTPException(status_code=400, detail="Invalid captcha")
            result = await db.execute(
                select(User)
                .options(selectinload(User.role).selectinload(Role.permissions))
                .filter(User.email == admin.email)
            )
            admin_obj = result.scalar_one_or_none()
            if admin_obj is None:
                raise HTTPException(status_code=404, detail="this email doesn't exists")
            admin_hashed_password: str = str(admin_obj.password_hash)
            if not self.verify_password(admin.password, admin_hashed_password):
                raise HTTPException(status_code=401, detail="the password is wrong")
            refresh_token, refresh_token_jti, expires_at = self.create_refresh_token(
                admin_obj
            )
            access_token = self.create_access_token(
                admin_obj, refresh_token_jti=refresh_token_jti
            )
            user_agent = request.headers.get("user-agent", "unknown")
            client_ip = request.client.host if request.client else "unknown"
            session = Session(
                user_id=admin_obj.user_id,
                refresh_token=refresh_token,
                refresh_token_jti=refresh_token_jti,
                device_info=user_agent,
                ip_address=client_ip,
                expires_at=expires_at,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            response = JSONResponse(
                status_code=200,
                content={
                    "msg": "Login Successfull",
                    "user_id": admin_obj.user_id,
                    "email": admin_obj.email,
                    "session_id": session.session_id,
                },
            )
            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=self.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 60,
                path="/auth/refresh",
            )
            return response
        except HTTPException:
            raise
        except Exception as e:
            print("----------------------")
            print(f"[login_admin] Internal error: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : login_admin route"
            )

    async def LOGOUT(
        self,
        access_token: str,
        db: AsyncSession,
    ):
        try:
            try:
                payload = await self.verify_token(
                    token=access_token,
                    secret_key=self.A_SECRET_KEY,
                    algorithm=self.ALGORITHM,
                )
                jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")
            await self.revoke_token(db=db, jti=jti)
            result = await db.execute(
                select(Session).filter(Session.refresh_token_jti == jti)
            )
            session_obj = result.scalar_one_or_none()
            if not session_obj:
                raise HTTPException(status_code=404, detail="session_id is not found")
            session_obj.is_revoked = True
            response = JSONResponse(
                status_code=200, content={"msg": "logged out successfully"}
            )
            response.delete_cookie(
                "access_token", httponly=True, secure=True, samesite="strict"
            )
            response.delete_cookie(
                "refresh_token", httponly=True, secure=True, samesite="strict"
            )
            await db.commit()
            return {"msg": "logged out successfully"}
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            print(f"[user-logout] error : {e}")
            raise HTTPException(status_code=500, detail="internal server error: logout")

    async def LOGOUT_ALL(self, user_id: int, db: AsyncSession, access_token: str):
        try:
            try:
                payload = jwt.decode(
                    access_token,
                    settings.ACCESS_SECRET_TOKEN,
                    algorithms=[settings.ALGORITHM],
                )
                jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")
            await self.revoke_token(db=db, jti=jti)
            result = await db.execute(
                select(Session).filter(Session.user_id == user_id)
            )
            sessions = result.scalars().all()
            for session in sessions:
                await self.revoke_token(db=db, jti=session.refresh_token_jti)
                session.is_revoked = True
            response = JSONResponse(
                status_code=200, content={"msg": "logged out from all successfully"}
            )
            response.delete_cookie(
                "access_token", httponly=True, secure=True, samesite="strict"
            )
            response.delete_cookie(
                "refresh_token", httponly=True, secure=True, samesite="strict"
            )
            await db.commit()
            return {"msg": "logged out from all devices"}
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[logout from all devices] {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [LOGOUT_ALL]"
            )

    async def LOGIN_USER(
        self, request: Request, user_data: UserCreate, db: AsyncSession
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
            access_token = self.create_access_token(user_obj)
            refresh_token, expires_at = self.create_refresh_token(user_obj)
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

    async def LOGOUT_USER(self, token: str, db: AsyncSession):
        try:
            try:
                payload = jwt.decode(
                    token, settings.ACCESS_SECRET_TOKEN, algorithms=[settings.ALGORITHM]
                )
                jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")
            revoked_entry = RevokedToken(jti=jti, revoked_at=datetime.utcnow())
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

    async def CREATE_ADMIN(
        self, request: Request, db: AsyncSession, admin_data: AdminCreate
    ) -> User:
        try:
            result = await db.execute(
                select(User).filter(User.email == admin_data.email)
            )
            admin_obj = result.scalar_one_or_none()
            if admin_obj:
                raise HTTPException(status_code=400, detail="this email already exists")
            new_user = User(
                email=admin_data.email,
                password_hash=self.hash_password(admin_data.password),
                role_id=admin_data.role_id,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            return new_user
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"[create_user]: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [create_user]"
            )

    async def ONBOARD_NEW_EMPLOYEE(self, db: AsyncSession, token: str, password: str):
        try:
            payload = jwt.decode(token, self.A_SECRET_KEY, algorithms=[self.ALGORITHM])
            email = payload.get("sub")
            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user.is_active:
                raise HTTPException(status_code=400, detail="User already onboarded")
            user.password_hash = self.hash_password(password)
            user.is_active = True
            await db.commit()
            return {"msg": "Welcome to the team!"}
        except ExpiredSignatureError as e:
            raise HTTPException(status_code=400, detail="Link expired : {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail="internal server error : {e}")

    async def FORGOT_PASSWORD(self, email: str, db: AsyncSession):
        try:
            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            reset_token = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(
                minutes=self.PASSWORD_RESET_EXPIRE_MINUTES
            )
            reset_entry = PasswordReset(
                user_id=user.user_id,
                token=reset_token,
                expires_at=expires_at,
            )
            db.add(reset_entry)
            await db.commit()
            await db.refresh(reset_entry)
            # 4️⃣ You can send email here (for now, just return the token)
            # In production, send via SendGrid, SMTP, or AWS SES
            reset_link = (
                f"https://your-frontend-domain.com/reset-password?token={reset_token}"
            )
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Password reset link has been sent to your email.",
                    "reset_link": reset_link,  # for dev/testing purpose only
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[forgot_password] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail="Internal server error: forgot_password"
            )

    async def RESET_PASSWORD(self, token: str, new_password: str, db: AsyncSession):
        try:
            result = await db.execute(
                select(PasswordReset).filter(PasswordReset.token == token)
            )
            reset_entry = result.scalar_one_or_none()
            if not reset_entry:
                raise HTTPException(status_code=400, detail="Invalid or expired token")
            if reset_entry.used:
                raise HTTPException(status_code=400, detail="Token already used")
            if reset_entry.expires_at < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Token expired")
            result = await db.execute(
                select(User).filter(User.user_id == reset_entry.user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            hashed_pw = self.hash_password(new_password)
            user.password_hash = hashed_pw
            reset_entry.used = True
            db.add(user)
            db.add(reset_entry)
            await db.commit()
            await db.refresh(user)
            return JSONResponse(
                status_code=200,
                content={"message": "Password reset successfully."},
            )
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[reset_password] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail="internal server error: reset_password"
            )

    async def REFRESH_TOKEN(self, db: AsyncSession, request: Request):
        try:
            refresh_token = request.cookies.get("refresh_token")
            if not refresh_token:
                raise HTTPException(status_code=401, detail="missing refresh token")
            try:
                payload = self.verify_token(
                    token=refresh_token,
                    secret_key=self.R_SECRET_KEY,
                    algorithm=self.ALGORITHM,
                )
                jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="incalid token")
            if not await self.is_token_revoked(db=db, jti=jti):
                raise HTTPException(
                    status_code=401, detail="token is revoked pls log in"
                )
            result = await db.execute(
                select(Session).filter(Session.refresh_token_jti == jti)
            )
            session_obj = result.scalar_one_or_none()
            if not session_obj or session_obj.is_revoked == True:
                raise HTTPException(
                    status_code=401, detail="the session has already expired"
                )
            if session_obj.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=401, detail="the session has already expired"
                )
            result = await db.execute(
                select(User).filter(User.user_id == payload.get("user_id"))
            )
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise HTTPException(status_code=404, detail="user id not found")
            new_refresh_token, new_jti, expiry = self.create_refresh_token(user_obj)
            new_access_token = self.create_access_token(user_obj, new_jti)
            await self.revoke_token(db=db, jti=jti)
            session_obj.is_revoked = True
            user_agent = request.headers.get("user-agent", "unknown")
            client_ip = request.client.host if request.client else "unknown"
            new_session = Session(
                user_id=user_obj.user_id,
                refresh_token=new_refresh_token,
                refresh_token_jti=new_jti,
                device_info=user_agent,
                ip_address=client_ip,
                expires_at=expiry,
            )
            response = JSONResponse(status_code=200, content={"msg": "token refreshed"})
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=self.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 60,
                path="/auth/refresh",
            )
            await db.commit()
            return response
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"refresh_token : {e}")
            raise HTTPException(
                status_code=500, detail="interna; server error : [refresh_token]"
            )
