from enum import Enum

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ReviewStatusEnum


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    # Relationships
    users = relationship("User", back_populates="role")
    permissions = relationship(
        "Permission", secondary="role_permissions", back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    roles = relationship(
        "Role", secondary="role_permissions", back_populates="permissions"
    )


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    phone_number = Column(String(20), unique=True)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255))
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    # Relationships
    role = relationship("Role", back_populates="users")
    management_profile = relationship(
        "ManagementProfile", back_populates="user", uselist=False
    )
    customer_profile = relationship(
        "CustomerProfile", back_populates="user", uselist=False
    )
    sessions = relationship("Session", back_populates="user")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.role_id"), primary_key=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("roles.role_id"), primary_key=True)
    permission_id = Column(
        Integer, ForeignKey("permissions.permission_id"), primary_key=True
    )
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    refresh_token = Column(Text, nullable=False)
    device_info = Column(Text, nullable=False)
    ip_address = Column(INET, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    revoked_token_id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(Text, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=False)


class FileAsset(Base):
    __tablename__ = "file_assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.user_id"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    size_bytes = Column(BigInteger)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)


class ManagementProfile(Base):
    __tablename__ = "management_profile"

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    profile_pic = Column(Integer, ForeignKey("file_assets.asset_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    user = relationship("User", back_populates="management_profile")
    profile_image = relationship("FileAsset")


class CustomerProfile(Base):
    __tablename__ = "customer_profile"

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    name = Column(String(255))
    address_id = Column(Integer, ForeignKey("addresses.address_id"))
    profile_pic = Column(Integer, ForeignKey("file_assets.asset_id"))
    blood_group = Column(String(3))
    gender = Column(String(1))
    dob = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    user = relationship("User", back_populates="customer_profile")
    address = relationship("Address")
    profile_image = relationship("FileAsset")


class Address(Base):
    __tablename__ = "addresses"

    address_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    house_no = Column(String(50), nullable=False)
    street_name = Column(String(255), nullable=False)
    locality = Column(String(255), nullable=False)
    city = Column(String(255), nullable=False)
    state = Column(String(255), nullable=False)
    pincode = Column(String(20), nullable=False)
    type_id = Column(Integer, ForeignKey("address_type.type_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    user = relationship("User")
    address_type = relationship("AddressType", back_populates="addresses")


class AddressType(Base):
    __tablename__ = "address_type"

    type_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(Integer)

    addresses = relationship("Address", back_populates="address_type")


class PasswordReset(Base):
    __tablename__ = "password_reset"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"))
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Review(Base):
    __tablename__ = "reviews"

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    medicine_id = Column(
        Integer, ForeignKey("medicines.medicine_id", onupdate="CASCADE"), nullable=False
    )
    rating = Column(Integer, nullable=False)
    review_text = Column(Text)
    status = Column(
        Enum(ReviewStatusEnum, name="review_status"),
        nullable=False,
        server_default=ReviewStatusEnum.visible.value,
    )
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(TIMESTAMP(timezone=True))
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    customer = relationship("User")
    medicine = relationship("Medicine")
