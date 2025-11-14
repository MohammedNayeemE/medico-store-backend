from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Security,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.enums import OrderStatusEnum, RequestOrderStatusEnum
from app.models.user_management_models import User
from app.schemas.inventory_schemas import VerifyPrescription
from app.schemas.order_schemas import OrderCreate, OrderItemCreate, OrderItemUpdate
from app.schemas.request_order import (
    RequestOrderApprove,
    RequestOrderCreate,
    RequestOrderItemUpdate,
    RequestOrderReject,
)
from app.services.order_management.order_management_service import OrderService

router = APIRouter(prefix="/request-orders", tags=["Request Orders"])
order_manager = OrderService()

# ============= CUSTOMER ENDPOINTS ============= #


@router.post("/create", description="Customer creates a new request order")
async def create_request_order(
    request_data: RequestOrderCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:write"]),
):
    result = await order_manager.CREATE_REQUEST_ORDER(
        db=db, current_user=current_user, request_data=request_data
    )
    return result


@router.get("/", description="Get all request orders for current customer")
async def get_my_request_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:read"]),
):
    result = await order_manager.GET_MY_REQUEST_ORDERS(
        db=db, current_user=current_user, skip=skip, limit=limit
    )
    return result


@router.get(
    "/admin",
    description="Admin: Get all request orders with filters, pagination, and sorting",
)
async def admin_get_all_request_orders(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(
        get_current_user, scopes=["request_order_admin:read"]
    ),
    status: RequestOrderStatusEnum | None = Query(None),
    customer_id: int | None = Query(None),
    prescription_id: int | None = Query(None),
    search: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
):
    result = await order_manager.GET_ALL_REQUEST_ORDERS_FOR_ADMIN(
        db=db,
        filters={
            "status": status,
            "customer_id": customer_id,
            "prescription_id": prescription_id,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/{request_order_id}", description="Get request order details")
async def get_request_order_details(
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:read"]),
):
    result = await order_manager.GET_REQUEST_ORDER_DETAILS(
        db=db,
        request_order_id=request_order_id,
        user_id=current_user.user_id,
        role_id=current_user.role_id,
    )
    return result


@router.delete("/{request_order_id}", description="Cancel a request order")
async def cancel_request_order(
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:write"]),
):
    result = await order_manager.CANCEL_REQUEST_ORDER(
        db=db, request_order_id=request_order_id, user_id=current_user.user_id
    )
    return result


@router.post(
    "/{request_order_id}/confirm",
    description="Customer confirms the approved request order",
)
async def confirm_request_order(
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:write"]),
):
    result = await order_manager.CONFIRM_REQUEST_ORDER(
        db=db,
        request_order_id=request_order_id,
        user_id=current_user.user_id,
    )
    return {"message": "Request order confirmed successfully", "result": result}


@router.post(
    "/{request_order_id}/reject",
    description="Customer rejects the approved request order",
)
async def reject_request_order(
    request_order_id: int = Path(...),
    reason: RequestOrderReject = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["request_order:write"]),
):
    result = await order_manager.CUSTOMER_REJECT_REQUEST_ORDER(
        db=db,
        request_order_id=request_order_id,
        user_id=current_user.user_id,
        reason=reason,
    )
    return {"message": "Request order rejected by customer", "result": result}


# ============= ADMIN ENDPOINTS ============= #


@router.post(
    "/{request_order_id}/change-status",
    description="Admin: Change the status of the request order (approve/reject)",
)
async def change_status_of_request_order(
    background_tasks: BackgroundTasks,
    request_order_id: int = Path(...),
    status: RequestOrderStatusEnum = Query(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(
        get_current_user, scopes=["request_order_admin:update"]
    ),
    reason: RequestOrderApprove | RequestOrderReject = Body(...),
):
    if status == RequestOrderStatusEnum.approved:
        result = await order_manager.MOVE_TO_PENDING_CUSTOMER_CONFIRMATION(
            db=db,
            request_order_id=request_order_id,
            admin_id=current_user.user_id,
            data=reason,
        )
        await order_manager.SEND_PAYMENT_NOTIFICATION(
            db=db,
            request_order_id=request_order_id,
            admin_id=current_user.user_id,
            background_tasks=background_tasks,
        )
        return {
            "message": "Request order moved to 'pending_customer_confirmation'. Notification sent to customer.",
            "result": result,
        }
    elif status == RequestOrderStatusEnum.rejected:
        result = await order_manager.REJECT_REQUEST_ORDER(
            db=db,
            admin_id=current_user.user_id,
            reason=reason,
            request_order_id=request_order_id,
        )
        return {"message": "Request order rejected successfully", "result": result}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition to {status}. Only 'approved' or 'rejected' are allowed here.",
        )


@router.post(
    "/{request_order_id}/notify-payment",
    description="Send payment notification to customer",
    include_in_schema=False,
)
async def notify_payment(
    background_tasks: BackgroundTasks,
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(
        get_current_user, scopes=["request_order_admin:update"]
    ),
):
    result = await order_manager.SEND_PAYMENT_NOTIFICATION(
        db=db,
        request_order_id=request_order_id,
        admin_id=current_user.user_id,
        background_tasks=background_tasks,
    )
    return result


@router.post(
    "/{request_order_id}/convert",
    description="Convert request order to final order (after payment)",
    include_in_schema=False,
)
async def convert_to_final_order(
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await order_manager.CONVERT_REQUEST_TO_ORDER(
        db=db, request_order_id=request_order_id
    )
    return result


@router.put(
    "/{request_order_id}/items",
    description="Admin: Add, update, or remove medicine items from a request order",
)
async def modify_request_order_items(
    request_order_id: int = Path(..., description="ID of the request order to modify"),
    items: List[RequestOrderItemUpdate] = Body(
        ..., description="List of item modifications"
    ),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(
        get_current_user, scopes=["request_order_admin:update"]
    ),
):
    result = await order_manager.MODIFY_REQUEST_ORDER_ITEMS(
        db=db,
        request_order_id=request_order_id,
        admin_id=current_user.user_id,
        items=items,
    )
    return result
