from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.audit_log_schemas import AuditLogBase


class AuditLogService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["audit_logs"]

    async def LOG_ACTION(
        self,
        actor_id: Optional[int],
        actor_role: Optional[str],
        action: str,
        resource: str,
        resource_id: Optional[Any] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "SUCCESS",
    ):
        """Insert a new audit log entry into MongoDB."""
        log_entry = AuditLogBase(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource=resource,
            resource_id=resource_id,
            old_data=old_data,
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            timestamp=datetime.utcnow(),
        )
        await self.collection.insert_one(log_entry.dict())

    async def GET_LOGS(
        self,
        actor_id: Optional[int] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditLogBase]:
        """Fetch audit logs filtered by actor, resource, or action."""
        query = {}
        if actor_id:
            query["actor_id"] = actor_id
        if resource:
            query["resource"] = resource
        if action:
            query["action"] = action
        cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
        return [AuditLogBase(**doc) async for doc in cursor]

    async def CLEAR_LOGS(self):
        await self.collection.delete_many({})
