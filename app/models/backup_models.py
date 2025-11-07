from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.core.database import Base


class Backup(Base):
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    backup_type = Column(String(50), nullable=False, default="full")  # full | partial
    parts = Column(Text, nullable=True)  # e.g., "postgres,mongo,files"
    status = Column(String(50), nullable=False, default="queued")
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    artifact_path = Column(Text)
    size_bytes = Column(BigInteger)
    created_by = Column(String(255))
    error_message = Column(Text)


class Restore(Base):
    __tablename__ = "restores"

    id = Column(Integer, primary_key=True)
    backup_id = Column(Integer, ForeignKey("backups.id", ondelete="CASCADE"))
    environment = Column(String(50), default="production")
    status = Column(String(50), nullable=False, default="queued")
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True))
    restored_by = Column(String(255))
    error_message = Column(Text)
