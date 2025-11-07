from enum import Enum as PyEnum

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    by_user_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=True
    )
    type = Column(Enum(NotificationType, name="notification_type"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    read_at = Column(TIMESTAMP(timezone=True))
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    # ------------------------------------------------------------
    # Relationships (optional but helpful)
    # ------------------------------------------------------------
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref="received_notifications",
    )

    created_by = relationship(
        "User",
        foreign_keys=[by_user_id],
        backref="sent_notifications",
    )

    deleted_by_user = relationship(
        "User",
        foreign_keys=[deleted_by],
        backref="deleted_notifications",
    )
