from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class BackupCreate(BaseModel):
    name: str
    backup_type: str  # e.g. "manual" or "scheduled"
    parts: Optional[List[str]] = None  # ["postgres", "mongo"]
    postgres_tables: Optional[List[str]] = (
        None  # ⬅️ new field for selective table backup
    )


class BackupRead(BaseModel):
    id: int
    name: str
    backup_type: str
    parts: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    artifact_path: Optional[str]
    size_bytes: Optional[int]
    created_by: Optional[str]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)
