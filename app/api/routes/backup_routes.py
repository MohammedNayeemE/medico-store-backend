from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.backup_models import Backup, Restore
from app.models.user_management_models import User
from app.schemas.backup_schemas import BackupCreate, BackupRead
from app.services.backup_service import BackupService
from app.services.restore_service import RestoreService

router = APIRouter(prefix="/backups", tags=["Backup Management"])


@router.post("/", response_model=BackupRead)
async def trigger_backup(
    req: BackupCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["backup:write"]),
):
    backup = Backup(
        name=req.name,
        backup_type=req.backup_type,
        parts=",".join(req.parts or ["postgres", "mongo", "files"]),
        status="queued",
        created_by=current_user.username,
    )
    db.add(backup)
    await db.commit()
    await db.refresh(backup)

    background_tasks.add_task(
        BackupService.create_backup,
        db,
        backup.id,
        req.parts,
        req.postgres_tables,  # ⬅️ pass table list
    )
    return backup


@router.get("/", response_model=list[BackupRead])
async def list_backups(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["backup:read"]),
):
    result = await db.execute(select(Backup))
    return result.scalars().all()


@router.get("/{backup_id}")
async def get_backup_by_id(
    db: AsyncSession = Depends(get_postgres),
    backup_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["backup:read"]),
):
    result = await db.execute(select(Backup).filter(Backup.id == backup_id))
    backup_obj = result.scalar_one_or_none()
    return backup_obj


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["backup:write"]),
):
    background_tasks.add_task(
        RestoreService.restore_backup,
        db,
        backup_id,
    )
    return {"message": f"Restore for backup {backup_id} started"}


@router.get("/restore")
async def restores(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["backup:read"]),
):
    result = await db.execute(select(Restore))
    return result
