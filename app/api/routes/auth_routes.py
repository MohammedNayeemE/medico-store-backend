import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependecies.auth import get_current_user, oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres
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
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
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


@router.post(
    "/admin-logout", description="Logout admin and revoke the active session/token"
)
async def admin_logout(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=404, detail="access_token not found")
    result = await auth.LOGOUT(access_token=access_token, db=db)
    return result


@router.post(
    "/admin-forgot-password",
    description="Initiate admin password reset by sending OTP/link",
)
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


@router.post("/logout-all", description="Logout From All Devices")
async def logout_all(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    access_token = request.cookies.get("access_token")
    result = await auth.LOGOUT_ALL(
        user_id=current_user.user_id, db=db, access_token=access_token
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


@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_postgres)):
    result = await auth.REFRESH_TOKEN(db=db, request=request)
    return result
