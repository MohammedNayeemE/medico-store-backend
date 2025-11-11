from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, confloat, conint, constr

from app.models.enums import RequestOrderStatusEnum

# ============================================================
# 🧱 Base Schemas
# ============================================================


class RequestOrderItemCreate(BaseModel):
    """Schema for creating a new item in a request order."""

    medicine_id: conint(gt=0) = Field(
        ..., example=101, description="Unique ID of the medicine being requested"
    )
    quantity: conint(gt=0, le=30) = Field(
        ..., example=2, description="Quantity of medicine units requested"
    )


class RequestOrderItemResponse(RequestOrderItemCreate):
    """Returned when fetching request order details."""

    request_order_item_id: int = Field(
        ..., example=501, description="Unique ID of the request order item"
    )
    is_deleted: bool = Field(
        False, example=False, description="Indicates if this item was deleted"
    )
    deleted_at: Optional[datetime] = Field(
        None, example="2025-11-08T12:30:00Z", description="Timestamp when deleted"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 🧱 Main Request Order Schemas
# ============================================================


class RequestOrderCreate(BaseModel):
    """Used when a customer creates a new request order."""

    prescription_id: Optional[conint(gt=0)] = Field(
        None, example=3001, description="Linked prescription ID if applicable"
    )
    remarks: Optional[constr(min_length=3, max_length=255)] = Field(
        None,
        example="Please deliver before 5 PM",
        description="Customer remarks or notes",
    )

    items: List[RequestOrderItemCreate] = Field(
        ...,
        min_length=1,
        example=[{"medicine_id": 101, "quantity": 2}],
        description="List of requested items",
    )

    member_id: Optional[conint(gt=0)] = Field(
        None, example=42, description="Family member ID if order is for another member"
    )


class RequestOrderApprove(BaseModel):
    """Used when admin approves a request order."""

    remarks: Optional[constr(min_length=3, max_length=255)] = Field(
        None,
        example="Approved after verifying prescription",
        description="Approval remarks or comments",
    )


class RequestOrderReject(BaseModel):
    """Used when admin rejects a request order."""

    reason: constr(min_length=5, max_length=255) = Field(
        ...,
        example="Prescription is expired",
        description="Reason for rejecting the request order",
    )


# ============================================================
# 🧱 Response Schemas
# ============================================================


class RequestOrderResponse(RequestOrderCreate):
    """Detailed response schema for a request order."""

    request_order_id: int = Field(
        ..., example=1001, description="Unique ID of the request order"
    )
    customer_id: int = Field(
        ..., example=15, description="ID of the customer who created the request order"
    )
    status: RequestOrderStatusEnum = Field(
        ...,
        example="awaiting_approval",
        description="Current status of the request order",
    )

    created_at: datetime = Field(
        ...,
        example="2025-11-08T10:15:00Z",
        description="Timestamp when order was created",
    )
    updated_at: Optional[datetime] = Field(
        None,
        example="2025-11-08T11:45:00Z",
        description="Timestamp when order was last updated",
    )

    is_deleted: bool = Field(
        False, example=False, description="Indicates if this order was soft deleted"
    )
    deleted_at: Optional[datetime] = Field(
        None,
        example="2025-11-09T09:00:00Z",
        description="Timestamp when deleted (if applicable)",
    )

    model_config = ConfigDict(from_attributes=True)


class RequestOrderListResponse(BaseModel):
    """Paginated list of request orders."""

    total: conint(ge=0) = Field(
        ..., example=125, description="Total number of request orders found"
    )
    request_orders: List[RequestOrderResponse] = Field(
        ..., description="List of paginated request orders"
    )


# ============================================================
# 🧱 Item Update Schema (Admin Operations)
# ============================================================


class RequestOrderItemUpdate(BaseModel):
    """Used by admin to add, update, or remove items in a request order."""

    medicine_id: conint(gt=0) = Field(
        ..., example=101, description="ID of the medicine to add or update"
    )
    quantity: Optional[conint(gt=0, le=1000)] = Field(
        None, example=3, description="Updated quantity (omit if removing)"
    )
    estimated_price: Optional[confloat(gt=0, le=100000)] = Field(
        None, example=250.50, description="Updated estimated price for the medicine"
    )
    action: constr(pattern="^(add|update|remove)$") = Field(
        ...,
        example="update",
        description="Action to perform: add, update, or remove the item",
    )
