from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Security,
)
from fastapi.openapi.models import SecuritySchemeType
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependecies.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    oauth2_scheme,
    verify_password,
)
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.config import settings
from app.models.user_management_models import (
    Address,
    CustomerProfile,
    ManagementProfile,
    RevokedToken,
    Session,
    User,
)
from app.schemas.user_schemas import (
    AddressResponse,
    AdminCreate,
    AdminProfileCreate,
    AdminProfileResponse,
    AdminResponse,
    CustomerProfileCreate,
    CustomerProfileResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/profile", tags=["Profiles"])


@router.get("/dev")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.get("/get-admin-profile/{admin_id}", response_model=AdminProfileResponse)
async def get_admin_profile(
    admin_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["profile:read"]),
):
    try:
        result = await db.execute(
            select(ManagementProfile).filter(ManagementProfile.user_id == admin_id)
        )
        profile_obj = result.scalar_one_or_none()
        if profile_obj is None:
            raise HTTPException(
                status_code=404, detail=f"profile not found for this id {admin_id}"
            )
        return profile_obj

    except HTTPException:
        raise
    except Exception as e:
        print(f"[get-admin-profile] error : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error: get_admin_profile"
        )


@router.post("/update-admin-profile/{admin_id}", response_model=AdminProfileResponse)
async def update_admin_profile(
    admin_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["profile:write"]),
    profile_data: AdminProfileCreate = Body(...),
):
    try:
        result = await db.execute(
            select(ManagementProfile).filter(ManagementProfile.user_id == admin_id)
        )
        profile_obj = result.scalar_one_or_none()

        if profile_obj is not None:
            if profile_data.name is not None:
                profile_obj.name = profile_data.name
            if profile_data.phone_number is not None:
                profile_obj.phone_number = profile_data.phone_number
            if profile_data.profile_pic is not None:
                profile_obj.profile_pic = profile_data.profile_pic

            profile_obj.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(profile_obj)
            return profile_obj

        new_profile = ManagementProfile(
            user_id=admin_id,
            name=profile_data.name,
            phone_number=profile_data.phone_number,
            profile_pic=profile_data.profile_pic,
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        return new_profile

    except HTTPException:
        raise
    except Exception as e:
        print(f"[update-admin-profile] Internal error: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error: update_admin_profile"
        )


@router.get(
    "/get-customer-profile/{customer_id}", response_model=CustomerProfileResponse
)
async def get_customer_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["customer_profile:read"]),
    customer_id: int = Path(...),
):
    try:
        result = await db.execute(
            select(CustomerProfile).filter(CustomerProfile.user_id == customer_id)
        )
        profile_obj = result.scalar_one_or_none()
        if profile_obj is None:
            raise HTTPException(
                status_code=404,
                detail=f"Customer profile not found for id {customer_id}",
            )
        return profile_obj
    except HTTPException:
        raise
    except Exception as e:
        print(f"[get-customer-profile] Error: {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [get-customer-profile]"
        )


@router.post(
    "/update-customer-profile/{customer_id}", response_model=CustomerProfileResponse
)
async def update_customer_profile(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["customer_profile:write"]),
    customer_id: int = Path(...),
    profile_data: CustomerProfileCreate = Body(...),
):
    try:
        result = await db.execute(
            select(CustomerProfile).filter(CustomerProfile.user_id == customer_id)
        )
        profile_obj = result.scalar_one_or_none()
        if profile_obj is not None:
            if profile_data.name is not None:
                profile_obj.name = profile_data.name
            if profile_data.address_id is not None:
                profile_obj.address_id = profile_data.address_id
            if profile_data.profile_pic is not None:
                profile_obj.profile_pic = profile_data.profile_pic
            if profile_data.blood_group is not None:
                profile_obj.blood_group = profile_data.blood_group
            if profile_data.gender is not None:
                profile_obj.gender = profile_data.gender
            if profile_data.dob is not None:
                profile_obj.dob = profile_data.dob
            profile_obj.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(profile_obj)
            return profile_obj
        new_profile = CustomerProfile(
            user_id=customer_id,
            name=profile_data.name,
            address_id=profile_data.address_id,
            profile_pic=profile_data.profile_pic,
            blood_group=profile_data.blood_group,
            gender=profile_data.gender,
            dob=profile_data.dob,
        )
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        return new_profile
    except HTTPException:
        raise
    except Exception as e:
        print(f"[update-customer-profile] Error: {e}")
        raise HTTPException(
            status_code=500, detail="internal server error: [update-customer-profile]"
        )


@router.get(
    "/get-customer-addresses/{customer_id}", response_model=List[AddressResponse]
)
async def get_customer_addresses(
    customer_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["customer_profile:read"]),
):
    try:
        result = await db.execute(
            select(Address).filter(
                Address.user_id == customer_id, Address.is_deleted == False
            )
        )
        addresses = result.scalars().all()
        if not addresses:
            raise HTTPException(
                status_code=404, detail=f"No addresses found for user {customer_id}"
            )
        return addresses
    except HTTPException:
        raise
    except Exception as e:
        print(f"[get-customer-addresses] Error: {e}")
        raise HTTPException(
            status_code=500, detail="internal server error: [get-customer-addresses]"
        )
