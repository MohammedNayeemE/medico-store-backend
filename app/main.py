from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.dependecies.get_db_sessions import get_postgres
from app.api.routes import (
    auth_routes,
    cart_routes,
    discount_routes,
    file_routes,
    inventory_routes,
    issues_routes,
    order_routes,
    payment_routes,
    prescriptions,
    profile_routes,
    request_medicines_routes,
    request_orders,
    role_routes,
)
from app.core.config import allowed_origins, settings
from app.core.database import Base, close_redis, engine, init_redis
from app.middlewares.logging_middleware import LoggingMiddleware
from app.models.inventory_management_models import *
from app.models.order_management_models import *
from app.models.user_management_models import *
from app.services.auth_service import AuthService

auth_manager = AuthService()
app = FastAPI(
    root_path="/api/v1", title=settings.APP_NAME, version=settings.APP_VERSION
)


# def custom_openapi():
#     if app.openapi_schema:
#         return app.openapi_schema
#
#     # 🧩 Generate the default OpenAPI schema (keeps title, version, description)
#     openapi_schema = get_openapi(
#         title=app.title,
#         version=app.version,
#         description=app.description,
#         routes=app.routes,
#     )
#
#     # 🔐 Add multiple OAuth2 schemes
#     openapi_schema["components"]["securitySchemes"] = {
#         "AdminOAuth2": {
#             "type": "oauth2",
#             "flows": {
#                 "password": {
#                     "tokenUrl": f"{app.root_path}/auth/admin/token",
#                     "scopes": {
#                         "profile:read": "Read admin profiles",
#                         "profile:write": "Write admin profiles",
#                     },
#                 }
#             },
#         },
#         "CustomerOAuth2": {
#             "type": "oauth2",
#             "flows": {
#                 "password": {
#                     "tokenUrl": f"{app.root_path}/auth/customer/token",
#                     "scopes": {
#                         "customer_profile:read": "Read customer profiles",
#                         "customer_profile:write": "Write customer profiles",
#                     },
#                 }
#             },
#         },
#     }
#
#     app.openapi_schema = openapi_schema
#     return app.openapi_schema
#
#
# app.openapi = custom_openapi
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


@app.post("/auth/admin/token", include_in_schema=False)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_postgres),
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

    refresh_token, refresh_token_jti, expires_at = auth_manager.create_refresh_token(
        user_obj
    )
    access_token = auth_manager.create_access_token(
        user_obj, refresh_token_jti=refresh_token_jti
    )
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


app.include_router(router=auth_routes.router)
app.include_router(router=profile_routes.router)
app.include_router(router=role_routes.router)
app.include_router(router=file_routes.router)
app.include_router(router=inventory_routes.router)
app.include_router(router=cart_routes.router)
app.include_router(router=prescriptions.router)
app.include_router(router=request_orders.router)
app.include_router(router=order_routes.router)
app.include_router(router=issues_routes.router)
app.include_router(router=payment_routes.router)
app.include_router(router=discount_routes.router)
app.include_router(router=request_medicines_routes.router)
