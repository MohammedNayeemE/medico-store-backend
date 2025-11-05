from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import IssueStatusEnum
from app.models.order_management_models import (Issue, IssueAttachment,
                                                IssueCategory, IssueMessage,
                                                Order)
from app.models.user_management_models import User
from app.schemas.issue_schemas import (IssueCategoryCreate,
                                       IssueCategoryUpdate, IssueCreate,
                                       IssueMessageCreate)
from app.services.file_service import FileService


class IssueService:
    def __init__(self):
        self.file_service = FileService()

    # ==================== ISSUE CATEGORIES ==================== #

    async def LIST_ISSUE_CATEGORIES(self, db: AsyncSession):
        try:
            result = await db.execute(
                select(IssueCategory).filter(IssueCategory.is_deleted == False)
            )
            return result.scalars().all()
        except Exception as e:
            print(f"[LIST_ISSUE_CATEGORIES] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def CREATE_ISSUE_CATEGORY(
        self, db: AsyncSession, category_data: IssueCategoryCreate, admin_id: int
    ):
        try:
            new_category = IssueCategory(
                name=category_data.name, description=category_data.description
            )
            db.add(new_category)
            await db.commit()
            await db.refresh(new_category)
            return new_category
        except Exception as e:
            print("=====================================")
            print(f"[CREATE_ISSUE_CATEGORY] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def UPDATE_ISSUE_CATEGORY(
        self, db: AsyncSession, category_id: int, category_data: IssueCategoryUpdate
    ):
        try:
            result = await db.execute(
                select(IssueCategory).filter(IssueCategory.category_id == category_id)
            )
            category_obj = result.scalar_one_or_none()
            if not category_obj:
                raise HTTPException(status_code=404, detail="Category not found")

            category_obj.name = category_data.name
            category_obj.description = category_data.description
            await db.commit()
            await db.refresh(category_obj)
            return category_obj
        except HTTPException:
            raise
        except Exception as e:
            print("===================================")
            print(f"[UPDATE_ISSUE_CATEGORY] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def SOFT_DELETE_ISSUE_CATEGORY(
        self, db: AsyncSession, category_id: int, admin_id: int
    ):
        try:
            result = await db.execute(
                select(IssueCategory).filter(IssueCategory.category_id == category_id)
            )
            category_obj = result.scalar_one_or_none()
            if not category_obj:
                raise HTTPException(status_code=404, detail="Category not found")

            category_obj.is_deleted = True
            category_obj.deleted_at = datetime.utcnow()
            category_obj.deleted_by = admin_id
            await db.commit()
        except HTTPException:
            raise
        except Exception as e:
            print("=============================================")
            print(f"[SOFT_DELETE_ISSUE_CATEGORY] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # ==================== ISSUES ==================== #

    async def CREATE_ISSUE(
        self, db: AsyncSession, customer_id: int, issue_data: IssueCreate
    ):
        try:
            if issue_data.order_id:
                result = await db.execute(select(Order).filter(Order.order_id == issue_data.order_id))
                order_obj = result.scalar_one_or_none()
                if not order_obj:
                    raise HTTPException(status_code=404, detail="Order not found")

            new_issue = Issue(
                customer_id=customer_id,
                order_id=issue_data.order_id,
                category_id=issue_data.category_id,
                description=issue_data.description,
                status=IssueStatusEnum.open,
                opened_at=datetime.utcnow(),
            )
            db.add(new_issue)
            await db.commit()
            await db.refresh(new_issue)
            return new_issue
        except Exception as e:
            print("============================")
            print(f"[CREATE_ISSUE] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def GET_ISSUE_DETAILS(self, db: AsyncSession, issue_id: int):
        try:
            result = await db.execute(
                select(Issue)
                .options(selectinload(Issue.messages))
                .filter(Issue.issue_id == issue_id, Issue.is_deleted == False)
            )
            issue_obj = result.scalar_one_or_none()
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")
            return issue_obj
        except HTTPException:
            raise
        except Exception as e:
            print("================================")
            print(f"[GET_ISSUE_DETAILS] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def LIST_ISSUES_BY_CUSTOMER(self, db: AsyncSession, customer_id: int):
        try:
            result = await db.execute(
                select(Issue)
                .filter(Issue.customer_id == customer_id, Issue.is_deleted == False)
                .order_by(Issue.opened_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            print("================================")
            print(f"[LIST_ISSUES_BY_CUSTOMER] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def LIST_ISSUES_BY_ORDER(self, db: AsyncSession, order_id: int):
        try:
            result = await db.execute(
                select(Issue).filter(
                    Issue.order_id == order_id, Issue.is_deleted == False
                )
            )
            return result.scalars().all()
        except Exception as e:
            print("================================")
            print(f"[LIST_ISSUES_BY_ORDER] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def UPDATE_ISSUE_STATUS(self, db: AsyncSession, issue_id: int, status: str):
        try:
            result = await db.execute(select(Issue).filter(Issue.issue_id == issue_id))
            issue_obj = result.scalar_one_or_none()
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

            issue_obj.status = status
            if status.lower() == IssueStatusEnum.closed.value:
                issue_obj.closed_at = datetime.utcnow()

            await db.commit()
            await db.refresh(issue_obj)
            return issue_obj
        except Exception as e:
            print("================================")
            print(f"[UPDATE_ISSUE_STATUS] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def ASSIGN_ISSUE(self, db: AsyncSession, issue_id: int, assigned_to: int):
        try:
            result = await db.execute(select(Issue).filter(Issue.issue_id == issue_id))
            issue_obj = result.scalar_one_or_none()
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

            issue_obj.assigned_to = assigned_to
            await db.commit()
            await db.refresh(issue_obj)
            return issue_obj
        except Exception as e:
            print("================================")
            print(f"[ASSIGN_ISSUE] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def SOFT_DELETE_ISSUE(self, db: AsyncSession, issue_id: int, deleted_by: int):
        try:
            result = await db.execute(select(Issue).filter(Issue.issue_id == issue_id))
            issue_obj = result.scalar_one_or_none()
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

            issue_obj.is_deleted = True
            issue_obj.deleted_at = datetime.utcnow()
            issue_obj.deleted_by = deleted_by
            await db.commit()
        except Exception as e:
            return {"message": f"Issue {issue_id} deleted successfully"}
            print(f"[SOFT_DELETE_ISSUE] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def ADD_ISSUE_MESSAGE(
        self,
        db: AsyncSession,
        issue_id: int,
        sender_id: int,
        message_data: IssueMessageCreate,
    ):
        try:
            result = await db.execute(
                select(Issue).filter(
                    Issue.issue_id == issue_id, Issue.is_deleted == False
                )
            )
            issue_obj = result.scalar_one_or_none()
            if not issue_obj:
                raise HTTPException(status_code=404, detail="Issue not found")

            new_msg = IssueMessage(
                issue_id=issue_id,
                sender_id=sender_id,
                message=message_data.message,
                message_type=message_data.message_type
            )
            db.add(new_msg)
            await db.commit()
            await db.refresh(new_msg)
            return new_msg
        except Exception as e:
            print('==============================')
            print(f"[ADD_ISSUE_MESSAGE] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def GET_ISSUE_MESSAGES(self, db: AsyncSession, issue_id: int):
        try:
            result = await db.execute(
                select(IssueMessage)
                .filter(
                    IssueMessage.issue_id == issue_id, IssueMessage.is_deleted == False
                )
                .order_by(IssueMessage.created_at.asc())
            )
            return result.scalars().all()
        except Exception as e:
            print('==============================')
            print(f"[GET_ISSUE_MESSAGES] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # ==================== ATTACHMENTS ==================== #

    async def UPLOAD_MESSAGE_ATTACHMENT(
        self, db: AsyncSession, message_id: int, file: UploadFile
    ):
        try:
            uploaded_file = await self.file_service.UPLOAD_SINGLE_FILE(
                db=db, file=file, user_id=None
            )
            new_attachment = IssueAttachment(
                message_id=message_id,
                file_name=file.filename,
                file_url=uploaded_file.get("url"),
                file_type=file.content_type,
            )
            db.add(new_attachment)
            await db.commit()
            await db.refresh(new_attachment)
            return new_attachment
        except Exception as e:
            print('==============================')
            print(f"[UPLOAD_MESSAGE_ATTACHMENT] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def GET_MESSAGE_ATTACHMENTS(self, db: AsyncSession, message_id: int):
        try:
            result = await db.execute(
                select(IssueAttachment)
                .filter(
                    IssueAttachment.message_id == message_id,
                    IssueAttachment.is_deleted == False,
                )
                .order_by(IssueAttachment.uploaded_at.asc())
            )
            return result.scalars().all()
        except Exception as e:
            print('==============================')
            print(f"[GET_MESSAGE_ATTACHMENTS] Error: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
