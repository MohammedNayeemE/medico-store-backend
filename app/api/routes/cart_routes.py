from typing import List

from fastapi import APIRouter, Body, Depends, Path, Security
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.cart_schemas import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
    CartWithDiscountResponse,
)
from app.services.cart_service import CartService

router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
)
cart_manager = CartService()

# ===================== CART ROUTES ===================== #


@router.get("/", description="Get the current user's cart", response_model=CartResponse)
async def get_cart(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:read"]),
):
    result = await cart_manager.GET_USER_CART(db=db, user_id=current_user.user_id)
    return result


@router.post(
    "/items/",
    description="Add an item to the user's cart",
)
async def add_item_to_cart(
    item_data: CartItemCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:write"]),
):
    result = await cart_manager.ADD_ITEM(
        db=db, user_id=current_user.user_id, item_data=item_data
    )
    return result


@router.put(
    "/items/{cart_item_id}",
    description="Update quantity or details of a specific cart item",
)
async def update_cart_item(
    cart_item_id: int = Path(..., description="Cart item ID to update"),
    item_data: CartItemUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:write"]),
):
    result = await cart_manager.UPDATE_ITEM(
        db=db,
        cart_item_id=cart_item_id,
        item_data=item_data,
        user_id=current_user.user_id,
    )
    return result


@router.delete(
    "/items/{cart_item_id}",
    description="Remove an item from the user's cart",
)
async def delete_cart_item(
    cart_item_id: int = Path(..., description="Cart item ID to delete"),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:delete"]),
):
    result = await cart_manager.DELETE_ITEM(
        db=db, cart_item_id=cart_item_id, user_id=current_user.user_id
    )
    return result


@router.delete(
    "/clear",
    description="Clear all items from the user's cart",
)
async def clear_cart(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:delete"]),
):
    result = await cart_manager.CLEAR_USER_CART(db=db, user_id=current_user.user_id)
    return result


@router.get(
    "/get-cart-page/",
    description="Get cart with automatic discounts applied",
    response_model=CartWithDiscountResponse,
)
async def get_cart_with_discounts(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:read"]),
):
    result = await cart_manager.GET_CART_WITH_DISCOUNTS(
        db=db, user_id=current_user.user_id
    )
    return result


@router.post(
    "/apply-coupon/{coupon_code}",
    description="Apply a coupon to the cart and get discounted total",
)
async def apply_coupon(
    coupon_code: str = Path(..., description="Coupon code to apply"),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["cart:write"]),
):
    result = await cart_manager.APPLY_COUPON(
        db=db, user_id=current_user.user_id, coupon_code=coupon_code
    )
    return result
