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
