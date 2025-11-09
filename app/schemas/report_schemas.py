"""
Report Management Schemas
Location: app/schemas/report_schemas.py
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, validator
from app.models.enums import ReportTypeEnum, ReportFormatEnum, ReportStatusEnum


# ==================== Base Schemas ==================== #

class ReportFilterBase(BaseModel):
    """Base filters applicable to all reports"""
    date_from: Optional[datetime] = Field(None, description="Start date for report")
    date_to: Optional[datetime] = Field(None, description="End date for report")
    
    @field_validator('date_to')
    def validate_date_range(cls, v, values):
        if v and 'date_from' in values and values['date_from']:
            if v < values['date_from']:
                raise ValueError('date_to must be after date_from')
        return v


# ==================== Sales Report Schemas ==================== #

class SalesReportFilters(ReportFilterBase):
    """Filters for sales and revenue reports"""
    payment_mode: Optional[List[str]] = Field(None, description="Filter by payment modes")
    category_ids: Optional[List[int]] = Field(None, description="Filter by medicine categories")
    medicine_ids: Optional[List[int]] = Field(None, description="Filter by specific medicines")
    customer_ids: Optional[List[int]] = Field(None, description="Filter by customers")
    min_amount: Optional[float] = Field(None, ge=0, description="Minimum order amount")
    max_amount: Optional[float] = Field(None, ge=0, description="Maximum order amount")


class DailySalesSummary(BaseModel):
    """Daily sales summary data"""
    date: datetime
    total_orders: int
    total_revenue: float
    total_profit: float
    avg_order_value: float
    total_discounts: float
    total_tax: float


class RevenueBySummary(BaseModel):
    """Revenue breakdown by various dimensions"""
    category: str
    total_revenue: float
    total_orders: int
    percentage: float


class TopSellingMedicine(BaseModel):
    """Top selling medicine data"""
    medicine_id: int
    medicine_name: str
    generic_name: str
    total_quantity: int
    total_revenue: float
    total_orders: int


class ProfitMarginData(BaseModel):
    """Profit margin analysis data"""
    medicine_id: int
    medicine_name: str
    avg_purchase_price: float
    avg_selling_price: float
    profit_margin_percentage: float
    total_profit: float
    total_quantity_sold: int


# ==================== Report Request Schemas ==================== #

class ReportGenerateRequest(BaseModel):
    """Request to generate a new report"""
    report_type: ReportTypeEnum
    report_name: Optional[str] = Field(None, description="Custom name for the report")
    file_format: ReportFormatEnum = ReportFormatEnum.pdf
    filters: Dict[str, Any] = Field(default_factory=dict, description="Report-specific filters")
    send_email: bool = Field(False, description="Send report via email")
    recipient_emails: Optional[List[EmailStr]] = Field(None, description="Email recipients")
    use_cache: bool = Field(True, description="Use cached report if available")
    
    @field_validator('recipient_emails')
    def validate_emails(cls, v, values):
        if values.get('send_email') and not v:
            raise ValueError('recipient_emails required when send_email is True')
        return v


class ReportTemplateCreate(BaseModel):
    """Create a new report template"""
    template_name: str = Field(..., min_length=3, max_length=255)
    report_type: ReportTypeEnum
    description: Optional[str] = None
    default_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    default_format: ReportFormatEnum = ReportFormatEnum.pdf
    is_scheduled: bool = False
    schedule_config: Optional[Dict[str, Any]] = None


class ReportTemplateUpdate(BaseModel):
    """Update an existing report template"""
    template_name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    default_filters: Optional[Dict[str, Any]] = None
    default_format: Optional[ReportFormatEnum] = None
    is_scheduled: Optional[bool] = None
    schedule_config: Optional[Dict[str, Any]] = None


class ReportScheduleCreate(BaseModel):
    """Create a scheduled report"""
    template_id: int
    schedule_name: str = Field(..., min_length=3, max_length=255)
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    recipient_emails: List[EmailStr] = Field(..., min_items=1)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    file_format: ReportFormatEnum = ReportFormatEnum.pdf
    is_active: bool = True


class ReportScheduleUpdate(BaseModel):
    """Update a scheduled report"""
    schedule_name: Optional[str] = Field(None, min_length=3, max_length=255)
    cron_expression: Optional[str] = None
    recipient_emails: Optional[List[EmailStr]] = None
    filters: Optional[Dict[str, Any]] = None
    file_format: Optional[ReportFormatEnum] = None
    is_active: Optional[bool] = None


# ==================== Response Schemas ==================== #

class ReportTemplateResponse(BaseModel):
    """Report template response"""
    template_id: int
    template_name: str
    report_type: ReportTypeEnum
    description: Optional[str]
    default_filters: Optional[Dict[str, Any]]
    default_format: ReportFormatEnum
    is_scheduled: bool
    schedule_config: Optional[Dict[str, Any]]
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(
        from_attributes = True
    )


class GeneratedReportResponse(BaseModel):
    """Generated report response"""
    report_id: int
    template_id: Optional[int]
    report_name: str
    report_type: ReportTypeEnum
    file_format: ReportFormatEnum
    file_asset_id: Optional[int]
    filters_applied: Optional[Dict[str, Any]]
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    status: ReportStatusEnum
    error_message: Optional[str]
    file_size: Optional[int]
    cache_key: Optional[str]
    cache_expires_at: Optional[datetime]
    generated_by: int
    generated_at: datetime
    is_scheduled: bool
    download_url: Optional[str] = None

    model_config = ConfigDict(
        from_attributes = True
    )


class ReportScheduleResponse(BaseModel):
    """Report schedule response"""
    schedule_id: int
    template_id: int
    schedule_name: str
    cron_expression: str
    is_active: bool
    recipient_emails: Optional[List[str]]
    filters: Optional[Dict[str, Any]]
    file_format: ReportFormatEnum
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(
        from_attributes = True
    )


class ReportListResponse(BaseModel):
    """Paginated list of reports"""
    total: int
    page: int
    page_size: int
    reports: List[GeneratedReportResponse]


class ReportStatsResponse(BaseModel):
    """Report generation statistics"""
    total_reports: int
    reports_today: int
    reports_this_week: int
    reports_this_month: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_format: Dict[str, int]