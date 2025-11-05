from datetime import datetime

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory_management_models import (
    Medicine,
    MedicineRequest,
    RequestStatusEnum,
)
from app.models.user_management_models import User
from app.schemas.request_medicines_schemas import (
    MedicineRequestCreate,
    MedicineRequestVerify,
)
from app.services.mail_service import MailService


class RequestMedicineService:
    def __init__(self) -> None:
        self.mail_service = MailService()

    async def CREATE_MEDICINE_REQUEST(
        self, db: AsyncSession, user_id: int, request_data: MedicineRequestCreate
    ):
        try:
            result = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == request_data.requested_medicine_id,
                    Medicine.is_deleted == False,
                )
            )
            medicine_obj = result.scalar_one_or_none()
            if not medicine_obj:
                raise HTTPException(
                    status_code=404, detail="Requested medicine not found"
                )
            new_request = MedicineRequest(
                user_id=user_id,
                requested_medicine_id=request_data.requested_medicine_id,
                note_text=request_data.note_text,
                note_img=request_data.note_img,
                status=RequestStatusEnum.pending,
            )
            db.add(new_request)
            await db.commit()
            await db.refresh(new_request)
            return new_request
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------------------")
            print(f"[CREATE_MEDICINE_REQUEST] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error [CREATE_MEDICINE_REQUEST]",
            )

    async def GET_USER_REQUESTS(
        self, db: AsyncSession, user_id: int, skip: int = 0, limit: int = 10
    ):
        try:
            query = (
                select(MedicineRequest)
                .options(selectinload(MedicineRequest.requested_medicine))
                .filter(
                    MedicineRequest.user_id == user_id,
                    MedicineRequest.is_deleted == False,
                )
                .order_by(MedicineRequest.requested_time.desc())
                .offset(skip)
                .limit(limit)
            )
            results = await db.execute(query)
            requests = results.scalars().all()
            return requests
        except Exception as e:
            print("-----------------------------------")
            print(f"[GET_USER_REQUESTS] Error: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [GET_USER_REQUESTS]"
            )

    async def GET_REQUEST_DETAILS(
        self, db: AsyncSession, user_id: int, request_id: int
    ):
        try:
            query = (
                select(MedicineRequest)
                .options(selectinload(MedicineRequest.requested_medicine))
                .filter(
                    MedicineRequest.request_id == request_id,
                    MedicineRequest.is_deleted == False,
                )
            )
            result = await db.execute(query)
            request_obj = result.scalar_one_or_none()
            if not request_obj or request_obj.user_id != user_id:
                raise HTTPException(
                    status_code=404, detail="Request not found or not owned by user"
                )
            return request_obj
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------")
            print(f"[GET_REQUEST_DETAILS] Error: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [GET_REQUEST_DETAILS]"
            )

    async def SOFT_DELETE_REQUEST(
        self, db: AsyncSession, user_id: int, request_id: int
    ):
        try:
            result = await db.execute(
                select(MedicineRequest).filter(
                    MedicineRequest.request_id == request_id,
                    MedicineRequest.is_deleted == False,
                )
            )
            req_obj = result.scalar_one_or_none()
            if not req_obj or req_obj.user_id != user_id:
                raise HTTPException(
                    status_code=404, detail="Request not found or not owned by user"
                )
            req_obj.is_deleted = True
            req_obj.deleted_at = datetime.utcnow()
            req_obj.deleted_by = user_id
            await db.commit()
            return {
                "message": "Medicine request deleted successfully",
                "request_id": request_id,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------")
            print(f"[SOFT_DELETE_REQUEST] Error: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [SOFT_DELETE_REQUEST]"
            )

    async def GET_ALL_REQUESTS(self, db: AsyncSession, skip: int = 0, limit: int = 20):
        try:
            query = (
                select(MedicineRequest)
                .options(
                    selectinload(MedicineRequest.user),
                    selectinload(MedicineRequest.requested_medicine),
                )
                .filter(MedicineRequest.is_deleted == False)
                .order_by(MedicineRequest.requested_time.desc())
                .offset(skip)
                .limit(limit)
            )
            results = await db.execute(query)
            requests = results.scalars().all()
            return requests
        except Exception as e:
            print("--------------------------------------")
            print(f"[ADMIN_GET_ALL_REQUESTS] Error: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [GET_ALL_REQUESTS]"
            )

    async def VERIFY_MEDICINE_REQUEST(
        self,
        db: AsyncSession,
        request_id: int,
        admin_id: int,
        verify_data: MedicineRequestVerify,
        background_tasks: BackgroundTasks,
    ):
        try:
            result = await db.execute(
                select(MedicineRequest).filter(
                    MedicineRequest.request_id == request_id,
                    MedicineRequest.is_deleted == False,
                )
            )
            request_obj = result.scalar_one_or_none()
            if not request_obj:
                raise HTTPException(
                    status_code=404, detail="Medicine request not found"
                )
            if request_obj.status != RequestStatusEnum.pending.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Request already marked as '{request_obj.status}'",
                )
            request_obj.status = (
                RequestStatusEnum.verified
                if verify_data.is_verified
                else RequestStatusEnum.rejected
            )
            request_obj.admin_response = verify_data.response
            request_obj.verified_by = admin_id
            request_obj.verified_at = datetime.utcnow()
            await db.commit()
            await db.refresh(request_obj)
            result = await db.execute(
                select(User).filter(User.user_id == request_obj.user_id)
            )
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise HTTPException(status_code=404, detail="User not found")
            user_email = user_obj.email
            user_name = user_email.split("@")[0]
            result = await db.execute(
                select(Medicine.medicine_name, Medicine.generic_name).filter(
                    Medicine.medicine_id == request_obj.requested_medicine_id
                )
            )
            medicine_data = result.first()
            if not medicine_data:
                raise HTTPException(status_code=404, detail="Medicine not found")
            medicine_name, generic_name = medicine_data
            background_tasks.add_task(
                self.mail_service.SEND_MEDICINE_REQUEST_STATUS_MAIL,
                user_email=str(user_email),
                user_name=user_name,
                medicine_name=medicine_name,
                generic_name=generic_name,
                status=request_obj.status.value,
                response=str(request_obj.admin_response),
            )
            return request_obj
        except HTTPException:
            raise
        except Exception as e:
            print("=======================================")
            print(f"[VERIFY_MEDICINE_REQUEST] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error [VERIFY_MEDICINE_REQUEST]",
            )
