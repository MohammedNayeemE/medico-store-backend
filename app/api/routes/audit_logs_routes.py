from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.dependecies.get_db_sessions import get_mongo_db  # your mongo dependency
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/logs", tags=["Audit LOGS"])


@router.get("/")
async def get_audit_logs(mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    audit_service = AuditLogService(mongo_db)
    logs = await audit_service.GET_LOGS(limit=20)
    return [log.dict() for log in logs]
