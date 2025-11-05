from fastapi import APIRouter, Body, Depends, Path, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.request_medicines_schemas import (
    MedicineRequestCreate,
    MedicineRequestVerify,
)
from app.services.request_medicine_service import RequestMedicineService

router = APIRouter(prefix="/request-medicine", tags=["Medicine Requests"])

rq_manager = RequestMedicineService()


@router.post("/", description="Create a new medicine request")
async def create_medicine_request(
    request_data: MedicineRequestCreate = Body(...),
    current_user: User = Security(get_current_user, scopes=["customer:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await rq_manager.CREATE_MEDICINE_REQUEST(
        db=db, user_id=current_user.user_id, request_data=request_data
    )
    return result


@router.get("/my", description="Get all medicine requests by the logged-in user")
async def get_my_medicine_requests(
    current_user: User = Security(get_current_user, scopes=["customer:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await rq_manager.GET_USER_REQUESTS(
        db=db, user_id=current_user.user_id, skip=skip, limit=limit
    )
    return result


@router.get("/{request_id}", description="Get details of a specific medicine request")
async def get_medicine_request_details(
    request_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["customer:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await rq_manager.GET_REQUEST_DETAILS(
        request_id=request_id, db=db, user_id=current_user.user_id
    )
    return result


@router.delete("/{request_id}", description="Soft delete a specific medicine request")
async def delete_medicine_request(
    request_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["customer:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await rq_manager.SOFT_DELETE_REQUEST(
        db=db, user_id=current_user.user_id, request_id=request_id
    )
    return result


@router.get("/admin/all", description="View all medicine requests in the system")
async def get_all_medicine_requests(
    current_user: User = Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
):
    result = await rq_manager.GET_ALL_REQUESTS(db=db, skip=skip, limit=limit)
    return result


@router.put(
    "/admin/verify/{request_id}", description="Verify or reject a medicine request"
)
async def verify_medicine_request(
    request_id: int = Path(...),
    verify_data: MedicineRequestVerify = Body(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await rq_manager.VERIFY_MEDICINE_REQUEST(
        db=db,
        request_id=request_id,
        admin_id=current_user.user_id,
        verify_data=verify_data,
    )
    return result
