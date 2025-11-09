import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.enums import (
    InvoicePaymentStatusEnum,
    OrderStatusEnum,
    PaymentStatusEnum,
    RequestOrderStatusEnum,
)
from app.models.inventory_management_models import Medicine, MedicineBatch
from app.models.order_management_models import (
    Coupon,
    Discount,
    Invoice,
    InvoiceItem,
    Order,
    OrderItem,
    Payment,
    RequestOrder,
    RequestOrderItem,
)
from app.services.order_management.order_management_service import OrderService


class PaymentService:
    def __init__(self) -> None:
        self.order_service = OrderService()

    async def _reserve_for_item(
        self, db: AsyncSession, req_item: RequestOrderItem, order_id: int
    ) -> Tuple[bool, int]:
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
            order_items_to_create.append(
                OrderItem(
                    order_id=order_id,
                    batch_id=batch.batch_id,
                    quantity=take,
                    price=req_item.estimated_price or 0,
                    is_backordered=False,
                    backordered_qty=0,
                )
            )
        if needed > 0:
            order_items_to_create.append(
                OrderItem(
                    order_id=order_id,
                    batch_id=None,
                    quantity=0,
                    price=req_item.estimated_price or 0,
                    is_backordered=True,
                    backordered_qty=needed,
                )
            )
        if order_items_to_create:
            db.add_all(order_items_to_create)
        return (needed == 0), reserved_total

    async def _release_reservation_for_order(
        self, db: AsyncSession, order_id: int
    ) -> None:
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
        batch_ids = [oi.batch_id for oi in reserved_items if oi.batch_id]
        batch_q = (
            select(MedicineBatch)
            .filter(MedicineBatch.batch_id.in_(batch_ids))
            .with_for_update()
        )
        batch_res = await db.execute(batch_q)
        batches = {b.batch_id: b for b in batch_res.scalars().all()}
        for oi in reserved_items:
            batch = batches.get(oi.batch_id)
            if batch:
                batch.reserved_quantity = max(
                    0, int(batch.reserved_quantity or 0) - int(oi.quantity)
                )

    async def _finalize_reserved_items_on_payment(
        self, db: AsyncSession, order_id: int
    ) -> None:
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
        batch_ids = [oi.batch_id for oi in reserved_items if oi.batch_id]
        batch_q = (
            select(MedicineBatch)
            .filter(MedicineBatch.batch_id.in_(batch_ids))
            .with_for_update()
        )
        batch_res = await db.execute(batch_q)
        batches = {b.batch_id: b for b in batch_res.scalars().all()}
        for oi in reserved_items:
            batch = batches.get(oi.batch_id)
            if batch:
                sold = int(oi.quantity)
                batch.quantity = max(0, batch.quantity - sold)
                batch.reserved_quantity = max(0, batch.reserved_quantity - sold)

    async def _calculate_and_set_order_totals(
        self, db: AsyncSession, order: Order, coupon_code: Optional[str] = None
    ) -> None:
        """
        Expects OrderItem.price to be a per-unit price.
        """
        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")
        total_discount = Decimal("0.00")
        now = datetime.now(timezone.utc)

        q = (
            select(OrderItem)
            .options(
                selectinload(OrderItem.batch)
                .selectinload(MedicineBatch.medicine)
                .selectinload(Medicine.gst_slab)
            )
            .filter(OrderItem.order_id == order.order_id)
        )
        res = await db.execute(q)
        order_items: List[OrderItem] = res.scalars().all()
        active_discount = None
        if coupon_code:
            coupon_q = (
                select(Coupon)
                .options(selectinload(Coupon.discount))
                .filter(
                    Coupon.code == coupon_code,
                    Coupon.valid_from <= now,
                    Coupon.valid_to >= now,
                    Coupon.is_deleted == False,
                )
            )
            coupon_res = await db.execute(coupon_q)
            coupon = coupon_res.scalar_one_or_none()
            if coupon:
                active_discount = coupon.discount
                coupon.used_count = (coupon.used_count or 0) + 1
        discount_q = (
            select(Discount)
            .filter(
                Discount.is_deleted == False,
                Discount.start_date <= now,
                Discount.end_date >= now,
            )
            .options(
                selectinload(Discount.discount_type),
                selectinload(Discount.medicines),
                selectinload(Discount.categories),
            )
        )
        discount_res = await db.execute(discount_q)
        active_discounts = discount_res.scalars().all()
        for oi in order_items:
            if not oi.batch or not oi.batch.medicine:
                continue
            med = oi.batch.medicine
            qty = Decimal(str(oi.quantity))
            unit_price = Decimal(str(oi.price or 0))  # expected per-unit price
            line_total = qty * unit_price
            applicable_discount = active_discount
            if not applicable_discount:
                for d in active_discounts:
                    med_ids = [
                        dm.medicine_id for dm in d.medicines if not dm.is_deleted
                    ]
                    cat_ids = [
                        dc.category_id for dc in d.categories if not dc.is_deleted
                    ]
                    if med.medicine_id in med_ids or (
                        med.category_id and med.category_id in cat_ids
                    ):
                        applicable_discount = d
                        break
            discount_amt = Decimal("0.00")
            if applicable_discount and line_total >= (
                applicable_discount.min_purchase_amount or 0
            ):
                if applicable_discount.discount_type.type_name.lower() == "percentage":
                    discount_amt = (
                        line_total * Decimal(applicable_discount.value)
                    ) / Decimal("100.0")
                else:
                    discount_amt = Decimal(applicable_discount.value)
                if applicable_discount.max_discount_amount:
                    discount_amt = min(
                        discount_amt, Decimal(applicable_discount.max_discount_amount)
                    )
            discounted_price = line_total - discount_amt
            gst_rate = (
                (Decimal(str(med.gst_slab.gst_rate)) / Decimal("100.00"))
                if med.gst_slab
                else Decimal("0.00")
            )
            tax_amt = discounted_price * gst_rate

            subtotal += discounted_price
            total_tax += tax_amt
            total_discount += discount_amt
        gross = subtotal + total_tax
        order.total_amount = gross.quantize(Decimal("0.01"))
        order.updated_at = now
        await db.flush()

    async def _generate_invoice(self, db: AsyncSession, order: Order):
        invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now(timezone.utc)
        q = (
            select(OrderItem)
            .options(
                selectinload(OrderItem.batch)
                .selectinload(MedicineBatch.medicine)
                .selectinload(Medicine.gst_slab)
            )
            .filter(OrderItem.order_id == order.order_id, OrderItem.is_deleted == False)
        )
        res = await db.execute(q)
        order_items = res.scalars().all()
        subtotal, total_tax = Decimal("0.00"), Decimal("0.00")
        invoice_items = []
        for item in order_items:
            if not item.batch or not item.batch.medicine:
                continue
            med = item.batch.medicine
            qty = Decimal(str(item.quantity))
            price = Decimal(str(item.price))
            gst_rate = Decimal(str(med.gst_slab.gst_rate)) / Decimal("100.00")
            tax_amt = qty * price * gst_rate
            total = (qty * price) + tax_amt
            subtotal += qty * price
            total_tax += tax_amt
            invoice_items.append(
                InvoiceItem(
                    medicine_id=med.medicine_id,
                    quantity=int(qty),
                    unit_price=price,
                    gst_rate=med.gst_slab.gst_rate,
                    cgst=tax_amt / 2,
                    sgst=tax_amt / 2,
                    igst=Decimal("0.00"),
                    total_amount=total,
                )
            )
        invoice = Invoice(
            order_id=order.order_id,
            user_id=order.customer_id,
            invoice_number=invoice_number,
            subtotal_amount=subtotal,
            total_tax=total_tax,
            gross_amount=subtotal + total_tax,
            discount_amount=Decimal("0.00"),
            payment_status=InvoicePaymentStatusEnum.paid.value,
        )
        db.add(invoice)
        await db.flush()
        for item in invoice_items:
            item.invoice_id = invoice.invoice_id
            db.add(item)
        order.invoice = invoice
        await db.flush()

    async def INITIATE_PAYMENT(
        self,
        db: AsyncSession,
        request_order_id: int,
        payment_mode: str,
        user_id: int,
        role_id: int,
    ):
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
            result = await db.execute(
                select(RequestOrder).filter(
                    RequestOrder.request_order_id == request_order_id
                )
            )
            request_order = result.scalar_one_or_none()
            if not request_order or request_order.status not in [
                RequestOrderStatusEnum.awaiting_payment.value,
                RequestOrderStatusEnum.approved.value,
            ]:
                raise BadRequestException("Payment not allowed at this stage")
            if request_order.updated_at + timedelta(days=1) < datetime.now(
                timezone.utc
            ):
                raise BadRequestException("Payment link expired")
            new_order = await self.order_service.CONVERT_REQUEST_TO_ORDER(
                db=db, request_order_id=request_order_id
            )
            new_order.status = (
                OrderStatusEnum.pending.value
                if isinstance(OrderStatusEnum.pending, Enum)
                else OrderStatusEnum.pending
            )
            db.add(new_order)
            await db.flush()
            query = select(RequestOrderItem).filter(
                RequestOrderItem.request_order_id == request_order_id,
                RequestOrderItem.is_deleted == False,
            )
            req_res = await db.execute(query)
            req_items = req_res.scalars().all()
            is_allocated_full, is_reserved = True, False
            for req_item in req_items:
                fully_allocated, reserved_qty = await self._reserve_for_item(
                    db, req_item, new_order.order_id
                )
                if reserved_qty > 0:
                    is_reserved = True
                if not fully_allocated:
                    is_allocated_full = False
            now = datetime.now(timezone.utc)
            new_order.predicted_delivery_date = now + timedelta(
                days=1 if is_allocated_full else 2
            )
            # -------------------------
            # Safety normalization:
            # If some OrderItem.price was mistakenly stored as line_total (unit_price * qty),
            # convert it back to per-unit price before calculating totals.
            # This uses the batch.medicine.price as a hint; if batch.medicine.price exists,
            # and oi.price is significantly larger than the medicine base price, divide by quantity.
            # -------------------------
            oi_q = select(OrderItem).filter(OrderItem.order_id == new_order.order_id)
            oi_res = await db.execute(
                oi_q.options(
                    selectinload(OrderItem.batch).selectinload(MedicineBatch.medicine)
                )
            )
            order_items = oi_res.scalars().all()
            for oi in order_items:
                try:
                    if oi.price is None:
                        continue
                    oi_price_dec = Decimal(str(oi.price))
                    qty_dec = Decimal(str(oi.quantity or 1))
                    # if batch.medicine.price exists, use it to decide whether oi.price is a line total
                    med_price_dec = None
                    if (
                        oi.batch
                        and oi.batch.medicine
                        and getattr(oi.batch.medicine, "price", None) is not None
                    ):
                        med_price_dec = Decimal(str(oi.batch.medicine.price))
                    # Heuristic:
                    # - If oi.price is roughly equal to med.price => it's unit price -> keep
                    # - If oi.price is roughly equal to med.price * qty -> it's line total -> convert
                    # If med_price is not available, fallback to dividing when oi_price / qty is much smaller than oi_price
                    converted = False
                    if med_price_dec is not None:
                        if (
                            oi_price_dec >= (med_price_dec * qty_dec * Decimal("0.9"))
                            and qty_dec > 1
                        ):
                            # looks like a line total (or close to it)
                            new_unit_price = (oi_price_dec / qty_dec).quantize(
                                Decimal("0.01")
                            )
                            oi.price = float(new_unit_price)
                            db.add(oi)
                            converted = True
                    else:
                        # no med price available — if price significantly larger than 1*qty, convert
                        if oi_price_dec > qty_dec * Decimal("1.0") and qty_dec > 1:
                            # convert fallback (safe)
                            new_unit_price = (oi_price_dec / qty_dec).quantize(
                                Decimal("0.01")
                            )
                            oi.price = float(new_unit_price)
                            db.add(oi)
                            converted = True
                    if converted:
                        # optional: log a debug message
                        print(
                            f"[INITIATE_PAYMENT] normalized order_item id={getattr(oi,'order_item_id',None)} price -> {oi.price}"
                        )
                except (InvalidOperation, ZeroDivisionError):
                    # skip problematic rows (shouldn't normally happen)
                    continue
            await db.flush()
            await self._calculate_and_set_order_totals(
                db=db,
                order=new_order,
                coupon_code=getattr(request_order, "coupon_code", None),
            )
            new_payment = Payment(
                order_id=new_order.order_id,
                amount=float(new_order.total_amount),
                status=PaymentStatusEnum.pending.value,
                payment_mode=payment_mode,
                user_id=user_id,
                transaction_id=f"TXN-{uuid.uuid4().hex.upper()}",
            )
            db.add(new_payment)
            await db.commit()
            await db.refresh(new_payment)
            await db.refresh(new_order)
            return new_payment
        except Exception as e:
            print("======================================")
            print(f"[INITIATE_PAYMENT] Error: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "Internal server error: [INITIATE_PAYMENT]"
            )

    async def UPDATE_PAYMENT_STATUS(
        self,
        db: AsyncSession,
        payment_id: int,
        new_status: PaymentStatusEnum,
        paid_at: Optional[datetime] = None,
    ):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.payment_id == payment_id)
            )
            payment_obj = result.scalar_one_or_none()
            if not payment_obj:
                raise NotFoundException("Payment not found")
            if (
                payment_obj.status == new_status.value
                and payment_obj.status != "failed"
            ):
                raise BadRequestException("Invalid status update")
            if new_status == PaymentStatusEnum.completed:
                payment_obj.status = PaymentStatusEnum.completed.value
                payment_obj.paid_at = paid_at or datetime.now(timezone.utc)
                await self._finalize_reserved_items_on_payment(db, payment_obj.order_id)

                order_res = await db.execute(
                    select(Order).filter(Order.order_id == payment_obj.order_id)
                )
                order = order_res.scalar_one_or_none()
                if order:
                    order.status = OrderStatusEnum.confirmed.value

                await self._generate_invoice(db, order)
                await db.commit()
                await db.refresh(payment_obj)
                return payment_obj

            if new_status == PaymentStatusEnum.failed:
                payment_obj.status = PaymentStatusEnum.failed.value
                await self._release_reservation_for_order(db, payment_obj.order_id)
                await db.commit()
                await db.refresh(payment_obj)
                return payment_obj

            payment_obj.status = new_status.value
            await db.commit()
            await db.refresh(payment_obj)
            return payment_obj

        except Exception as e:
            print("======================================")
            print(f"[UPDATE_PAYMENT_STATUS] Error: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "Internal server error: [UPDATE_PAYMENT_STATUS]"
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
            print(f"[GET_ORDER_PAYMENTS] Error: {e}")
            raise InternalServerErrorException(
                "Internal server error: [GET_ORDER_PAYMENTS]"
            )

    async def GET_CUSTOMER_PAYMENTS(self, db: AsyncSession, user_id: int):
        try:
            result = await db.execute(
                select(Payment).filter(Payment.user_id == user_id)
            )
            payments = result.scalars().unique().all()
            return payments
        except Exception as e:
            print(f"[GET_CUSTOMER_PAYMENTS] Error: {e}")
            raise InternalServerErrorException(
                "Internal server error: [GET_CUSTOMER_PAYMENTS]"
            )
