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
    """
    Development and testing endpoint for authentication routes.

    This is a simple health check endpoint used to verify that the authentication
    routes are properly configured and accessible. It returns a simple success message
    without requiring any authentication.

    Returns:
        JSONResponse: A JSON response with status 200 containing a success message.
                     Response format: {"msg": "this route is working...."}

    Note:
        This endpoint is primarily for development and testing purposes.
        It does not require authentication and should not be used in production
        for sensitive operations.
    """
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post(
    "/admin-login", description="Authenticate an admin and issue access tokens"
)
async def login_admin(
    request: Request, admin: AdminCreate, db: AsyncSession = Depends(get_postgres)
):
    """
    Authenticate an admin user and issue JWT access and refresh tokens.

    This endpoint handles admin authentication by validating email and password
    credentials. Upon successful authentication, it creates a new session, generates
    JWT access and refresh tokens, and stores the session information in the database.
    The tokens are also set as HTTP-only cookies for security.

    Args:
        request (Request): The FastAPI request object containing headers and client
                          information (IP address, user agent) for session tracking.
        admin (AdminCreate): Admin credentials containing:
                            - email (str): Admin email address
                            - password (str): Admin password (plaintext, will be verified)
        db (AsyncSession): Database session dependency for querying user data and
                          creating sessions. Defaults to Depends(get_postgres).

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message
                     - user_id (int): Authenticated admin's user ID
                     - email (str): Admin's email address
                     - session_id (int): Created session ID
                     - access_token (str): JWT access token for API authentication
                     - refresh_token (str): JWT refresh token for obtaining new access tokens
                     - token_type (str): Token type, typically "bearer"

    Raises:
        HTTPException (401): If email or password is incorrect, or user is not found.
        HTTPException (403): If the user account is disabled or locked.
        HTTPException (500): If there's an internal server error during authentication.

    Security:
        - Passwords are verified using secure hashing (bcrypt)
        - Access tokens are set as HTTP-only cookies
        - Refresh tokens are set as HTTP-only cookies with secure and same-site flags
        - Session information (IP address, user agent) is recorded for security

    Example Request:
        ```json
        {
            "email": "admin@example.com",
            "password": "secure_password"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Login Successfull",
            "user_id": 1,
            "email": "admin@example.com",
            "session_id": 123,
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "bearer"
        }
        ```

    Note:
        - The access token has a shorter expiration time (typically 15-30 minutes)
        - The refresh token has a longer expiration time (typically 7-30 days)
        - Cookies are set with secure, httponly, and samesite=strict flags
        - Session is created in the database with device and IP information
    """
    result = await auth.LOGIN_ADMIN(request=request, admin=admin, db=db)
    return result


@router.post("/admin-register", description="Register a new admin account")
async def register_admin(
    request: Request, admin: AdminCreate, db: AsyncSession = Depends(get_postgres)
):
    """
    Register a new admin account in the system.

    This endpoint creates a new admin user account with the provided credentials.
    The admin account is created with appropriate role and permissions. A verification
    email or onboarding link may be sent to complete the registration process.

    Args:
        request (Request): The FastAPI request object containing headers and client
                          information for tracking registration requests.
        admin (AdminCreate): Admin registration data containing:
                            - email (str): Admin email address (must be unique)
                            - password (str): Admin password (will be hashed)
                            - Optional: name, phone_number, etc.
        db (AsyncSession): Database session dependency for creating the admin user.
                          Defaults to Depends(get_postgres).

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success or error message
                     - user_id (int): Created admin's user ID (if successful)
                     - email (str): Admin's email address
                     - Optional: verification token or onboarding link

    Raises:
        HTTPException (400): If the email already exists or validation fails.
        HTTPException (422): If the request data is invalid or missing required fields.
        HTTPException (500): If there's an internal server error during registration.

    Security:
        - Password is hashed using secure hashing (bcrypt) before storage
        - Email uniqueness is enforced
        - Admin role and permissions are automatically assigned

    Example Request:
        ```json
        {
            "email": "admin@example.com",
            "password": "secure_password",
            "name": "Admin Name"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Admin registered successfully",
            "user_id": 1,
            "email": "admin@example.com",
            "verification_token": "abc123..."
        }
        ```

    Note:
        - The admin account may require email verification before it can be used
        - An onboarding email with a magic link may be sent to complete registration
        - The admin is assigned the admin role with full system permissions
        - Password must meet security requirements (length, complexity, etc.)
    """
    result = await auth.CREATE_ADMIN(request=request, admin_data=admin, db=db)
    return result


@router.post("/verify-onboarding", description="verify the magick link")
async def verify_onboarding(token: str = Query(...)):
    """
    Verify an onboarding token from a magic link.

    This endpoint verifies the onboarding token sent via email during admin registration.
    The token is validated, and if valid, the admin account is activated and marked as
    verified. This completes the onboarding process for new admin users.

    Args:
        token (str): The verification token from the magic link sent via email.
                    This is provided as a query parameter.

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success or error message
                     - user_id (int): Verified admin's user ID (if successful)
                     - email (str): Admin's email address
                     - Optional: access_token and refresh_token for immediate login

    Raises:
        HTTPException (400): If the token is invalid, expired, or already used.
        HTTPException (404): If the token does not exist in the system.
        HTTPException (500): If there's an internal server error during verification.

    Security:
        - Tokens are single-use and expire after a certain time period
        - Token validation includes expiration and usage checks
        - Successful verification activates the admin account

    Example Request:
        ```
        POST /auth/verify-onboarding?token=abc123def456...
        ```

    Example Response:
        ```json
        {
            "msg": "Onboarding verified successfully",
            "user_id": 1,
            "email": "admin@example.com"
        }
        ```

    Note:
        - Tokens are typically sent via email during registration
        - Tokens expire after a configurable time period (e.g., 24 hours)
        - Once verified, the token cannot be used again
        - The admin account is activated and ready for use after verification
    """
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
    """
    Onboard a new employee by setting their password using an onboarding token.

    This endpoint completes the employee onboarding process by allowing new employees
    to set their password using a valid onboarding token. The token is typically sent
    via email when an employee account is created by an admin. After password setup,
    the employee account is activated and ready for use.

    Args:
        db (AsyncSession): Database session dependency for updating employee data.
                          Defaults to Depends(get_postgres).
        token (str): The onboarding token sent to the employee via email.
                    This token verifies the employee's identity and authorizes
                    password setup. Provided in the request body.
        password (str): The new password to set for the employee account.
                       Provided in the request body. Must meet password requirements.

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success or error message
                     - user_id (int): Employee's user ID (if successful)
                     - email (str): Employee's email address
                     - Optional: access_token and refresh_token for immediate login

    Raises:
        HTTPException (400): If the token is invalid, expired, or password doesn't
                            meet requirements.
        HTTPException (404): If the token does not exist or employee not found.
        HTTPException (500): If there's an internal server error during onboarding.

    Security:
        - Token is validated before allowing password setup
        - Password is hashed using secure hashing (bcrypt) before storage
        - Tokens are single-use and expire after a certain time period
        - Password must meet security requirements (length, complexity, etc.)

    Example Request:
        ```json
        {
            "token": "onboarding_token_abc123...",
            "password": "secure_employee_password"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Employee onboarded successfully",
            "user_id": 5,
            "email": "employee@example.com"
        }
        ```

    Note:
        - This endpoint is typically used after an admin creates an employee account
        - The onboarding token is sent via email to the employee
        - Tokens expire after a configurable time period (e.g., 7 days)
        - Once the password is set, the token cannot be used again
        - The employee account is activated and ready for use after onboarding
    """
    result = await auth.ONBOARD_NEW_EMPLOYEE(db=db, token=token, password=password)
    return result


@router.post("/logout", description="Logout users revoke the active session/token")
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["auth:write"]),
):
    """
    Logout the current user by revoking their access and refresh tokens.

    This endpoint invalidates the current user's session by revoking both the access
    token and refresh token. The tokens are marked as revoked in the database, preventing
    their future use. The session associated with the refresh token is also terminated.

    Args:
        request (Request): The FastAPI request object containing cookies with the
                          refresh token.
        token (str): The JWT access token from the Authorization header.
                    Extracted automatically using OAuth2PasswordBearer.
        db (AsyncSession): Database session dependency for revoking tokens and sessions.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "auth:write" permission.

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message indicating logout was successful

    Raises:
        HTTPException (404): If the refresh token is not found in the request cookies.
        HTTPException (401): If the access token is invalid or expired.
        HTTPException (500): If there's an internal server error during logout.

    Security:
        - Both access and refresh tokens are revoked
        - Session is terminated in the database
        - Revoked tokens cannot be used for future requests
        - Requires authentication and "auth:write" permission

    Example Request:
        ```
        POST /auth/logout
        Authorization: Bearer <access_token>
        Cookie: refresh_token=<refresh_token>
        ```

    Example Response:
        ```json
        {
            "msg": "Logged out successfully"
        }
        ```

    Note:
        - The refresh token must be present in the request cookies
        - Both tokens are permanently revoked and cannot be reused
        - The session associated with the refresh token is deleted
        - User must be authenticated to logout (requires valid access token)
    """
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
    """
    Initiate password reset process for an admin user.

    This endpoint starts the password reset flow by generating a reset token and
    sending it to the admin's email address. The reset token can be used with the
    reset-password endpoint to set a new password. The email is sent asynchronously
    using background tasks to avoid blocking the request.

    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks for sending
                                           email asynchronously without blocking
                                           the response.
        data (ForgotPasswordRequest): Request data containing:
                                     - email (str): Admin's email address
        db (AsyncSession): Database session dependency for querying user data and
                          generating reset tokens. Defaults to Depends(get_postgres).

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message (email sent confirmation)
                     - Optional: Token or reset link information (for testing)

    Raises:
        HTTPException (404): If the admin user with the provided email is not found.
        HTTPException (400): If the email is invalid or the user account is disabled.
        HTTPException (500): If there's an internal server error during the process.

    Security:
        - Reset tokens are generated with expiration time
        - Tokens are single-use and expire after a configurable period
        - Email is sent asynchronously to avoid blocking
        - Does not reveal whether an email exists in the system (security best practice)

    Example Request:
        ```json
        {
            "email": "admin@example.com"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Password reset email sent successfully"
        }
        ```

    Note:
        - A password reset token is generated and sent via email
        - The token expires after a configurable time period (e.g., 1 hour)
        - The email is sent asynchronously using background tasks
        - For security, the response does not reveal if the email exists
        - Use the reset-password endpoint with the token to complete the reset
    """
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
    """
    Request a password change for an admin user (authenticated user only).

    This endpoint allows an authenticated admin to request a password change by
    sending a password reset email. Unlike the forgot-password endpoint, this
    requires the user to be authenticated. The reset token is sent via email
    asynchronously, and the user can then use the reset-password endpoint to
    complete the password change.

    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks for sending
                                           email asynchronously without blocking
                                           the response.
        db (AsyncSession): Database session dependency for querying user data and
                          generating reset tokens. Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "auth:write" permission.
        data (ForgotPasswordRequest): Request data containing:
                                     - email (str): Admin's email address (must match
                                                   the authenticated user's email)

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message (email sent confirmation)

    Raises:
        HTTPException (400): If the email doesn't match the authenticated user or
                            validation fails.
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "auth:write" permission.
        HTTPException (404): If the user is not found.
        HTTPException (500): If there's an internal server error during the process.

    Security:
        - Requires authentication and "auth:write" permission
        - Reset tokens are generated with expiration time
        - Tokens are single-use and expire after a configurable period
        - Email is sent asynchronously to avoid blocking
        - User ID and role ID are used for authorization

    Example Request:
        ```json
        {
            "email": "admin@example.com"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Password change email sent successfully"
        }
        ```

    Note:
        - The user must be authenticated to use this endpoint
        - The email should match the authenticated user's email
        - A password reset token is generated and sent via email
        - The token expires after a configurable time period (e.g., 1 hour)
        - Use the reset-password endpoint with the token to complete the change
    """
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
    """
    Reset a user's password using a valid reset token.

    This endpoint completes the password reset process by validating the reset token
    and updating the user's password. The token is typically obtained from the email
    sent by the forgot-password or admin-change-password endpoints. After successful
    reset, the token is invalidated and cannot be used again.

    Args:
        data (ResetPasswordRequest): Request data containing:
                                    - token (str): The password reset token from email
                                    - new_password (str): The new password to set
                                                        (must meet password requirements)
        db (AsyncSession): Database session dependency for validating tokens and
                          updating passwords. Defaults to Depends(get_postgres).

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message indicating password was reset

    Raises:
        HTTPException (400): If the token is invalid, expired, or already used.
        HTTPException (422): If the new password doesn't meet requirements.
        HTTPException (404): If the token doesn't exist in the system.
        HTTPException (500): If there's an internal server error during reset.

    Security:
        - Token is validated before allowing password reset
        - Password is hashed using secure hashing (bcrypt) before storage
        - Tokens are single-use and expire after a configurable period
        - Password must meet security requirements (length, complexity, etc.)
        - Token is invalidated after successful password reset

    Example Request:
        ```json
        {
            "token": "reset_token_abc123...",
            "new_password": "new_secure_password"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "Password reset successfully"
        }
        ```

    Note:
        - The token is obtained from the password reset email
        - Tokens expire after a configurable time period (e.g., 1 hour)
        - Once used, the token cannot be reused
        - The new password must meet security requirements
        - After reset, the user can login with the new password
    """
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
    """
    Logout the user from all devices and revoke all active sessions.

    This endpoint terminates all active sessions for the authenticated user across
    all devices. All access tokens and refresh tokens associated with the user are
    revoked, forcing the user to login again on all devices. This is useful for
    security purposes when a user suspects unauthorized access.

    Args:
        request (Request): The FastAPI request object containing cookies with the
                          access token.
        db (AsyncSession): Database session dependency for revoking all tokens and
                          sessions. Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "auth:write" permission.

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message indicating logout from all devices
                     - sessions_revoked (int): Number of sessions revoked (optional)

    Raises:
        HTTPException (401): If the access token is invalid or expired.
        HTTPException (403): If the user doesn't have "auth:write" permission.
        HTTPException (500): If there's an internal server error during logout.

    Security:
        - All sessions for the user are terminated
        - All access and refresh tokens are revoked
        - User must be authenticated to logout (requires valid access token)
        - Requires "auth:write" permission
        - Revoked tokens cannot be used for future requests

    Example Request:
        ```
        POST /auth/logout-all
        Authorization: Bearer <access_token>
        Cookie: access_token=<access_token>
        ```

    Example Response:
        ```json
        {
            "msg": "Logged out from all devices successfully",
            "sessions_revoked": 3
        }
        ```

    Note:
        - This action is irreversible and affects all devices
        - All active sessions are terminated immediately
        - The user will need to login again on all devices
        - Useful for security when unauthorized access is suspected
        - The current session is also revoked as part of this operation
    """
    access_token = request.cookies.get("access_token")
    result = await auth.LOGOUT_ALL(
        user_id=current_user.user_id, db=db, access_token=access_token
    )
    return result


@router.post("/get-otp", description="Generate and send an OTP for phone verification")
async def get_otp(data: OtpRequest, redis=Depends(get_redis_client)):
    """
    Generate and send a one-time password (OTP) for phone number verification.

    This endpoint generates a random OTP and sends it to the provided phone number
    via SMS. The OTP is stored in Redis with an expiration time for verification.
    This is commonly used for user authentication, phone verification, or two-factor
    authentication.

    Args:
        data (OtpRequest): Request data containing:
                          - phone_number (str): Phone number to send OTP to
                                              (format: +1234567890 or 1234567890)
        redis: Redis client dependency for storing OTP with expiration.
               Defaults to Depends(get_redis_client).

    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message
                     - otp_sent (bool): Whether OTP was sent successfully
                     - phone_number (str): Phone number the OTP was sent to
                     - Optional: OTP value (for testing/development only)

    Raises:
        HTTPException (400): If the phone number is invalid or malformed.
        HTTPException (429): If too many OTP requests are made in a short time
                            (rate limiting).
        HTTPException (500): If there's an error sending the OTP or storing it.

    Security:
        - OTP is stored in Redis with expiration time (typically 5-10 minutes)
        - Rate limiting prevents abuse (multiple requests in short time)
        - OTP is a random numeric code (typically 4-6 digits)
        - OTP can only be used once
        - Phone number format is validated

    Example Request:
        ```json
        {
            "phone_number": "+1234567890"
        }
        ```

    Example Response:
        ```json
        {
            "msg": "OTP sent successfully",
            "otp_sent": true,
            "phone_number": "+1234567890"
        }
        ```

    Note:
        - OTP is stored in Redis with key format: "otp:{phone_number}"
        - OTP expires after a configurable time (e.g., 5-10 minutes)
        - Rate limiting prevents too many OTP requests
        - OTP is sent via SMS service (configured in the service)
        - In development, OTP might be returned in response (for testing)
        - Use the OTP with the login endpoint to authenticate
    """
    result = await auth.GET_OTP(data=data, redis_client=redis)
    return result


@router.post("/login", description="Authenticate user and issue access tokens")
async def user_login(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_postgres),
    redis=Depends(get_redis_client),
):
    """
    Authenticate a customer user using phone number and OTP, then issue access tokens.

    This endpoint handles customer authentication using phone number and OTP verification.
    The OTP is verified against the value stored in Redis. If valid, a new user account
    is created (if it doesn't exist), a session is created, and JWT access and refresh
    tokens are generated. The tokens are set as HTTP-only cookies for security.

    Args:
        request (Request): The FastAPI request object containing headers and client
                          information (IP address, user agent) for session tracking.
        user_data (UserCreate): User credentials containing:
                               - phone_number (str): User's phone number
                               - otp (str): One-time password for verification
        db (AsyncSession): Database session dependency for querying/creating user data
                          and creating sessions. Defaults to Depends(get_postgres).

    Returns:
        JSONResponse: A JSON response containing:
                     - access_token (str): JWT access token for API authentication
                     - refresh_token (str): JWT refresh token for obtaining new access tokens
                     - token_type (str): Token type, typically "bearer"
                     - user_id (int): Authenticated user's user ID
                     - session_id (int): Created session ID

    Raises:
        HTTPException (400): If the OTP is invalid or doesn't match.
        HTTPException (404): If the OTP is not found or expired in Redis.
        HTTPException (500): If there's an internal server error during authentication.

    Security:
        - OTP is verified against Redis storage
        - OTP is deleted after successful verification (single-use)
        - Access tokens are set as HTTP-only cookies
        - Refresh tokens are set as HTTP-only cookies with secure and same-site flags
        - Session information (IP address, user agent) is recorded
        - New users are automatically created with customer role

    Example Request:
        ```json
        {
            "phone_number": "+1234567890",
            "otp": "123456"
        }
        ```

    Example Response:
        ```json
        {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "bearer",
            "user_id": 1,
            "session_id": 123
        }
        ```

    Note:
        - OTP must be obtained from the get-otp endpoint first
        - OTP expires after a configurable time (e.g., 5-10 minutes)
        - If user doesn't exist, a new customer account is created automatically
        - Access token has shorter expiration (typically 15-30 minutes)
        - Refresh token has longer expiration (typically 7-30 days)
        - Cookies are set with secure, httponly, and samesite=strict flags
    """
    result = await auth.LOGIN_USER(
        request=request, user_data=user_data, db=db, redis_client=redis
    )
    return result


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
):
    result = await auth.REFRESH_TOKEN(db=db, request=request)
    return result
