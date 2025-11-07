from typing import List

from fastapi import APIRouter, Body, Depends, Path, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.review_schemas import ReviewCreate, ReviewResponse
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])
review_manager = ReviewService()


@router.get(
    "/",
)
async def get_reviews(
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.GET_ALL_REVIEWS(db=db)
    return result


@router.get(
    "/medicine/{medicine_id}",
)
async def get_reviews_for_medicine(
    medicine_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.GET_REVIEWS_FOR_MEDICINE(
        db=db, medicine_id=medicine_id
    )
    return result


# -----------------------------------------------------------
@router.get(
    "/{review_id}",
)
async def get_reviews_by_id(
    review_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.GET_REVIEW_BY_ID(db=db, review_id=review_id)
    return result


# -----------------------------------------------------------
# Get reviews of logged-in user
# -----------------------------------------------------------
@router.get(
    "/my",
)
async def my_reviews(
    current_user: User = Security(get_current_user, scopes=["user:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.GET_REVIEWS_BY_USER(
        db=db, user_id=current_user.user_id
    )
    return result


@router.get(
    "/admin/user/{customer_id}",
)
async def get_reviews_by_user_id(
    customer_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.GET_REVIEWS_BY_USER(db=db, user_id=customer_id)
    return result


# -----------------------------------------------------------
@router.delete("/admin/{review_id}")
async def delete_review(
    review_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.DELETE_REVIEW(
        db=db, review_id=review_id, deleted_by=current_user.user_id
    )
    return result


# -----------------------------------------------------------
# Add a new review for a medicine
# -----------------------------------------------------------
@router.post(
    "/medicine/{medicine_id}",
)
async def add_review(
    medicine_id: int = Path(...),
    review_data: ReviewCreate = Body(...),
    current_user: User = Security(get_current_user, scopes=["user:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await review_manager.ADD_REVIEW(
        db=db,
        user_id=current_user.user_id,
        medicine_id=medicine_id,
        review_data=review_data,
    )
    return result
