from typing import List

from fastapi import APIRouter, Body, Depends, File, Path, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import AlternativeCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/alternatives", tags=["Medicine Alternatives"])
inventory_manager = InventoryManagementService()


@router.post("/{medicine_id}/alternatives")
async def link_medicine_to_alternatives(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["alternate:write"]),
    db: AsyncSession = Depends(get_postgres),
    alternative_data: AlternativeCreate = Body(...),
):
    result = await inventory_manager.LINK_MEDICINE_ALTERNATIVES(
        db=db, medicine_id=medicine_id, alternative_IDS=alternative_data
    )
    return result


@router.get("/{medicine_id}")
async def get_medicine_alternatives(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["alternate:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.LIST_ALL_MEDICINE_ALTERNATIVES(
        db=db, medicine_id=medicine_id
    )
    return result


@router.put("/{medicine_id}")
async def update_link_medicine_to_alternatives(
    medicine_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["alternate:update"]),
    db: AsyncSession = Depends(get_postgres),
    alternative_ids: List[int] = Body(...),
):
    result = await inventory_manager.UPDATE_LINK_MEDICINES_TO_ALTERNATIVES(
        db=db,
        alternative_ids=alternative_ids,
        medicine_id=medicine_id,
        deleted_by=current_user.user_id,
    )
    return result


