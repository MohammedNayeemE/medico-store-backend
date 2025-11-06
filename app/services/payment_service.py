from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import exc
from sqlalchemy.util import parse_user_argument_for_enum

from app.core.exceptions import (
    BadRequestException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.enums import OrderStatusEnum, PaymentStatusEnum, RequestOrderStatusEnum
from app.models.inventory_management_models import MedicineBatch
from app.models.order_management_models import (
    Order,
    OrderItem,
    Payment,
    RequestOrder,
    RequestOrderItem,
)
from app.services.order_management_service import OrderService


class PaymentService:
    def __init__(self) -> None:
        self.order_service = OrderService()

    async def _reserve_for_item(
        self, db: AsyncSession, req_item: RequestOrderItem, order_id: int
    ) -> Tuple[bool, int]:
        """
        Reserve available stock for the given request item by creating OrderItem rows:
         - For reserved units: OrderItem(batch_id=..., quantity=X, is_backordered=False)
         - If not fully satisfied: create one backorder OrderItem with batch_id=None,
           quantity=0, is_backordered=True, backordered_qty=remaining
        Returns:
            (fully_allocated: bool, reserved_total: int)
        """
        needed = int(req_item.quantity)
        reserved_total = 0
        order_items_to_create: List[OrderItem] = []
        batches_q = (
            select(MedicineBatch)
            .filter(
                MedicineBatch.medicine_id == req_item.medicine_id,
                MedicineBatch.is_deleted == False,
                (
                    MedicineBatch.quantity
                    - func.coalesce(MedicineBatch.reserved_quantity, 0)
                )
                > 0,
            )
            .order_by(MedicineBatch.expiry_date.asc())
            .with_for_update()
        )
        result = await db.execute(batches_q)
        batches: List[MedicineBatch] = result.scalars().all()
        for batch in batches:
            if needed <= 0:
                break
            available = int(batch.quantity) - int(
                getattr(batch, "reserved_quantity", 0)
            )
            if available <= 0:
                continue
            take = min(needed, available)
            batch.reserved_quantity = int(getattr(batch, "reserved_quantity", 0)) + take
            reserved_total += take
            needed -= take
            oi = OrderItem(
                order_id=order_id,
                batch_id=batch.batch_id,
                quantity=take,
                price=req_item.estimated_price or 0,
                is_backordered=False,
                backordered_qty=0,
            )
            order_items_to_create.append(oi)
        if needed > 0:
            backorder = OrderItem(
                order_id=order_id,
                batch_id=None,
                quantity=0,
                price=req_item.estimated_price or 0,
                is_backordered=True,
                backordered_qty=needed,
            )
            order_items_to_create.append(backorder)
        if order_items_to_create:
            db.add_all(order_items_to_create)
        fully_allocated = needed == 0
        return fully_allocated, reserved_total

    async def _release_reservation_for_order(
        self, db: AsyncSession, order_id: int
    ) -> None:
        """
        Find OrderItems for this order that have batch_id (reserved), and decrement
        the corresponding MedicineBatch.reserved_quantity by the order item quantity.
        Use FOR UPDATE on batches to prevent races.
        """
        q = select(OrderItem).filter(
            OrderItem.order_id == order_id,
            OrderItem.is_deleted == False,
            OrderItem.is_backordered == False,
            OrderItem.batch_id.isnot(None),
        )
        res = await db.execute(q)
        reserved_items: List[OrderItem] = res.scalars().all()
        if not reserved_items:
            return
        batch_ids = [oi.batch_id for oi in reserved_items if oi.batch_id is not None]
        if not batch_ids:
            return
        batch_q = (
            select(MedicineBatch)
            .filter(MedicineBatch.batch_id.in_(batch_ids))
            .with_for_update()
        )
        batch_res = await db.execute(batch_q)
        batches = {b.batch_id: b for b in batch_res.scalars().all()}
        for oi in reserved_items:
            batch = batches.get(oi.batch_id)
            if not batch:
                continue
            batch.reserved_quantity = max(
                0, int(getattr(batch, "reserved_quantity", 0)) - int(oi.quantity)
            )

        # Commit will be done by caller or here - keep caller responsible to allow transaction composition.

    async def _finalize_reserved_items_on_payment(
        self, db: AsyncSession, order_id: int
    ) -> None:
        """
        For reserved order items (non-backordered) decrease both:
          - MedicineBatch.quantity (actual stock)
          - MedicineBatch.reserved_quantity (release reservation)
        This should be done once payment is confirmed.
        """
        q = select(OrderItem).filter(
            OrderItem.order_id == order_id,
            OrderItem.is_deleted == False,
            OrderItem.is_backordered == False,
            OrderItem.batch_id.isnot(None),
        )
        res = await db.execute(q)
        reserved_items: List[OrderItem] = res.scalars().all()
        if not reserved_items:
            return
        batch_ids = [oi.batch_id for oi in reserved_items if oi.batch_id is not None]
        if not batch_ids:
            return
        batch_q = (
            select(MedicineBatch)
            .filter(MedicineBatch.batch_id.in_(batch_ids))
            .with_for_update()
        )
        batch_res = await db.execute(batch_q)
        batches = {b.batch_id: b for b in batch_res.scalars().all()}
        for oi in reserved_items:
            batch = batches.get(oi.batch_id)
            if not batch:
                print(
                    "Batch not found while finalizing payment for order_item %s",
                    oi.order_item_id,
                )
                continue
            sold = int(oi.quantity)
            batch.quantity = max(0, int(batch.quantity) - sold)
            batch.reserved_quantity = max(
                0, int(getattr(batch, "reserved_quantity", 0)) - sold
            )

    async def INITIATE_PAYMENT(
        self, db: AsyncSession, request_order_id: int, payment_mode: str, user_id: int
    ):
        try:
            result = await db.execute(
                select(RequestOrder).filter(
                    RequestOrder.request_order_id == request_order_id
                )
            )
            request_order_obj = result.scalar_one_or_none()

            if not request_order_obj or request_order_obj.status not in [
                RequestOrderStatusEnum.awaiting_payment.value,
                RequestOrderStatusEnum.approved.value,
            ]:
                raise NotFoundException(
                    "u can't pay at this stage approval from admin required"
                )

            if request_order_obj.updated_at + timedelta(days=1) < datetime.now(
                timezone.utc
            ):
                raise BadRequestException("payment link expired")

            # ✅ Convert request to order (adds new order to the session)
            new_order = await self.order_service.CONVERT_REQUEST_TO_ORDER(
                db=db, request_order_id=request_order_id
            )

            # ❌ Removed async with db.begin()
            db.add(new_order)
            await db.flush()  # flush new_order to get its ID

            # Fetch request items
            query = (
                select(RequestOrderItem)
                .filter(
                    RequestOrderItem.request_order_id == request_order_id,
                    RequestOrderItem.is_deleted == False,
                )
                .order_by(RequestOrderItem.request_order_item_id.asc())
            )
            req_res = await db.execute(query)
            req_items: List[RequestOrderItem] = req_res.scalars().all()

            is_allocated_full, is_reserved = True, False
            for req_item in req_items:
                fully_allocated, reserved_qty = await self._reserve_for_item(
                    db=db, req_item=req_item, order_id=new_order.order_id
                )
                if reserved_qty > 0:
                    is_reserved = True
                if not fully_allocated:
                    is_allocated_full = False

            now = datetime.now(timezone.utc)
            if is_allocated_full:
                new_order.predicted_delivery_date = now + timedelta(days=1)
            elif is_reserved:
                new_order.predicted_delivery_date = now + timedelta(days=2)

            new_order.status = OrderStatusEnum.pending.value

            # Create payment record
            new_payment = Payment(
                order_id=new_order.order_id,
                amount=float(new_order.total_amount),
                status=PaymentStatusEnum.pending.value,
                payment_mode=payment_mode,
                user_id=user_id,
            )
            db.add(new_payment)

            await db.commit()
            await db.refresh(new_payment)
            await db.refresh(new_order)
            return new_payment

        except (BadRequestException, NotFoundException):
            raise
        except Exception as e:
            print("---------------------------------------------")
            print(f"[initiate_payment] : {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [initiate_payment]"
            )

    async def UPDATE_PAYMENT_STATUS(
        self,
        db: AsyncSession,
        payment_id: int,
        new_status: PaymentStatusEnum,
        paid_at: datetime | None = None,
    ):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.payment_id == payment_id)
            )
            payment_obj = result.scalar_one_or_none()
            if not payment_obj:
                raise NotFoundException("payment_id not found")
            current_status = payment_obj.status
            if current_status == new_status:
                raise BadRequestException("invalid status")
            if new_status == PaymentStatusEnum.completed:
                payment_obj.status = PaymentStatusEnum.completed.value
                payment_obj.paid_at = paid_at or datetime.now(timezone.utc)
                await self._finalize_reserved_items_on_payment(
                    db=db, order_id=payment_obj.order_id
                )
                order_res = await db.execute(
                    select(Order).filter(Order.order_id == payment_obj.order_id)
                )
                order = order_res.scalar_one_or_none()
                if order:
                    order.status = OrderStatusEnum.confirmed.value
                payment_obj.paid_at = datetime.utcnow()
                await db.commit()
                await db.refresh(payment_obj)
                return payment_obj
            if new_status == PaymentStatusEnum.failed:
                payment_obj.status = PaymentStatusEnum.failed.value
                await self._release_reservation_for_order(
                    db=db, order_id=payment_obj.order_id
                )
                order_res = await db.execute(
                    select(Order).filter(Order.order_id == payment_obj.order_id)
                )
                order = order_res.scalar_one_or_none()
                if order:
                    order.status = OrderStatusEnum.pending.value  # or "payment_failed"
                await db.commit()
                await db.refresh(payment_obj)
                return payment_obj
            payment_obj.status = new_status.value
            await db.commit()
            await db.refresh(payment_obj)
            return payment_obj
        except (BadRequestException, NotFoundException):
            raise
        except Exception as e:
            print("------------------------")
            print(f"[update_payment_status] : {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [update_payment_status]"
            )

    async def ROLLBACK_PAYMENT(self, db: AsyncSession, payment_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.payment_id == payment_id)
            )
            payment_obj = result.scalar_one_or_none()
            if not payment_obj:
                raise NotFoundException("payment_id not found")
            payment_obj.status = PaymentStatusEnum.failed.value
            await db.commit()
            await db.refresh(payment_obj)
            return payment_obj
        except NotFoundException:
            raise
        except Exception as e:
            print("------------------------")
            print(f"[rollback_payment] : {e}")
            raise InternalServerErrorException(
                "internal server error : [rollback_payment]"
            )

    async def GET_ORDER_PAYMENTS(self, db: AsyncSession, order_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.order_id == order_id)
            )
            payments = result.scalar_one_or_none()
            if not payments:
                raise NotFoundException("order_id not found")
            return payments
        except NotFoundException:
            raise
        except Exception as e:
            print("------------------------")
            print(f"[get_order_payments] : {e}")
            raise InternalServerErrorException(
                "internal server error : [get_order_payments]"
            )

    async def GET_CUSTOMER_PAYMENTS(self, db: AsyncSession, user_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.user_id == user_id)
            )
            payments = result.scalars().unique().all()
            return payments
        except Exception as e:
            print("------------------------")
            print(f"[GET_CUSTOMER_PAYMENTS] : {e}")
            raise InternalServerErrorException(
                "internal server error : [GET_CUSTOMER_PAYMENTS]"
            )
