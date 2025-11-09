import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr, field_validator

# =====================================================
# USER SCHEMAS
# =====================================================


class UserCreate(BaseModel):
    otp: constr(pattern=r"^\d{6}$") = Field(
        ..., example="123456", description="6-digit OTP sent to user's phone"
    )
    phone_number: constr(pattern=r"^\+91[6-9]\d{9}$") = Field(
        ...,
        example="+919876543210",
        description="Indian phone number with +91 country code (e.g. +919876543210)",
    )
    role_id: int = Field(
        ..., ge=1, example=2, description="Role ID associated with the user"
    )

    @field_validator("otp")
    def validate_otp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("Invalid OTP. Must be exactly 6 digits.")
        return v


class UserResponse(UserCreate):
    user_id: int = Field(..., example=1)
    is_active: bool = Field(..., example=True)
    created_at: datetime = Field(..., example="2025-11-08T10:30:00Z")

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# EMPLOYEE & ADMIN
# =====================================================


class EmployeeCreate(BaseModel):
    email: EmailStr = Field(..., example="john.doe@company.com")
    password: str = Field(..., min_length=6, max_length=20, example="StrongPass123")
    role_id: int = Field(..., ge=1, example=3, description="Role ID for employee")


class OnBoardEmployee(BaseModel):
    email: EmailStr = Field(..., example="new.employee@company.com")
    password: str = Field(..., min_length=6, max_length=20, example="Welcome123")


class AdminCreate(BaseModel):
    email: EmailStr = Field(..., example="admin@epms.com")
    password: str = Field(..., min_length=6, max_length=20, example="Admin@1234")
    captcha_token: Optional[str] = Field(
        None, example="03AGdBq26...", description="Captcha token from Google reCAPTCHA"
    )


class AdminResponse(AdminCreate):
    user_id: int = Field(..., example=1)
    is_active: bool = Field(..., example=True)
    created_at: datetime = Field(..., example="2025-11-08T10:30:00Z")

    model_config = ConfigDict(from_attributes=True)


class AdminProfileCreate(BaseModel):
    name: Optional[constr(strip_whitespace=True, min_length=2, max_length=100)] = Field(
        None, example="Mohammed Nayeem"
    )
    phone_number: Optional[constr(pattern=r"^[6-9]\d{9}$")] = Field(
        None, example="9876543210"
    )
    profile_pic: Optional[int] = Field(None, example=15)


class AdminProfileResponse(AdminProfileCreate):
    user_id: int = Field(..., example=1)
    created_at: datetime = Field(..., example="2025-11-08T11:00:00Z")

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# ROLES
# =====================================================


class RoleCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=2, max_length=50) = Field(
        ..., example="Admin"
    )
    description: constr(strip_whitespace=True, min_length=5, max_length=255) = Field(
        ..., example="Administrator with full permissions"
    )
    permissions: List[str] = Field(
        ..., example=["read:users", "write:users", "delete:users"]
    )


class RoleResponse(RoleCreate):
    role_id: int = Field(..., example=1)
    model_config = ConfigDict(from_attributes=True)


# =====================================================
# OTP & AUTH
# =====================================================


class OtpRequest(BaseModel):
    phone_number: constr(pattern=r"^\+91[6-9]\d{9}$") = Field(
        ...,
        example="+919876543210",
        description="Phone number with country code +91 (India)",
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")


class ResetPasswordRequest(BaseModel):
    token: str = Field(
        ..., example="eyJhbGciOiJIUzI1NiIsInR5...", description="Password reset token"
    )
    new_password: str = Field(
        ..., min_length=8, example="NewPass@2025", description="New user password"
    )


# =====================================================
# CUSTOMER PROFILE
# =====================================================


class CustomerProfileCreate(BaseModel):
    name: Optional[str] = Field(None, example="Ayesha Khan")
    address_id: Optional[int] = Field(None, example=10)
    profile_pic: Optional[int] = Field(None, example=21)
    blood_group: Optional[str] = Field(None, pattern=r"^(A|B|AB|O)[+-]$", example="B+")
    gender: Optional[str] = Field(
        None, pattern=r"^[MF]$", example="F", description="Gender: M or F"
    )
    dob: Optional[date] = Field(None, example="1998-03-15")


class CustomerProfileResponse(CustomerProfileCreate):
    user_id: int = Field(..., example=5)
    created_at: Optional[datetime] = Field(None, example="2025-10-08T09:15:00Z")
    updated_at: Optional[datetime] = Field(None, example="2025-11-08T09:25:00Z")

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# ADDRESS & ADDRESS TYPE
# =====================================================


class AddressResponse(BaseModel):
    address_id: int = Field(..., example=12)
    house_no: str = Field(..., example="12B")
    street_name: str = Field(..., example="Anna Salai (Mount Road)")
    locality: str = Field(..., example="Nandanam Officers Enclave")
    city: str = Field(..., example="Chennai")
    state: str = Field(..., example="Tamil Nadu")
    pincode: constr(pattern=r"^\d{6}$") = Field(..., example="600001")

    model_config = ConfigDict(from_attributes=True)


class AddressTypeBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=2, max_length=50) = Field(
        ..., example="Home"
    )


class AddressTypeCreate(AddressTypeBase):
    pass


class AddressTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, example="Office")
    is_deleted: Optional[bool] = Field(None, example=True)


class AddressTypeResponse(AddressTypeBase):
    type_id: int = Field(..., example=1)
    is_deleted: bool = Field(..., example=False)
    deleted_at: Optional[datetime] = Field(None, example="2025-11-08T10:45:00Z")

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# FAMILY MEMBERS
# =====================================================


class FamilyMemberCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=2, max_length=100) = Field(
        ..., example="Ayesha Khan"
    )
    phone_number: Optional[constr(pattern=r"^\+91[6-9]\d{9}$")] = Field(
        None,
        example="+919876543210",
        description="Indian phone number with +91 country code",
    )
    email: Optional[EmailStr] = Field(None, example="ayesha.khan@example.com")
    age: int = Field(..., ge=0, le=120, example=32)
    gender: constr(pattern=r"^[MF]$") = Field(
        ..., example="F", description="Gender: M or F"
    )
    dob: date = Field(..., example="1993-04-15")


class FamilyMemberUpdate(BaseModel):
    name: Optional[str] = Field(None, example="Updated Name")
    phone_number: Optional[str] = Field(None, example="9123456789")
    email: Optional[EmailStr] = Field(None, example="new.email@example.com")
    age: Optional[int] = Field(None, ge=0, le=120, example=30)
    gender: Optional[str] = Field(None, pattern=r"^[MF]$", example="M")
    dob: Optional[date] = Field(None, example="1995-06-21")


class FamilyMemberResponse(FamilyMemberCreate):
    member_id: int = Field(..., example=1)
    user_id: int = Field(..., example=7)

    model_config = ConfigDict(from_attributes=True)
