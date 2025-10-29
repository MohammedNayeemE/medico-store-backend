from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_management_models import Permission, Role, RolePermission
from app.schemas.user_schemas import RoleCreate


class RoleManagementService:
    def __init__(self) -> None:
        pass

    async def CREATE_ROLE(self, db: AsyncSession, role_data: RoleCreate) -> Role:
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
                    db.add(perm)
                    await db.flush()
                role_perm_link = RolePermission(
                    role_id=role.role_id, permission_id=perm.permission_id
                )
                db.add(role_perm_link)
            await db.commit()
            await db.refresh(role)
            return role
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            print(
                "--------------------------------------------------------------------"
            )
            print(f"[create-role]: error : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_role]"
            )

    async def GET_ROLES(
        self,
        db: AsyncSession,
        name: Optional[str] = None,
        skip: Optional[int] = 0,
        limit: Optional[int] = 0,
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

    async def UPDATE_ROLE(
        self, db: AsyncSession, role_id: int, role_data: RoleCreate
    ) -> Role:
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
