from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import NotificationType


class NotificationCreate(BaseModel):
    type: NotificationType
    user_id: int
    by_user_id: Optional[int]
    title: str = Field(...)
    message: str = Field(...)


class NotficationResponse(NotificationCreate):
    read_at: datetime
    is_deleted: bool
    notification_id: int
