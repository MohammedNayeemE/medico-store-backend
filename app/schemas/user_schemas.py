import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr, field_validator


class UserCreate(BaseModel):
    otp: str = Field(...)
    phone_number: str
    role_id: int

    @field_validator("phone_number")
    def validate_phone_number(cls, v):
        pattern = r"^[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid phone number. Must be 10 digits and start with 6–9."
            )
        return v

    @field_validator("otp")
    def validate_otp(cls, v):
        pattern = r"^\d{6}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid OTP. Must be exactly 6 digits.")
        return v


class UserResponse(UserCreate):
    user_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminCreate(BaseModel):
    email: EmailStr
    role_id: int
    password: str = Field(..., min_length=6, max_length=20)


class AdminResponse(AdminCreate):
    user_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProfileCreate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_pic: Optional[int] = None


class AdminProfileResponse(AdminProfileCreate):
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    name: str
    description: str
    permissions: List[str]


class RoleResponse(RoleCreate):
    role_id: int
    model_config = ConfigDict(from_attributes=True)


class OtpRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    def validate_phone_number(cls, v):
        pattern = r"^[6-9]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid phone number. Must be 10 digits and start with 6–9."
            )
        return v


class CustomerProfileCreate(BaseModel):
    name: Optional[str] = None
    address_id: Optional[int] = None
    profile_pic: Optional[int] = None
    blood_group: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None


class CustomerProfileResponse(CustomerProfileCreate):
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AddressResponse(BaseModel):
    address_id: int
    house_no: str
    street_name: str
    locality: str
    city: str
    state: str
    pincode: str

    model_config = ConfigDict(from_attributes=True)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset token sent to user's email")
    new_password: str = Field(
        ..., min_length=8, description="New password for the user"
    )
