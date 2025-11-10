from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, HTTPException
from jose import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_management_models import Permission, Role, RolePermission, User
from app.schemas.user_schemas import EmployeeCreate, RoleCreate
from app.services.audit_log_service import AuditLogService
from app.services.mail_service import MailService


class RoleManagementService:
    def __init__(self) -> None:
        self.A_SECRET_KEY = settings.ACCESS_SECRET_TOKEN
        self.ALGORITHM = settings.ALGORITHM
        self.mail_service = MailService()
        self.background_tasks = BackgroundTasks()

    def create_onboarding_token(self, email: str):
        payload = {
            "sub": email,
            "type": "onboarding",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        return jwt.encode(payload, self.A_SECRET_KEY, self.ALGORITHM)

    async def CREATE_ROLE(
        self,
        db: AsyncSession,
        role_data: RoleCreate,
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Role:
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
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="CREATE_ROLE",
                    resource="roles",
                    resource_id=role.role_id,
                    new_data={
                        "name": role.name,
                        "description": role.description,
                        "permissions": role_data.permissions,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )
            return role
        except HTTPException:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="CREATE_ROLE",
                    resource="roles",
                    new_data=role_data.dict() if hasattr(role_data, "dict") else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            await db.rollback()
            # Log failure
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="CREATE_ROLE",
                    resource="roles",
                    new_data=role_data.dict() if hasattr(role_data, "dict") else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
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
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
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
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_ROLES",
                    resource="roles",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )

            return roles
        except HTTPException:
            # Log failure
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_ROLES",
                    resource="roles",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_ROLES",
                    resource="roles",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            print("----------------------")
            print(f"[get-roles] error: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_roles]"
            )

    async def UPDATE_ROLE(
        self,
        db: AsyncSession,
        role_id: int,
        role_data: RoleCreate,
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Role:
        try:
            old_role_result = await db.execute(
                select(Role).filter(Role.role_id == role_id)
            )
            old_role = old_role_result.scalar_one_or_none()
            old_data = None
            if old_role:
                old_perms_result = await db.execute(
                    select(Permission.name)
                    .join(
                        RolePermission,
                        Permission.permission_id == RolePermission.permission_id,
                    )
                    .filter(RolePermission.role_id == role_id)
                )
                old_permissions = [perm[0] for perm in old_perms_result.all()]
                old_data = {
                    "name": old_role.name,
                    "description": old_role.description,
                    "permissions": old_permissions,
                }
            if not old_role:
                raise HTTPException(status_code=404, detail="Role not found")
            if role_data.name:
                old_role.name = role_data.name
            if role_data.description:
                old_role.description = role_data.description
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
            await db.refresh(old_role)
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="UPDATE_ROLE",
                    resource="roles",
                    resource_id=role_id,
                    old_data=old_data,
                    new_data={
                        "name": old_role.name,
                        "description": old_role.description,
                        "permissions": role_data.permissions,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )
            return old_role
        except HTTPException:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="UPDATE_ROLE",
                    resource="roles",
                    resource_id=role_id,
                    new_data=role_data.dict() if hasattr(role_data, "dict") else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="UPDATE_ROLE",
                    resource="roles",
                    resource_id=role_id,
                    new_data=role_data.dict() if hasattr(role_data, "dict") else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            print("----------------------")
            print(f"[update-role] error : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [update_role]"
            )

    async def ADD_EMPLOYEE(
        self,
        db: AsyncSession,
        employeeData: EmployeeCreate,
        background_tasks: BackgroundTasks,
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        try:
            result = await db.execute(
                select(User.email).filter(User.email == employeeData.email)
            )
            employee_obj = result.scalar_one_or_none()
            if employee_obj:
                raise HTTPException(status_code=404, detail="this email already exists")
            new_user = User(
                email=employeeData.email,
                password_hash=employeeData.password,
                role_id=employeeData.role_id,
                is_active=False,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            token = self.create_onboarding_token(employeeData.email)
            magic_link = f"{settings.PRODUCTION_URL}/onboard?token={token}"
            background_tasks.add_task(
                self.mail_service.SEND_ONBOARDING_MAIL, employeeData.email, magic_link
            )
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="ADD_EMPLOYEE",
                    resource="employees",
                    resource_id=new_user.user_id,
                    new_data={
                        "email": employeeData.email,
                        "role_id": employeeData.role_id,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )
            return {"msg": "Employee added and onboarding mail sent"}
        except HTTPException:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="ADD_EMPLOYEE",
                    resource="employees",
                    new_data={
                        "email": employeeData.email,
                        "role_id": employeeData.role_id,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            # Log failure
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="ADD_EMPLOYEE",
                    resource="employees",
                    new_data={
                        "email": employeeData.email,
                        "role_id": employeeData.role_id,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            print("----------------------")
            print(f"[ADD_EMPLOYEE] error : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [ADD_EMPLOYEE]"
            )

    async def GET_EMPLOYEES(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        try:
            query = (
                select(User)
                .filter(User.is_deleted == False, User.role_id != 1)
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            employees = result.scalars().all()
            if not employees:
                raise HTTPException(status_code=404, detail="No employees found")
            response = []
            for emp in employees:
                role_result = await db.execute(
                    select(Role).filter(Role.role_id == emp.role_id)
                )
                role = role_result.scalar_one_or_none()
                response.append(
                    {
                        "user_id": emp.user_id,
                        "email": emp.email,
                        "role": role.name if role else None,
                        "is_active": emp.is_active,
                    }
                )
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_EMPLOYEES",
                    resource="employees",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )
            return response
        except HTTPException:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_EMPLOYEES",
                    resource="employees",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            # Log failure
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_EMPLOYEES",
                    resource="employees",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            print("----------------------")
            print(f"[GET_EMPLOYEES] error: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [GET_EMPLOYEES]"
            )

    async def GET_PERMISSIONS_FOR_ROLE(
        self,
        db: AsyncSession,
        role_id: int,
        mongo_db: Optional[AsyncIOMotorDatabase] = None,
        actor_id: Optional[int] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        try:
            result = await db.execute(select(Role).filter(Role.role_id == role_id))
            role = result.scalar_one_or_none()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            result = await db.execute(
                select(Permission)
                .join(
                    RolePermission,
                    Permission.permission_id == RolePermission.permission_id,
                )
                .filter(RolePermission.role_id == role_id)
            )
            permissions = result.scalars().all()
            if not permissions:
                raise HTTPException(
                    status_code=404, detail="No permissions found for this role"
                )
            response = [
                {"permission_id": p.permission_id, "name": p.name} for p in permissions
            ]
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_PERMISSIONS",
                    resource="roles",
                    resource_id=role_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="SUCCESS",
                )
            return response
        except HTTPException:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_PERMISSIONS",
                    resource="roles",
                    resource_id=role_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            raise
        except Exception as e:
            if mongo_db is not None:
                audit_service = AuditLogService(mongo_db)
                await audit_service.LOG_ACTION(
                    actor_id=actor_id,
                    actor_role=actor_role,
                    action="GET_PERMISSIONS",
                    resource="roles",
                    resource_id=role_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="FAILURE",
                )
            print("----------------------")
            print(f"[GET_PERMISSIONS_FOR_ROLE] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [GET_PERMISSIONS_FOR_ROLE]",
            )
