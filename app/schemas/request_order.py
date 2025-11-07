from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestOrderStatusEnum

# ============================================================
# 🧱 Base Schemas
# ============================================================


class RequestOrderItemCreate(BaseModel):
    medicine_id: int = Field(..., description="ID of the medicine requested")
    quantity: int = Field(..., ge=1, description="Quantity requested for the medicine")


class RequestOrderItemResponse(RequestOrderItemCreate):
    """Returned when fetching request order details."""

    request_order_item_id: int
    is_deleted: bool
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 🧱 Main Request Order Schemas
# ============================================================


class RequestOrderCreate(BaseModel):
    """Used when a customer creates a new request order."""

    prescription_id: Optional[int] = Field(
        None, description="Linked prescription if applicable"
    )
    remarks: Optional[str] = Field(None, description="Customer remarks or notes")

    items: List[RequestOrderItemCreate] = Field(
        ..., min_length=1, description="List of requested items"
    )
    member_id: Optional[int] = Field(None, description="member id")


class RequestOrderApprove(BaseModel):
    """Used when admin approves a request order."""

    remarks: Optional[str] = Field(None, description="Approval remarks or notes")
    updated_estimated_total: Optional[float] = Field(
        None, description="Updated total price after approval"
    )


class RequestOrderReject(BaseModel):
    """Used when admin rejects a request order."""

    reason: str = Field(
        ..., min_length=5, description="Reason for rejecting the request order"
    )


# ============================================================
# 🧱 Response Schemas
# ============================================================


class RequestOrderResponse(RequestOrderCreate):
    request_order_id: int
    customer_id: int
    status: RequestOrderStatusEnum
    created_at: datetime
    updated_at: Optional[datetime]
    is_deleted: bool
    deleted_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


class RequestOrderListResponse(BaseModel):
    """Paginated list of request orders"""

    total: int
    request_orders: List[RequestOrderResponse]


class RequestOrderItemUpdate(BaseModel):
    """Used by admin to add, remove, or update items in a request order."""

    medicine_id: int = Field(..., description="ID of the medicine to update or add")
    quantity: Optional[int] = Field(
        None, description="Updated quantity (None if removing)"
    )
    estimated_price: Optional[float] = Field(
        None, description="Updated estimated price"
    )
    action: str = Field(
        ...,
        pattern="^(add|update|remove)$",
        description="Action to perform: add, update, or remove the medicine item",
    )
