from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

# -------------------
# ORDER ITEM SCHEMAS
# -------------------


class OrderItemCreate(BaseModel):
    batch_id: int
    quantity: int
    price: float


class OrderItemUpdate(BaseModel):
    quantity: int
    price: int


class OrderItemResponse(BaseModel):
    order_item_id: int
    batch_id: int
    quantity: int
    price: float

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    customer_id: int
    member_id: Optional[int] = None
    prescription_id: Optional[int] = None
    total_amount: float
    items: List[OrderItemCreate]


class OrderResponse(OrderItemCreate):
    status: str
    created_at: datetime
    order_items: List[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)
