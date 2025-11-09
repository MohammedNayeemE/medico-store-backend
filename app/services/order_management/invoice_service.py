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
