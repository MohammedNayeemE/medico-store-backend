from typing import List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Security,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import Permission, Role, RolePermission
from app.schemas.user_schemas import RoleCreate, RoleResponse

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/dev")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working..."})


@router.post("/create-role", response_model=RoleResponse)
async def create_role(
    current_user=Security(oauth2_scheme, scopes=["role:write"]),
    db: AsyncSession = Depends(get_postgres),
    role_data: RoleCreate = Body(...),
):
    try:
        result = await db.execute(select(Role).filter(Role.name == role_data.name))
        existing_role = result.scalar_one_or_none()
        if existing_role:
            raise HTTPException(
                status_code=400, detail=f"{existing_role.name} already exists"
            )
        role = Role(name=role_data.name, description=role_data.description)
        db.add(role)
        await db.commit()
        await db.refresh(role)
        role_permissions: List[RolePermission] = []
        new_permissions: List[Permission] = []
        for perm_name in role_data.permissions:
            result = await db.execute(
                select(Permission).filter(Permission.name == perm_name)
            )
            perm = result.scalar_one_or_none()
            if not perm:
                perm = Permission(name=perm_name, description=f"Scope: {perm_name}")
                new_permissions.append(perm)
            role_perm_link = RolePermission(
                role_id=role.role_id, permission_id=perm.permission_id
            )
            role_permissions.append(role_perm_link)
        data_tobe_commited = role_permissions + new_permissions
        db.add_all(data_tobe_commited)
        await db.commit()
        return role
    except HTTPException:
        raise
    except Exception as e:
        print(f"[create-role]: error : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [create_role]"
        )


@router.get("/get-roles", response_model=List[RoleResponse])
async def get_roles(
    current_user=Security(oauth2_scheme, scopes=["role:read"]),
    db: AsyncSession = Depends(get_postgres),
    name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    try:
        query = select(Role).filter(Role.is_deleted == False)
        if name:
            query = query.filter(Role.name.ilike(f"%{name}%"))
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        roles = result.scalars().all()
        if not roles:
            raise HTTPException(status_code=404, detail="No roles found")
        return roles
    except HTTPException:
        raise
    except Exception as e:
        print(f"[get-roles] error: {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [get_roles]"
        )


@router.put("/update-role/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleCreate = Body(...),
    current_user=Security(oauth2_scheme, scopes=["role:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    try:
        result = await db.execute(select(Role).filter(Role.role_id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        if role_data.name:
            role.name = role_data.name
        if role_data.description:
            role.description = role_data.description
        result = await db.execute(
            select(RolePermission).filter(RolePermission.role_id == role_id)
        )
        current_permissions = result.scalars().all()
        new_permission_names = set(role_data.permissions or [])
        existing_perms_result = await db.execute(
            select(Permission).filter(Permission.name.in_(new_permission_names))
        )
        existing_permissions = existing_perms_result.scalars().all()
        existing_perm_names = {str(p.name) for p in existing_permissions}
        new_perms_to_add = [
            Permission(name=p, description=f"Scope: {p}")
            for p in new_permission_names - existing_perm_names
        ]
        db.add_all(new_perms_to_add)
        await db.flush()
        all_permissions = existing_permissions + new_perms_to_add
        await db.execute(
            delete(RolePermission).filter(RolePermission.role_id == role_id)
        )
        db.add_all(
            [
                RolePermission(role_id=role_id, permission_id=p.permission_id)
                for p in all_permissions
            ]
        )
        await db.commit()
        await db.refresh(role)
        return role
    except HTTPException:
        raise
    except Exception as e:
        print(f"[update-role] error : {e}")
        raise HTTPException(
            status_code=500, detail="internal server error : [update_role]"
        )
