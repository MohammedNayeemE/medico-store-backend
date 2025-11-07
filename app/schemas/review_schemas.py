from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatusEnum


class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating between 1 to 5")
    review_text: Optional[str] = Field(None, description="Optional text review")


class ReviewCreate(ReviewBase):
    """
    Used when adding a new review for a medicine.
    """

    pass


class ReviewResponse(BaseModel):
    review_id: int
    customer_id: int
    medicine_id: int
    rating: int
    review_text: Optional[str]
    status: ReviewStatusEnum
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
