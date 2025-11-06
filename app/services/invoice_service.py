import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.enums import InvoicePaymentStatusEnum
from app.models.inventory_management_models import *
from app.models.order_management_models import *
from app.models.user_management_models import *


class InvoiceService:
    async def GENERATE_INVOICE(
        self,
        db: AsyncSession,
        order_id: int,
        include_taxes: bool = True,
        notes: str | None = None,
    ):
        try:
            # Eager-load everything we will access to avoid lazy loads
            result = await db.execute(
                select(Order)
                .options(
                    selectinload(Order.invoice),  # <<-- important: eager-load invoice
                    selectinload(Order.order_items)
                    .selectinload(OrderItem.batch)
                    .selectinload(MedicineBatch.medicine)
                    .selectinload(Medicine.gst_slab),
                )
                .filter(Order.order_id == order_id)
            )
            order = result.scalar_one_or_none()
            if not order:
                raise NotFoundException("Order not found")

            # invoice now safe to access because we eager-loaded it
            if order.invoice:
                raise BadRequestException("Invoice already exists for this order")

            order_items = order.order_items
            if not order_items:
                raise BadRequestException("No order items found")

            subtotal = Decimal("0.00")
            total_tax = Decimal("0.00")
            discount_total = Decimal(0.0)
            invoice_items_data = []

            for item in order_items:
                batch = item.batch
                if not batch:
                    raise BadRequestException(
                        f"Batch not found for order item {item.order_item_id}"
                    )
                medicine = batch.medicine
                if not medicine:
                    raise BadRequestException(
                        f"Medicine not found for batch {batch.batch_id}"
                    )
                gst_slab = medicine.gst_slab
                if not gst_slab:
                    raise BadRequestException(
                        f"GST slab not found for medicine {medicine.medicine_name}"
                    )

                gst_rate = Decimal(str(gst_slab.gst_rate)) / Decimal("100.00")
                quantity = Decimal(str(item.quantity))
                unit_price = Decimal(str(batch.selling_price))
                line_total = quantity * unit_price

                if include_taxes:
                    tax_amount = line_total * gst_rate
                    cgst = tax_amount / 2
                    sgst = tax_amount / 2
                    igst = Decimal("0.00")  # assuming intra-state sale
                else:
                    tax_amount = cgst = sgst = igst = Decimal("0.00")

                total_amount = line_total + tax_amount

                invoice_items_data.append(
                    {
                        "medicine_id": medicine.medicine_id,
                        "quantity": int(quantity),
                        "unit_price": unit_price,
                        "gst_rate": gst_slab.gst_rate,
                        "cgst": cgst,
                        "sgst": sgst,
                        "igst": igst,
                        "total_amount": total_amount,
                    }
                )
                subtotal += line_total
                total_tax += tax_amount

            gross = subtotal + total_tax - discount_total
            invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # NOTE: invoice_pdf_id is defined as nullable=False in your model.
            # You MUST either supply a valid invoice_pdf_id or change the model to nullable=True.
            invoice = Invoice(
                order_id=order.order_id,
                user_id=order.customer_id,  # use customer_id (Order has no user_id)
                invoice_number=invoice_number,
                invoice_pdf_id=3,  # <-- will fail if column is NOT NULL; change model or provide id
                subtotal_amount=subtotal,
                total_tax=total_tax,
                gross_amount=gross,
                discount_amount=discount_total,
                payment_status=InvoicePaymentStatusEnum.paid,
            )

            db.add(invoice)
            await db.flush()  # now invoice.invoice_id is available

            for data in invoice_items_data:
                db.add(InvoiceItem(invoice_id=invoice.invoice_id, **data))

            await db.commit()
            await db.refresh(invoice)

            return {
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "subtotal": float(subtotal),
                "total_tax": float(total_tax),
                "gross_amount": float(gross),
                "discount": float(discount_total),
                "items": [
                    {
                        "medicine_id": i["medicine_id"],
                        "unit_price": float(i["unit_price"]),
                        "gst_rate": float(i["gst_rate"]),
                        "cgst": float(i["cgst"]),
                        "sgst": float(i["sgst"]),
                        "total_amount": float(i["total_amount"]),
                    }
                    for i in invoice_items_data
                ],
            }

        except (BadRequestException, NotFoundException):
            raise
        except Exception as e:
            print("---------------------------------------")
            print(f"[GENERATE_INVOICE] : {e}")
            await db.rollback()
            raise InternalServerErrorException(
                f"internal server error : [GENERATE_INVOICE]"
            )

    async def GET_INVOICE_DETAILS(self, db: AsyncSession, invoice_id: int):
        try:
            result = await db.execute(
                select(Invoice).filter(Invoice.invoice_id == invoice_id)
            )
            invoice = result.scalar_one_or_none()
            if not invoice:
                raise NotFoundException("Invoice not found")
            return invoice
        except NotFoundException:
            raise
        except Exception as e:
            print("-------------------------------------------------")
            print(f"[GET_INVOICE_DETAILS]: {e}")
            raise InternalServerErrorException(
                f"internal server error : [GET_INVOICE_DETAILS]"
            )

    async def GET_CUSTOMER_INVOICES(self, db: AsyncSession, customer_id: int):
        try:
            result = await db.execute(
                select(Invoice).filter(Invoice.user_id == customer_id)
            )
            invoices = result.scalars().all()
            return invoices
        except Exception as e:
            print("---------------------------------------------")
            print(f"[GET_CUSTOMER_INVOICES]: {e}")
            raise InternalServerErrorException(
                f"internal server error: [GET_CUSTOMER_INVOICES]"
            )

    # async def update_invoice_status(
    #     self, db: AsyncSession, invoice_id: int, status: str, updated_by: int
    # ):
    #     result = await db.execute(
    #         select(Invoice).filter(Invoice.invoice_id == invoice_id)
    #     )
    #     invoice = result.scalar_one_or_none()
    #     if not invoice:
    #         raise HTTPException(status_code=404, detail="Invoice not found")
    #
    #     allowed = [e.value for e in InvoicePaymentStatusEnum]
    #     if status not in allowed:
    #         raise HTTPException(
    #             status_code=400, detail=f"Invalid status. Allowed: {allowed}"
    #         )
    #
    #     invoice.payment_status = status
    #     await db.commit()
    #     await db.refresh(invoice)
    #     return {"message": f"Invoice status updated to {status}"}

    # async def download_invoice_pdf(self, db: AsyncSession, invoice_id: int):
    #     result = await db.execute(
    #         select(Invoice).filter(Invoice.invoice_id == invoice_id)
    #     )
    #     invoice = result.scalar_one_or_none()
    #     if not invoice:
    #         raise HTTPException(status_code=404, detail="Invoice not found")
    #
    #     pdf = invoice.invoice_pdf
    #     if not pdf:
    #         raise HTTPException(status_code=404, detail="PDF file not found")
    #
    #     return pdf.path  # you can stream file in actual implementation
