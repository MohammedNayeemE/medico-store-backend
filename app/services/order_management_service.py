import json
from datetime import datetime
from operator import or_
from typing import Any, Dict, List, Optional

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.enums import OrderStatusEnum, PrescriptionStatusEnum
from app.models.inventory_management_models import (
    FamilyMember,
    MedicineBatch,
    Prescription,
)
from app.models.order_management_models import Order, OrderItem
from app.models.user_management_models import User
from app.schemas.order_schemas import OrderCreate, OrderItemCreate, OrderItemUpdate
from app.services.file_service import FileService


class OrderService:
    def __init__(self) -> None:
        self.file_manager = FileService()
        self.MAX_FILE_SIZE_MB = 10
        self.ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "application/pdf"}

    async def UPLOAD_PRESCRIPTION(
        self,
        file: UploadFile,
        customer_id: int,
        db: AsyncSession,
        bucket: AsyncIOMotorGridFSBucket,
    ):
        try:
            if file.content_type not in self.ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file.content_type}. "
                    f"Allowed types are: {', '.join(self.ALLOWED_CONTENT_TYPES)}",
                )
            content = await file.read()
            file_size_mb = len(content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large ({file_size_mb:.2f} MB). "
                    f"Maximum allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            await file.seek(0)
            result = await self.file_manager.UPLOAD_SINGLE_FILE(
                bucket=bucket, db=db, file=file, user_id=customer_id
            )
            asset_id = result["asset_id"]
            return {"asset_id": asset_id}
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[upload_prescription] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [upload_prescription]"
            )

    async def GET_CUSTOMER_PRESCRIPTIONS(
        self,
        db: AsyncSession,
        customer_id: int,
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            result = await db.execute(
                select(User).filter(
                    User.user_id == customer_id, User.is_deleted == False
                )
            )
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise HTTPException(status_code=404, detail="customer_id doesn't exist")
            total_query = select(func.count()).where(
                Prescription.customer_id == customer_id,
                Prescription.is_deleted == False,
            )
            total = (await db.execute(total_query)).scalar() or 0
            query = (
                select(Prescription)
                .where(
                    Prescription.customer_id == customer_id,
                    Prescription.is_deleted == False,
                )
                .order_by(Prescription.uploaded_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            prescriptions = result.scalars().unique().all()
            return {
                "total": total,
                "page": skip,
                "limit": limit,
                "prescriptions": prescriptions,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("----------------------")
            print(f"[get_customer_prescriptions] : {e}")
            raise HTTPException(status_code=500, detail="internal server error")

    async def GET_PRESCRIPTION_DETAILS(
        self,
        db: AsyncSession,
        prescription_id: int,
    ):
        try:
            query = (
                select(Prescription)
                .options(selectinload(Prescription.prescription_items))
                .where(
                    Prescription.prescription_id == prescription_id,
                    Prescription.is_deleted == False,
                )
            )
            result = await db.execute(query)
            prescription = result.scalar_one_or_none()
            if not prescription:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prescription ID {prescription_id} not found",
                )
            return prescription
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------------")
            print(f"[get_prescription_details] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error: [get_prescription_details]",
            )

    async def VERIFY_PRESCRIPTION(
        self,
        db: AsyncSession,
        prescription_id: int,
        is_verified: bool,
        verified_by: int,
        notes: str | None = None,
    ):
        try:
            result = await db.execute(
                select(Prescription).where(
                    Prescription.prescription_id == prescription_id,
                    Prescription.is_deleted == False,
                )
            )
            prescription = result.scalar_one_or_none()
            if not prescription:
                raise HTTPException(status_code=404, detail="Prescription not found")
            if prescription.status != PrescriptionStatusEnum.pending.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Prescription already marked as '{prescription.status}'",
                )
            prescription.status = (
                PrescriptionStatusEnum.verified.value
                if is_verified
                else PrescriptionStatusEnum.rejected.value
            )
            prescription.verified_by = verified_by
            prescription.verified_at = datetime.utcnow()
            if notes:
                print(f"Notes for prescription {prescription_id}: {notes}")
            await db.commit()
            await db.refresh(prescription)
            return {"prescription": prescription, "notes": notes if notes else ""}
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------")
            print(f"[verify_prescription] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error: [verify_prescription]",
            )

    async def SOFT_DELETE_PRESCRIPTION(
        self,
        db: AsyncSession,
        prescription_id: int,
        deleted_by: int,
    ):
        try:
            result = await db.execute(
                select(Prescription).where(
                    Prescription.prescription_id == prescription_id,
                    Prescription.is_deleted == False,
                )
            )
            prescription = result.scalar_one_or_none()
            if not prescription:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prescription with ID {prescription_id} not found or already deleted",
                )
            prescription.is_deleted = True
            prescription.deleted_at = datetime.utcnow()
            prescription.deleted_by = deleted_by
            await db.commit()
            return {
                "message": "Prescription deleted successfully",
                "prescription_id": prescription_id,
                "deleted_by": deleted_by,
                "deleted_at": prescription.deleted_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------------")
            print(f"[soft_delete_prescription] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error: [soft_delete_prescription]",
            )

    async def CREATE_ORDER(self, db: AsyncSession, order_data: OrderCreate):
        result = await db.execute(
            select(User).filter(User.user_id == order_data.customer_id)
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        if order_data.member_id:
            result = await db.execute(
                select(FamilyMember).filter(
                    FamilyMember.member_id == order_data.member_id
                )
            )
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Family member not found")
        if order_data.prescription_id:
            result = await db.execute(
                select(Prescription).filter(
                    Prescription.prescription_id == order_data.prescription_id
                )
            )
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Prescription not found")
        new_order = Order(
            customer_id=order_data.customer_id,
            member_id=order_data.member_id,
            prescription_id=order_data.prescription_id,
            total_amount=order_data.total_amount,
            status=OrderStatusEnum.pending.value,
            created_at=datetime.utcnow(),
        )
        db.add(new_order)
        await db.flush()
        for item in order_data.items:
            new_item = OrderItem(
                order_id=new_order.order_id,
                batch_id=item.batch_id,
                quantity=item.quantity,
                price=item.price,
            )
            db.add(new_item)
        await db.commit()
        await db.refresh(new_order)
        return new_order

    async def GET_ORDER_DETAILS(self, db: AsyncSession, order_id: int):
        try:
            result = await db.execute(
                select(Order)
                .options(
                    selectinload(Order.customer),
                    selectinload(Order.member),
                    selectinload(Order.prescription),
                    selectinload(Order.order_items).selectinload(OrderItem.batch),
                    selectinload(Order.invoice),
                    selectinload(Order.payments),
                )
                .filter(Order.order_id == order_id, Order.is_deleted == False)
            )
            order_obj = result.scalar_one_or_none()
            if not order_obj:
                raise HTTPException(status_code=404, detail="Order not found")
            return order_obj
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------------")
            print(f"[get_order_details_service]: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [get_order_details]"
            )

    async def GET_CUSTOMER_ORDERS(
        self, db: AsyncSession, customer_id: int, skip: int = 0, limit: int = 10
    ):
        try:
            result = await db.execute(
                select(Order)
                .options(
                    selectinload(Order.order_items).selectinload(OrderItem.batch),
                    selectinload(Order.invoice),
                    selectinload(Order.payments),
                )
                .filter(Order.customer_id == customer_id, Order.is_deleted == False)
                .order_by(Order.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            orders = result.scalars().all()
            return orders
        except Exception as e:
            print(f"[get_customer_orders_service]: {e}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error [get_customer_orders]"
            )

    async def UPDATE_ORDER_STATUS(
        self,
        db: AsyncSession,
        order_id: int,
        new_status: OrderStatusEnum,
    ):
        try:
            result = await db.execute(
                select(Order).filter(
                    Order.order_id == order_id, Order.is_deleted == False
                )
            )
            order_obj = result.scalar_one_or_none()
            if not order_obj:
                raise HTTPException(status_code=404, detail="Order not found")
            valid_transitions = {
                OrderStatusEnum.pending: [
                    OrderStatusEnum.shipped,
                    OrderStatusEnum.cancelled,
                ],
                OrderStatusEnum.shipped: [
                    OrderStatusEnum.delivered,
                    OrderStatusEnum.cancelled,
                ],
                OrderStatusEnum.delivered: [],
                OrderStatusEnum.cancelled: [],
            }
            if new_status not in valid_transitions[order_obj.status]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot change status from '{order_obj.status}' to '{new_status}'",
                )
            order_obj.status = new_status
            order_obj.updated_at = datetime.utcnow()
            await db.flush()
            await db.commit()
            await db.refresh(order_obj)
            return order_obj
        except HTTPException:
            raise
        except Exception as e:
            print("----------------------------")
            print(f"[update_order_status_service] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error [update_order_status]"
            )

    async def SOFT_DELETE_ORDER(self, db: AsyncSession, order_id: int, deleted_by: int):
        try:
            result = await db.execute(
                select(Order).filter(
                    Order.order_id == order_id, Order.is_deleted == False
                )
            )
            order_obj = result.scalar_one_or_none()
            if not order_obj:
                raise HTTPException(status_code=404, detail="Order not found")
            order_obj.is_deleted = True
            order_obj.deleted_at = datetime.utcnow()
            order_obj.deleted_by = deleted_by
            await db.commit()
            await db.refresh(order_obj)
            return {"message": "Order soft deleted successfully", "order_id": order_id}
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------")
            print(f"[soft_delete_order_service] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error [soft_delete_order]"
            )

    async def GET_ORDER_ITEMS(self, order_id: int, db: AsyncSession):
        try:
            results = await db.execute(
                select(OrderItem).filter(OrderItem.order_id == order_id)
            )
            items = results.scalars().all()
            if not items:
                raise HTTPException(status_code=404, detail="order id not found")
            return items
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"get_order_items : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_order_items]"
            )

    async def ADD_ORDER_ITEM(
        self, order_id: int, order_item: OrderItemCreate, db: AsyncSession
    ):
        try:
            result = await db.execute(select(Order).filter(Order.order_id == order_id))
            order_obj = result.scalar_one_or_none()
            if not order_obj:
                raise HTTPException(status_code=404, detail="order id not found")
            result = await db.execute(
                select(MedicineBatch).filter(
                    MedicineBatch.batch_id == order_item.batch_id
                )
            )
            batch_obj = result.scalar_one_or_none()
            if not batch_obj:
                raise HTTPException(status_code=404, detail="batch id not found")
            new_order_item = OrderItem(
                order_id=order_id,
                batch_id=batch_obj.batch_id,
                quantity=order_item.quantity,
                price=order_item.price,
            )
            db.add(new_order_item)
            await db.commit()
            await db.refresh(new_order_item)
            return new_order_item
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"add_order_item: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [add_order_item]"
            )

    async def UPDATE_ORDER_ITEM(
        self, db: AsyncSession, order_item_id: int, order_item: OrderItemUpdate
    ):
        try:
            result = await db.execute(
                select(OrderItem).filter(OrderItem.order_item_id == order_item_id)
            )
            order_item_obj = result.scalar_one_or_none()
            if not order_item_obj:
                raise HTTPException(status_code=404, detail="order_item_id not found")
            order_item_obj.quantity = order_item.quantity
            order_item_obj.price = order_item.price
            order_item_obj.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(order_item_obj)
            return order_item_obj
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"update_order_item :  {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [update_order_item]"
            )

    async def SOFT_DELETE_ORDER_ITEM(
        self, db: AsyncSession, order_item_id: int, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(OrderItem).filter(OrderItem.order_item_id == order_item_id)
            )
            item = result.scalar_one_or_none()
            if not item or item.is_deleted:
                raise HTTPException(
                    status_code=404, detail="Order item not found or already deleted."
                )
            item.is_deleted = True
            item.deleted_at = datetime.utcnow()
            item.deleted_by = deleted_by
            await db.commit()
            return {"message": f"Order item {order_item_id} soft deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"soft_delete_order_item :  {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [soft_delete_order_item]",
            )
