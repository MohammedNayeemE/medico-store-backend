import logging
from re import L

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.dependecies.get_db_sessions import get_postgres
from app.api.routes import (
    auth_routes,
    file_routes,
    inventory_routes,
    profile_routes,
    role_routes,
)
from app.core.config import allowed_origins, settings
from app.core.database import Base, engine
from app.middlewares.logging_middleware import LoggingMiddleware
from app.models.inventory_management_models import *
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
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created!")


@app.get("/", include_in_schema=False)
async def get_root():
    return JSONResponse(status_code=200, content={"msg": "the server is running"})


@app.post("/auth/admin/token", include_in_schema=False)
async def login(
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
    if not auth_manager.verify_password(form_data.password, user_obj.password_hash):
        raise HTTPException(status_code=401, detail="wrong password")

    access_token = auth_manager.create_access_token(user=user_obj)
    refresh_token = auth_manager.create_refresh_token(user=user_obj)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


app.include_router(router=auth_routes.router)
app.include_router(router=profile_routes.router)
app.include_router(router=role_routes.router)
app.include_router(router=file_routes.router)
app.include_router(router=inventory_routes.router)
