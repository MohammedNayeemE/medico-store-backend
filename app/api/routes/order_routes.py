from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.enums import OrderStatusEnum
from app.models.user_management_models import User
from app.schemas.inventory_schemas import VerifyPrescription
from app.schemas.order_schemas import OrderCreate, OrderItemCreate, OrderItemUpdate
from app.services.order_management_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders", "Prescriptions"])
order_manager = OrderService()

# ================== PRESCRIPTIONS ===================== #


@router.post(
    "/prescriptions/upload",
    description="Upload a new prescription with file and customer_id",
)
async def upload_prescription(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.UPLOAD_PRESCRIPTION(
        db=db, file=file, customer_id=current_user.user_id, bucket=bucket
    )
    return result


@router.get(
    "/prescriptions/{customer_id}",
    description="Get all prescriptions for a specific customer",
)
async def get_customer_prescriptions(
    customer_id: int = Path(...),
    skip: int = Query(0, ge=0, description="range"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_CUSTOMER_PRESCRIPTIONS(
        db=db, customer_id=customer_id, skip=skip, limit=limit
    )
    return result


@router.get(
    "/prescriptions/details/{prescription_id}",
    description="Get prescription details and items",
)
async def get_prescription_details(
    prescription_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_PRESCRIPTION_DETAILS(
        db=db, prescription_id=prescription_id
    )
    return result


@router.put(
    "/prescriptions/verify/{prescription_id}",
    description="Mark prescription as verified or rejected (pharmacist/admin)",
)
async def verify_prescription(
    prescription_id: int = Path(...),
    prescription_data: VerifyPrescription = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.VERIFY_PRESCRIPTION(
        db=db,
        prescription_id=prescription_id,
        is_verified=prescription_data.is_verified,
        verified_by=current_user.user_id,
        notes=prescription_data.notes,
    )
    return result


@router.delete(
    "/prescriptions/{prescription_id}", description="Soft delete a prescription"
)
async def soft_delete_prescription(
    prescription_id: int = Path(...),
    deleted_by: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = order_manager.SOFT_DELETE_PRESCRIPTION(
        db=db, prescription_id=prescription_id, deleted_by=current_user.user_id
    )
    return result


# ================== ORDERS ===================== #


@router.post("/create", description="Create a new order")
async def create_order(
    order_data: OrderCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.CREATE_ORDER(db=db, order_data=order_data)
    return result


@router.get("/{order_id}", description="Get order details (items, payment, invoice)")
async def get_order_details(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_ORDER_DETAILS(db=db, order_id=order_id)
    return result


@router.get("/customer/{customer_id}", description="Get all orders for a customer")
async def get_customer_orders(
    customer_id: int = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_CUSTOMER_ORDERS(
        db=db, customer_id=customer_id, skip=skip, limit=limit
    )
    return result


@router.put("/{order_id}/status", description="Update status of an order")
async def update_order_status(
    order_id: int = Path(...),
    status: OrderStatusEnum = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.UPDATE_ORDER_STATUS(
        db=db, order_id=order_id, new_status=status
    )
    return result


@router.delete("/{order_id}", description="Soft delete an order")
async def soft_delete_order(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.SOFT_DELETE_ORDER(
        db=db, order_id=order_id, deleted_by=current_user.user_id
    )
    return result


# ================== ORDER ITEMS ===================== #


@router.get("/{order_id}/items", description="Get all items in a particular order")
async def get_order_items(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    result = await order_manager.GET_ORDER_ITEMS(db=db, order_id=order_id)
    return result


@router.post("/{order_id}/items/add", description="Add a new item to an existing order")
async def add_order_item(
    order_id: int = Path(...),
    order_item: OrderItemCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.ADD_ORDER_ITEM(
        db=db, order_id=order_id, order_item=order_item
    )
    return result


@router.put(
    "/order_items/{order_item_id}", description="Update order item quantity or price"
)
async def update_order_item(
    order_item_id: int = Path(...),
    order_item: OrderItemUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.UPDATE_ORDER_ITEM(
        db=db, order_item_id=order_item_id, order_item=order_item
    )
    return result


@router.delete("/order_items/{order_item_id}", description="Soft delete an order item")
async def soft_delete_order_item(
    order_item_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
):
    result = await order_manager.SOFT_DELETE_ORDER_ITEM(
        db=db, order_item_id=order_item_id, deleted_by=current_user.user_id
    )
    return result


# ================== INVOICES ===================== #


@router.post(
    "/invoices/generate/{order_id}",
    description="Generate an invoice for a completed order",
)
async def generate_invoice(
    order_id: int = Path(...),
    generated_by: Optional[int] = Body(None, embed=True),
    include_taxes: Optional[bool] = Body(True, embed=True),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Generate an invoice for the given order. Optionally include taxes and notes."""
    pass


@router.get(
    "/invoices/{invoice_id}",
    description="Get invoice details by invoice_id",
)
async def get_invoice_details(
    invoice_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    """Retrieve the invoice record with totals, taxes, items, and status."""
    pass


@router.get(
    "/invoices/customer/{customer_id}",
    description="Get all invoices for a specific customer",
)
async def get_customer_invoices(
    customer_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    """List all invoices that belong to the specified customer."""
    pass


@router.get(
    "/invoices/{invoice_id}/download",
    description="Download invoice as a PDF file",
)
async def download_invoice_pdf(
    invoice_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    """Download the invoice PDF for the specified invoice_id."""
    pass


@router.put(
    "/invoices/{invoice_id}/status",
    description="Update invoice/payment status (paid/unpaid)",
)
async def update_invoice_status(
    invoice_id: int = Path(...),
    status: str = Body(..., embed=True),
    updated_by: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Update the payment status of the invoice. Allowed: paid, unpaid."""
    pass
