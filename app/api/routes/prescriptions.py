from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.enums import OrderStatusEnum
from app.models.user_management_models import User
from app.schemas.inventory_schemas import VerifyPrescription
from app.schemas.order_schemas import OrderCreate, OrderItemCreate, OrderItemUpdate
from app.services.order_management_service import OrderService

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])
order_manager = OrderService()


@router.post(
    "/upload",
    description="Upload a new prescription with file and customer_id",
)
async def upload_prescription(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.UPLOAD_PRESCRIPTION(
        db=db, file=file, customer_id=current_user.user_id, bucket=bucket
    )
    return result


@router.get(
    "/myprescriptions/",
    description="Get all prescriptions for a specific customer",
)
async def get_customer_prescriptions(
    skip: int = Query(0, ge=0, description="range"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_CUSTOMER_PRESCRIPTIONS(
        db=db, customer_id=current_user.user_id, skip=skip, limit=limit
    )
    return result


@router.get(
    "/details/{prescription_id}",
    description="Get prescription details and items",
)
async def get_prescription_details(
    prescription_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_PRESCRIPTION_DETAILS(
        db=db, prescription_id=prescription_id
    )
    return result


@router.put(
    "/verify/{prescription_id}",
    description="Mark prescription as verified or rejected (pharmacist/admin)",
)
async def verify_prescription(
    prescription_id: int = Path(...),
    prescription_data: VerifyPrescription = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.VERIFY_PRESCRIPTION(
        db=db,
        prescription_id=prescription_id,
        is_verified=prescription_data.is_verified,
        verified_by=current_user.user_id,
        notes=prescription_data.notes,
    )
    return result


@router.delete("/{prescription_id}", description="Soft delete a prescription")
async def soft_delete_prescription(
    prescription_id: int = Path(...),
    deleted_by: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = order_manager.SOFT_DELETE_PRESCRIPTION(
        db=db, prescription_id=prescription_id, deleted_by=current_user.user_id
    )
    return result
