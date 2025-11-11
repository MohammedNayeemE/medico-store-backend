from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.audit_log_schemas import AuditLogBase


class AuditLogService:
    """
    Service class for managing audit logs.
    
    Handles audit log creation, retrieval, and filtering for tracking system activities.
    """
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
        """
        Insert a new audit log entry into MongoDB.
        
        Args:
            actor_id: ID of the user performing the action
            actor_role: Role of the user performing the action
            action: Action performed (e.g., "create", "update", "delete")
            resource: Resource type (e.g., "user", "order", "medicine")
            resource_id: ID of the resource being acted upon
            old_data: Optional previous state of the resource
            new_data: Optional new state of the resource
            ip_address: Optional IP address of the actor
            user_agent: Optional user agent of the actor
            status: Action status (default: "SUCCESS")
        """
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
        """
        Fetch audit logs filtered by actor, resource, or action.
        
        Args:
            actor_id: Optional filter by actor ID
            resource: Optional filter by resource type
            action: Optional filter by action type
            limit: Maximum number of logs to return (default: 50)
        
        Returns:
            List of audit log entries
        """
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
