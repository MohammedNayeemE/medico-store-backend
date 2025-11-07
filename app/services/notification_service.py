from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InternalServerErrorException, NotFoundException
from app.models.enums import NotificationType
from app.models.notification_management_models import Notification
from app.models.user_management_models import User
from app.schemas import notification_schemas
from app.schemas.notification_schemas import NotificationCreate


class NotificationService:
    def __init__(self) -> None:
        pass

    async def PUSH_NOTIFICATIONS(
        self,
        db: AsyncSession,
        to_user_id: int,
        notification_content: NotificationCreate,
        by_user_id: Optional[int] = None,
    ):
        try:
            result = await db.execute(select(User).filter(User.user_id == to_user_id))
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise NotFoundException("user_id not found")
            new_notification = Notification(
                user_id=to_user_id,
                type=notification_content.type,
                by_user_id=by_user_id,
                title=notification_content.title,
                message=notification_content.message,
            )
            db.add(new_notification)
            await db.commit()
            await db.refresh(new_notification)
            return {"notfication sent succesfully"}
        except NotFoundException:
            raise
        except Exception as e:
            print("-----------------------------")
            print("PUSH_NOTIFICATIONS: {e}")
            raise InternalServerErrorException(
                f"internal server error : [PUSH_NOTIFICATIONS]"
            )

    async def GET_NOTFICATION_BY_ID(self, db: AsyncSession, notificaiton_id: int):
        try:
            result = await db.execute(
                select(Notification).filter(
                    Notification.notification_id == notificaiton_id
                )
            )
            notification_obj = result.scalar_one_or_none()
            if not notification_obj:
                raise NotFoundException("notification ID not found")
            return notification_obj
        except NotFoundException:
            raise
        except Exception as e:
            print("-----------------------------")
            print("GET_NOTFICATION_BY_ID")
            raise InternalServerErrorException(
                f"internal server error : [GET_NOTFICATION_BY_ID]"
            )

    async def GET_NOTFICATIONS_FOR_USER(self, db: AsyncSession, user_id: int):
        try:
            result = await db.execute(select(User).filter(User.user_id == user_id))
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise NotFoundException("user_id not found")
            res = await db.execute(
                select(Notification).filter(Notification.user_id == user_id)
            )
            notifications = res.scalars().all()
            return notifications
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print("GET_NOTFICATIONS_FOR_USER: {e}")
            raise InternalServerErrorException(
                f"internal server error : [GET_NOTFICATIONS_FOR_USER]"
            )
