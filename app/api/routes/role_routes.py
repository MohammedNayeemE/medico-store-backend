from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, Query, Security
from fastapi.responses import JSONResponse
from fastapi.utils import deep_dict_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres
from app.schemas.user_schemas import EmployeeCreate, RoleCreate, RoleResponse
from app.services.role_management_service import RoleManagementService

router = APIRouter(prefix="/roles", tags=["Roles"])
role_manager = RoleManagementService()


@router.get("/dev", description="Health check endpoint for Roles routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working..."})


@router.post("/create-role", description="Create a new role with permissions")
async def create_role(
    # current_user=Security(oauth2_scheme, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    role_data: RoleCreate = Body(...),
):
    result = await role_manager.CREATE_ROLE(db=db, role_data=role_data)
    return result


@router.post("/add-employees", description="add new employee with roles")
async def add_employee(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_postgres),
    employeeData: EmployeeCreate = Body(...),
    current_user=Security(oauth2_scheme, scopes=["admin:write"]),
):
    result = await role_manager.ADD_EMPLOYEE(
        db=db, employeeData=employeeData, background_tasks=background_tasks
    )
    return result


@router.post("/get-employees", description="get all the employees")
async def get_employees(
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await role_manager.GET_EMPLOYEES(db=db, skip=skip, limit=limit)
    return result


@router.get("/get-permissions/{role_id}", description="get all permissions for a role")
async def get_permissions(
    db: AsyncSession = Depends(get_postgres), role_id: int = Path(...)
):
    result = await role_manager.GET_PERMISSIONS_FOR_ROLE(db=db, role_id=role_id)
    return result


@router.get(
    "/get-roles", description="List roles with optional name filter and pagination"
)
async def get_roles(
    current_user=Security(oauth2_scheme, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await role_manager.GET_ROLES(db=db, name=name, skip=skip, limit=limit)
    return result


@router.put("/update-role/{role_id}", description="Update an existing role by ID")
async def update_role(
    role_id: int,
    role_data: RoleCreate = Body(...),
    current_user=Security(oauth2_scheme, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await role_manager.UPDATE_ROLE(db=db, role_id=role_id, role_data=role_data)
    return result
