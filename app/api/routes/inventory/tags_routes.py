from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import TagCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/tags", tags=["Tags"])
inventory_manager = InventoryManagementService()


@router.get("/download-template", description="download the tag template")
async def download_template(
    current_user: User = Security(get_current_user, scopes=["admin:read"])
):
    result = await inventory_manager.DOWNLOAD_TAG_TEMPLATE()
    return result


@router.post(
    "/bulk-upload-tags",
    description="bulk-upload-tags using excel or csv file",
)
async def bulk_upload_tags(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    file: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_TAGS(db=db, file=file)
    return result


@router.post("/", description="Create a new tag")
async def create_tag(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    tag_data: TagCreate = Body(...),
):
    result = await inventory_manager.CREATE_TAG(db=db, tag_data=tag_data)
    return result


@router.get("/", description="List all tags with pagination")
async def list_all_tags(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_TAGS(db=db, skip=skip, limit=limit)
    return result


@router.get("/{tag_id}", description="Get tag details by ID")
async def get_tag_details(
    tag_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_TAG_DETAILS_BY_ID(db=db, tag_id=tag_id)
    return result


@router.put("/{tag_id}", description="Update a tag by ID")
async def update_tag(
    tag_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    tag_data: TagCreate = Body(...),
):
    result = await inventory_manager.UPDATE_TAG(db=db, tag_id=tag_id, tag_data=tag_data)
    return result


@router.delete("/{tag_id}", description="Soft delete a tag by ID")
async def soft_delete_tag(
    tag_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_TAG(
        db=db, tag_id=tag_id, deleted_by=current_user.user_id
    )
    return result

