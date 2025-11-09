from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatusEnum

# ============================================================
# ⭐ BASE SCHEMA
# ============================================================


class ReviewBase(BaseModel):
    """Base schema for reviews, shared by create and response models."""

    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Numerical rating between 1 (worst) and 5 (best).",
        examples=[5],
    )
    review_text: Optional[str] = Field(
        None,
        description="Optional written feedback about the medicine.",
        min_length=3,
        max_length=500,
        examples=["Worked great for my headache!"],
    )


# ============================================================
# ✍️ CREATE SCHEMA
# ============================================================


class ReviewCreate(ReviewBase):
    """
    Used when a customer adds a new review for a specific medicine.
    """

    customer_id: int = Field(
        ...,
        description="Unique ID of the customer submitting the review.",
        examples=[101],
        ge=1,
    )
    medicine_id: int = Field(
        ...,
        description="Unique ID of the medicine being reviewed.",
        examples=[205],
        ge=1,
    )

    # Optional field: if the review requires moderation or context
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the review was created (auto-set).",
        examples=["2025-11-08T14:35:00Z"],
    )


# ============================================================
# 📦 RESPONSE SCHEMA
# ============================================================


class ReviewResponse(BaseModel):
    """Response model for returning review details."""

    review_id: int = Field(
        ...,
        description="Unique ID of the review record.",
        examples=[5001],
        ge=1,
    )
    customer_id: int = Field(
        ...,
        description="ID of the customer who submitted the review.",
        examples=[101],
        ge=1,
    )
    medicine_id: int = Field(
        ...,
        description="ID of the medicine being reviewed.",
        examples=[205],
        ge=1,
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Star rating between 1 and 5.",
        examples=[4],
    )
    review_text: Optional[str] = Field(
        None,
        description="Customer's feedback text, if provided.",
        examples=["Mild side effects, but effective overall."],
    )
    status: ReviewStatusEnum = Field(
        ...,
        description="Moderation status of the review (e.g., pending, approved, rejected).",
        examples=[ReviewStatusEnum.visible],
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the review was created.",
        examples=["2025-11-08T14:35:00Z"],
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the last update to the review (if edited).",
        examples=["2025-11-09T09:00:00Z"],
    )

    model_config = ConfigDict(from_attributes=True)
