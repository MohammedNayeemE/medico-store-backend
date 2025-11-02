from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import parse_user_argument_for_enum

from app.models.enums import PaymentStatusEnum
from app.models.order_management_models import Order, Payment


class PaymentService:
    async def INITIATE_PAYMENT(
        self, db: AsyncSession, order_id: int, payment_mode: str, user_id: int
    ):
        try:
            result = await db.execute(select(Order).filter(Order.order_id == order_id))
            order_obj = result.scalar_one_or_none()
            if not order_obj:
                raise HTTPException(status_code=404, detail="order_id not found")
            existing = await db.execute(
                select(Payment).filter(
                    Payment.order_id == order_id,
                    Payment.status == PaymentStatusEnum.pending.value,
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=400, detail="Pending payment already exists"
                )
            new_payment = Payment(
                order_id=order_id,
                amount=order_obj.total_amount,
                status=PaymentStatusEnum.pending.value,
                payment_mode=payment_mode,
                user_id=user_id,
            )
            db.add(new_payment)
            await db.commit()
            await db.refresh(new_payment)
            return new_payment
        except Exception as e:
            print("------------------------")
            print(f"[initiate_payment] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [initiate_payment]"
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
                raise HTTPException(status_code=404, detail="payment_id not found")
            payment_obj.status = new_status.value
            if new_status == PaymentStatusEnum.completed:
                payment_obj.paid_at = paid_at or datetime.utcnow()
            await db.commit()
            await db.refresh(payment_obj)
            return payment_obj
        except Exception as e:
            print("------------------------")
            print(f"[update_payment_status] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [update_payment_status]",
            )

    async def ROLLBACK_PAYMENT(self, db: AsyncSession, payment_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.payment_id == payment_id)
            )
            payment_obj = result.scalar_one_or_none()
            if not payment_obj:
                raise HTTPException(status_code=404, detail="payment_id not found")
            payment_obj.status = PaymentStatusEnum.failed.value
            await db.commit()
            await db.refresh(payment_obj)
            return payment_obj
        except Exception as e:
            print("------------------------")
            print(f"[rollback_payment] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [rollback_payment]"
            )

    async def GET_ORDER_PAYMENTS(self, db: AsyncSession, order_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.order_id == order_id)
            )
            payments = result.scalar_one_or_none()
            if not payments:
                raise HTTPException(status_code=404, detail="order_id not found")
            return payments
        except HTTPException:
            raise
        except Exception as e:
            print("------------------------")
            print(f"[get_order_payments] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_order_payments]"
            )

    async def GET_CUSTOMER_PAYMENTS(self, db: AsyncSession, user_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.user_id == user_id)
            )
            payments = result.scalars().unique().all()
            return payments
        except HTTPException:
            raise
        except Exception as e:
            print("------------------------")
            print(f"[GET_CUSTOMER_PAYMENTS] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [GET_CUSTOMER_PAYMENTS]",
            )
