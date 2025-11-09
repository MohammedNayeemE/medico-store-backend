from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    actor_id: Optional[int] = Field(
        None, description="ID of the user who performed the action"
    )
    actor_role: Optional[str] = Field(
        None, description="Role of the user (admin/customer/etc)"
    )
    action: str = Field(
        ..., description="Action performed, e.g., CREATE_ORDER, DELETE_USER"
    )
    resource: str = Field(
        ..., description="Name of the affected resource, e.g., 'orders'"
    )
    resource_id: Optional[Any] = Field(
        None, description="ID or identifier of the resource"
    )
    old_data: Optional[dict] = Field(None, description="Data before update/delete")
    new_data: Optional[dict] = Field(None, description="Data after create/update")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = Field(None, description="IP address of actor")
    user_agent: Optional[str] = Field(None, description="User-Agent header of actor")
    status: str = Field(
        default="SUCCESS", description="Status of action (SUCCESS, FAILURE, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "actor_id": 42,
                "actor_role": "admin",
                "action": "UPDATE_ORDER_STATUS",
                "resource": "orders",
                "resource_id": 1234,
                "old_data": {"status": "pending"},
                "new_data": {"status": "shipped"},
                "ip_address": "192.168.0.1",
                "user_agent": "Mozilla/5.0",
                "status": "SUCCESS",
            }
        }
