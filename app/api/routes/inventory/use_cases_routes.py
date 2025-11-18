from typing import List

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.schemas.inventory_schemas import UseCaseCreate, UseCaseLinkCreate
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/use-cases", tags=["Use Cases"])
inventory_manager = InventoryManagementService()


@router.get("/download-template", description="Download the use case template")
async def download_template(
    current_user: User = Security(get_current_user, scopes=["use_case:read"])
):
    result = await inventory_manager.DOWNLOAD_USE_CASE_TEMPLATE()
    return result


@router.post(
    "/bulk-upload-use-cases",
    description="Bulk upload use cases using excel or csv file",
)
async def bulk_upload_use_cases(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["use_case:write"]),
    file: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_USE_CASES(db=db, file=file)
    return result


@router.post("/", description="Create a new use case")
async def create_use_case(
    current_user=Security(get_current_user, scopes=["use_case:write"]),
    db: AsyncSession = Depends(get_postgres),
    use_case_data: UseCaseCreate = Body(...),
):
    result = await inventory_manager.CREATE_USE_CASE(
        db=db, use_case_data=use_case_data
    )
    return result


@router.get("/", description="List all use cases with pagination")
async def list_all_use_cases(
    current_user=Security(get_current_user, scopes=["use_case:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_ALL_USE_CASES(db=db, skip=skip, limit=limit)
    return result


@router.get("/{use_case_id}", description="Get use case details by ID")
async def get_use_case_details(
    use_case_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["use_case:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_USE_CASE_BY_ID(
        db=db, use_case_id=use_case_id
    )
    return result


@router.put("/{use_case_id}", description="Update a use case by ID")
async def update_use_case(
    use_case_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["use_case:write"]),
    db: AsyncSession = Depends(get_postgres),
    use_case_data: UseCaseCreate = Body(...),
):
    result = await inventory_manager.UPDATE_USE_CASE(
        db=db, use_case_id=use_case_id, use_case_data=use_case_data
    )
    return result


@router.delete("/{use_case_id}", description="Soft delete a use case by ID")
async def soft_delete_use_case(
    use_case_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["use_case:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_USE_CASE(
        db=db, use_case_id=use_case_id, deleted_by=current_user.user_id
    )
    return result


# Routes for linking medicines to use cases
@router.post("/medicines/{medicine_id}/link", description="Link use cases to a medicine")
async def link_medicine_to_use_cases(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["use_case:write"]),
    db: AsyncSession = Depends(get_postgres),
    use_case_data: UseCaseLinkCreate = Body(...),
):
    result = await inventory_manager.LINK_MEDICINE_USE_CASES(
        db=db, medicine_id=medicine_id, use_case_data=use_case_data
    )
    return result


@router.get("/medicines/{medicine_id}", description="Get all use cases for a medicine")
async def get_medicine_use_cases(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["use_case:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.LIST_ALL_MEDICINE_USE_CASES(
        db=db, medicine_id=medicine_id
    )
    return result


@router.put("/medicines/{medicine_id}/update", description="Update use case links for a medicine")
async def update_link_medicine_to_use_cases(
    medicine_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["use_case:update"]),
    db: AsyncSession = Depends(get_postgres),
    use_case_ids: List[int] = Body(...),
):
    result = await inventory_manager.UPDATE_LINK_MEDICINES_TO_USE_CASES(
        db=db,
        use_case_ids=use_case_ids,
        medicine_id=medicine_id,
        deleted_by=current_user.user_id,
    )
    return result

