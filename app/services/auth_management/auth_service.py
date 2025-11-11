import random
import uuid
from datetime import datetime, datetime_CAPI, timedelta, timezone
from typing import Tuple

import httpx
from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.types import HTTPExceptionHandler
from twilio.rest import Client

from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.models.user_management_models import (
    PasswordReset,
    RevokedToken,
    Role,
    Session,
    User,
)
from app.schemas.user_schemas import (
    AdminCreate,
    OnBoardEmployee,
    OtpRequest,
    UserCreate,
)
from app.services.mail_service import MailService


class AuthService:
    """
    Service class for managing authentication and authorization operations.
    
    This service handles user authentication, token management, password operations,
    and session management. It provides methods for login, registration, token
    creation/validation, password hashing/verification, and OTP generation.
    """
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
        self.mail_service = MailService()

    def verify_password(self, plain: str, hashed: str) -> bool:
        """
        Verify a plain text password against a hashed password.
        
        Args:
            plain (str): The plain text password to verify.
            hashed (str): The hashed password to verify against.
        
        Returns:
            bool: True if the password matches, False otherwise.
        """
        return self.pwd_context.verify(plain, hashed)

    def hash_password(self, password: str) -> str:
        """
        Hash a plain text password using Argon2 algorithm.
        
        Args:
            password (str): The plain text password to hash.
        
        Returns:
            str: The hashed password string.
        """
        return self.pwd_context.hash(password)

    async def verify_token(self, token: str, secret_key: str, algorithm: str):
        """
        Verify and decode a JWT token.
        
        Args:
            token (str): The JWT token to verify.
            secret_key (str): The secret key used to sign the token.
            algorithm (str): The algorithm used to sign the token.
        
        Returns:
            dict: The decoded token payload.
        
        Raises:
            JWTError: If the token is invalid, expired, or malformed.
        """
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload

    async def create_access_token(self, user: User) -> str:
        """
        Create a JWT access token for a user.
        
        This method generates a short-lived access token that can be used for API
        authentication. The token includes the user ID, role ID, expiration time,
        and a unique JWT ID (jti) for token revocation.
        
        Args:
            user (User): The user object for whom to create the access token.
        
        Returns:
            str: The encoded JWT access token.
        
        Note:
            - Token expiration is set based on ACCESS_TOKEN_EXPIRE_MINUTES
            - Token includes user_id (sub), role_id, expiration (exp), and jti
            - Token is signed using the access token secret key
            - JTI (JWT ID) is used for token revocation
        """
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user.user_id),
            "role_id": user.role_id,
            "exp": datetime.utcnow()
            + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": jti,
        }
        return jwt.encode(payload, self.A_SECRET_KEY, algorithm=self.ALGORITHM)

    async def create_refresh_token(self, user: User) -> Tuple[str, str, datetime]:
        """
        Create a JWT refresh token for a user.
        
        This method generates a long-lived refresh token that can be used to obtain
        new access tokens. The token includes the user ID, role ID, expiration time,
        and a unique JWT ID (jti) for token revocation and session management.
        
        Args:
            user (User): The user object for whom to create the refresh token.
        
        Returns:
            Tuple[str, str, datetime]: A tuple containing:
                                      - encoded_jwt (str): The encoded JWT refresh token
                                      - jti (str): The unique JWT ID for token revocation
                                      - expiration_dt (datetime): The token expiration datetime
        
        Note:
            - Token expiration is set based on REFRESH_TOKEN_EXPIRE_DAYS
            - Token includes user_id (sub), role_id, expiration (exp), and jti
            - Token is signed using the refresh token secret key
            - JTI is used for token revocation and session management
            - Refresh tokens have longer expiration than access tokens
        """
        jti = str(uuid.uuid4())
        expiration_dt = datetime.utcnow() + timedelta(
            hours=self.REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = {
            "sub": str(user.user_id),
            "role_id": user.role_id,
            "exp": expiration_dt,
            "jti": jti,
        }
        encoded_jwt = jwt.encode(payload, self.R_SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt, jti, expiration_dt

    async def is_token_revoked(self, db: AsyncSession, jti: str) -> bool:
        """
        Check if a token has been revoked.
        
        This method checks if a token's JWT ID (jti) exists in the revoked tokens
        table, indicating that the token has been revoked and should not be accepted.
        
        Args:
            db (AsyncSession): Database session for querying revoked tokens.
            jti (str): The JWT ID (jti) of the token to check.
        
        Returns:
            bool: True if the token is revoked, False otherwise.
        """
        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        return result.scalar_one_or_none() is not None

    async def revoke_token(self, db: AsyncSession, jti: str):
        """
        Revoke a token by adding its JWT ID to the revoked tokens table.
        
        This method marks a token as revoked by adding its JWT ID (jti) to the
        revoked tokens table. Once revoked, the token cannot be used for authentication.
        If the token is already revoked, this method does nothing.
        
        Args:
            db (AsyncSession): Database session for storing revoked token.
            jti (str): The JWT ID (jti) of the token to revoke.
        
        Note:
            - Only revokes the token if it's not already revoked
            - Records the revocation timestamp
            - Commits the revocation to the database
        """
        if not await self.is_token_revoked(db, jti):
            revoked_at = datetime.utcnow()
            db.add(RevokedToken(jti=jti, revoked_at=revoked_at))
            await db.commit()

    async def verify_captcha(
        self, captcha_token: str, min_score: float | None = None
    ) -> bool:
        # print(type(self.CAPTCHA_BYPASS))
        if self.CAPTCHA_BYPASS == True:
            # print("log_here")
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
            refresh_token, refresh_token_jti, expires_at = (
                await self.create_refresh_token(admin_obj)
            )
            access_token = await self.create_access_token(admin_obj)
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
        refresh_token: str,
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
            try:
                payload = await self.verify_token(
                    token=refresh_token,
                    secret_key=self.R_SECRET_KEY,
                    algorithm=self.ALGORITHM,
                )
                r_jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")
            await self.revoke_token(db=db, jti=jti)
            await self.revoke_token(db=db, jti=r_jti)
            result = await db.execute(
                select(Session).filter(Session.refresh_token_jti == r_jti)
            )
            session_obj = result.scalar_one_or_none()
            if not session_obj:
                raise HTTPException(status_code=404, detail="session_id is not found")
            session_obj.is_revoked = True
            response = JSONResponse(
                status_code=200, content={"msg": "logged out successfully"}
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

    async def GET_OTP(self, data: OtpRequest, redis_client):
        try:
            otp = random.randint(100000, 999999)
            expiry_seconds = 300  # 5 minutes
            await redis_client.setex(
                f"otp:{data.phone_number}", expiry_seconds, str(otp)
            )
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # message = client.messages.create(
            #     body=f"Your verification OTP is {otp}. It will expire in 5 minutes.",
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=data.phone_number,
            # )
            print(f"[OTP] Sent {otp} to {data.phone_number} | Twilio SID: ")
            return JSONResponse(
                status_code=200, content={"msg": "OTP sent successfully"}
            )
        except Exception as e:
            print("================================")
            print(f"[get-otp error] {e}")
            raise HTTPException(status_code=500, detail="Failed to send OTP")

    async def LOGIN_USER(
        self, request: Request, user_data: UserCreate, db: AsyncSession
    ):
        try:
            phone_key = f"otp:{user_data.phone_number}"
            stored_otp = await redis_client.get(phone_key)
            if not stored_otp:
                raise HTTPException(status_code=404, detail="OTP found or expired")
            if stored_otp != str(user_data.otp):
                raise HTTPException(status_code=400, detail="Invalid OTP")
            await redis_client.delete(phone_key)
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
            access_token = await self.create_access_token(user_obj)
            refresh_token, jti, expires_at = await self.create_refresh_token(user_obj)
            user_agent = request.headers.get("user-agent", "unknown")
            client_ip = request.client.host if request.client else "unknown"
            session = Session(
                user_id=user_obj.user_id,
                refresh_token_jti=jti,
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
                    "user_id": user_obj.user_id,
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("============================")
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
                role_id=2,
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

    async def FORGOT_PASSWORD(
        self, email: str, db: AsyncSession, background_tasks: BackgroundTasks
    ):
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
            link: str = (
                "http://localhost:8000/api/v1/reset-passoword?token={reset_token}"
            )
            background_tasks.add_task(self.mail_service.SEND_RESET_TOKEN, email, link)
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

    async def CHANGE_PASSWORD(
        self,
        email: str,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
        role_id: int,
        user_id: int,
    ):
        try:
            if role_id == 1:
                raise ForbiddenException("forbidden access")
            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundException("user not found")
            if user.user_id != user_id:
                raise ForbiddenException("forbidden acess")
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
            link: str = (
                f"http://localhost:8000/api/v1/reset-passoword?token={reset_token}"
            )
            reset_link = (
                f"https://your-frontend-domain.com/reset-password?token={reset_token}"
            )
            return {
                "message": "PasswordReset link has been sent your mail",
                "reset_link": reset_link,
            }
            background_tasks.add_task(self.mail_service.SEND_RESET_TOKEN, email, link)
        except (NotFoundException, ForbiddenException) as e:
            raise
        except Exception as e:
            print(f"[change_password] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail="Internal server error: change_password"
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
                payload = await self.verify_token(
                    token=refresh_token,
                    secret_key=self.R_SECRET_KEY,
                    algorithm=self.ALGORITHM,
                )
                jti = payload.get("jti")
            except JWTError:
                raise HTTPException(status_code=401, detail="incalid token")
            # print(jti)
            if await self.is_token_revoked(db=db, jti=jti):
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
            print("=========================")
            print(session_obj.expires_at, datetime.now(timezone.utc))
            if session_obj.expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=401, detail="the session has already expired"
                )
            user_id = int(payload.get("sub"))
            result = await db.execute(select(User).filter(User.user_id == user_id))
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise HTTPException(status_code=404, detail="user id not found")
            new_refresh_token, new_jti, expiry = await self.create_refresh_token(
                user_obj
            )
            new_access_token = await self.create_access_token(user_obj)
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
            db.add(new_session)
            response = JSONResponse(
                status_code=200,
                content={
                    "msg": "token refreshed",
                    "access_token": new_access_token,
                    "token_type": "bearer",
                },
            )
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=self.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 60,
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
