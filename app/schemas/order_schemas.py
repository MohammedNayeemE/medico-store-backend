from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ==========================================================
# 🧾 ORDER ITEM SCHEMAS
# ==========================================================


class OrderItemCreate(BaseModel):
    """Schema for creating a single order item."""

    batch_id: int = Field(
        ...,
        description="Unique ID of the medicine batch being ordered.",
        examples=[101],
        ge=1,
    )
    quantity: int = Field(
        ...,
        description="Number of units being ordered for this batch.",
        examples=[5],
        ge=1,
        le=1000,
    )
    price: float = Field(
        ...,
        description="Per-unit price (in INR) for this medicine batch.",
        examples=[75.5],
        ge=0.01,
    )


class OrderItemUpdate(BaseModel):
    """Schema for updating an existing order item."""

    quantity: int = Field(
        ...,
        description="Updated quantity for the item.",
        examples=[10],
        ge=1,
        le=1000,
    )
    price: float = Field(
        ...,
        description="Updated per-unit price of the medicine batch (in INR).",
        examples=[70.0],
        ge=0.01,
    )


class OrderItemResponse(BaseModel):
    """Response schema for an order item."""

    order_item_id: int = Field(
        ...,
        description="Unique identifier for the order item.",
        examples=[5001],
        ge=1,
    )
    batch_id: int = Field(
        ...,
        description="ID of the batch associated with this order item.",
        examples=[101],
        ge=1,
    )
    quantity: int = Field(
        ...,
        description="Number of units ordered from this batch.",
        examples=[10],
        ge=1,
    )
    price: float = Field(
        ...,
        description="Per-unit price of the ordered medicine (in INR).",
        examples=[75.0],
        ge=0.01,
    )

    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# 🧾 ORDER SCHEMAS
# ==========================================================


class OrderCreate(BaseModel):
    """Schema for creating a new order."""

    customer_id: int = Field(
        ...,
        description="Unique ID of the customer placing the order.",
        examples=[2001],
        ge=1,
    )
    member_id: Optional[int] = Field(
        None,
        description="Optional ID of the family member associated with the order.",
        examples=[3002],
        ge=1,
    )
    prescription_id: Optional[int] = Field(
        None,
        description="Optional prescription ID linked to this order.",
        examples=[4001],
        ge=1,
    )
    total_amount: float = Field(
        ...,
        description="Total amount of the order (sum of all items + taxes - discounts).",
        examples=[840.0],
        ge=0.0,
    )
    items: List[OrderItemCreate] = Field(
        ...,
        description="List of items included in the order.",
        examples=[
            [
                {"batch_id": 101, "quantity": 2, "price": 75.5},
                {"batch_id": 102, "quantity": 1, "price": 150.0},
            ]
        ],
        min_length=1,
    )


class OrderResponse(BaseModel):
    """Response schema for an order, including order items."""

    customer_id: int = Field(
        ...,
        description="Unique ID of the customer who placed the order.",
        examples=[2001],
        ge=1,
    )
    member_id: Optional[int] = Field(
        None,
        description="Optional ID of the member associated with the order.",
        examples=[3002],
    )
    prescription_id: Optional[int] = Field(
        None,
        description="Optional prescription ID linked to this order.",
        examples=[4001],
    )
    total_amount: float = Field(
        ...,
        description="Final total amount for the order (in INR).",
        examples=[840.0],
        ge=0.0,
    )
    status: str = Field(
        ...,
        description="Current status of the order (e.g., pending, paid, shipped, delivered).",
        examples=["pending"],
        min_length=3,
        max_length=20,
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the order was created.",
        examples=["2025-11-08T19:30:00Z"],
    )
    order_items: List[OrderItemResponse] = Field(
        ...,
        description="List of items associated with this order.",
        examples=[
            [
                {
                    "order_item_id": 5001,
                    "batch_id": 101,
                    "quantity": 10,
                    "price": 75.0,
                }
            ]
        ],
    )

    model_config = ConfigDict(from_attributes=True)
