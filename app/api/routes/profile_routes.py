from typing import List

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import roles

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.user_management_models import User
from app.schemas.user_schemas import (
    AddressResponse,
    AddressTypeCreate,
    AddressTypeUpdate,
    AdminProfileCreate,
    AdminProfileResponse,
    CustomerProfileCreate,
    CustomerProfileResponse,
    FamilyMemberCreate,
    FamilyMemberUpdate,
)
from app.services.file_service import FileService
from app.services.profile_management.profile_service import ProfileService

router = APIRouter(
    prefix="/profile",
    tags=["Profiles"],
    dependencies=[Depends(RateLimiter(times=100, seconds=60))],
)
profile = ProfileService()
file_manager = FileService()


@router.get("/dev", description="Health check endpoint for Profile routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.get(
    "/get-admin-profile/",
    response_model=AdminProfileResponse,
    description="Get detailed profile information for a specific admin",
)
async def get_admin_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:read"]),
):
    result = await profile.GET_ADMIN_PROFILE(
        admin_id=current_user.user_id, db=db, role_id=current_user.role_id
    )
    return result


@router.post(
    "/upload-profile-pic/",
    description="Upload or replace the profile picture for an admin",
)
async def upload_admin_pic(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["profile:write"]),
):
    result = await file_manager.UPLOAD_SINGLE_FILE(
        bucket=bucket, db=db, user_id=current_user.user_id, file=file
    )
    file_url = f"http://localhost:8000/api/v1/files/assets/{result['asset_id']}"
    return {"file_url": file_url, "profile_id": result["asset_id"]}


@router.post(
    "/update-admin-profile/",
    response_model=AdminProfileResponse,
    description="Update the profile details of a specific admin",
)
async def update_admin_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:update"]),
    profile_data: AdminProfileCreate = Body(...),
):
    result = await profile.UPDATE_ADMIN_PROFILE(
        admin_id=current_user.user_id,
        db=db,
        profile_data=profile_data,
        role_id=current_user.role_id,
    )
    return result


@router.get(
    "/get-customer-profile/",
    response_model=CustomerProfileResponse,
    description="Get detailed profile information for a specific customer",
)
async def get_customer_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:read"]),
):
    result = await profile.GET_CUSTOMER_PROFILE(
        db=db, customer_id=current_user.user_id, role_id=current_user.role_id
    )
    return result


@router.post("/update_customer_profile")
async def update_customer_profile(
    profile_data: CustomerProfileCreate,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:write"]),
):
    result = await profile.UPDATE_CUSTOMER_PROFILE(
        db=db,
        customer_id=current_user.user_id,
        profile_data=profile_data,
        role_id=current_user.role_id,
    )
    return result


@router.get(
    "/get-customer-addresses/",
    description="List all saved addresses for a given customer",
)
async def get_customer_addresses(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:read"]),
):
    result = await profile.GET_CUSTOMER_ADDRESSES(
        customer_id=current_user.user_id, db=db, role_id=current_user.role_id
    )
    return result


@router.post("/add-address", description="Add address of the customer")
async def add_addresses(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["profile:write"]),
    latitude: float = Query(...),
    longitude: float = Query(...),
    type_id: int = Query(None),
):
    result = await profile.ADD_ADDRESS(
        customer_id=current_user.user_id,
        db=db,
        longitude=longitude,
        latitude=latitude,
        type_id=type_id,
        role_id=current_user.role_id,
    )
    return result


@router.post("/add-address-type", description="Add a new address type")
async def add_address_type(
    data: AddressTypeCreate,
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["address_type:write"]),
):
    result = await profile.ADD_ADDRESS_TYPE(db=db, data=data)
    return result


@router.get(
    "/address-types",
    description="List all active address types",
)
async def get_address_types(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user),
):
    result = await profile.GET_ALL_ADDRESS_TYPES(db=db)
    return result


@router.put(
    "/{type_id}",
    description="Update address type details",
)
async def update_address_type(
    type_id: int = Path(...),
    data: AddressTypeUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["address_type:write"]),
):
    result = await profile.UPDATE_ADDRESS_TYPE(db=db, data=data, type_id=type_id)
    return result


@router.delete("/{type_id}", description="Soft delete an address type")
async def delete_address_type(
    type_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["address_type:delete"]),
):
    result = await profile.DELETE_ADDRESS_TYPE(db=db, type_id=type_id)
    return result


@router.post("/add-family-member", description="Add a family member")
async def add_family_member(
    family_member_data: FamilyMemberCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["members:write"]),
):
    """Add a new family member for the logged-in user."""
    result = await profile.ADD_FAMILY_MEMBER(
        db=db,
        user_id=current_user.user_id,
        data=family_member_data,
        role_id=current_user.role_id,
    )
    return result


@router.get(
    "/get-family-memebers",
    description="List all family members of a user",
)
async def get_family_members(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["members:read"]),
):
    """Get all family members of a specific user."""
    result = await profile.GET_FAMILY_MEMBERS(db=db, user_id=current_user.user_id)
    return result


@router.put(
    "/members/{member_id}",
    description="Update a family member by ID",
)
async def update_family_member(
    member_id: int = Path(...),
    family_member_data: FamilyMemberUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["members:write"]),
):
    """Update a specific family member."""
    result = await profile.UPDATE_FAMILY_MEMBER(
        db=db, member_id=member_id, data=family_member_data
    )
    return result
