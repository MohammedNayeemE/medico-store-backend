from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscountTypeCreate(BaseModel):
    type_name: str = Field(..., example="Percentage")
    description: str = Field(..., example="Discount based on percentage")


class DiscountTypeUpdate(DiscountTypeCreate):
    pass


class DiscountTypeResponse(DiscountTypeCreate):
    discount_type_id: int
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class DiscountCreate(BaseModel):
    name: str = Field(..., example="Summer Sale")
    description: str = Field(None, example="Flat 10% off on all medicines")
    discount_type_id: int = Field(..., example=1)
    value: float = Field(..., example=10.000)
    start_date: datetime = Field(..., example="2025-06-01T00:00:00Z")
    end_date: datetime = Field(..., example="2025-06-30T23:59:59Z")
    min_purchase_amount: int = Field(100)
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    category_ids: Optional[List[int]] = []
    medicine_ids: Optional[List[int]] = []
    parameters: Optional[List[dict]] = []

    # outdated function needs to be changed
    @field_validator("end_date")
    def validate_dates(cls, end_date, values):
        if "start_date" in values and end_date <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return end_date


class DiscountUpdate(DiscountCreate):
    pass


class DiscountResponse(DiscountCreate):
    discount_id: int
    is_deleted: bool
    model_config = ConfigDict(from_attributes=True)


class DiscountParamterCreate(BaseModel):
    param_key: str = Field(...)
    param_value: str = Field(...)


class DiscountParameterResponse(DiscountParamterCreate):
    paramter_id: int
    discount_id: int
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


class CouponCreate(BaseModel):
    code: str = Field(..., description="Unique coupon code")
    discount_id: int = Field(..., description="Associated discount ID")
    max_usage: int = Field(..., description="Maximum times this coupon can be used")
    valid_from: datetime = Field(..., description="Start validity timestamp")
    valid_to: datetime = Field(..., description="End validity timestamp")


class CouponResponse(CouponCreate):
    coupon_id: int
    used_count: int
    is_deleted: bool
    created_at: datetime
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)
