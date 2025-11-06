from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IssueStatusEnum


class IssueCategoryCreate(BaseModel):
    name: str = Field(..., example="Delivery Issue")
    description: str = Field(..., example="Problems related to order delivery.")


class IssueCategoryUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]


class IssueCategoryResponse(IssueCategoryCreate):
    category_id: int
    is_deleted: bool
    deleted_at: Optional[datetime]
    deleted_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class IssueCreate(BaseModel):
    request_order_id: Optional[int] = Field(None, description="Associated order ID")
    category_id: int = Field(..., description="Category of issue")
    description: str = Field(..., example="The package arrived damaged.")


class IssueResponse(IssueCreate):
    issue_id: int
    customer_id: int
    request_order_id: Optional[int]
    category_id: int
    description: str
    status: IssueStatusEnum
    assigned_to: Optional[int]
    opened_at: datetime
    closed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class IssueStatusUpdate(BaseModel):
    status: IssueStatusEnum = Field(..., example="resolved")


class IssueAssign(BaseModel):
    assigned_to: int = Field(
        ..., description="User ID of support staff assigned to handle issue"
    )


class IssueMessageCreate(BaseModel):
    message: str = Field(
        ..., example="Can you please share the expected delivery date?"
    )
    message_type: str = Field("text", example="text")


class IssueMessageResponse(IssueMessageCreate):
    message_id: int
    issue_id: int
    sender_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueAttachmentBase(BaseModel):
    file_name: str
    file_url: str
    file_type: Optional[str]


class IssueAttachmentResponse(IssueAttachmentBase):
    attachment_id: int
    message_id: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueWithMessages(IssueResponse):

    messages: List[IssueMessageResponse] = []


class IssueMessageWithAttachments(IssueMessageResponse):
    attachments: List[IssueAttachmentResponse] = []
