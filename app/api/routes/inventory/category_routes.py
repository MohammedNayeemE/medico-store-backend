from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import CategoryCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/categories", tags=["Categories"])
inventory_manager = InventoryManagementService()


@router.get("/download-template", description="download the category template")
async def download_template(
    current_user: User = Security(get_current_user, scopes=["admin:read"])
):
    result = await inventory_manager.DOWNLOAD_CATEGORY_TEMPLATE()
    return result


@router.post(
    "/bulk-upload-categories",
    description="bulk-upload-categories using excel or csv file",
)
async def bulk_upload_categories(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    file: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_CATEGORIES(db=db, file=file)
    return result


@router.post("/", description="Create a new category")
async def create_category(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    category_data: CategoryCreate = Body(...),
):
    result = await inventory_manager.CREATE_CATEGORY(db=db, category_data=category_data)
    return result


@router.get("/", description="List all categories with pagination")
async def list_all_categories(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_ALL_CATEGORIES(db=db, skip=skip, limit=limit)
    return result


@router.get("/{category_id}", description="Get category details by ID")
async def get_category_details(
    category_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_CATEGORY_BY_ID(db=db, category_id=category_id)
    return result


@router.put("/{category_id}", description="Update a category by ID")
async def update_category(
    category_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    category_data: CategoryCreate = Body(...),
):
    result = await inventory_manager.UPDATE_CATEGORY(
        db=db, category_id=category_id, category_data=category_data
    )
    return result


@router.delete("/{category_id}", description="Soft delete a category by ID")
async def soft_delete_category(
    category_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_CATEGORY(
        db=db, category_id=category_id, deleted_by=current_user.user_id
    )
    return result
