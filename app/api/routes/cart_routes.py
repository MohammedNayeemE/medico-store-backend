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
    """
    Retrieve the current authenticated user's shopping cart.
    
    This endpoint fetches the user's shopping cart along with all cart items and their
    associated medicine details. If the user doesn't have a cart, a new empty cart is
    automatically created. The cart includes all items with their quantities, prices,
    and medicine information.
    
    Args:
        db (AsyncSession): Database session dependency for querying cart data.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:read" permission.
    
    Returns:
        CartResponse: A Pydantic model containing:
                     - cart_id (int): Unique cart identifier
                     - customer_id (int): User ID of the cart owner
                     - cart_items (List[CartItemResponse]): List of items in the cart
                     - created_at (datetime): Cart creation timestamp
                     - updated_at (datetime): Cart last update timestamp
                     - total_amount (Decimal): Total value of all items in cart
    
    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:read" permission.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:read" permission
        - Users can only access their own cart
        - Cart is automatically created if it doesn't exist
    
    Example Response:
        ```json
        {
            "cart_id": 1,
            "customer_id": 123,
            "cart_items": [
                {
                    "cart_item_id": 1,
                    "medicine_id": 5,
                    "quantity": 2,
                    "medicine": {...}
                }
            ],
            "total_amount": 150.00,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        ```
    
    Note:
        - If no cart exists, a new empty cart is created automatically
        - Cart items include full medicine details via eager loading
        - Deleted items are excluded from the response
        - The response includes calculated totals and item details
    """
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
    """
    Add a medicine item to the user's shopping cart.
    
    This endpoint adds a medicine to the user's cart. If the medicine already exists
    in the cart, the quantity is increased by the specified amount. If it doesn't exist,
    a new cart item is created. The medicine must exist and be available in the inventory.
    
    Args:
        item_data (CartItemCreate): Cart item data containing:
                                   - medicine_id (int): ID of the medicine to add
                                   - quantity (int): Quantity to add (must be positive)
        db (AsyncSession): Database session dependency for cart operations.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:write" permission.
    
    Returns:
        Cart: The updated cart object with all items, including the newly added item.
              The cart is automatically refreshed to include updated totals.
    
    Raises:
        HTTPException (400): If the quantity is invalid or medicine is unavailable.
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:write" permission.
        HTTPException (404): If the medicine is not found or cart doesn't exist.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:write" permission
        - Users can only add items to their own cart
        - Medicine availability is validated
    
    Example Request:
        ```json
        {
            "medicine_id": 5,
            "quantity": 2
        }
        ```
    
    Example Response:
        ```json
        {
            "cart_id": 1,
            "customer_id": 123,
            "cart_items": [...],
            "total_amount": 150.00
        }
        ```
    
    Note:
        - If the medicine already exists in the cart, quantity is increased
        - If the medicine doesn't exist in the cart, a new item is added
        - The cart must exist (created automatically on first get_cart call)
        - Medicine must exist and be available in inventory
        - Quantity must be a positive integer
    """
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
    """
    Update the quantity or details of a specific cart item.
    
    This endpoint updates an existing cart item, typically to change its quantity.
    The cart item must belong to the authenticated user's cart. The quantity can be
    increased, decreased, or set to a specific value. If quantity is set to 0, the
    item may be removed from the cart.
    
    Args:
        cart_item_id (int): The unique identifier of the cart item to update.
                           Provided as a path parameter.
        item_data (CartItemUpdate): Update data containing:
                                   - quantity (int, optional): New quantity for the item
                                                              (must be positive)
        db (AsyncSession): Database session dependency for cart operations.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:write" permission.
    
    Returns:
        CartItem: The updated cart item object with new quantity and updated timestamp.
    
    Raises:
        HTTPException (400): If the quantity is invalid or item doesn't belong to user.
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:write" permission.
        HTTPException (404): If the cart item is not found.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:write" permission
        - Users can only update items in their own cart
        - Cart item ownership is validated
    
    Example Request:
        ```json
        {
            "quantity": 5
        }
        ```
    
    Example Response:
        ```json
        {
            "cart_item_id": 1,
            "cart_id": 1,
            "medicine_id": 5,
            "quantity": 5,
            "added_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        ```
    
    Note:
        - The cart item must belong to the user's cart
        - Quantity must be a positive integer
        - Setting quantity to 0 may remove the item from the cart
        - The item's updated_at timestamp is automatically updated
        - Medicine availability is not re-checked on update
    """
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
    """
    Remove an item from the user's shopping cart.
    
    This endpoint removes a specific cart item from the user's cart. The item is
    soft-deleted (marked as deleted) rather than permanently removed from the database.
    The cart item must belong to the authenticated user's cart.
    
    Args:
        cart_item_id (int): The unique identifier of the cart item to remove.
                           Provided as a path parameter.
        db (AsyncSession): Database session dependency for cart operations.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:delete" permission.
    
    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message indicating item was removed
                     - cart_item_id (int): ID of the removed item
    
    Raises:
        HTTPException (400): If the item doesn't belong to the user's cart.
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:delete" permission.
        HTTPException (404): If the cart item is not found.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:delete" permission
        - Users can only delete items from their own cart
        - Cart item ownership is validated
    
    Example Response:
        ```json
        {
            "msg": "Item removed from cart successfully",
            "cart_item_id": 1
        }
        ```
    
    Note:
        - The cart item is soft-deleted (marked as deleted, not permanently removed)
        - The item must belong to the user's cart
        - After deletion, the item won't appear in cart retrieval
        - The cart totals are automatically updated
        - Deleted items can be restored if needed (depending on implementation)
    """
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
    """
    Clear all items from the user's shopping cart.
    
    This endpoint removes all items from the user's cart in a single operation.
    All cart items are soft-deleted (marked as deleted) rather than permanently
    removed. The cart itself remains but becomes empty.
    
    Args:
        db (AsyncSession): Database session dependency for cart operations.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:delete" permission.
    
    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success message indicating cart was cleared
                     - cart_id (int): ID of the cleared cart
                     - items_removed (int): Number of items removed (optional)
    
    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:delete" permission.
        HTTPException (404): If the cart is not found.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:delete" permission
        - Users can only clear their own cart
        - Cart ownership is validated
    
    Example Response:
        ```json
        {
            "msg": "Cart cleared successfully",
            "cart_id": 1,
            "items_removed": 5
        }
        ```
    
    Note:
        - All cart items are soft-deleted (marked as deleted)
        - The cart remains but becomes empty
        - This operation is irreversible (items are marked as deleted)
        - Cart totals are reset to zero
        - The cart can be repopulated after clearing
    """
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
    """
    Get the user's cart with automatic discounts and coupons applied.
    
    This endpoint retrieves the user's cart and automatically applies all eligible
    discounts and coupons. This is optimized for displaying the cart on the shopping
    page with all pricing calculations, discounts, and final totals. The response
    includes original prices, discount amounts, and final prices after discounts.
    
    Args:
        db (AsyncSession): Database session dependency for querying cart and discount data.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:read" permission.
    
    Returns:
        CartWithDiscountResponse: A Pydantic model containing:
                                 - cart (CartResponse): The user's cart with items
                                 - discounts_applied (List[Discount]): List of applied discounts
                                 - coupon_applied (Coupon, optional): Applied coupon if any
                                 - subtotal (Decimal): Total before discounts
                                 - discount_amount (Decimal): Total discount amount
                                 - final_total (Decimal): Total after discounts
                                 - savings (Decimal): Total savings from discounts
    
    Raises:
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:read" permission.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:read" permission
        - Users can only view their own cart
        - Discount eligibility is calculated based on cart contents
    
    Example Response:
        ```json
        {
            "cart": {...},
            "discounts_applied": [
                {
                    "discount_id": 1,
                    "discount_type": "percentage",
                    "value": 10,
                    "amount": 15.00
                }
            ],
            "coupon_applied": {
                "coupon_id": 1,
                "code": "SAVE10",
                "discount_amount": 5.00
            },
            "subtotal": 150.00,
            "discount_amount": 20.00,
            "final_total": 130.00,
            "savings": 20.00
        }
        ```
    
    Note:
        - All eligible discounts are automatically applied
        - Discounts are calculated based on cart items and medicine eligibility
        - Coupons are applied if a valid coupon code was previously applied
        - The response includes detailed breakdown of all discounts
        - This endpoint is optimized for cart page display
        - Discount calculations are performed in real-time
    """
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
    """
    Apply a coupon code to the user's cart.
    
    This endpoint applies a coupon code to the user's cart if it's valid and eligible.
    The coupon is validated for expiration, usage limits, and eligibility criteria.
    If valid, the coupon discount is applied to the cart total, and the coupon is
    associated with the cart for future calculations.
    
    Args:
        coupon_code (str): The coupon code to apply. Provided as a path parameter.
                          Must be a valid, active coupon code.
        db (AsyncSession): Database session dependency for coupon and cart operations.
                          Defaults to Depends(get_postgres).
        current_user (User): The currently authenticated user, obtained from the
                            access token. Requires "cart:write" permission.
    
    Returns:
        JSONResponse: A JSON response containing:
                     - msg (str): Success or error message
                     - coupon (Coupon): Applied coupon details
                     - discount_amount (Decimal): Discount amount applied
                     - cart_total (Decimal): Updated cart total after coupon
                     - Optional: Error details if coupon is invalid
    
    Raises:
        HTTPException (400): If the coupon code is invalid, expired, or already used.
        HTTPException (401): If the user is not authenticated.
        HTTPException (403): If the user doesn't have "cart:write" permission.
        HTTPException (404): If the coupon code is not found.
        HTTPException (500): If there's an internal server error.
    
    Security:
        - Requires authentication and "cart:write" permission
        - Users can only apply coupons to their own cart
        - Coupon validity and eligibility are validated
        - Usage limits are enforced
    
    Example Request:
        ```
        POST /cart/apply-coupon/SAVE10
        ```
    
    Example Response:
        ```json
        {
            "msg": "Coupon applied successfully",
            "coupon": {
                "coupon_id": 1,
                "code": "SAVE10",
                "discount_type": "percentage",
                "value": 10,
                "discount_amount": 15.00
            },
            "discount_amount": 15.00,
            "cart_total": 135.00
        }
        ```
    
    Note:
        - Coupon must be valid, active, and not expired
        - Coupon usage limits are enforced (e.g., one-time use, per-user limits)
        - Coupon eligibility is checked (minimum cart value, specific products, etc.)
        - Only one coupon can be applied to a cart at a time
        - Previous coupon is replaced if a new one is applied
        - Coupon discount is calculated based on cart total and coupon rules
    """
    result = await cart_manager.APPLY_COUPON(
        db=db, user_id=current_user.user_id, coupon_code=coupon_code
    )
    return result
