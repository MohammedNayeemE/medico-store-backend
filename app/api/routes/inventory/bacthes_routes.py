from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import MedicineBatchCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/batches", tags=["Medicine Batches"])
inventory_manager = InventoryManagementService()


@router.post("/", description="Create a medicine batch entry")
async def create_batch(
    background_tasks: BackgroundTasks,
    current_user=Security(get_current_user, scopes=["batch:write"]),
    db: AsyncSession = Depends(get_postgres),
    batch_data: MedicineBatchCreate = Body(...),
):
    result = await inventory_manager.CREATE_MEDICINE_BATCH(
        db=db, batch_data=batch_data, background_tasks=background_tasks
    )
    return result


@router.get(
    "/", description="List medicine batches filtered by medicine and pagination"
)
async def list_all_batches(
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    medicine_id: int = Query(None),
):
    result = await inventory_manager.GET_MEDICINE_BATCHES(
        db=db, skip=skip, limit=limit, medicine_id=medicine_id
    )
    return result


@router.get("/low-stock", description="List low-stock medicine batches")
async def get_low_stock_items(
    threshold: int = Query(10, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    return await inventory_manager.GET_LOW_STOCK_ITEMS(db, threshold, skip, limit)


@router.get("/expired", description="List expired medicine batches")
async def get_expired_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    return await inventory_manager.GET_EXPIRED_BATCHES(db, skip, limit)


@router.get("/expiring-soon", description="List batches expiring soon")
async def get_expiring_soon(
    days: int = Query(30, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    return await inventory_manager.GET_EXPIRING_SOON(db, days, skip, limit)


@router.get("/stock-summary", description="List total stock summary per medicine")
async def get_stock_summary(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    return await inventory_manager.GET_STOCK_SUMMARY(db, skip, limit)


@router.get("/{batch_id}", description="Get batch details by ID")
async def get_batch_by_id(
    batch_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["batch:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_BATCH_BY_ID(db=db, batch_id=batch_id)
    return result


@router.put("/{batch_id}", description="Update a batch by ID")
async def update_batch(
    batch_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["batch:write"]),
    db: AsyncSession = Depends(get_postgres),
    batch_data: MedicineBatchCreate = Body(...),
):
    result = await inventory_manager.UPDATE_BATCH(
        db=db, batch_id=batch_id, batch_data=batch_data
    )
    return result


@router.delete("/{batch_id}", description="Soft delete a batch by ID")
async def soft_delete_batch(
    batch_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["batch:delete"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_BATCH(
        db=db, batch_id=batch_id, deleted_by=current_user.user_id
    )
    return result
