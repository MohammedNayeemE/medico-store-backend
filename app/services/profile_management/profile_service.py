from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import Sequence, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_management_models import FamilyMember
from app.models.user_management_models import (
    Address,
    AddressType,
    CustomerProfile,
    ManagementProfile,
)
from app.schemas.user_schemas import (
    AddressTypeCreate,
    AddressTypeUpdate,
    AdminProfileCreate,
    CustomerProfileCreate,
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
)


class ProfileService:
    def __init__(self) -> None:
        pass

    async def GET_ADMIN_PROFILE(
        self, admin_id: int, db: AsyncSession, role_id: int
    ) -> ManagementProfile:
        try:
            if role_id == 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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

    async def UPDATE_ADMIN_PROFILE(
        self,
        admin_id: int,
        db: AsyncSession,
        profile_data: AdminProfileCreate,
        role_id: int,
    ) -> ManagementProfile:
        try:
            if role_id == 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
                profile_obj.updated_at = datetime.utcnow()
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
            print("--------------------------------------")
            print(f"[update-admin-profile] Internal error: {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: update_admin_profile"
            )

    async def GET_CUSTOMER_PROFILE(
        self, db: AsyncSession, customer_id: int, role_id: int
    ) -> CustomerProfile:
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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

    async def UPDATE_CUSTOMER_PROFILE(
        self,
        db: AsyncSession,
        customer_id: int,
        profile_data: CustomerProfileCreate,
        role_id: int,
    ) -> CustomerProfile:
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
            result = await db.execute(
                select(CustomerProfile).filter(CustomerProfile.user_id == customer_id)
            )
            profile_obj = result.scalar_one_or_none()
            if profile_obj is not None:
                if profile_data.name is not None:
                    profile_obj.name = profile_data.name
                if profile_data.email is not None:
                    profile_obj.email = profile_data.email
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
                email=profile_data.email,
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
                status_code=500,
                detail="internal server error: [update-customer-profile]",
            )

    async def GET_CUSTOMER_ADDRESSES(
        self, customer_id: int, db: AsyncSession, role_id: int
    ) -> Sequence[Address]:
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
                status_code=500,
                detail="internal server error: [get-customer-addresses]",
            )

    async def _reverse_geocode(self, lat: float, lon: float):
        params = {"lat": lat, "lon": lon, "apiKey": "d70123d0a670448b977f0f3d51658056"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.geoapify.com/v1/geocode/reverse",
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
            except httpx.RequestError as e:
                raise HTTPException(status_code=500, detail=f"Network error: {e}")
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Geoapify API error: {e.response.text}",
                )
        data = response.json()
        if not data.get("features"):
            raise HTTPException(
                status_code=404, detail="No address found for given coordinates"
            )
        props = data["features"][0]["properties"]
        address = {
            "formatted": props.get("formatted"),
            "country": props.get("country"),
            "state": props.get("state"),
            "city": props.get("city"),
            "postcode": props.get("postcode"),
            "road": props.get("road"),
            "house_number": props.get("housenumber"),
            "lat": props.get("lat"),
            "lon": props.get("lon"),
        }
        return {"address": address}

    async def ADD_ADDRESS(
        self,
        customer_id: int,
        role_id: int,
        db: AsyncSession,
        longitude: float,
        latitude: float,
        type_id: int = 1,
    ):
        if role_id != 1:
            raise HTTPException(status_code=403, detail="Forbidden Access")
        geo_result = await self._reverse_geocode(lat=latitude, lon=longitude)
        address_data = geo_result.get("address", {}) if geo_result else {}
        result = await db.execute(
            select(AddressType).filter(
                AddressType.type_id == type_id,
                AddressType.is_deleted == False,
            )
        )
        address_type = result.scalar_one_or_none()
        if not address_type:
            raise HTTPException(status_code=404, detail="Invalid address type")
        new_address = Address(
            user_id=customer_id,
            house_no=address_data.get("house_number") or "N/A",
            street_name=address_data.get("road") or "Unknown Street",
            locality=address_data.get("formatted") or "Unknown Area",
            city=address_data.get("city") or "Unknown City",
            state=address_data.get("state") or "Unknown State",
            pincode=address_data.get("postcode") or "000000",
            type_id=type_id,
            created_at=datetime.utcnow(),
            is_deleted=False,
            # Optional: if you’ve added these columns
            # latitude=address_data.get("lat"),
            # longitude=address_data.get("lon"),
        )
        db.add(new_address)
        await db.commit()
        await db.refresh(new_address)
        return {
            "message": "Address added successfully",
            "address_id": new_address.address_id,
            "details": {
                "formatted": address_data.get("formatted"),
                "city": new_address.city,
                "state": new_address.state,
                "pincode": new_address.pincode,
            },
        }

    async def ADD_ADDRESS_TYPE(self, db: AsyncSession, data: AddressTypeCreate):
        """Create a new address type (e.g., Home, Work, Other)."""
        existing = await db.execute(
            select(AddressType).filter(
                AddressType.name.ilike(data.name), AddressType.is_deleted == False
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Address type already exists")
        new_type = AddressType(name=data.name.strip())
        db.add(new_type)
        await db.commit()
        await db.refresh(new_type)
        return new_type

    async def GET_ALL_ADDRESS_TYPES(self, db: AsyncSession):
        """Fetch all active address types."""
        result = await db.execute(
            select(AddressType).filter(AddressType.is_deleted == False)
        )
        return result.scalars().all()

    async def UPDATE_ADDRESS_TYPE(
        self, db: AsyncSession, type_id: int, data: AddressTypeUpdate
    ):
        """Update address type name or mark as deleted."""
        result = await db.execute(
            select(AddressType).filter(AddressType.type_id == type_id)
        )
        addr_type = result.scalar_one_or_none()
        if not addr_type:
            raise HTTPException(status_code=404, detail="Address type not found")
        if data.name is not None:
            addr_type.name = data.name.strip()
        if data.is_deleted is not None:
            addr_type.is_deleted = data.is_deleted
            addr_type.deleted_at = datetime.utcnow() if data.is_deleted else None
        await db.commit()
        await db.refresh(addr_type)
        return addr_type

    async def DELETE_ADDRESS_TYPE(self, db: AsyncSession, type_id: int):
        """Soft delete address type."""
        result = await db.execute(
            select(AddressType).filter(AddressType.type_id == type_id)
        )
        addr_type = result.scalar_one_or_none()
        if not addr_type:
            raise HTTPException(status_code=404, detail="Address type not found")
        addr_type.is_deleted = True
        addr_type.deleted_at = datetime.utcnow()
        await db.commit()
        return {"message": f"Address type '{addr_type.name}' deleted successfully"}

    async def ADD_FAMILY_MEMBER(
        self, db: AsyncSession, user_id: int, data: FamilyMemberCreate, role_id: int
    ) -> FamilyMember:
        """Add a new family member for a user."""
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
            new_member = FamilyMember(
                user_id=user_id,
                name=data.name,
                phone_number=data.phone_number,
                relation=data.relation,
                email=data.email,
                age=data.age,
                gender=data.gender,
                dob=data.dob,
            )
            db.add(new_member)
            await db.commit()
            await db.refresh(new_member)
            return new_member
        except Exception as e:
            print(f"[add_family_member] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error while adding family member",
            )

    async def GET_FAMILY_MEMBERS(self, db: AsyncSession, user_id: int):
        """List all family members for a user."""
        try:
            result = await db.execute(
                select(FamilyMember).filter(FamilyMember.user_id == user_id)
            )
            members = result.scalars().all()
            if not members:
                raise HTTPException(
                    status_code=404,
                    detail=f"No family members found for user {user_id}",
                )
            return members
        except HTTPException:
            raise
        except Exception as e:
            print(f"[get_family_members] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error while fetching family members",
            )

    async def UPDATE_FAMILY_MEMBER(
        self, db: AsyncSession, member_id: int, data: FamilyMemberUpdate
    ) -> FamilyMember:
        """Update a family member by ID."""
        try:
            result = await db.execute(
                select(FamilyMember).filter(FamilyMember.member_id == member_id)
            )
            member = result.scalar_one_or_none()
            if not member:
                raise HTTPException(status_code=404, detail="Family member not found")
            for field, value in data.dict(exclude_unset=True).items():
                setattr(member, field, value)
            await db.commit()
            await db.refresh(member)
            return member
        except HTTPException:
            raise
        except Exception as e:
            print(f"[update_family_member] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error while updating family member",
            )

    async def DELETE_FAMILY_MEMBER(self, db: AsyncSession, member_id: int):
        """Permanently delete a family member by ID."""
        try:
            result = await db.execute(
                select(FamilyMember).filter(FamilyMember.member_id == member_id)
            )
            member = result.scalar_one_or_none()
            if not member:
                raise HTTPException(status_code=404, detail="Family member not found")
            await db.delete(member)
            await db.commit()
            return {"message": f"Family member '{member.name}' deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            print(f"[delete_family_member] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error while deleting family member",
            )
