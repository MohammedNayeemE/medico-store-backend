import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from operator import or_
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import NotFoundException
from app.models.enums import (
    OrderStatusEnum,
    PrescriptionStatusEnum,
    RequestOrderStatusEnum,
)
from app.models.inventory_management_models import (
    FamilyMember,
    Medicine,
    MedicineBatch,
    Prescription,
)
from app.models.order_management_models import (
    Order,
    OrderItem,
    RequestOrder,
    RequestOrderItem,
)
from app.models.user_management_models import User
from app.schemas.order_schemas import OrderCreate, OrderItemCreate, OrderItemUpdate
from app.schemas.request_order import (
    RequestOrderApprove,
    RequestOrderCreate,
    RequestOrderItemUpdate,
    RequestOrderResponse,
)
from app.services.file_service import FileService
from app.services.mail_service import MailService


class OrderService:
    def __init__(self) -> None:
        self.file_manager = FileService()
        self.MAX_FILE_SIZE_MB = 10
        self.ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "application/pdf"}
        self.BASE_FILE_URL = (
            "http://localhost:8000/api/file_routes/assets/prescriptions"
        )
        self.mail_service = MailService()

    def _attach_file_url(self, asset_id: str) -> str:
        return f"{self.BASE_FILE_URL}/{asset_id}"

    async def UPLOAD_PRESCRIPTION(
        self,
        file: UploadFile,
        customer_id: int,
        db: AsyncSession,
        bucket: AsyncIOMotorGridFSBucket,
        role_id: int,
    ):
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
            new_prescription = Prescription(
                customer_id=customer_id,
                asset_id=asset_id,
            )
            db.add(new_prescription)
            await db.commit()
            await db.refresh(new_prescription)
            return {
                "prescription_id": new_prescription.prescription_id,
                "asset_id": self._attach_file_url(asset_id),
            }
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
        role_id: int,
        db: AsyncSession,
        customer_id: int,
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
            prescription_list = []
            for p in prescriptions:
                prescription_list.append(
                    {
                        "prescription_id": p.prescription_id,
                        "customer_id": p.customer_id,
                        "uploaded_at": p.uploaded_at,
                        "asset_id": p.asset_id,
                        "file_url": (
                            self._attach_file_url(str(p.asset_id))
                            if p.asset_id
                            else None
                        ),
                    }
                )
            return {
                "total": total,
                "page": skip,
                "limit": limit,
                "prescriptions": prescription_list,
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
            return {
                "id": prescription.prescription_id,
                "prescription": prescription,
                "file_url": (
                    self._attach_file_url(str(prescription.asset_id))
                    if prescription.asset_id
                    else None
                ),
            }
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
        role_id: int,
        prescription_id: int,
        is_verified: bool,
        verified_by: int,
        notes: str | None = None,
    ):
        try:
            if role_id == 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
            return {
                "id": prescription.prescription_id,
                "prescription": prescription,
                "notes": notes if notes else "",
            }
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

    async def CREATE_REQUEST_ORDER(
        self, db: AsyncSession, request_data: RequestOrderCreate, current_user: User
    ) -> RequestOrderCreate:

        try:
            customer_id: int = current_user.user_id
            if request_data.prescription_id:
                result = await db.execute(
                    select(Prescription).filter(
                        Prescription.prescription_id == request_data.prescription_id,
                        Prescription.customer_id == customer_id,
                        Prescription.is_deleted == False,
                    )
                )
                prescription = result.scalar_one_or_none()
                if not prescription:
                    raise HTTPException(
                        status_code=404,
                        detail="Invalid or unauthorized prescription ID",
                    )
            medicine_ids = [item.medicine_id for item in request_data.items]
            result = await db.execute(
                select(Medicine.medicine_id).filter(
                    Medicine.medicine_id.in_(medicine_ids), Medicine.is_deleted == False
                )
            )
            valid_medicines = {row.medicine_id for row in result.all()}
            missing_ids = [mid for mid in medicine_ids if mid not in valid_medicines]
            if missing_ids:
                raise HTTPException(
                    status_code=404, detail=f"invalid medicine_ids : {missing_ids}"
                )
            batch_prices = {}
            for med_id in medicine_ids:
                batch_res = await db.execute(
                    select(MedicineBatch)
                    .filter(
                        MedicineBatch.medicine_id == med_id,
                        MedicineBatch.is_deleted == False,
                        MedicineBatch.expiry_date >= date.today(),
                        MedicineBatch.quantity > MedicineBatch.reserved_quantity,
                    )
                    .order_by(MedicineBatch.created_at.desc())
                    .limit(1)
                )
                batch = batch_res.scalar_one_or_none()
                if not batch:
                    raise NotFoundException(
                        f"Medicine {med_id} is not available in the stock"
                    )
                batch_prices[med_id] = float(batch.selling_price)
            new_order = RequestOrder(
                customer_id=customer_id,
                prescription_id=request_data.prescription_id,
                remarks=request_data.remarks,
                status=RequestOrderStatusEnum.pending.value,
                created_at=datetime.utcnow(),
                member_id=request_data.member_id,
            )
            db.add(new_order)
            await db.flush()
            for item in request_data.items:
                price_per_unit = batch_prices[item.medicine_id]
                estimated_price = price_per_unit * item.quantity
                order_item = RequestOrderItem(
                    request_order_id=new_order.request_order_id,
                    medicine_id=item.medicine_id,
                    quantity=item.quantity,
                    estimated_price=estimated_price,
                )
                db.add(order_item)
            await db.commit()
            await db.refresh(new_order)
            response = RequestOrderResponse(
                request_order_id=new_order.request_order_id,
                customer_id=new_order.customer_id,
                member_id=new_order.member_id,
                prescription_id=new_order.prescription_id,
                remarks=new_order.remarks,
                items=request_data.items,
                status=new_order.status,
                created_at=new_order.created_at,
                updated_at=new_order.updated_at,
                is_deleted=new_order.is_deleted,
                deleted_at=new_order.deleted_at,
            )
            return response
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[create_request_order] error: {e}")
            await db.rollback()
            raise HTTPException(status_code=500, detail="Internal server error")

    async def GET_MY_REQUEST_ORDERS(
        self,
        db: AsyncSession,
        current_user: User,
        skip: int = 0,
        limit: int = Query(10),
    ):
        try:
            customer_id: int = current_user.user_id
            total_result = await db.execute(
                select(func.count()).where(
                    RequestOrder.customer_id == customer_id,
                    RequestOrder.is_deleted == False,
                )
            )
            total = total_result.scalar() or 0
            query = (
                select(RequestOrder)
                .options(
                    selectinload(RequestOrder.items),
                    selectinload(RequestOrder.prescription),
                )
                .filter(
                    RequestOrder.customer_id == customer_id,
                    RequestOrder.is_deleted == False,
                )
                .order_by(RequestOrder.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            request_orders = result.scalars().unique().all()
            return {"total": total, "orders": request_orders}
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[get_my_request_orders] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error : [get_my_request_orders]",
            )

    async def GET_REQUEST_ORDER_DETAILS(
        self, db: AsyncSession, request_order_id: int, user_id: int, role_id: int
    ):
        try:
            query = (
                select(RequestOrder)
                .options(
                    selectinload(RequestOrder.items).selectinload(
                        RequestOrderItem.medicine
                    ),
                    selectinload(RequestOrder.prescription),
                )
                .filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            result = await db.execute(query)
            request_order = result.scalar_one_or_none()
            if not request_order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if role_id == 1 and request_order.customer_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to view this request order",
                )
            order_items = []
            for item in request_order.items:
                order_items.append(
                    {
                        "request_order_item_id": item.request_order_item_id,
                        "medicine_id": item.medicine_id,
                        "medicine_name": item.medicine.name if item.medicine else None,
                        "quantity": item.quantity,
                        "estimated_price": float(item.estimated_price or 0),
                    }
                )
            prescription_info = None
            if request_order.prescription:
                prescription_info = {
                    "prescription_id": request_order.prescription.prescription_id,
                    "file_url": f"http://localhost:8000/api/file_routes/assets/{request_order.prescription.asset_id}",
                }
            response = {
                "request_order_id": request_order.request_order_id,
                "customer_id": request_order.customer_id,
                "status": request_order.status,
                "remarks": request_order.remarks,
                "prescription": prescription_info,
                "items": order_items,
                "created_at": request_order.created_at,
                "updated_at": request_order.updated_at,
                "deleted_at": request_order.deleted_at,
            }
            return response
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[get_request_order_details] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [get_request_order_details]",
            )

    async def CANCEL_REQUEST_ORDER(
        self,
        db: AsyncSession,
        request_order_id: int,
        user_id: int,
    ):
        try:
            result = await db.execute(
                select(RequestOrder).filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            request_order = result.scalar_one_or_none()
            if not request_order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if request_order.customer_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to cancel this order",
                )
            if request_order.status not in [
                RequestOrderStatusEnum.pending,
                RequestOrderStatusEnum.awaiting_payment,
                RequestOrderStatusEnum.approved,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel order in status: {request_order.status}",
                )
            request_order.status = RequestOrderStatusEnum.cancelled
            request_order.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(request_order)
            return {
                "message": "Request order cancelled successfully",
                "request_order_id": request_order.request_order_id,
                "status": request_order.status,
                "updated_at": request_order.updated_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[cancel_request_order] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [cancel_request_order]",
            )

    async def GET_ALL_REQUEST_ORDERS_FOR_ADMIN(
        self,
        db: AsyncSession,
        filters: dict,
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            status = filters.get("status")
            customer_id = filters.get("customer_id")
            prescription_id = filters.get("prescription_id")
            search = filters.get("search")
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")
            sort_by = filters.get("sort_by", "created_at")
            sort_order = filters.get("sort_order", "desc")
            query = (
                select(RequestOrder)
                .options(
                    selectinload(RequestOrder.customer),
                    selectinload(RequestOrder.prescription),
                )
                .filter(RequestOrder.is_deleted == False)
            )
            if status:
                query = query.filter(RequestOrder.status == status)
            if customer_id:
                query = query.filter(RequestOrder.customer_id == customer_id)
            if prescription_id:
                query = query.filter(RequestOrder.prescription_id == prescription_id)
            if search:
                search_term = f"%{search.lower()}%"
                query = query.join(User).filter(
                    or_(
                        func.lower(User.email).like(search_term),
                        func.lower(User.phone_number).like(search_term),
                        func.lower(RequestOrder.remarks).like(search_term),
                    )
                )
            if date_from:
                try:
                    start_date = datetime.strptime(date_from, "%Y-%m-%d")
                    query = query.filter(RequestOrder.created_at >= start_date)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid date_from format. Use YYYY-MM-DD",
                    )
            if date_to:
                try:
                    end_date = datetime.strptime(date_to, "%Y-%m-%d")
                    query = query.filter(RequestOrder.created_at <= end_date)
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD"
                    )
            valid_sort_fields = {
                "created_at": RequestOrder.created_at,
                "updated_at": RequestOrder.updated_at,
            }
            sort_column = valid_sort_fields.get(sort_by, RequestOrder.created_at)
            query = query.order_by(
                asc(sort_column) if sort_order == "asc" else desc(sort_column)
            )
            count_query = query.with_only_columns(func.count()).order_by(None)
            total = (await db.execute(count_query)).scalar() or 0
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            orders = result.scalars().unique().all()
            response_orders = []
            for order in orders:
                response_orders.append(
                    {
                        "request_order_id": order.request_order_id,
                        "customer": (
                            {
                                "user_id": order.customer.user_id,
                                "email": order.customer.email,
                                "phone_number": order.customer.phone_number,
                            }
                            if order.customer
                            else None
                        ),
                        "prescription_id": order.prescription_id,
                        "status": order.status,
                        "remarks": order.remarks,
                        "created_at": order.created_at,
                        "updated_at": order.updated_at,
                    }
                )
            return {
                "total": total,
                "skip": skip,
                "limit": limit,
                "orders": response_orders,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[GET_ALL_REQUEST_ORDERS_FOR_ADMIN] error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [GET_ALL_REQUEST_ORDERS_FOR_ADMIN]",
            )

    async def MODIFY_REQUEST_ORDER_ITEMS(
        self,
        db: AsyncSession,
        request_order_id: int,
        admin_id: int,
        items: list[RequestOrderItemUpdate],
    ):
        try:
            result = await db.execute(
                select(RequestOrder)
                .options(selectinload(RequestOrder.items))
                .filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            order = result.scalar_one_or_none()
            if not order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if order.status not in [
                RequestOrderStatusEnum.pending,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot modify items for order in status: {order.status}",
                )
            for change in items:
                action = change.action.lower()
                if action == "remove":
                    existing_item = next(
                        (i for i in order.items if i.medicine_id == change.medicine_id),
                        None,
                    )
                    if not existing_item:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Medicine ID {change.medicine_id} not found in order",
                        )
                    await db.delete(existing_item)
                    continue
                med_result = await db.execute(
                    select(Medicine).filter(
                        Medicine.medicine_id == change.medicine_id,
                        Medicine.is_deleted == False,
                    )
                )
                medicine = med_result.scalar_one_or_none()
                if not medicine:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Medicine ID {change.medicine_id} not found",
                    )
                existing_item = next(
                    (i for i in order.items if i.medicine_id == change.medicine_id),
                    None,
                )
                if action == "update":
                    if not existing_item:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Medicine ID {change.medicine_id} not found in order",
                        )
                    if change.quantity is not None:
                        existing_item.quantity = change.quantity
                    if change.estimated_price is not None:
                        existing_item.estimated_price = change.estimated_price
                    continue
                if action == "add":
                    if existing_item:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Medicine ID {change.medicine_id} already exists in order",
                        )
                    price = (
                        float(change.estimated_price)
                        if change.estimated_price is not None
                        else float(medicine.price)
                    )
                    qty = change.quantity or 1
                    new_item = RequestOrderItem(
                        request_order_id=request_order_id,
                        medicine_id=change.medicine_id,
                        quantity=qty,
                        estimated_price=price * qty,
                    )
                    db.add(new_item)
            order.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(order)
            return {
                "message": "Request order items modified successfully",
                "request_order_id": order.request_order_id,
                "updated_at": order.updated_at,
                "total_items": len(order.items),
            }
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[modify_request_order_items] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [modify_request_order_items]",
            )

    async def APPROVE_REQUEST_ORDER(
        self,
        db: AsyncSession,
        request_order_id: int,
        admin_id: int,
        data: RequestOrderApprove,
    ):
        try:
            result = await db.execute(
                select(RequestOrder)
                .options(selectinload(RequestOrder.items))
                .filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            order = result.scalar_one_or_none()
            if not order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if order.status not in [
                RequestOrderStatusEnum.pending,
                RequestOrderStatusEnum.rejected,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve order in status: {order.status}",
                )
            if not order.items or len(order.items) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot approve an order with no items.",
                )
            order.status = RequestOrderStatusEnum.approved.value
            order.remarks = data.remarks or order.remarks
            order.updated_at = datetime.utcnow()
            order.deleted_at = None  # ensure it's active
            if hasattr(order, "verified_by"):
                order.verified_by = admin_id
            if hasattr(order, "verified_at"):
                order.verified_at = datetime.utcnow()
            result = await db.execute(
                select(Prescription).filter(
                    Prescription.prescription_id == order.prescription_id
                )
            )
            prescription_obj = result.scalar_one_or_none()
            if prescription_obj:
                prescription_obj.status = PrescriptionStatusEnum.verified.value
            await db.commit()
            await db.refresh(order)
            return {
                "message": "Request order approved successfully",
                "request_order_id": order.request_order_id,
                "status": order.status,
                "approved_by": admin_id,
                "updated_at": order.updated_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[approve_request_order] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [approve_request_order]",
            )

    async def REJECT_REQUEST_ORDER(
        self,
        db: AsyncSession,
        request_order_id: int,
        admin_id: int,
        reason: RequestOrderApprove,
    ):
        try:
            result = await db.execute(
                select(RequestOrder).filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            order = result.scalar_one_or_none()
            if not order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if order.status not in [
                RequestOrderStatusEnum.pending,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot reject order in status: {order.status}",
                )
            order.status = RequestOrderStatusEnum.rejected
            order.remarks = reason
            order.updated_at = datetime.utcnow()
            if hasattr(order, "verified_by"):
                order.verified_by = admin_id
            if hasattr(order, "verified_at"):
                order.verified_at = datetime.utcnow()
            await db.commit()
            await db.refresh(order)
            return {
                "message": "Request order rejected successfully",
                "request_order_id": order.request_order_id,
                "status": order.status,
                "reason": order.remarks,
                "rejected_by": admin_id,
                "updated_at": order.updated_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[reject_request_order] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [reject_request_order]",
            )

    async def CONVERT_REQUEST_TO_ORDER(
        self,
        db: AsyncSession,
        request_order_id: int,
    ) -> Order:
        try:
            result = await db.execute(
                select(RequestOrder)
                .options(selectinload(RequestOrder.items))
                .filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            request_order = result.scalar_one_or_none()
            if not request_order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if request_order.status not in (
                RequestOrderStatusEnum.approved,
                RequestOrderStatusEnum.awaiting_payment,
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot convert order in status: {request_order.status.value}",
                )
            if not request_order.items:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot convert an order with no items.",
                )

            # Sum unit_price * quantity for each request item.
            # I assume RequestOrderItem has fields: estimated_price (per-unit) and quantity.
            total_amount_dec = Decimal("0.00")
            for i in request_order.items:
                unit = Decimal(str(i.estimated_price or 0))
                qty = Decimal(str(getattr(i, "quantity", 1) or 1))
                total_amount_dec += unit * qty

            new_order = Order(
                customer_id=request_order.customer_id,
                member_id=request_order.member_id,
                prescription_id=request_order.prescription_id,
                # store numeric consistently (float or Decimal depending on your model)
                total_amount=float(total_amount_dec.quantize(Decimal("0.01"))),
                status=(
                    OrderStatusEnum.pending.value
                    if isinstance(OrderStatusEnum.pending, Enum)
                    else OrderStatusEnum.pending
                ),
                request_order_id=request_order_id,
                created_at=datetime.utcnow(),
            )
            return new_order
        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[convert_request_to_order] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [convert_request_to_order]",
            )

    async def SEND_PAYMENT_NOTIFICATION(
        self,
        db: AsyncSession,
        request_order_id: int,
        admin_id: int,
        background_tasks: BackgroundTasks,
    ):
        try:
            result = await db.execute(
                select(RequestOrder)
                .options(selectinload(RequestOrder.items))
                .filter(
                    RequestOrder.request_order_id == request_order_id,
                    RequestOrder.is_deleted == False,
                )
            )
            order = result.scalar_one_or_none()
            if not order:
                raise HTTPException(status_code=404, detail="Request order not found")
            if order.status not in [
                RequestOrderStatusEnum.approved.value,
                RequestOrderStatusEnum.awaiting_payment.value,
            ]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot send payment notification for order in status: {order.status}",
                )
            # ✅ Compute total estimated price
            total_estimated_price = sum(
                float(item.estimated_price or 0) for item in order.items
            )
            # ✅ Update status to awaiting payment
            order.status = RequestOrderStatusEnum.awaiting_payment.value
            order.updated_at = datetime.utcnow()
            if hasattr(order, "verified_by"):
                order.verified_by = admin_id
            if hasattr(order, "verified_at"):
                order.verified_at = datetime.utcnow()
            await db.commit()
            await db.refresh(order)
            user_result = await db.execute(
                select(User).filter(User.user_id == order.customer_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="Customer not found")
            user_email = user.email
            user_name = user_email.split("@")[0] if user_email else "Customer"
            # ✅ Prepare payment link
            link = f"http://localhost:8000/api/v1/payments/initiate?request_order_id={request_order_id}"
            # ✅ Queue background email notification
            background_tasks.add_task(
                self.mail_service.SEND_PAYMENT_NOTIFICATION_MAIL,
                user_email,
                user_name,
                request_order_id,
                total_estimated_price,  # ✅ fixed
                order.prescription_id,
                link,
            )
            return {
                "message": "Payment notification sent successfully",
                "request_order_id": order.request_order_id,
                "status": order.status,
                "notified_by": admin_id,
                "updated_at": order.updated_at,
                "total_estimated_price": total_estimated_price,
            }

        except HTTPException:
            raise
        except Exception as e:
            print("========================")
            print(f"[send_payment_notification] error: {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [send_payment_notification]",
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
        self,
        db: AsyncSession,
        customer_id: int,
        role_id: int,
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            if role_id != 1:
                raise HTTPException(status_code=403, detail="Forbidden Access")
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
