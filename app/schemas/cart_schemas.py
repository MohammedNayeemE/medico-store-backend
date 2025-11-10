from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# =============================================================
# 1️⃣ CART ITEM SCHEMAS
# =============================================================


class CartItemCreate(BaseModel):
    medicine_id: int = Field(..., description="ID of the medicine")
    quantity: int = Field(..., gt=0, description="Quantity of the medicine in the cart")


class CartItemUpdate(CartItemCreate):
    quantity: int = Field(..., gt=0, description="Updated quantity for the cart item")


class CartItemResponse(CartItemCreate):
    cart_item_id: int
    added_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================
# 2️⃣ CART SCHEMAS
# =============================================================


class CartBase(BaseModel):
    customer_id: int


class CartResponse(CartBase):
    cart_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    cart_items: List[CartItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class DiscountedCartItem(BaseModel):
    medicine_id: int = Field(..., description="ID of the medicine")
    medicine_name: str = Field(..., description="Name of the medicine")
    quantity: int = Field(..., ge=1, description="Quantity of this medicine in cart")
    unit_price: float = Field(..., description="Unit selling price of the medicine")
    original_price: float = Field(..., description="Price before applying discount")
    discount_applied: float = Field(..., description="Discount amount applied")
    final_price: float = Field(..., description="Price after discount")

    model_config = ConfigDict(from_attributes=True)


class CartWithDiscountResponse(BaseModel):
    cart_id: int = Field(..., description="Unique cart identifier")
    items: List[DiscountedCartItem] = Field(
        ..., description="List of discounted items in cart"
    )
    total_amount: float = Field(
        ..., description="Total payable amount after all discounts"
    )

    class Config:
        from_attributes = True
