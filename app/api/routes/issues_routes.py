from fastapi import APIRouter, Body, Path, UploadFile, File, Depends, Security
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres

router = APIRouter(prefix="/issues", tags=["Issues"])

# ================== ISSUE CATEGORIES ===================== #

@router.get("/issue_categories/", description="List all issue categories")
async def list_issue_categories(
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    """Get a list of all defined issue categories (e.g., delivery, payment, returns)."""
    pass

@router.post("/issue_categories/", description="Create a new issue category (admin only)")
async def create_issue_category(
    category: dict = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Admin creates a new issue category."""
    pass

@router.put("/issue_categories/{category_id}", description="Update details for an existing issue category")
async def update_issue_category(
    category_id: int = Path(...),
    category: dict = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Update name or properties of an issue category."""
    pass

@router.delete("/issue_categories/{category_id}", description="Soft delete an issue category")
async def soft_delete_issue_category(
    category_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Soft delete (deactivate) the issue category."""
    pass

# ================== ISSUES ===================== #

@router.post("/create", description="Raise a new issue (customer)")
async def create_issue(
    order_id: int = Body(..., embed=True),
    category_id: int = Body(..., embed=True),
    description: str = Body(..., embed=True),
    customer_id: Optional[int] = Body(None, embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    """Raise an issue for an order, specifying category & description. Customer-initiated."""
    pass

@router.get("/{issue_id}", description="Fetch details for a specific issue")
async def get_issue_details(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """Fetch all info associated with an issue: status, messages, assignment, etc."""
    pass

@router.get("/customer/{customer_id}", description="List all issues raised by a customer")
async def list_issues_by_customer(
    customer_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """Get all issues recorded by a particular customer."""
    pass

@router.get("/order/{order_id}", description="List issues for a given order")
async def list_issues_by_order(
    order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:read"]),
):
    """Retrieve all issues related to the specified order_id."""
    pass

@router.put("/{issue_id}/status", description="Update status of an issue (open, in_progress, resolved, closed)")
async def update_issue_status(
    issue_id: int = Path(...),
    status: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Update issue status (open, in_progress, resolved, closed)."""
    pass

@router.put("/{issue_id}/assign", description="Assign the issue to a support staff member")
async def assign_issue(
    issue_id: int = Path(...),
    assigned_to: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Manually assign the issue to a support staff member."""
    pass

@router.delete("/{issue_id}", description="Soft delete an issue")
async def soft_delete_issue(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["admin:write"]),
):
    """Soft delete (deactivate) the issue."""
    pass

# ========== ISSUE MESSAGES & ATTACHMENTS ========== #

@router.post("/{issue_id}/messages", description="Add a message to an issue (customer/support)")
async def add_issue_message(
    issue_id: int = Path(...),
    message: dict = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    """Add a new message (as customer or support staff) to an existing issue."""
    pass

@router.get("/{issue_id}/messages", description="List all messages for an issue")
async def get_issue_messages(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """Fetch all messages for the specified issue in order."""
    pass

@router.post("/issue_messages/{message_id}/attachments", description="Upload a file/image attachment for an issue message")
async def upload_message_attachment(
    message_id: int = Path(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:write"]),
):
    """Upload an attachment to an issue message. Only 1 file per call."""
    pass

@router.get("/issue_messages/{message_id}/attachments", description="Get all attachments for a message")
async def get_message_attachments(
    message_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user=Security(get_current_user, scopes=["user:read"]),
):
    """Fetch all attachments belonging to a specific issue message."""
    pass
