from fastapi import APIRouter, Body, Depends, Path, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.user_management_models import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
notification_manager = NotificationService()


@router.get("/{notificaiton_id}")
async def GET_NOTIFICATIONS(
    notificaiton_id: int = Path(...), db: AsyncSession = Depends(get_postgres)
):
    result = await notification_manager.GET_NOTFICATION_BY_ID(
        db=db, notificaiton_id=notificaiton_id
    )
    return result


@router.get("/")
async def GET_NOTIFICATIONS_USER(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["notification:read"]),
):
    result = await notification_manager.GET_NOTFICATIONS_FOR_USER(
        db=db, user_id=current_user.user_id
    )
    return result
