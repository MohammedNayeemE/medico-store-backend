from datetime import datetime
from typing import List

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.exceptions import (
    BadRequestException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.enums import ReviewStatusEnum
from app.models.inventory_management_models import Medicine
from app.models.user_management_models import Review
from app.schemas.review_schemas import ReviewCreate, ReviewResponse


class ReviewService:
    """
    Service class for managing medicine reviews.
    
    Handles review creation, retrieval, and status updates for medicines.
    """
    def __init__(self) -> None:
        pass

    async def ADD_REVIEW(
        self,
        db: AsyncSession,
        user_id: int,
        role_id: int,
        medicine_id: int,
        review_data: ReviewCreate,
    ):
        """
        Add a review for a medicine (customers only).
        
        Args:
            db: Database session
            user_id: Customer user ID
            role_id: User role ID (must be customer)
            medicine_id: Medicine ID to review
            review_data: Review data (rating, comment)
        
        Returns:
            Created review object
        
        Raises:
            HTTPException (403): If user is not a customer
            NotFoundException: If medicine not found
        """
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
            medicine_q = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == medicine_id,
                    Medicine.is_deleted == False,
                )
            )
            medicine = medicine_q.scalar_one_or_none()
            if not medicine:
                raise NotFoundException("Medicine not found")
            existing_review_q = await db.execute(
                select(Review).filter(
                    Review.medicine_id == medicine_id,
                    Review.customer_id == user_id,
                    Review.is_deleted == False,
                )
            )
            existing_review = existing_review_q.scalar_one_or_none()
            if existing_review:
                raise BadRequestException("User has already reviewed this medicine")
            new_review = Review(
                customer_id=user_id,
                medicine_id=medicine_id,
                rating=review_data.rating,
                review_text=review_data.review_text,
                status=ReviewStatusEnum.visible,
                created_at=datetime.utcnow(),
            )
            db.add(new_review)
            await db.commit()
            await db.refresh(new_review)
            return new_review
        except (NotFoundException, BadRequestException):
            raise
        except Exception as e:
            print("==========================")
            print(f"[ADD_REVIEW] : {e}")
            raise InternalServerErrorException("internal server error : [ADD_REVIEW]")

    # -----------------------------------------------------------
    # GET ALL REVIEWS (public)
    # -----------------------------------------------------------
    async def GET_ALL_REVIEWS(self, db: AsyncSession):
        try:
            query = await db.execute(
                select(Review).filter(
                    Review.is_deleted == False,
                    Review.status == ReviewStatusEnum.visible,
                )
            )
            reviews = query.scalars().all()
            return reviews
        except Exception as e:
            print("==========================")
            print(f"[GET_ALL_REVIEWS] : {e}")
            raise InternalServerErrorException(
                "internal server error : [GET_ALL_REVIEWS]"
            )

    # -----------------------------------------------------------
    # GET REVIEWS FOR A SPECIFIC MEDICINE
    # -----------------------------------------------------------
    async def GET_REVIEWS_FOR_MEDICINE(self, db: AsyncSession, medicine_id: int):
        try:
            medicine_q = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == medicine_id,
                    Medicine.is_deleted == False,
                )
            )
            medicine = medicine_q.scalar_one_or_none()
            if not medicine:
                raise NotFoundException("Medicine not found")
            reviews_q = await db.execute(
                select(Review).filter(
                    Review.medicine_id == medicine_id,
                    Review.is_deleted == False,
                    Review.status == ReviewStatusEnum.visible,
                )
            )
            reviews = reviews_q.scalars().all()
            return reviews
        except NotFoundException:
            raise
        except Exception as e:
            print("==========================")
            print(f"[GET_REVIEWS_FOR_MEDICINE] : {e}")
            raise InternalServerErrorException(
                "internal server error : [GET_REVIEWS_FOR_MEDICINE]"
            )

    # -----------------------------------------------------------
    # GET REVIEW BY ID
    # -----------------------------------------------------------
    async def GET_REVIEW_BY_ID(self, db: AsyncSession, review_id: int):
        try:
            review_q = await db.execute(
                select(Review).filter(
                    Review.review_id == review_id,
                    Review.is_deleted == False,
                )
            )
            review = review_q.scalar_one_or_none()
            if not review:
                raise NotFoundException("Review not found")
            return review
        except NotFoundException:
            raise
        except Exception as e:
            print("==========================")
            print(f"[GET_REVIEW_BY_ID] : {e}")
            raise InternalServerErrorException(
                "internal server error : [GET_REVIEW_BY_ID]"
            )

    async def GET_REVIEWS_BY_USER(self, db: AsyncSession, user_id: int, role_id: int):
        try:
            if role_id != 1:
                raise HTTPException(status_code=404, detail="Forbidden Access")
            reviews_q = await db.execute(
                select(Review).filter(
                    Review.customer_id == user_id,
                    Review.is_deleted == False,
                )
            )
            reviews = reviews_q.scalars().all()
            if not reviews:
                raise NotFoundException("No reviews found for user")
            return reviews
        except NotFoundException:
            raise
        except Exception as e:
            print("==========================")
            print(f"[GET_REVIEWS_BY_USER] : {e}")
            raise InternalServerErrorException(
                "internal server error : [GET_REVIEWS_BY_USER]"
            )

    # -----------------------------------------------------------
    # DELETE REVIEW (ADMIN ONLY)
    # -----------------------------------------------------------
    async def DELETE_REVIEW(
        self, db: AsyncSession, review_id: int, deleted_by: int, role_id: int
    ):
        try:
            if role_id == 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
            review_q = await db.execute(
                select(Review).filter(
                    Review.review_id == review_id,
                    Review.is_deleted == False,
                )
            )
            review = review_q.scalar_one_or_none()
            if not review:
                raise NotFoundException("Review not found")

            review.is_deleted = True
            review.deleted_at = datetime.utcnow()
            review.deleted_by = deleted_by
            review.status = ReviewStatusEnum.deleted
            await db.commit()
            return {"message": "Review deleted successfully", "review_id": review_id}
        except NotFoundException:
            raise
        except Exception as e:
            print("==========================")
            print(f"[DELETE_REVIEW] : {e}")
            raise InternalServerErrorException(
                "internal server error : [DELETE_REVIEW]"
            )
