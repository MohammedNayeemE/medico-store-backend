import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
)
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependecies.auth import get_current_user, oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres, get_redis_client
from app.core.config import settings
from app.core.database import otp_store
from app.models.user_management_models import User
from app.schemas.user_schemas import (
    AdminCreate,
    AdminResponse,
    ForgotPasswordRequest,
    OnBoardEmployee,
    OtpRequest,
    ResetPasswordRequest,
    UserCreate,
)
from app.services.auth_management.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
)
auth = AuthService()


@router.get("/dev", description="this route is for testing")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post(
    "/admin-login", description="Authenticate an admin and issue access tokens"
)
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


@router.post("/verify-onboarding", description="verify the magick link")
async def verify_onboarding(token: str = Query(...)):
    result = await auth.VERIFY_ONBOARDING(token=token)
    return result


@router.post(
    "/employee-onboard", description="On Board new employees into the applications"
)
async def onboard_employee(
    db: AsyncSession = Depends(get_postgres),
    token: str = Body(...),
    password: str = Body(...),
):
    result = await auth.ONBOARD_NEW_EMPLOYEE(db=db, token=token, password=password)
    return result


@router.post("/logout", description="Logout users revoke the active session/token")
async def admin_logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["auth:write"]),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=404, detail="refresh_token not found")
    result = await auth.LOGOUT(access_token=token, db=db, refresh_token=refresh_token)
    return result


@router.post(
    "/admin-forgot-password",
    description="Initiate admin password reset by sending OTP/link",
)
async def admin_forgot_password(
    background_tasks: BackgroundTasks,
    data: ForgotPasswordRequest = Body(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await auth.FORGOT_PASSWORD(
        email=data.email, db=db, background_tasks=background_tasks
    )
    return result


@router.post("/admin-change-password", description="request for changing the password")
async def admin_change_password(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["auth:write"]),
    data: ForgotPasswordRequest = Body(...),
):
    result = await auth.CHANGE_PASSWORD(
        db=db,
        email=data.email,
        background_tasks=background_tasks,
        role_id=current_user.role_id,
        user_id=current_user.user_id,
    )
    return result


@router.post("/reset-password", description="Reset password using a valid reset token")
async def reset_password(
    data: ResetPasswordRequest, db: AsyncSession = Depends(get_postgres)
):
    result = await auth.RESET_PASSWORD(
        token=data.token, new_password=data.new_password, db=db
    )
    return result


@router.post("/logout-all", description="Logout From All Devices")
async def logout_all(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["auth:write"]),
):
    access_token = request.cookies.get("access_token")
    result = await auth.LOGOUT_ALL(
        user_id=current_user.user_id, db=db, access_token=access_token
    )
    return result


@router.post("/get-otp", description="Generate and send an OTP for phone verification")
async def get_otp(data: OtpRequest, redis=Depends(get_redis_client)):
    result = await auth.GET_OTP(data=data, redis_client=redis)
    return result


@router.post("/login", description="Authenticate user and issue access tokens")
async def user_login(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_postgres)
):
    result = auth.LOGIN_USER(request=request, user_data=user_data, db=db)
    return result


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["auth:write"]),
):
    result = await auth.REFRESH_TOKEN(db=db, request=request)
    return result
