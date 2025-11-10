from os import times
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.user_management_models import User
from app.schemas.inventory_schemas import MedicineCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(
    prefix="/medicines",
    tags=["Medicines"],
    dependencies=[Depends(RateLimiter(times=200, seconds=60))],
)
inventory_manager = InventoryManagementService()


@router.post(
    "/upload-thumbnail-image/{medicine_id}",
    description="Upload a single medicine image",
)
async def upload_thumbnail_image(
    current_user: User = Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
    file: UploadFile = File(...),
    medicine_id: int = Path(...),
):
    result = await inventory_manager.UPLOAD_MEDICINE_IMAGE(
        db=db,
        user_id=current_user.user_id,
        file=file,
        bucket=bucket,
        medicine_id=medicine_id,
    )
    return result


@router.post(
    "/upload-mulitple-images/{medicine_id}",
    description="Upload Multiple Images for the medicine",
)
async def upload_mulitple_images(
    current_user: User = Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
    files: List[UploadFile] = File(...),
    medicine_id: int = Path(...),
):
    result = await inventory_manager.UPLOAD_MEDICINE_IMAGES(
        db=db,
        user_id=current_user.user_id,
        bucket=bucket,
        files=files,
        medicine_id=medicine_id,
    )
    return result


@router.get("/download-template", description="download the medicine template")
async def download_template():
    result = await inventory_manager.DOWNLOAD_TEMPLATE()
    return result


@router.post("/create", description="Create a new medicine entry")
async def create_medicine(
    current_user=Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: MedicineCreate = Body(...),
):
    result = await inventory_manager.CREATE_MEDICINE(db=db, medicine_data=medicine_data)
    return result


@router.post("/bulk-upload-medicines", description="Bulk upload the medicine data")
async def bulk_upload_medicine(
    current_user=Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_MEDICINES(db=db, file=medicine_data)
    return result


@router.get(
    "/",
    description="List medicines with optional filters and pagination for the shopping page",
)
async def get_all_medicines(
    db: AsyncSession = Depends(get_postgres),
    search: Optional[str] = Query(None, description="Search by name or description"),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: Optional[str] = Query("name", description="Sort by 'price' or 'name'"),
    order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_MEDICINES(
        db=db,
        name=search,
        category=category,
        tag=tag,
        sort_by=sort_by,
        sort_order=order,
        skip=skip,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
    )
    return result


@router.get(
    "/light", description="List all the medicines with minimal data to optimise the api"
)
async def get_all_light_medicines(
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
):
    result = await inventory_manager.GET_LIGHT_MEDICINES(db=db, skip=skip, limit=limit)
    return result


@router.get("/{medicine_id}", description="Get details of a specific medicine by ID")
async def get_medicine_details(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_MEDICINE_BY_ID(db=db, medicine_id=medicine_id)
    return result


@router.put("/{medicine_id}", description="Update an existing medicine by ID")
async def update_medicine(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: MedicineCreate = Body(...),
):
    result = await inventory_manager.UPDATE_MEDICINE(
        db=db, medicine_id=medicine_id, medicine_data=medicine_data
    )
    return result


@router.delete("/{medicine_id}", description="Soft delete a medicine by ID")
async def soft_delete_medicine(
    medicine_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["medicine:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_MEDICINE(
        db=db, medicine_id=medicine_id, deleted_by=current_user.user_id
    )
    return result


@router.get(
    "/customer/medicines/{medicine_id}",
    description="Get detailed information about a specific medicine",
)
async def get_medicine_details_for_customer(
    db: AsyncSession = Depends(get_postgres),
    medicine_id: int = Path(...),
):
    pass
    result = await inventory_manager.GET_CUSTOMER_MEDICINE_DETAILS(
        db=db, medicine_id=medicine_id
    )
    return result


@router.get(
    "/customer/medicines/{medicine_id}/related",
    description="Fetch related or similar medicines based on category or tags",
)
async def get_related_medicines(
    db: AsyncSession = Depends(get_postgres),
    medicine_id: int = Path(...),
):
    pass
    # result = await inventory_manager.GET_RELATED_MEDICINES(
    #     db=db, medicine_id=medicine_id
    # )
    # return result
