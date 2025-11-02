import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from models.enums import InvoicePaymentStatusEnum
from models.inventory_management_models import *
from models.order_management_models import *
from models.user_management_models import *
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


class InvoiceService:
    async def generate_invoice(
        self,
        db: AsyncSession,
        order_id: int,
        generated_by: int,
        include_taxes: bool = True,
        notes: str | None = None,
    ):
        result = await db.execute(select(Order).filter(Order.order_id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if hasattr(order, "invoice") and order.invoice is not None:
            raise HTTPException(
                status_code=400, detail="Invoice already exists for this order"
            )
        order_items = order.order_items
        if not order_items:
            raise HTTPException(status_code=400, detail="No order items found")
        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")
        discount_total = Decimal(str(order.discount_amount or 0.0))

        invoice_items_data = []

        # 4️⃣ For each item → find GST slab → compute taxes
        for item in order_items:
            # Fetch medicine + GST slab
            batch = item.batch  # OrderItem → MedicineBatch
            medicine = batch.medicine  # MedicineBatch → Medicine
            gst_slab = medicine.gst_slab  # Medicine → GSTSlab

            if not gst_slab:
                raise HTTPException(
                    status_code=400,
                    detail=f"GST slab not found for medicine {medicine.medicine_name}",
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
                    "quantity": quantity,
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

        # 5️⃣ Create invoice number
        invoice_number = (
            f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        # 6️⃣ Create FileAsset (simulate PDF for now)
        pdf_asset = FileAsset(
            file_name=f"{invoice_number}.pdf",
            file_type="application/pdf",
            path="/invoices/pdfs/",
        )
        db.add(pdf_asset)
        await db.flush()

        # 7️⃣ Create Invoice record
        invoice = Invoice(
            order_id=order.order_id,
            user_id=order.user_id,
            invoice_number=invoice_number,
            invoice_pdf_id=pdf_asset.asset_id,
            subtotal_amount=subtotal,
            total_tax=total_tax,
            gross_amount=gross,
            discount_amount=discount_total,
            payment_status=InvoicePaymentStatusEnum.unpaid,
        )
        db.add(invoice)
        await db.flush()

        # 8️⃣ Create InvoiceItems
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

    async def get_invoice_details(self, db: AsyncSession, invoice_id: int):
        result = await db.execute(
            select(Invoice).filter(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        return invoice

    async def get_customer_invoices(self, db: AsyncSession, customer_id: int):
        result = await db.execute(
            select(Invoice).filter(Invoice.user_id == customer_id)
        )
        invoices = result.scalars().all()
        return invoices

    async def update_invoice_status(
        self, db: AsyncSession, invoice_id: int, status: str, updated_by: int
    ):
        result = await db.execute(
            select(Invoice).filter(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        allowed = [e.value for e in InvoicePaymentStatusEnum]
        if status not in allowed:
            raise HTTPException(
                status_code=400, detail=f"Invalid status. Allowed: {allowed}"
            )

        invoice.payment_status = status
        await db.commit()
        await db.refresh(invoice)
        return {"message": f"Invoice status updated to {status}"}

    async def download_invoice_pdf(self, db: AsyncSession, invoice_id: int):
        result = await db.execute(
            select(Invoice).filter(Invoice.invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        pdf = invoice.invoice_pdf
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF file not found")

        return pdf.path  # you can stream file in actual implementation
