from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas import discount_schemas
from app.schemas.discount_schemas import (
    CouponCreate,
    DiscountCreate,
    DiscountParamterCreate,
    DiscountTypeCreate,
    DiscountTypeUpdate,
    DiscountUpdate,
)
from app.services.discount_service import DiscountService

router = APIRouter(prefix="/discounts", tags=["Discounts"])
discount_manager = DiscountService()

# ================== DISCOUNT TYPES ===================== #


@router.get(
    "/discount_types/",
    description="List all available discount types (e.g., percentage, flat)",
)
async def list_discount_types(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await discount_manager.LIST_DISCOUNT_TYPE(db=db, skip=skip, limit=limit)
    return result


@router.post("/discount_types/", description="Create a new discount type")
async def create_discount_type(
    discount_type: DiscountTypeCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.CREATE_DISCOUNT_TYPE(
        db=db, discount_type_data=discount_type
    )
    return result


@router.put("/discount_types/{id}", description="Update an existing discount type")
async def update_discount_type(
    id: int = Path(...),
    discount_type: DiscountTypeUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.UPDATE_DISCOUNT_TYPE(
        db=db, discount_type_data=discount_type, id=id
    )
    return result


@router.delete("/discount_types/{id}", description="Soft delete a discount type")
async def soft_delete_discount_type(
    id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.SOFT_DELETE_DISCOUNT_TYPE(
        db=db, user_id=current_user.user_id, discount_type_id=id
    )
    return result


# ================== DISCOUNTS ===================== #


@router.get("/", description="List all discounts (active/inactive)")
async def list_discounts(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await discount_manager.LIST_ALL_DISCOUNTS(
        db=db, skip=skip, limit=limit, is_active=is_active
    )
    return result


@router.post("/", description="Create a new discount")
async def create_discount(
    discount_data: DiscountCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.CREATE_DISCOUNT(db=db, discount_data=discount_data)
    return result


@router.get("/{discount_id}", description="Get a discount's details")
async def get_discount_details(
    discount_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await discount_manager.GET_DISCOUNT_DETAILS(db=db, discount_id=discount_id)
    return result


@router.put("/{discount_id}", description="Update discount information")
async def update_discount(
    discount_id: int = Path(...),
    discount: DiscountUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.UPDATE_DISCOUNT(
        db=db,
        discount_id=discount_id,
        discount_data=discount,
        user_id=current_user.user_id,
    )
    return result


@router.delete("/{discount_id}", description="Soft delete a discount")
async def soft_delete_discount(
    discount_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.SOFT_DELETE_DISCOUNT(
        db=db, discount_id=discount_id, user_id=current_user.user_id
    )
    return result


# ========== DISCOUNT PARAMETERS / APPLICABILITY ========== #


@router.get(
    "/{discount_id}/parameters", description="Get parameters for a specific discount"
)
async def get_discount_parameters(
    discount_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await discount_manager.GET_DISCOUNT_DETAILS(db=db, discount_id=discount_id)
    return result


@router.post("/{discount_id}/parameters", description="Add new parameter to a discount")
async def add_discount_parameter(
    discount_id: int = Path(...),
    parameter_data: DiscountParamterCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.ADD_PARAMETER(
        db=db, discount_id=discount_id, parameter_data=parameter_data
    )
    return result


@router.delete(
    "/discount_parameters/{parameter_id}",
    description="Delete a discount parameter by ID",
)
async def delete_discount_parameter(
    parameter_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.DELETE_PARAMETER(
        db=db, parameter_id=parameter_id, user_id=current_user.user_id
    )
    return result


@router.put(
    "/discount_parameters/{parameter_id}",
    description="Update an existing discount parameter",
)
async def update_dicount_paramter(
    parameter_id: int = Path(...),
    parameter_data: DiscountParamterCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.UPDATE_PARAMETER(
        db=db,
        parameter_id=parameter_id,
        data=parameter_data,
    )
    return result


# ================== DISCOUNT ASSOCIATIONS ===================== #


@router.post("/{discount_id}/medicines", description="Assign discount to medicines")
async def assign_discount_medicines(
    discount_id: int = Path(...),
    medicine_ids: List[int] = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.ASSIGN_DISCOUNT_MEDICINES(
        db=db, discount_id=discount_id, medicine_ids=medicine_ids
    )
    return result


@router.post("/{discount_id}/categories", description="Assign discount to categories")
async def assign_discount_categories(
    discount_id: int = Path(...),
    category_ids: List[int] = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.ASSIGN_DISCOUNT_CATEGORIES(
        db=db, discount_id=discount_id, category_ids=category_ids
    )
    return result


@router.delete(
    "/discount_medicines/{discount_id}/{medicine_id}",
    description="Remove discount from a medicine",
)
async def remove_discount_medicine(
    discount_id: int = Path(...),
    medicine_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.REMOVE_DISCOUNT_MEDICINE(
        db=db,
        discount_id=discount_id,
        medicine_id=medicine_id,
        deleted_by=current_user.user_id,
    )
    return result


@router.delete(
    "/discount_categories/{discount_id}/{category_id}",
    description="Remove discount from a category",
)
async def remove_discount_category(
    discount_id: int = Path(...),
    category_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.REMOVE_DISCOUNT_CATEGORY(
        db=db,
        discount_id=discount_id,
        category_id=category_id,
        deleted_by=current_user.user_id,
    )
    return result


# ================== COUPONS ===================== #


@router.post("/coupons/", description="Create a new coupon")
async def create_coupon(
    coupon: CouponCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.CREATE_COUPON(db=db, data=coupon)
    return result


@router.get(
    "/coupons/validate/{code}", description="Validate a coupon (expiry, usage limit)"
)
async def validate_coupon(
    code: str = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    result = await discount_manager.VALIDATE_COUPON(db=db, code=code)
    return result


@router.put("/coupons/{coupon_id}/usage", description="Increment coupon used count")
async def increment_coupon_usage(
    coupon_id: int = Path(...),
    delta: int = Body(..., ge=1),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    result = await discount_manager.INCREMENT_COUPON_USAGE(
        db=db, coupon_id=coupon_id, delta=delta
    )
    return result


@router.get("/coupons/{coupon_id}", description="Get coupon details by ID")
async def get_coupon_details(
    coupon_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    result = await discount_manager.GET_COUPON_DETAILS(db=db, coupon_id=coupon_id)
    return result


@router.delete("/coupons/{coupon_id}", description="Soft delete a coupon")
async def soft_delete_coupon(
    coupon_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await discount_manager.SOFT_DELETE_COUPON(
        db=db, coupon_id=coupon_id, deleted_by=current_user.user_id
    )
    return result
