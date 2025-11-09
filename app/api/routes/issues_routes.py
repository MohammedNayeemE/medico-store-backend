from fastapi import APIRouter, Body, Depends, File, Path, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import roles

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.models.enums import IssueStatusEnum
from app.models.user_management_models import User
from app.schemas.issue_schemas import (
    IssueAssign,
    IssueCategoryCreate,
    IssueCategoryUpdate,
    IssueCreate,
    IssueMessageCreate,
    IssueStatusUpdate,
)
from app.services.issue_service import IssueService

router = APIRouter(prefix="/issues", tags=["Issues"])
issue_manager = IssueService()

# ================== ISSUE CATEGORIES ===================== #


@router.get("/issue_categories/", description="List all issue categories")
async def list_issue_categories(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Get a list of all defined issue categories (e.g., delivery, payment, returns)."""
    result = await issue_manager.LIST_ISSUE_CATEGORIES(
        db=db, role_id=current_user.role_id
    )
    return result


@router.post(
    "/issue_categories/", description="Create a new issue category (admin only)"
)
async def create_issue_category(
    category_data: IssueCategoryCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Admin creates a new issue category."""
    result = await issue_manager.CREATE_ISSUE_CATEGORY(
        db=db,
        category_data=category_data,
        role_id=current_user.role_id,
    )
    return result


@router.put(
    "/issue_categories/{category_id}",
    description="Update details for an existing issue category",
)
async def update_issue_category(
    category_id: int = Path(...),
    category_data: IssueCategoryUpdate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Update name or properties of an issue category."""
    result = await issue_manager.UPDATE_ISSUE_CATEGORY(
        db=db,
        category_id=category_id,
        category_data=category_data,
        role_id=current_user.role_id,
    )
    return result


@router.delete(
    "/issue_categories/{category_id}", description="Soft delete an issue category"
)
async def soft_delete_issue_category(
    category_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Soft delete (deactivate) the issue category."""
    result = await issue_manager.SOFT_DELETE_ISSUE_CATEGORY(
        db=db,
        category_id=category_id,
        admin_id=current_user.user_id,
        role_id=current_user.role_id,
    )
    return result


# ================== ISSUES ===================== #


@router.post("/create", description="Raise a new issue (customer)")
async def create_issue(
    issue_data: IssueCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Raise an issue for an order, specifying category & description. Customer-initiated."""
    result = await issue_manager.CREATE_ISSUE(
        db=db,
        customer_id=current_user.user_id,
        issue_data=issue_data,
        role_id=current_user.role_id,
    )
    return result


@router.get("/{issue_id}", description="Fetch details for a specific issue")
async def get_issue_details(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Fetch all info associated with an issue: status, messages, assignment, etc."""
    result = await issue_manager.GET_ISSUE_DETAILS(db=db, issue_id=issue_id)
    return result


@router.get("/my-issues", description="List all issues raised by a customer")
async def list_issues_by_customer(
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Get all issues recorded by a particular customer."""
    customer_id: int = current_user.user_id
    result = await issue_manager.LIST_ISSUES_BY_CUSTOMER(db=db, customer_id=customer_id)
    return result


@router.get(
    "/request_order/{request_order_id}", description="List issues for a given order"
)
async def list_issues_by_order(
    request_order_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Retrieve all issues related to the specified order_id."""
    result = await issue_manager.LIST_ISSUES_BY_ORDER(
        db=db, req_order_id=request_order_id
    )
    return result


@router.put(
    "/{issue_id}/status",
    description="Update status of an issue (open, in_progress, resolved, closed)",
)
async def update_issue_status(
    issue_id: int = Path(...),
    status_data: IssueStatusEnum = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Update issue status (open, in_progress, resolved, closed)."""
    result = await issue_manager.UPDATE_ISSUE_STATUS(
        db=db, issue_id=issue_id, status=status_data, role_id=current_user.role_id
    )
    return result


@router.put(
    "/{issue_id}/assign", description="Assign the issue to a support staff member"
)
async def assign_issue(
    issue_id: int = Path(...),
    assign_data: IssueAssign = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Manually assign the issue to a support staff member."""
    result = await issue_manager.ASSIGN_ISSUE(
        db=db,
        issue_id=issue_id,
        assigned_to=assign_data.assigned_to,
        role_id=current_user.role_id,
    )
    return result


@router.delete("/{issue_id}", description="Soft delete an issue")
async def soft_delete_issue(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Soft delete (deactivate) the issue."""
    result = await issue_manager.SOFT_DELETE_ISSUE(
        db=db, issue_id=issue_id, deleted_by=current_user.user_id
    )
    return result


# ========== ISSUE MESSAGES & ATTACHMENTS ========== #


@router.post(
    "/{issue_id}/messages", description="Add a message to an issue (customer/support)"
)
async def add_issue_message(
    issue_id: int = Path(...),
    message_data: IssueMessageCreate = Body(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Add a new message (as customer or support staff) to an existing issue."""
    result = await issue_manager.ADD_ISSUE_MESSAGE(
        db=db,
        issue_id=issue_id,
        sender_id=current_user.user_id,
        message_data=message_data,
    )
    return result


@router.get("/{issue_id}/messages", description="List all messages for an issue")
async def get_issue_messages(
    issue_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Fetch all messages for the specified issue in order."""
    result = await issue_manager.GET_ISSUE_MESSAGES(db=db, issue_id=issue_id)
    return result


@router.post(
    "/issue_messages/{message_id}/attachments",
    description="Upload a file/image attachment for an issue message",
)
async def upload_message_attachment(
    message_id: int = Path(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:write"]),
):
    """Upload an attachment to an issue message. Only 1 file per call."""
    result = await issue_manager.UPLOAD_MESSAGE_ATTACHMENT(
        user_id=current_user.user_id, db=db, message_id=message_id, file=file
    )
    return result


@router.get(
    "/issue_messages/{message_id}/attachments",
    description="Get all attachments for a message",
)
async def get_message_attachments(
    message_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["issue:read"]),
):
    """Fetch all attachments belonging to a specific issue message."""
    result = await issue_manager.GET_MESSAGE_ATTACHMENTS(db=db, message_id=message_id)
    return result
