from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    TIMESTAMP,
    JSON,
    func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import ReportStatusEnum, ReportTypeEnum, ReportFormatEnum


class ReportTemplate(Base):
    """Stores reusable report templates"""
    __tablename__ = "report_templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True)
    template_name = Column(String(255), nullable=False, unique=True, index=True)
    report_type = Column(
        Enum(ReportTypeEnum, name="report_type_enum"),
        nullable=False,
        index=True
    )
    description = Column(Text)
    query_template = Column(Text, nullable=False)  # SQL query template
    default_filters = Column(JSON)  # Default filter configuration
    default_format = Column(
        Enum(ReportFormatEnum, name="report_format_enum"),
        nullable=False,
        server_default=ReportFormatEnum.pdf.value
    )
    is_scheduled = Column(Boolean, default=False)
    schedule_config = Column(JSON)  # Cron-like schedule configuration
    created_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    generated_reports = relationship("GeneratedReport", back_populates="template")


class GeneratedReport(Base):
    """Stores metadata for generated reports"""
    __tablename__ = "generated_reports"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(
        Integer, 
        ForeignKey("report_templates.template_id", onupdate="CASCADE"),
        nullable=False,
        index=True
    )
    report_name = Column(String(255), nullable=False)
    report_type = Column(
        Enum(ReportTypeEnum, name="report_type_enum"),
        nullable=False,
        index=True
    )
    file_format = Column(
        Enum(ReportFormatEnum, name="report_format_enum"),
        nullable=False
    )
    file_asset_id = Column(
        Integer,
        ForeignKey("file_assets.asset_id", onupdate="CASCADE")
    )
    filters_applied = Column(JSON)  # Stores the filters used for generation
    date_range_start = Column(DateTime(timezone=True), index=True)
    date_range_end = Column(DateTime(timezone=True), index=True)
    status = Column(
        Enum(ReportStatusEnum, name="report_status_enum"),
        nullable=False,
        server_default=ReportStatusEnum.pending.value,
        index=True
    )
    error_message = Column(Text)
    file_size = Column(Integer)  # in bytes
    cache_key = Column(String(255), unique=True, index=True)
    cache_expires_at = Column(TIMESTAMP(timezone=True))
    generated_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False)
    generated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_scheduled = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    # Relationships
    template = relationship("ReportTemplate", back_populates="generated_reports")
    file_asset = relationship("FileAsset")
    generator = relationship("User", foreign_keys=[generated_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    email_deliveries = relationship("ReportEmailDelivery", back_populates="report")


class ReportEmailDelivery(Base):
    """Tracks email deliveries of reports"""
    __tablename__ = "report_email_deliveries"

    delivery_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(
        Integer,
        ForeignKey("generated_reports.report_id", onupdate="CASCADE"),
        nullable=False,
        index=True
    )
    recipient_email = Column(String(255), nullable=False)
    sent_at = Column(TIMESTAMP(timezone=True))
    delivery_status = Column(String(50), default="pending")  # pending, sent, failed
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    report = relationship("GeneratedReport", back_populates="email_deliveries")


class ReportSchedule(Base):
    """Manages scheduled report generation"""
    __tablename__ = "report_schedules"

    schedule_id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(
        Integer,
        ForeignKey("report_templates.template_id", onupdate="CASCADE"),
        nullable=False,
        index=True
    )
    schedule_name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)  # e.g., "0 9 * * 1" for every Monday at 9 AM
    is_active = Column(Boolean, default=True, index=True)
    recipient_emails = Column(JSON)  # List of email addresses
    filters = Column(JSON)  # Filters to apply
    file_format = Column(
        Enum(ReportFormatEnum, name="report_format_enum"),
        nullable=False,
        server_default=ReportFormatEnum.pdf.value
    )
    last_run_at = Column(TIMESTAMP(timezone=True))
    next_run_at = Column(TIMESTAMP(timezone=True), index=True)
    created_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    # Relationships
    template = relationship("ReportTemplate")
    creator = relationship("User", foreign_keys=[created_by])
    deleter = relationship("User", foreign_keys=[deleted_by])