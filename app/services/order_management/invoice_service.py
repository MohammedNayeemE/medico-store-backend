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
    """
    Service class for managing invoices.
    
    Handles invoice generation, retrieval, and customer invoice management.
    """
    async def GET_INVOICE_DETAILS(self, db: AsyncSession, invoice_id: int):
        """
        Get detailed information about a specific invoice.
        
        Args:
            db: Database session
            invoice_id: Unique identifier of the invoice
        
        Returns:
            Invoice object with invoice details
        
        Raises:
            NotFoundException: If invoice not found
        """
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

    async def GET_CUSTOMER_INVOICES(
        self, db: AsyncSession, customer_id: int, role_id: int
    ):
        """
        Get all invoices for a customer (customers only).
        
        Args:
            db: Database session
            customer_id: Customer user ID
            role_id: User role ID (must be customer)
        
        Returns:
            List of invoices for the customer
        
        Raises:
            HTTPException (403): If user is not a customer
        """
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
