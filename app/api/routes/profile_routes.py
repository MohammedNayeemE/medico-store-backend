from typing import List

from fastapi import APIRouter, Body, Depends, File, Path, Security, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.schemas.user_schemas import (
    AddressResponse,
    AdminProfileCreate,
    AdminProfileResponse,
    CustomerProfileCreate,
    CustomerProfileResponse,
)
from app.services.file_service import FileService
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profiles"])
profile = ProfileService()
file_manager = FileService()


@router.get("/dev", description="Health check endpoint for Profile routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.get(
    "/get-admin-profile/{admin_id}",
    response_model=AdminProfileResponse,
    description="Get detailed profile information for a specific admin",
)
async def get_admin_profile(
    admin_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await profile.get_admin_profile(admin_id=admin_id, db=db)
    return result


@router.post(
    "/upload-admin-pic/{admin_id}",
    description="Upload or replace the profile picture for an admin",
)
async def upload_admin_pic(
    admin_id: int = Path(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await file_manager.UPLOAD_SINGLE_FILE(
        bucket=bucket, db=db, user_id=admin_id, file=file
    )
    return result


@router.post(
    "/update-admin-profile/{admin_id}",
    response_model=AdminProfileResponse,
    description="Update the profile details of a specific admin",
)
async def update_admin_profile(
    admin_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    profile_data: AdminProfileCreate = Body(...),
):
    result = await profile.update_admin_profile(
        admin_id=admin_id, db=db, profile_data=profile_data
    )
    return result


@router.get(
    "/get-customer-profile/{customer_id}",
    response_model=CustomerProfileResponse,
    description="Get detailed profile information for a specific customer",
)
async def get_customer_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
    customer_id: int = Path(...),
):
    result = await profile.get_customer_profile(db=db, customer_id=customer_id)
    return result


@router.post(
    "/upload-customer-pic/{customer_id}",
    description="Upload or replace the profile picture for a customer",
)
async def upload_customer_pic(
    db: AsyncSession = Depends(get_postgres),
    file: UploadFile = File(...),
    customer_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    result = await file_manager.UPLOAD_SINGLE_FILE(
        bucket=bucket, file=file, user_id=customer_id, db=db
    )
    return result


@router.post(
    "/update-customer-profile/{customer_id}",
    response_model=CustomerProfileResponse,
    description="Update the profile details of a specific customer",
)
async def update_customer_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
    customer_id: int = Path(...),
    profile_data: CustomerProfileCreate = Body(...),
):
    result = await profile.update_customer_profile(
        db=db, customer_id=customer_id, profile_data=profile_data
    )
    return result


@router.get(
    "/get-customer-addresses/{customer_id}",
    response_model=List[AddressResponse],
    description="List all saved addresses for a given customer",
)
async def get_customer_addresses(
    customer_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    result = profile.get_customer_addresses(customer_id=customer_id, db=db)
    return result
