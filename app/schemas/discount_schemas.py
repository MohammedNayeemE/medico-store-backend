from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==============================================================
# 🏷️ DISCOUNT TYPE SCHEMAS
# ==============================================================


class DiscountTypeCreate(BaseModel):
    """Schema for creating a new discount type (e.g., percentage or flat)."""

    type_name: str = Field(
        ...,
        description="Type of discount — either 'Percentage' or 'Flat'.",
        examples=["Percentage"],
        min_length=3,
        max_length=50,
    )
    description: Optional[str] = Field(
        None,
        description="Detailed explanation of the discount type.",
        examples=["Discount based on percentage value (e.g., 10%)"],
        max_length=255,
    )


class DiscountTypeUpdate(DiscountTypeCreate):
    """Schema for updating an existing discount type."""

    pass


class DiscountTypeResponse(DiscountTypeCreate):
    """Response schema for a discount type record."""

    discount_type_id: int = Field(
        ..., description="Unique ID of the discount type.", examples=[1], ge=1
    )
    is_deleted: bool = Field(
        ...,
        description="Flag indicating if this discount type is soft-deleted.",
        examples=[False],
    )
    deleted_at: Optional[datetime] = Field(
        None, description="Timestamp when this discount type was deleted."
    )
    deleted_by: Optional[int] = Field(
        None, description="User ID who deleted this discount type.", ge=1
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================
# 💸 DISCOUNT SCHEMAS
# ==============================================================


class DiscountCreate(BaseModel):
    """Schema for creating a discount configuration."""

    name: str = Field(
        ...,
        description="Name of the discount campaign.",
        examples=["Summer Sale"],
        min_length=3,
        max_length=100,
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of the discount offer.",
        examples=["Flat 10% off on all medicines above ₹100 purchase."],
        max_length=255,
    )
    discount_type_id: int = Field(
        ...,
        description="ID of the discount type (e.g., Percentage or Flat).",
        examples=[1],
        ge=1,
    )
    value: float = Field(
        ...,
        description="Value of the discount (e.g., 10 for 10%).",
        examples=[10.0],
        ge=0.01,
    )
    start_date: datetime = Field(
        ...,
        description="Start date and time for the discount validity.",
        examples=["2025-06-01T00:00:00Z"],
    )
    end_date: datetime = Field(
        ...,
        description="End date and time for the discount validity.",
        examples=["2025-06-30T23:59:59Z"],
    )
    min_purchase_amount: float = Field(
        100.0,
        description="Minimum order amount required for the discount to apply.",
        examples=[100.0],
        ge=0.0,
    )
    max_discount_amount: Optional[float] = Field(
        None,
        description="Maximum discount that can be applied per order.",
        examples=[500.0],
        ge=0.0,
    )
    usage_limit: Optional[int] = Field(
        None,
        description="Maximum number of times this discount can be used across all users.",
        examples=[100],
        ge=1,
    )
    category_ids: Optional[List[int]] = Field(
        default_factory=list,
        description="List of category IDs where this discount is applicable.",
        examples=[[1, 2, 3]],
    )
    medicine_ids: Optional[List[int]] = Field(
        default_factory=list,
        description="List of medicine IDs where this discount is applicable.",
        examples=[[10, 11, 12]],
    )
    parameters: Optional[List[dict]] = Field(
        default_factory=list,
        description="Additional key-value parameters for dynamic discount logic.",
        examples=[[{"param_key": "max_items", "param_value": "3"}]],
    )

    # --------------------------
    # Validation logic
    # --------------------------

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date: datetime, info):
        start_date = info.data.get("start_date")
        if start_date and end_date <= start_date:
            raise ValueError("end_date must be after start_date.")
        return end_date

    @field_validator("value")
    @classmethod
    def validate_value(cls, value):
        if value <= 0:
            raise ValueError("Discount value must be greater than 0.")
        return value


class DiscountUpdate(DiscountCreate):
    """Schema for updating an existing discount."""

    pass


class DiscountResponse(DiscountCreate):
    """Response schema for a discount record."""

    discount_id: int = Field(
        ..., description="Unique ID of the discount.", examples=[101], ge=1
    )
    is_deleted: bool = Field(
        ...,
        description="Flag indicating whether the discount is soft-deleted.",
        examples=[False],
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================
# ⚙️ DISCOUNT PARAMETER SCHEMAS
# ==============================================================


class DiscountParameterCreate(BaseModel):
    """Schema for adding a dynamic parameter to a discount."""

    param_key: str = Field(
        ...,
        description="Parameter key name.",
        examples=["max_items"],
        min_length=1,
        max_length=50,
    )
    param_value: str = Field(
        ...,
        description="Parameter value.",
        examples=["3"],
        min_length=1,
        max_length=100,
    )


class DiscountParameterResponse(DiscountParameterCreate):
    """Response schema for discount parameters."""

    parameter_id: int = Field(
        ..., description="Unique ID of the discount parameter.", examples=[1001], ge=1
    )
    discount_id: int = Field(
        ..., description="Associated discount ID.", examples=[101], ge=1
    )
    is_deleted: bool = Field(
        ..., description="Whether the parameter is soft-deleted.", examples=[False]
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================
# 🎟️ COUPON SCHEMAS
# ==============================================================


class CouponCreate(BaseModel):
    """Schema for creating a coupon linked to a discount."""

    code: str = Field(
        ...,
        description="Unique alphanumeric coupon code (e.g., SAVE10).",
        examples=["SAVE10"],
        min_length=3,
        max_length=30,
    )
    discount_id: int = Field(
        ..., description="ID of the associated discount.", examples=[101], ge=1
    )
    max_usage: int = Field(
        ...,
        description="Maximum number of times this coupon can be used.",
        examples=[500],
        ge=1,
    )
    valid_from: datetime = Field(
        ...,
        description="Start timestamp for coupon validity.",
        examples=["2025-06-01T00:00:00Z"],
    )
    valid_to: datetime = Field(
        ...,
        description="End timestamp for coupon validity.",
        examples=["2025-06-30T23:59:59Z"],
    )

    @field_validator("valid_to")
    @classmethod
    def validate_validity(cls, valid_to: datetime, info):
        valid_from = info.data.get("valid_from")
        if valid_from and valid_to <= valid_from:
            raise ValueError("valid_to must be after valid_from.")
        return valid_to


class CouponResponse(CouponCreate):
    """Response schema for coupons."""

    coupon_id: int = Field(..., description="Unique coupon ID.", examples=[501], ge=1)
    used_count: int = Field(
        ...,
        description="How many times this coupon has been used.",
        examples=[10],
        ge=0,
    )
    is_deleted: bool = Field(
        ..., description="Whether the coupon is soft-deleted.", examples=[False]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the coupon was created.",
        examples=["2025-05-01T10:00:00Z"],
    )
    deleted_at: Optional[datetime] = Field(
        None, description="Timestamp when the coupon was deleted, if applicable."
    )
    deleted_by: Optional[int] = Field(
        None, description="User ID who deleted the coupon, if applicable.", ge=1
    )

    model_config = ConfigDict(from_attributes=True)
