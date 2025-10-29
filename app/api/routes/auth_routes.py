import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, Request, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependecies.auth import get_current_user, oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.core.database import otp_store
from app.schemas.user_schemas import (
    AdminCreate,
    AdminResponse,
    ForgotPasswordRequest,
    OtpRequest,
    ResetPasswordRequest,
    UserCreate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
auth = AuthService()


@router.get("/dev", description="this route is for testing")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post("/admin-login", description="Authenticate an admin and issue access tokens")
async def login_admin(
    request: Request, admin: AdminCreate, db: AsyncSession = Depends(get_postgres)
):
    result = await auth.LOGIN_ADMIN(request=request, admin=admin, db=db)
    return result


@router.post("/admin-register", description="Register a new admin account")
async def register_admin(
    request: Request, admin: AdminCreate, db: AsyncSession = Depends(get_postgres)
):
    result = await auth.CREATE_ADMIN(request=request, admin_data=admin, db=db)
    return result


@router.post("/admin-logout", description="Logout admin and revoke the active session/token")
async def admin_logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
    session_id: int = Body(...),
):
    result = await auth.LOGOUT_ADMIN(
        request=request, token=token, db=db, session_id=session_id
    )
    return result


@router.post("/admin-forgot-password", description="Initiate admin password reset by sending OTP/link")
async def admin_forgot_password(
    data: ForgotPasswordRequest, db: AsyncSession = Depends(get_postgres)
):
    result = await auth.FORGOT_PASSWORD(email=data.email, db=db)
    return result


@router.post("/reset-password", description="Reset password using a valid reset token")
async def reset_password(
    data: ResetPasswordRequest, db: AsyncSession = Depends(get_postgres)
):
    result = await auth.RESET_PASSWORD(
        token=data.token, new_password=data.new_password, db=db
    )
    return result


@router.post("/get-otp", description="Generate and send an OTP for phone verification")
async def get_otp(data: OtpRequest):
    otp = random.randint(100000, 999999)
    expiry = datetime.utcnow() + timedelta(minutes=5)
    otp_store[data.phone_number] = {"otp": str(otp), "expires": expiry}
    print(f"otp : {otp} sent")
    return JSONResponse(status_code=200, content={"msg": "otp sent successfully"})


@router.post("/login", description="Authenticate user and issue access tokens")
async def user_login(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_postgres)
):
    result = auth.LOGIN_USER(request=request, user_data=user_data, db=db)
    return result


@router.post("/user-logout", description="Logout user and revoke the access token")
async def user_logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["customer:write"]),
):
    result = await auth.LOGOUT_USER(token=token, db=db)
    return result
