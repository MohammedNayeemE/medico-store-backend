from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util.typing import includes_none

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.enums import OrderStatusEnum
from app.models.user_management_models import User
from app.schemas.inventory_schemas import VerifyPrescription
from app.schemas.order_schemas import (
    OrderCreate,
    OrderDetailsResponse,
    OrderItemCreate,
    OrderItemUpdate,
)
from app.services.order_management import invoice_service
from app.services.order_management.invoice_service import InvoiceService
from app.services.order_management.order_management_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])
order_manager = OrderService()
invoice_manager = InvoiceService()


@router.post("/create", description="Create a new order", include_in_schema=False)
async def create_order(
    order_data: OrderCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:write"]),
):
    """
    Create a new order from cart items or request order.
    
    Args:
        order_data: Order creation data with items and delivery details
        db: Database session
        current_user: Authenticated user (requires "order:write" permission)
    
    Returns:
        Created order object with order ID and status
    """
    result = await order_manager.CREATE_ORDER(db=db, order_data=order_data)
    return result


@router.get("/", description="List All the orders")
async def get_all_orders(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["order:read"]),
):
    """
    Get all orders. Returns different results based on user role (admin sees all, customer sees own).
    
    Args:
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        List of orders filtered by user role
    """
    result = await order_manager.GET_ALL_ORDERS(db=db, role_id=current_user.role_id)
    return result


@router.get("/my-orders", description="Get all orders for a customer")
async def get_customer_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["order:read"]),
):
    """
    Get paginated list of orders for the authenticated customer.
    
    Args:
        skip: Number of records to skip (pagination offset)
        limit: Maximum number of records to return (pagination limit, max 100)
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        Paginated list of customer orders
    """
    result = await order_manager.GET_CUSTOMER_ORDERS(
        db=db,
        customer_id=current_user.user_id,
        skip=skip,
        limit=limit,
        role_id=current_user.role_id,
    )
    return result


@router.get(
    "/{order_id}",
    description="Get order details (items, payment, invoice)",
    response_model=OrderDetailsResponse,
)
async def get_order_details(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:read"]),
):
    """
    Get detailed information about a specific order including items, payment, and invoice.
    
    Args:
        order_id: Unique identifier of the order
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        OrderDetailsResponse with order items, payment info, and invoice details
    """
    result = await order_manager.GET_ORDER_DETAILS(db=db, order_id=order_id)
    return result


@router.patch("/{order_id}/status", description="Update status of an order")
async def update_order_status(
    order_id: int = Path(...),
    status: OrderStatusEnum = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:write"]),
):
    """
    Update the status of an order (e.g., pending, confirmed, shipped, delivered, cancelled).
    
    Args:
        order_id: Unique identifier of the order to update
        status: New order status (OrderStatusEnum)
        db: Database session
        current_user: Authenticated user (requires "order:write" permission)
    
    Returns:
        Updated order object with new status
    """
    result = await order_manager.UPDATE_ORDER_STATUS(
        db=db, order_id=order_id, new_status=status
    )
    return result


@router.delete(
    "/{order_id}", description="Soft delete an order", include_in_schema=False
)
async def soft_delete_order(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["order:delete"]),
):
    """
    Soft delete an order (mark as deleted without permanent removal).
    
    Args:
        order_id: Unique identifier of the order to delete
        db: Database session
        current_user: Authenticated user (requires "order:delete" permission)
    
    Returns:
        Success message confirming order deletion
    """
    result = await order_manager.SOFT_DELETE_ORDER(
        db=db, order_id=order_id, deleted_by=current_user.user_id
    )
    return result


# ================== ORDER ITEMS ===================== #


@router.get("/{order_id}/items", description="Get all items in a particular order")
async def get_order_items(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:read"]),
):
    """
    Get all items in a specific order.
    
    Args:
        order_id: Unique identifier of the order
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        List of order items with medicine details and quantities
    """
    result = await order_manager.GET_ORDER_ITEMS(db=db, order_id=order_id)
    return result


# ================== INVOICES ===================== #


# @router.post(
#     "/invoices/generate/{order_id}",
#     description="Generate an invoice for a completed order",
# )
# async def generate_invoice(
#     order_id: int = Path(...),
#     db: AsyncSession = Depends(get_postgres),
#     current_user=Security(get_current_user, scopes=["order:write"]),
# ):
#     result = await invoice_manager.GENERATE_INVOICE(db=db, order_id=order_id)
#     return result


@router.get(
    "/invoices/my-invoices",
    description="Get all invoices for a specific customer",
)
async def get_customer_invoices(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["order:read"]),
):
    """
    Get all invoices for the authenticated customer.
    
    Args:
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        List of invoices for the customer
    """
    result = await invoice_manager.GET_CUSTOMER_INVOICES(
        db=db, customer_id=current_user.user_id, role_id=current_user.role_id
    )
    return result


@router.get(
    "/invoices/{invoice_id}",
    description="Get invoice details by invoice_id",
)
async def get_invoice_details(
    invoice_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:read"]),
):
    """
    Get detailed information about a specific invoice.
    
    Args:
        invoice_id: Unique identifier of the invoice
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        Invoice details with order information, items, and payment status
    """
    result = await invoice_manager.GET_INVOICE_DETAILS(db=db, invoice_id=invoice_id)
    return result


@router.get(
    "/invoices/{invoice_id}/download",
    description="Download invoice as a PDF file",
    include_in_schema=False,
)
async def download_invoice_pdf(
    invoice_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["order:read"]),
):
    """
    Download invoice as a PDF file.
    
    Args:
        invoice_id: Unique identifier of the invoice
        db: Database session
        current_user: Authenticated user (requires "order:read" permission)
    
    Returns:
        PDF file stream of the invoice
    """
    pass


# @router.put(
#     "/invoices/{invoice_id}/status",
#     description="Update invoice/payment status (paid/unpaid)",
#     include_in_schema=False,
# )
# async def update_invoice_status(
#     invoice_id: int = Path(...),
#     status: str = Body(..., embed=True),
#     updated_by: Optional[int] = Body(None, embed=True),
#     db: AsyncSession = Depends(get_postgres),
#     current_user=Security(get_current_user, scopes=["order:write"]),
# ):
#     """Update the payment status of the invoice. Allowed: paid, unpaid."""
#     pass
