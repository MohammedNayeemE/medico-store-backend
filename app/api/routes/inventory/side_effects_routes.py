from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import SideEffectCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/side-effects", tags=["Medicine SideEffects"])
inventory_manager = InventoryManagementService()


@router.get("/download-template", description="download the side effect template")
async def download_template(
    current_user: User = Security(get_current_user, scopes=["side_effect:read"])
):
    result = await inventory_manager.DOWNLOAD_SIDE_EFFECT_TEMPLATE()
    return result


@router.post(
    "/bulk-upload-side-effects",
    description="bulk-upload-side-effects using excel or csv file",
)
async def bulk_upload_side_effects(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["side_effect:write"]),
    file: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_SIDE_EFFECTS(db=db, file=file)
    return result


@router.post("/", description="Create a side effect entry")
async def create_side_effect(
    current_user=Security(get_current_user, scopes=["side_effect:write"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_data: SideEffectCreate = Body(...),
):
    result = await inventory_manager.CREATE_SIDE_EFFECT(
        db=db, side_effect_data=side_effect_data
    )
    return result


@router.get("/", description="List all side effects with pagination")
async def list_all_side_effects(
    current_user=Security(get_current_user, scopes=["side_effect:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_SIDE_EFFECTS(
        db=db, skip=skip, limit=limit
    )
    return result


@router.get("/{side_effect_id}", description="Get side effect details by ID")
async def get_side_effects_by_id(
    current_user=Security(get_current_user, scopes=["side_effect:read"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_id: int = Path(...),
):
    result = await inventory_manager.GET_SIDE_EFFECT_BY_ID(
        db=db, side_effect_id=side_effect_id
    )
    return result


@router.put("/{side_effect_id}", description="Update a side effect by ID")
async def update_side_effect(
    side_effect_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["side_effect:write"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_data: SideEffectCreate = Body(...),
):
    result = await inventory_manager.UPDATE_SIDE_EFFECT(
        db=db, side_effect_id=side_effect_id, side_effect_data=side_effect_data
    )
    return result


@router.delete("/{side_effect_id}", description="Soft delete a side effect by ID")
async def soft_delete_side_effect(
    side_effect_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["side_effect:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_SIDE_EFFECT(
        db=db, side_effect_id=side_effect_id, deleted_by=current_user.user_id
    )
    return result
