from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.inventory_management_models import (
    Cart,
    CartItem,
    Medicine,
    MedicineBatch,
)
from app.models.order_management_models import Coupon, Discount, DiscountMedicine
from app.schemas.cart_schemas import CartItemCreate, CartItemUpdate


class CartService:
    """
    Service class for managing shopping cart operations.
    
    This service handles all cart-related business logic including creating carts,
    adding/updating/removing items, applying coupons, and calculating discounts.
    It provides methods for cart management that are used by the cart routes.
    """
    def __init__(self):
        pass

    async def GET_USER_CART(self, db: AsyncSession, user_id: int) -> Cart:
        """
        Retrieve or create a shopping cart for a user.
        
        This method fetches the user's shopping cart from the database. If no cart
        exists for the user, a new empty cart is automatically created. The cart
        includes all cart items with their associated medicine details loaded via
        eager loading to avoid N+1 query problems.
        
        Args:
            db (AsyncSession): Database session for querying cart data.
            user_id (int): The unique identifier of the user whose cart to retrieve.
        
        Returns:
            Cart: The user's cart object with cart items and medicine details loaded.
                 If no cart exists, a new cart is created and returned.
        
        Raises:
            HTTPException (500): If there's an internal server error during cart retrieval
                                or creation.
        
        Note:
            - Cart items are eagerly loaded with medicine details
            - Deleted carts and items are excluded from the result
            - If no cart exists, a new cart is created automatically
            - The cart is refreshed after creation to ensure all relationships are loaded
        """
        try:
            result = await db.execute(
                select(Cart)
                .options(selectinload(Cart.cart_items).selectinload(CartItem.medicine))
                .filter(
                    Cart.customer_id == user_id,
                    Cart.is_deleted == False,
                )
            )
            cart = result.scalar_one_or_none()
            if not cart:
                cart = Cart(customer_id=user_id)
                db.add(cart)
                await db.commit()
                await db.refresh(cart)
            await db.refresh(cart)
            return cart
        except Exception as e:
            print("==========================")
            print(f"[GET_USER_CART] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [GET_USER_CART]"
            )

    async def ADD_ITEM(
        self, db: AsyncSession, user_id: int, item_data: CartItemCreate
    ) -> CartItem:
        """
        Add a medicine item to the user's shopping cart.
        
        This method adds a medicine to the user's cart. If the medicine already exists
        in the cart, the quantity is increased by the specified amount. If it doesn't
        exist, a new cart item is created. The medicine must exist in the database
        and the user must have an active cart.
        
        Args:
            db (AsyncSession): Database session for cart operations.
            user_id (int): The unique identifier of the user whose cart to update.
            item_data (CartItemCreate): Cart item data containing:
                                      - medicine_id (int): ID of the medicine to add
                                      - quantity (int): Quantity to add (must be positive)
        
        Returns:
            Cart: The updated cart object with all items, including the newly added item.
                 The cart is automatically refreshed to include updated relationships.
        
        Raises:
            NotFoundException: If the medicine is not found or the cart doesn't exist.
            HTTPException (500): If there's an internal server error.
        
        Note:
            - If the medicine already exists in the cart, quantity is increased
            - If the medicine doesn't exist in the cart, a new item is created
            - The cart must exist (created automatically by GET_USER_CART if needed)
            - Medicine existence is validated before adding to cart
            - Cart is refreshed after adding item to ensure relationships are loaded
        """
        medicine_q = await db.execute(
            select(Medicine).filter(Medicine.medicine_id == item_data.medicine_id)
        )
        medicine = medicine_q.scalar_one_or_none()
        if not medicine:
            raise NotFoundException("Medicine not found")
        result = await db.execute(
            select(Cart).filter(
                Cart.customer_id == user_id,
                Cart.is_deleted == False,
            )
        )
        cart = result.scalar_one_or_none()
        if not cart:
            raise NotFoundException("Cart not found")
        item_q = await db.execute(
            select(CartItem).filter(
                CartItem.cart_id == cart.cart_id,
                CartItem.medicine_id == item_data.medicine_id,
                CartItem.is_deleted == False,
            )
        )
        existing_item = item_q.scalar_one_or_none()
        if existing_item:
            existing_item.quantity += item_data.quantity
            existing_item.added_at = datetime.utcnow()
        else:
            new_item = CartItem(
                cart_id=cart.cart_id,
                medicine_id=item_data.medicine_id,
                quantity=item_data.quantity,
            )
            db.add(new_item)
        await db.commit()
        await db.refresh(cart)
        return cart

    async def UPDATE_ITEM(
        self,
        db: AsyncSession,
        user_id: int,
        cart_item_id: int,
        item_data: CartItemUpdate,
    ) -> CartItem:
        """
        Update the quantity of a specific cart item.
        
        This method updates an existing cart item's quantity. The cart item must belong
        to the user's cart. The quantity is validated to ensure it's greater than zero.
        The item's added_at timestamp is updated to reflect the modification time.
        
        Args:
            db (AsyncSession): Database session for cart operations.
            user_id (int): The unique identifier of the user whose cart item to update.
            cart_item_id (int): The unique identifier of the cart item to update.
            item_data (CartItemUpdate): Update data containing:
                                      - quantity (int): New quantity for the item
                                                       (must be greater than zero)
        
        Returns:
            CartItem: The updated cart item object with new quantity and updated timestamp.
        
        Raises:
            NotFoundException: If the cart item is not found or doesn't belong to the user.
            BadRequestException: If the quantity is less than or equal to zero.
            HTTPException (500): If there's an internal server error.
        
        Note:
            - The cart item must belong to the user's cart
            - Quantity must be greater than zero
            - The item's added_at timestamp is updated to current time
            - Cart item ownership is validated through cart relationship
            - Deleted items cannot be updated
        """
        q = await db.execute(
            select(CartItem)
            .join(Cart)
            .filter(
                CartItem.cart_item_id == cart_item_id,
                Cart.customer_id == user_id,
                CartItem.is_deleted == False,
                Cart.is_deleted == False,
            )
        )
        item = q.scalar_one_or_none()
        if not item:
            raise NotFoundException("Cart item not found")
        if item_data.quantity <= 0:
            raise BadRequestException("Quantity must be greater than zero")
        item.quantity = item_data.quantity
        item.added_at = datetime.utcnow()
        await db.commit()
        await db.refresh(item)
        return item

    async def DELETE_ITEM(
        self, db: AsyncSession, user_id: int, cart_item_id: int
    ) -> dict:
        """
        Remove a cart item from the user's shopping cart (soft delete).
        
        This method removes a cart item from the user's cart by marking it as deleted
        (soft delete). The item is not permanently removed from the database. The
        deletion timestamp and user who performed the deletion are recorded.
        
        Args:
            db (AsyncSession): Database session for cart operations.
            user_id (int): The unique identifier of the user whose cart item to delete.
            cart_item_id (int): The unique identifier of the cart item to remove.
        
        Returns:
            dict: A dictionary containing:
                 - message (str): Success message indicating item was removed
        
        Raises:
            NotFoundException: If the cart item is not found or doesn't belong to the user.
            HTTPException (500): If there's an internal server error.
        
        Note:
            - The cart item is soft-deleted (marked as deleted, not permanently removed)
            - The item must belong to the user's cart
            - Deletion timestamp and user are recorded
            - Soft-deleted items won't appear in cart retrieval
            - Cart item ownership is validated through cart relationship
        """
        q = await db.execute(
            select(CartItem)
            .join(Cart)
            .filter(
                CartItem.cart_item_id == cart_item_id,
                Cart.customer_id == user_id,
                CartItem.is_deleted == False,
            )
        )
        item = q.scalar_one_or_none()
        if not item:
            raise NotFoundException("Cart item not found")
        item.is_deleted = True
        item.deleted_at = datetime.utcnow()
        item.deleted_by = user_id
        await db.commit()
        return {"message": "Cart item removed successfully"}

    async def CLEAR_USER_CART(self, db: AsyncSession, user_id: int) -> dict:
        """
        Clear all items from the user's shopping cart.
        
        This method removes all items from the user's cart in a single operation by
        soft-deleting all cart items. The cart itself remains but becomes empty. All
        items are marked as deleted with the current timestamp and user ID.
        
        Args:
            db (AsyncSession): Database session for cart operations.
            user_id (int): The unique identifier of the user whose cart to clear.
        
        Returns:
            dict: A dictionary containing:
                 - message (str): Success message indicating cart was cleared
        
        Raises:
            NotFoundException: If the cart is not found for the user.
            HTTPException (500): If there's an internal server error.
        
        Note:
            - All cart items are soft-deleted (marked as deleted)
            - The cart remains but becomes empty
            - Deletion timestamp and user are recorded for all items
            - This operation is performed in a single database update for efficiency
            - Only non-deleted items are cleared
        """
        cart_q = await db.execute(
            select(Cart).filter(
                Cart.customer_id == user_id,
                Cart.is_deleted == False,
            )
        )
        cart = cart_q.scalar_one_or_none()
        if not cart:
            raise NotFoundException("Cart not found")
        await db.execute(
            update(CartItem)
            .where(CartItem.cart_id == cart.cart_id, CartItem.is_deleted == False)
            .values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                deleted_by=user_id,
            )
        )
        await db.commit()
        return {"message": "All items removed from cart"}

    async def APPLY_COUPON(
        self, db: AsyncSession, user_id: int, coupon_code: str
    ) -> dict:
        """
        Apply a coupon code to the user's cart and calculate discount.
        
        This method validates a coupon code and applies it to the user's cart if it's
        valid and eligible. The coupon is validated for expiration, usage limits, and
        minimum purchase amount. If valid, the discount is calculated and the coupon's
        usage count is incremented. The discount can be a percentage or fixed amount.
        
        Args:
            db (AsyncSession): Database session for coupon and cart operations.
            user_id (int): The unique identifier of the user whose cart to apply coupon to.
            coupon_code (str): The coupon code to validate and apply.
        
        Returns:
            dict: A dictionary containing:
                 - success (bool): Whether the coupon was applied successfully
                 - coupon_code (str): The applied coupon code
                 - discount_name (str): Name of the discount
                 - discount_value (float): Discount value
                 - discount_type (str): Type of discount (percentage or fixed)
                 - original_total (float): Cart total before discount
                 - discount_amount (float): Amount of discount applied
                 - final_total (float): Cart total after discount
        
        Raises:
            NotFoundException: If the coupon code is not found or cart doesn't exist.
            BadRequestException: If the coupon is expired, usage limit reached, or
                               minimum purchase amount not met.
            HTTPException (500): If there's an internal server error.
        
        Note:
            - Coupon must be valid, active, and not expired
            - Coupon usage limits are enforced
            - Minimum purchase amount is validated
            - Discount can be percentage or fixed amount
            - Maximum discount amount is enforced if specified
            - Coupon usage count is incremented after application
            - Cart total is calculated from all cart items
        """
        coupon_q = await db.execute(
            select(Coupon).filter(
                Coupon.code == coupon_code, Coupon.is_deleted == False
            )
        )
        coupon = coupon_q.scalar_one_or_none()
        if not coupon:
            raise NotFoundException("Invalid coupon code")
        now = datetime.utcnow()
        if not (coupon.valid_from <= now <= coupon.valid_to):
            raise BadRequestException("Coupon expired or not yet active")
        if coupon.max_usage is not None and coupon.used_count >= coupon.max_usage:
            raise BadRequestException("Coupon usage limit reached")
        discount_q = await db.execute(
            select(Discount).filter(
                Discount.discount_id == coupon.discount_id,
                Discount.is_deleted == False,
            )
        )
        discount = discount_q.scalar_one_or_none()
        if not discount:
            raise NotFoundException("Associated discount not found")
        cart_q = await db.execute(
            select(Cart).filter(Cart.customer_id == user_id, Cart.is_deleted == False)
        )
        cart = cart_q.scalar_one_or_none()
        if not cart:
            raise NotFoundException("Cart not found")
        await db.refresh(cart, attribute_names=["cart_items"])
        total_amount = Decimal(0)
        discount_amount = Decimal(0)
        for item in cart.cart_items:
            medicine = await db.get(Medicine, item.medicine_id)
            total_amount += Decimal(medicine.price) * item.quantity
        if total_amount < discount.min_purchase_amount:
            raise BadRequestException(
                f"Minimum purchase amount of {discount.min_purchase_amount} required"
            )
        if discount.discount_type.type_name.lower() == "percentage":
            discount_amount = total_amount * (Decimal(discount.value) / Decimal(100))
        else:
            discount_amount = Decimal(discount.value)
        if discount.max_discount_amount:
            discount_amount = min(discount_amount, discount.max_discount_amount)
        final_total = total_amount - discount_amount
        coupon.used_count += 1
        await db.commit()
        return {
            "success": True,
            "coupon_code": coupon.code,
            "discount_name": discount.name,
            "discount_value": float(discount.value),
            "discount_type": discount.discount_type.type_name,
            "original_total": float(total_amount),
            "discount_amount": float(discount_amount),
            "final_total": float(final_total),
        }

    async def GET_CART_WITH_DISCOUNTS(self, db: AsyncSession, user_id: int) -> dict:
        """
        Get the user's cart with automatic discounts applied to items.
        
        This method retrieves the user's cart and automatically applies all eligible
        discounts to cart items. Discounts are applied based on medicine eligibility
        and discount validity periods. Each item's price is calculated using the
        earliest expiring batch, and discounts are applied based on discount type
        (percentage or fixed amount). The response includes original prices, discount
        amounts, and final prices for each item.
        
        Args:
            db (AsyncSession): Database session for cart and discount operations.
            user_id (int): The unique identifier of the user whose cart to retrieve.
        
        Returns:
            dict: A dictionary containing:
                 - cart_id (int): ID of the cart
                 - items (List[dict]): List of cart items with discounts applied, each containing:
                                      - medicine_id (int): Medicine ID
                                      - medicine_name (str): Medicine name
                                      - quantity (int): Item quantity
                                      - unit_price (float): Price per unit
                                      - original_price (float): Total price before discount
                                      - discount_applied (float): Discount amount applied
                                      - final_price (float): Final price after discount
                 - total_amount (float): Total cart amount after all discounts
        
        Raises:
            HTTPException (500): If there's an internal server error.
        
        Note:
            - Discounts are automatically applied based on medicine eligibility
            - Item prices are calculated using the earliest expiring batch
            - Discounts must be active (within start and end dates)
            - Discounts can be percentage or fixed amount
            - Items without eligible discounts use their regular price
            - Total amount is the sum of all item final prices after discounts
            - Warnings are logged if no batch is found for a medicine
        """
        cart = await self.GET_USER_CART(db, user_id)
        await db.refresh(cart, attribute_names=["cart_items"])
        total_amount = Decimal(0)
        discounted_items = []
        for item in cart.cart_items:
            medicine = await db.get(Medicine, item.medicine_id)
            batch_q = await db.execute(
                select(MedicineBatch)
                .filter(
                    MedicineBatch.medicine_id == medicine.medicine_id,
                    MedicineBatch.is_deleted == False,
                )
                .order_by(MedicineBatch.expiry_date.asc())
                .limit(1)
            )
            batch = batch_q.scalar_one_or_none()
            if not batch:
                print(f"[Warning] No batch found for medicine {medicine.medicine_name}")
                continue
            price = Decimal(batch.selling_price)
            item_total = price * item.quantity
            discount_q = await db.execute(
                select(Discount)
                .join(DiscountMedicine)
                .filter(
                    DiscountMedicine.medicine_id == medicine.medicine_id,
                    Discount.is_deleted == False,
                    Discount.start_date <= datetime.utcnow(),
                    Discount.end_date >= datetime.utcnow(),
                )
            )
            discount = discount_q.scalar_one_or_none()
            if discount:
                if discount.discount_type.type_name.lower() == "percentage":
                    discount_value = item_total * (
                        Decimal(discount.value) / Decimal(100)
                    )
                else:
                    discount_value = Decimal(discount.value)
                discounted_price = item_total - discount_value
            else:
                discounted_price = item_total
                discount_value = Decimal(0)
            total_amount += discounted_price
            discounted_items.append(
                {
                    "medicine_id": medicine.medicine_id,
                    "medicine_name": medicine.medicine_name,
                    "quantity": item.quantity,
                    "unit_price": float(price),
                    "original_price": float(item_total),
                    "discount_applied": float(discount_value),
                    "final_price": float(discounted_price),
                }
            )
        return {
            "cart_id": cart.cart_id,
            "items": discounted_items,
            "total_amount": float(total_amount),
        }
