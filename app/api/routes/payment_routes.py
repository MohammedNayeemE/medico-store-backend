import random
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.enums import PaymentStatusEnum
from app.models.user_management_models import User
from app.services.order_management.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])
payment_manager = PaymentService()

# ================== PAYMENTS ===================== #


@router.post(
    "/initiate",
    description="Start/initiate a payment for an order",
)
async def initiate_payment(
    request_order_id: int = Body(...),
    method: str = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["payment:write"]),
):
    result = await payment_manager.INITIATE_PAYMENT(
        db=db,
        request_order_id=request_order_id,
        payment_mode=method,
        user_id=current_user.user_id,
        role_id=current_user.role_id,
    )
    return result


@router.get(
    "/mypayments",
    description="List payment history for a specific customer",
)
async def get_customer_payment_history(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["payment:read"]),
):
    result = await payment_manager.GET_CUSTOMER_PAYMENTS(
        db=db, user_id=current_user.user_id
    )
    return result


@router.get(
    "/{order_id}",
    description="Get all payments related to a specific order",
)
async def get_order_payments(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["payment:read"]),
):
    result = await payment_manager.GET_ORDER_PAYMENTS(db=db, order_id=order_id)
    return result


@router.patch(
    "/{payment_id}/status",
    description="Update payment status (pending, paid, failed)",
)
async def update_payment_status(
    payment_id: int = Path(...),
    status: PaymentStatusEnum = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["payment:update"]),
):
    result = await payment_manager.UPDATE_PAYMENT_STATUS(
        db=db, payment_id=payment_id, new_status=status
    )
    return result


@router.post("/simulate_callback")
async def simulate_payment_callback(
    payment_id: int, db: AsyncSession = Depends(get_postgres)
):
    """Simulates payment gateway result (success/failure randomly)."""
    simulated_status = random.choice(
        [PaymentStatusEnum.completed, PaymentStatusEnum.failed]
    )
    result = await payment_manager.UPDATE_PAYMENT_STATUS(
        db=db, payment_id=payment_id, new_status=simulated_status
    )
    return result


@router.patch("/{payment_id}/rollback", include_in_schema=False)
async def rollback_payment(
    payment_id: int = Path(...), db: AsyncSession = Depends(get_postgres)
):
    result = await payment_manager.ROLLBACK_PAYMENT(db=db, payment_id=payment_id)
    return result
