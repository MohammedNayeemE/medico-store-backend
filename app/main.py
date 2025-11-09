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
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
        <title>Custom Docs with Tag Filter</title>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({
            url: '/openapi.json',
            dom_id: '#swagger-ui',
            layout: 'BaseLayout',
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            onComplete: () => {
                // Wait for DOM to be ready
                const authButton = document.querySelector('.btn.authorize.unlocked');
    // Wait a short time in case the modal content loads dynamically
    setInterval(() => {
      
      const modal = document.querySelector('.modal-ux'); // or use your modal selector
modal.querySelectorAll('*').forEach(el => {
  el.childNodes.forEach(node => {
    if (node.nodeType === 3) {
      const text = node.textContent.trim();
      if (text.includes('username')) {
        node.textContent = text.replace(/username/gi, 'Mobile or Email ');
      }
      if (text.includes('password')) {
        node.textContent = text.replace(/password/gi, 'OTP or Password');
      }
    }  
  });
});
    }, 5000);
                setTimeout(() => {
                    const authWrapper = document.querySelector('.auth-wrapper');
                    if (authWrapper) {
                        const dropdown = document.createElement('select');
                        dropdown.style.marginRight = '10px';
                        dropdown.innerHTML = `
                            <option value="">-- Show All --</option>
                            <option value="default">Root</option>
                            <option value="Auth">Auth</option>
                            <option value="Profiles">Profile</option>
                            <option value="Roles">Roles</option>
                            <option value="Files Testing">Files</option>
                            <option value="Medicines">Medicines</option>
                            <option value="Categories">Categories</option>
                            <option value="Tags">Tags</option>
                            <option value="Medicine Alternatives">Medicine Alternatives</option>
                            <option value="Medicine Batches">Medicine Batches</option>
                            <option value="Medicine Sideffects">Medicine Sideeffects</option>
                            <option value="GST Slabs">GST Slabs</option>
                            <option value="Cart">Cart</option>
                            <option value="Prescriptions">Prescriptions</option>
                            <option value="Request Orders">Request Orders</option>
                            <option value="Orders">Orders</option>
                            <option value="Issues">Issues</option>
                            <option value="Payments">Payments</option>
                            <option value="Discounts">Discounts</option>
                            <option value="Medicine Requests">Medicine Requests</option>
                            <option value="Reviews">Reviews</option>
                            <option value="Notifications">Notifications</option>
                            <option value="Backup Management">Backup Management</option>
                            <option value="Content Management">Content Management</option>
                            <option value="Dashboard">Dashboard</option>
                            <option value="Audit LOGS">Logs</option>

                        `;

                        
                        dropdown.style.zIndex = '9999';
                        dropdown.style.padding = '8px';
                        dropdown.style.backgroundColor = '#f5f5f5';
                        dropdown.style.border = '1px solid #ccc';
                        dropdown.style.borderRadius = '4px';
                        dropdown.style.cursor = 'pointer';
                        dropdown.style.marginRight = '10px';


                        dropdown.onchange = function() {
                            const tag = this.value;
                            document.querySelectorAll('.opblock-tag-section').forEach(sec => {
                                const tagName = sec.querySelector('.opblock-tag').textContent.trim();
                                if (!tag || tagName === tag) {
                                    sec.style.display = '';
                                } else {
                                    sec.style.display = 'none';
                                }
                            });
                        };

                        // Insert dropdown before the auth button
                        authWrapper.parentNode.insertBefore(dropdown, authWrapper);
                    }
                }, 1000); // Small delay to ensure Swagger UI renders
            }
        });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


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
            max_age=auth_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 24 * 60,
            path="/auth/refresh",
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
