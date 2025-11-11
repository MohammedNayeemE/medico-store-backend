# Authentication & Role Documentation

**Project:** Electronic Pharmacy Management System (EPMS) - FastAPI Backend

**Version:** v1.0

**Last Updated:** 27-Oct-2025

## Overview

This document explains how **authentication** and **role-based access control (RBAC)** are implemented in the EPMS backend system built with **FastAPI**.

It covers login/registration flow, token management, and permissions assigned to each user role.

## Authentication Flow

| Step | Description |
| --- | --- |
| **1. Admin Register** | Admin registers using email and password (with onboarding token). |
| **2. Admin Login** | System verifies email/password and issues Access and Refresh tokens. |
| **3. Customer Login** | Customer authenticates using phone number and OTP (one-time password). |
| **4. Access Token** | Short-lived JWT (configurable, typically 15-30 min) for authenticated requests. |
| **5. Refresh Token** | Long-lived JWT (configurable, typically 7-30 days) to renew access tokens. |
| **6. Token Revocation** | Logout invalidates the refresh token (stored in database/Redis). |
| **7. Protected Routes** | Middleware verifies token and required permissions before route access. |

## JWT Token Structure

```json
{
  "sub": "user_id",
  "role_id": 1,
  "jti": "token_unique_id",
  "iat": 1730000000,
  "exp": 1730000300
}
```

**Token Claims:**
- `sub`: User ID (subject)
- `role_id`: User's role ID (1 = customer, others = admin)
- `jti`: JWT ID (unique token identifier for revocation)
- `iat`: Issued at timestamp
- `exp`: Expiration timestamp

## Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/admin-register` | Register new admin account | ❌ No |
| POST | `/api/v1/auth/admin-login` | Admin login (email/password) | ❌ No |
| POST | `/api/v1/auth/login` | Customer login (phone/OTP) | ❌ No |
| POST | `/api/v1/auth/refresh` | Refresh expired access token | ✅ Yes |
| POST | `/api/v1/auth/logout` | Logout and revoke refresh token | ✅ Yes |
| POST | `/api/v1/auth/logout-all` | Logout from all devices | ✅ Yes |
| POST | `/api/v1/auth/verify-onboarding` | Verify onboarding magic link | ❌ No |
| POST | `/api/v1/auth/employee-onboard` | Onboard employee with token | ❌ No |
| POST | `/api/v1/auth/admin-forgot-password` | Request password reset (admin) | ❌ No |
| POST | `/api/v1/auth/admin-change-password` | Request password change (admin) | ✅ Yes |
| POST | `/api/v1/auth/reset-password` | Reset password using token/OTP | ❌ No |
| POST | `/api/v1/auth/get-otp` | Generate and send OTP | ❌ No |

## Role-Based Access Control (RBAC)

### Roles

| Role | Description | Role ID | Example Permissions |
| --- | --- | --- | --- |
| **Customer** | Regular customers who can browse, order medicines | 1 | View medicines, manage cart, create orders, write reviews |
| **Admin** | System administrators with full access | != 1 | All permissions (full system access) |

### Customer Permissions

Customers have limited permissions for basic operations:

- **Authentication**: `auth:write`
- **Cart**: `cart:read`, `cart:write`, `cart:delete`
- **Orders**: `order:read`
- **Payments**: `payment:read`, `payment:write`
- **Prescriptions**: `prescription:read`, `prescription:write`
- **Profile**: `profile:read`, `profile:update`, `profile:write`
- **Request Orders**: `request_order:read`, `request_order:write`
- **Request Medicines**: `request_medicine:read`, `request_medicine:write`
- **Reviews**: `review:read`, `review:write`
- **Medicines**: `medicine:read`
- **Categories**: `category:read`
- **Discounts**: `discount:read`
- **Coupons**: `coupon:read`
- **Address Types**: `address_type:read`
- **Members**: `members:read`, `members:write`
- **Notifications**: `notification:read`

### Admin Permissions

Admins have **all permissions** in the system, including:

- All customer permissions
- **Medicine Management**: `medicine:write`, `medicine:delete`
- **Order Management**: `order:write`, `order:delete`
- **Payment Management**: `payment:update`
- **Request Order Admin**: `request_order_admin:read`, `request_order_admin:update`
- **Batch Management**: `batch:read`, `batch:write`, `batch:delete`
- **Discount Management**: `discount:write`, `discount:delete`
- **Coupon Management**: `coupon:write`
- **Category Management**: `category:write`
- **Role Management**: `role:read`, `role:write`, `role:update`
- **Admin Management**: `admin:read`, `admin:write`
- **Dashboard**: `dashboard:read`
- **Reports**: `reports:read`
- **Backup**: `backup:read`, `backup:write`
- **Content Management**: `content:write`
- **GST Management**: `gst:read`, `gst:write`
- **Issue Management**: `issue:read`, `issue:write`
- **Tag Management**: `tag:read`, `tag:write`
- **Side Effects**: `side_effect:read`, `side_effect:write`
- **Review Management**: `review:delete`
- **Address Type Management**: `address_type:write`, `address_type:delete`
- **Alternate Records**: `alternate:write`, `alternate:update`

## Permission Matrix

### Core Resources

| Resource | Action | Customer | Admin |
| --- | --- | --- | --- |
| **Medicine** | Read | ✅ | ✅ |
| **Medicine** | Write | ❌ | ✅ |
| **Medicine** | Delete | ❌ | ✅ |
| **Cart** | Read | ✅ | ✅ |
| **Cart** | Write | ✅ | ✅ |
| **Cart** | Delete | ✅ | ✅ |
| **Order** | Read | ✅ | ✅ |
| **Order** | Write | ❌ | ✅ |
| **Order** | Delete | ❌ | ✅ |
| **Payment** | Read | ✅ | ✅ |
| **Payment** | Write | ✅ | ✅ |
| **Payment** | Update | ❌ | ✅ |
| **Prescription** | Read | ✅ | ✅ |
| **Prescription** | Write | ✅ | ✅ |
| **Request Order** | Read | ✅ | ✅ |
| **Request Order** | Write | ✅ | ✅ |
| **Request Order (Admin)** | Read | ❌ | ✅ |
| **Request Order (Admin)** | Update | ❌ | ✅ |
| **Review** | Read | ✅ | ✅ |
| **Review** | Write | ✅ | ✅ |
| **Review** | Delete | ❌ | ✅ |
| **Profile** | Read | ✅ | ✅ |
| **Profile** | Update | ✅ | ✅ |
| **Profile** | Write | ✅ | ✅ |

### Administrative Resources

| Resource | Action | Customer | Admin |
| --- | --- | --- | --- |
| **Batch** | Read | ❌ | ✅ |
| **Batch** | Write | ❌ | ✅ |
| **Batch** | Delete | ❌ | ✅ |
| **Category** | Read | ✅ | ✅ |
| **Category** | Write | ❌ | ✅ |
| **Discount** | Read | ✅ | ✅ |
| **Discount** | Write | ❌ | ✅ |
| **Discount** | Delete | ❌ | ✅ |
| **Coupon** | Read | ✅ | ✅ |
| **Coupon** | Write | ❌ | ✅ |
| **Dashboard** | Read | ❌ | ✅ |
| **Reports** | Read | ❌ | ✅ |
| **Backup** | Read | ❌ | ✅ |
| **Backup** | Write | ❌ | ✅ |
| **Role** | Read | ❌ | ✅ |
| **Role** | Write | ❌ | ✅ |
| **Role** | Update | ❌ | ✅ |
| **Admin** | Read | ❌ | ✅ |
| **Admin** | Write | ❌ | ✅ |
| **Content** | Write | ❌ | ✅ |
| **GST** | Read | ❌ | ✅ |
| **GST** | Write | ❌ | ✅ |
| **Issue** | Read | ❌ | ✅ |
| **Issue** | Write | ❌ | ✅ |
| **Tag** | Read | ❌ | ✅ |
| **Tag** | Write | ❌ | ✅ |
| **Side Effect** | Read | ❌ | ✅ |
| **Side Effect** | Write | ❌ | ✅ |
| **Address Type** | Read | ✅ | ✅ |
| **Address Type** | Write | ❌ | ✅ |
| **Address Type** | Delete | ❌ | ✅ |

## Permission Naming Convention

Permissions follow the pattern: **`{resource}:{action}`**

**Resources:**
- `medicine`, `order`, `payment`, `cart`, `prescription`
- `review`, `profile`, `request_order`, `request_medicine`
- `batch`, `category`, `discount`, `coupon`
- `dashboard`, `reports`, `backup`, `role`, `admin`
- `content`, `gst`, `issue`, `tag`, `side_effect`
- `address_type`, `members`, `notification`, `auth`
- `alternate`

**Actions:**
- `read`: View/list resources
- `write`: Create new resources
- `update`: Modify existing resources
- `delete`: Remove resources

## Middleware & Token Validation

### Dependency Injection

All protected routes use FastAPI's dependency injection system with `Security(get_current_user, scopes=[...])`.

**Example:**
```python
@router.get("/medicines")
async def get_medicines(
    current_user: User = Security(get_current_user, scopes=["medicine:read"])
):
    # Route implementation
```

### Token Validation Process

1. **Extract Token**: Token is extracted from `Authorization: Bearer <token>` header
2. **Decode JWT**: Token is decoded and validated (signature, expiration)
3. **Check Revocation**: Token is checked against revoked tokens in database
4. **Load Permissions**: User's role permissions are loaded from database (cached in Redis)
5. **Validate Scopes**: Required scopes are checked against user's permissions
6. **Return User**: Authenticated user object is returned if validation passes

### Error Responses

| Status Code | Description |
| --- | --- |
| **401 Unauthorized** | Invalid or expired token, missing token |
| **403 Forbidden** | User lacks required permissions/scopes |
| **404 Not Found** | User not found or token invalid |

## Security Features

### Token Security
- **HTTP-Only Cookies**: Refresh tokens stored in HTTP-only cookies
- **Secure Flag**: Cookies sent only over HTTPS in production
- **SameSite**: Cookies protected against CSRF attacks
- **Token Revocation**: Tokens can be revoked and tracked in database
- **JWT ID (jti)**: Unique token identifier for revocation tracking

### Password Security
- **Hashing**: Passwords hashed using Argon2 (secure hashing algorithm)
- **OTP Expiration**: OTPs expire after 5-10 minutes
- **Rate Limiting**: Authentication endpoints rate-limited (100 requests per minute)

### Session Management
- **Session Tracking**: Sessions stored in database with IP address and user agent
- **Multi-Device Support**: Users can have multiple active sessions
- **Logout All**: Users can logout from all devices at once
- **Session Expiration**: Sessions expire when refresh token expires

## Authentication Examples

### Admin Login

**Request:**
```bash
POST /api/v1/auth/admin-login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "secure_password"
}
```

**Response:**
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

### Customer Login (OTP)

**Step 1: Get OTP**
```bash
POST /api/v1/auth/get-otp
Content-Type: application/json

{
  "phone_number": "+1234567890"
}
```

**Step 2: Login with OTP**
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "otp": "123456"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 1,
  "session_id": 123
}
```

### Protected Route Access

**Request:**
```bash
GET /api/v1/medicines
Authorization: Bearer eyJ...
```

**Response (Success):**
```json
{
  "success": true,
  "data": [...],
  "message": "Success"
}
```

**Response (Unauthorized):**
```json
{
  "detail": "Could not validate credentials"
}
```

**Response (Forbidden):**
```json
{
  "detail": "Missing required permissions: medicine:write"
}
```

## Employee Onboarding

### Admin Creates Employee
1. Admin creates employee account via admin panel
2. System generates onboarding token
3. Onboarding email sent to employee with magic link
4. Employee clicks link and sets password
5. Employee account activated

### Onboarding Flow
```
Admin creates employee
    ↓
Onboarding token generated
    ↓
Email sent with magic link
    ↓
Employee verifies token
    ↓
Employee sets password
    ↓
Account activated
```

## Password Reset Flow

### Admin Password Reset
1. Admin requests password reset via `/admin-forgot-password`
2. Reset token generated and sent via email
3. Admin uses token with `/reset-password` to set new password
4. Token invalidated after use

### Customer Password Reset
1. Customer requests OTP via `/get-otp`
2. OTP sent to phone number
3. Customer uses OTP with `/login` to authenticate
4. OTP invalidated after use

## Token Refresh Flow

### Refresh Access Token
1. Client sends refresh token from cookies
2. Server validates refresh token
3. Server generates new access token
4. New access token returned to client

**Request:**
```bash
POST /api/v1/auth/refresh
Cookie: refresh_token=eyJ...
Authorization: Bearer <expired_access_token>
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

## Logout Flow

### Single Device Logout
1. Client sends logout request with access token
2. Server revokes access token and refresh token
3. Session terminated in database
4. Tokens added to revocation list

### All Devices Logout
1. Client sends logout-all request
2. Server revokes all access tokens for user
3. All sessions terminated
4. All tokens added to revocation list

## Best Practices

### For Developers
1. **Always check permissions**: Use `Security(get_current_user, scopes=[...])` for protected routes
2. **Validate input**: Validate all user input before processing
3. **Handle errors**: Return appropriate error codes (401, 403, 404)
4. **Log security events**: Log authentication and authorization events
5. **Rate limiting**: Implement rate limiting on authentication endpoints

### For API Consumers
1. **Store tokens securely**: Store tokens in secure storage (HTTP-only cookies recommended)
2. **Handle token expiration**: Implement token refresh logic
3. **Handle errors**: Handle 401 (unauthorized) and 403 (forbidden) errors gracefully
4. **Don't expose tokens**: Never expose tokens in URLs or client-side code
5. **Use HTTPS**: Always use HTTPS in production

## Configuration

### Token Expiration
- **Access Token**: Configurable (default: 15-30 minutes)
- **Refresh Token**: Configurable (default: 7-30 days)
- **OTP Expiration**: Configurable (default: 5-10 minutes)
- **Reset Token Expiration**: Configurable (default: 1 hour)
- **Onboarding Token Expiration**: Configurable (default: 7 days)

### Rate Limiting
- **Authentication Endpoints**: 100 requests per minute
- **API Endpoints**: Configurable per route

## Troubleshooting

### Common Issues

**Issue: Token expired**
- **Solution**: Use refresh token to get new access token

**Issue: Invalid token**
- **Solution**: Re-authenticate to get new tokens

**Issue: Missing permissions**
- **Solution**: Check user's role and assigned permissions

**Issue: OTP not received**
- **Solution**: Check phone number format, rate limits, and SMS service configuration

**Issue: Password reset token invalid**
- **Solution**: Token may be expired or already used. Request new reset token.

## Additional Resources

- **API Documentation**: Swagger UI available at `/docs`
- **Seed Script**: Run `seed_roles_and_permissions()` to initialize roles and permissions
- **Database Models**: See `app/models/user_management_models.py`
- **Auth Service**: See `app/services/auth_management/auth_service.py`
- **Auth Dependencies**: See `app/api/dependecies/auth.py`

## Changelog

### v1.0 (27-Oct-2025)
- Initial documentation
- Customer and Admin roles
- JWT token-based authentication
- OTP-based customer authentication
- Role-based permission system
- Token revocation and session management

---

**Note:** This documentation is maintained as part of the EPMS backend project. For updates or questions, please refer to the project repository or contact the development team.

