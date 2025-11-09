from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, Query, Request, Security
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_mongo_db, get_postgres
from app.models.user_management_models import User
from app.schemas.user_schemas import EmployeeCreate, RoleCreate
from app.services.role_management_service import RoleManagementService

router = APIRouter(prefix="/roles", tags=["Roles"])
role_manager = RoleManagementService()


@router.get("/dev", description="Health check endpoint for Roles routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working..."})


@router.post("/create-role", description="Create a new role with permissions")
async def create_role(
    request: Request,
    current_user: User = Security(get_current_user, scopes=["role:write"]),
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    role_data: RoleCreate = Body(...),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.CREATE_ROLE(
        db=db,
        role_data=role_data,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result


@router.post("/add-employees", description="add new employee with roles")
async def add_employee(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    employeeData: EmployeeCreate = Body(...),
    current_user: User = Security(get_current_user, scopes=["role:write"]),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.ADD_EMPLOYEE(
        db=db,
        employeeData=employeeData,
        background_tasks=background_tasks,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result


@router.post("/get-employees", description="get all the employees")
async def get_employees(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user: User = Security(get_current_user, scopes=["role:read"]),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.GET_EMPLOYEES(
        db=db,
        skip=skip,
        limit=limit,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result


@router.get("/get-permissions/{role_id}", description="get all permissions for a role")
async def get_permissions(
    request: Request,
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    role_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["role:read"]),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.GET_PERMISSIONS_FOR_ROLE(
        db=db,
        role_id=role_id,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result


@router.get(
    "/get-roles", description="List roles with optional name filter and pagination"
)
async def get_roles(
    request: Request,
    current_user: User = Security(get_current_user, scopes=["role:read"]),
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.GET_ROLES(
        db=db,
        name=name,
        skip=skip,
        limit=limit,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result


@router.put("/update-role/{role_id}", description="Update an existing role by ID")
async def update_role(
    request: Request,
    role_id: int,
    role_data: RoleCreate = Body(...),
    current_user: User = Security(get_current_user, scopes=["role:update"]),
    db: AsyncSession = Depends(get_postgres),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    actor_role = current_user.role.name if current_user.role else None
    
    result = await role_manager.UPDATE_ROLE(
        db=db,
        role_id=role_id,
        role_data=role_data,
        mongo_db=mongo_db,
        actor_id=current_user.user_id,
        actor_role=actor_role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return result
