import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth_routes, profile_routes, role_routes
from app.core.config import allowed_origins, settings
from app.core.database import Base, engine
from app.middlewares.logging_middleware import LoggingMiddleware
from app.models.user_management_models import *

app = FastAPI(
    root_path="/api/v1", title=settings.APP_NAME, version=settings.APP_VERSION
)

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


@app.get("/")
async def get_root():
    return JSONResponse(status_code=200, content={"msg": "the server is running"})


app.include_router(router=auth_routes.router)
app.include_router(router=profile_routes.router)
app.include_router(router=role_routes.router)
