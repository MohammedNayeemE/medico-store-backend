from fastapi import APIRouter, Body, Path, Depends, Security
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres

router = APIRouter(prefix="/payments", tags=["Payments"])

# ================== PAYMENTS ===================== #

@router.post(
    "/initiate",
    description="Start/initiate a payment for an order",
)
async def initiate_payment(
    order_id: int = Body(..., embed=True),
    amount: Optional[float] = Body(None, embed=True),
    method: Optional[str] = Body(None, embed=True),
    currency: Optional[str] = Body("INR", embed=True),
    initiated_by: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    """Initiate a payment for the specified order with optional metadata."""
    pass

@router.get(
    "/{order_id}",
    description="Get all payments related to a specific order",
)
async def get_order_payments(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """List all payment attempts/records for the given order_id."""
    pass

@router.put(
    "/{payment_id}/status",
    description="Update payment status (pending, paid, failed)",
)
async def update_payment_status(
    payment_id: int = Path(...),
    status: str = Body(..., embed=True),
    updated_by: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Update the status for a payment. Allowed values: pending, paid, failed."""
    pass

@router.get(
    "/customer/{customer_id}",
    description="List payment history for a specific customer",
)
async def get_customer_payment_history(
    customer_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """Fetch all payment records associated with the specified customer."""
    pass
