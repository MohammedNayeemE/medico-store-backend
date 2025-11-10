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
    def __init__(self):
        pass

    async def GET_USER_CART(self, db: AsyncSession, user_id: int) -> Cart:
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
