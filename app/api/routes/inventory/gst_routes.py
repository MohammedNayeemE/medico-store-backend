from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import GSTSlabCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/gst-slabs", tags=["GST Slabs"])
inventory_manager = InventoryManagementService()


@router.get("/download-template", description="download the GST slab template")
async def download_template(
    current_user: User = Security(get_current_user, scopes=["gst:read"])
):
    result = await inventory_manager.DOWNLOAD_GST_SLAB_TEMPLATE()
    return result


@router.post(
    "/bulk-upload-gst-slabs",
    description="bulk-upload-gst-slabs using excel or csv file",
)
async def bulk_upload_gst_slabs(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["gst:write"]),
    file: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_GST_SLABS(db=db, file=file)
    return result


@router.post("/", description="Create a GST slab entry")
async def create_gst_slab(
    current_user=Security(get_current_user, scopes=["gst:write"]),
    db: AsyncSession = Depends(get_postgres),
    gst_slab_data: GSTSlabCreate = Body(...),
):
    result = await inventory_manager.CREATE_GST_SLAB(db=db, gst_slab_data=gst_slab_data)
    return result


@router.get("/", description="List all GST slabs with pagination")
async def list_all_gst_slabs(
    current_user=Security(get_current_user, scopes=["gst:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_GST_SLABS(db=db, skip=skip, limit=limit)
    return result


@router.get("/{hsn_code}", description="Get a GST slab by HSN code")
async def get_gst_slab(
    hsn_code: str = Path(...),
    current_user=Security(get_current_user, scopes=["gst:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_GST_SLAB_BY_HSN(db=db, hsn_code=hsn_code)
    return result


@router.put("/{hsn_code}", description="Update a GST slab by HSN code")
async def update_gst_slab(
    hsn_code: str = Path(...),
    current_user=Security(get_current_user, scopes=["gst:write"]),
    db: AsyncSession = Depends(get_postgres),
    gst_slab_data: GSTSlabCreate = Body(...),
):
    result = await inventory_manager.UPDATE_GST_SLAB(
        db=db, hsn_code=hsn_code, gst_slab_data=gst_slab_data
    )
    return result


@router.delete("/{hsn_code}", description="Soft delete a GST slab by HSN code")
async def soft_delete_gst_slab(
    hsn_code: str = Path(...),
    current_user: User = Security(get_current_user, scopes=["gst:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_GST_SLAB(
        db=db, hsn_code=hsn_code, deleted_by=current_user.user_id
    )
    return result
