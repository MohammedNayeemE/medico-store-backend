import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from httpx import request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.dependecies.get_db_sessions import get_postgres, get_redis_client
from app.api.routes import (
    audit_logs_routes,
    auth_routes,
    backup_routes,
    cart_routes,
    content_routes,
    dashboard_routes,
    discount_routes,
    file_routes,
    issues_routes,
    notification_routes,
    order_routes,
    payment_routes,
    prescriptions,
    profile_routes,
    report_routes,
    request_medicines_routes,
    request_orders,
    review_routes,
    role_routes,
)
from app.api.routes.inventory import router as inventory_router
from app.core.config import allowed_origins, settings
from app.core.database import Base, close_redis, engine, init_redis
from app.middlewares.logging_middleware import LoggingMiddleware
from app.models.inventory_management_models import *
from app.models.order_management_models import *
from app.models.user_management_models import *
from app.services.auth_management.auth_service import AuthService

auth_manager = AuthService()
app = FastAPI(
    root_path="/api/v1",
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url="/openapi.json",
    docs_url=None,
    redoc_url="/redoc",
)


@app.get("/docs", include_in_schema=False)
def custom_docs():
    html_path = os.path.join(os.path.dirname(__file__), "static", "custom_swagger.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=2)
app.add_middleware(LoggingMiddleware)


@app.on_event("startup")
async def startup():
    global redis_client
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created!")
    try:
        redis = await init_redis()
        pong = await redis.ping()
        if pong:
            print("✅ Redis connection established successfully!")
        else:
            print("Redis ping returned False — check configuration.")
        await FastAPILimiter.init(redis)
        print("Redis connection established")
    except Exception as e:
        print(f"error while connecting to redis : {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        await FastAPILimiter.close()
        await close_redis()
        print("Redis connection closed")
    except Exception as e:
        print(f"Error closing redis {e}")


@app.get("/", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_root():
    return JSONResponse(status_code=200, content={"msg": "the server is running"})


async def login_swagger_admin(
    request: Request, form_data: OAuth2PasswordRequestForm, db: AsyncSession
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .filter(User.email == form_data.username)
    )
    user_obj = result.scalar_one_or_none()
    if not user_obj:
        raise HTTPException(status_code=404, detail="user not found")
    # if not auth_manager.verify_password(form_data.password, user_obj.password_hash):
    #     raise HTTPException(status_code=401, detail="wrong password")
    refresh_token, refresh_token_jti, expires_at = (
        await auth_manager.create_refresh_token(user_obj)
    )
    access_token = await auth_manager.create_access_token(user_obj)
    user_agent = request.headers.get("user-agent", "unknown")
    client_ip = request.client.host if request.client else "unknown"
    session = Session(
        user_id=user_obj.user_id,
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
            "user_id": user_obj.user_id,
            "email": user_obj.email,
            "session_id": session.session_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 60,
        path="/auth/refresh",
    )
    return response


async def login_swagger_customer(
    request: Request,
    form_data: OAuth2PasswordRequestForm,
    db: AsyncSession,
    redis_client,
):
    try:
        phone_key = f"otp:{form_data.username}"
        stored_otp = await redis_client.get(phone_key)
        if not stored_otp:
            print("not found")
            raise HTTPException(status_code=404, detail="OTP found or expired")
        if stored_otp != str(form_data.password):
            raise HTTPException(status_code=400, detail="Invalid OTP")
        await redis_client.delete(phone_key)
        result = await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .filter(User.phone_number == form_data.username)
        )
        user_obj = result.scalar_one_or_none()
        if not user_obj:
            new_user = User(
                phone_number=form_data.username,
                password_hash="default@password",
                role_id=1,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user_obj = new_user
        access_token = await auth_manager.create_access_token(user_obj)
        refresh_token, jti, expires_at = await auth_manager.create_refresh_token(
            user_obj
        )
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
        response = JSONResponse(
            status_code=200,
            content={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user_obj.user_id,
                "session_id": session.session_id,
            },
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=auth_manager.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60,
        )
        db.add(session)
        await db.commit()
        return response
    except HTTPException:
        raise
    except Exception as e:
        print("============================")
        print(f"[user-login] : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [user_login]"
        )


@app.post("/auth/admin/token", include_in_schema=False)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_postgres),
    redis_client=Depends(get_redis_client),
):
    if "@" in form_data.username:
        return await login_swagger_admin(request=request, form_data=form_data, db=db)
    else:
        return await login_swagger_customer(
            request=request, form_data=form_data, db=db, redis_client=redis_client
        )


app.include_router(router=auth_routes.router)
app.include_router(router=profile_routes.router)
app.include_router(router=role_routes.router)
app.include_router(router=file_routes.router)
app.include_router(router=inventory_router)
app.include_router(router=cart_routes.router)
app.include_router(router=prescriptions.router)
app.include_router(router=request_orders.router)
app.include_router(router=order_routes.router)
app.include_router(router=issues_routes.router)
app.include_router(router=payment_routes.router)
app.include_router(router=discount_routes.router)
app.include_router(router=request_medicines_routes.router)
app.include_router(router=review_routes.router)
app.include_router(router=notification_routes.router)
app.include_router(router=backup_routes.router)
app.include_router(router=content_routes.router)
app.include_router(router=dashboard_routes.router)
app.include_router(router=audit_logs_routes.router)
app.include_router(router=report_routes.router)
