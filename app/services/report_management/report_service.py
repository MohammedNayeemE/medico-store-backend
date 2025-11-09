"""
Main Report Service
Location: app/services/report_management/report_service.py
"""

import io
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.report_management_models import (
    GeneratedReport, ReportTemplate, ReportSchedule, ReportEmailDelivery
)
from app.models.enums import ReportStatusEnum, ReportTypeEnum, ReportFormatEnum
from app.schemas.report_schemas import (
    ReportGenerateRequest, ReportTemplateCreate, ReportTemplateUpdate,
    ReportScheduleCreate, ReportScheduleUpdate
)
from app.services.cache_service import CacheService
from app.services.file_service import FileService
from app.services.mail_service import MailService
from app.services.report_management.sales_report_service import SalesReportService
from app.services.report_management.report_export_service import ReportExportService


class ReportService:
    """Main service for report generation and management"""
    
    def __init__(
        self,
        db: Session,
        cache_service: CacheService,
        file_service: FileService,
        mail_service: MailService
    ):
        self.db = db
        self.cache_service = cache_service
        self.file_service = file_service
        self.mail_service = mail_service
        
        # Initialize report type services
        self.sales_service = SalesReportService(db, cache_service)
        self.export_service = ReportExportService()
    
    # ==================== Report Generation ==================== #
    
    async def generate_report(
        self,
        request: ReportGenerateRequest,
        user_id: int
    ) -> GeneratedReport:
        """Generate a new report based on request"""
        
        # Check cache if requested
        if request.use_cache:
            cached_report = await self._get_cached_report(
                request.report_type,
                request.filters
            )
            if cached_report:
                return cached_report
        
        # Create report record
        report = GeneratedReport(
            report_name=request.report_name or f"{request.report_type.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            report_type=request.report_type,
            file_format=request.file_format,
            filters_applied=request.filters,
            date_range_start=request.filters.get('date_from'),
            date_range_end=request.filters.get('date_to'),
            status=ReportStatusEnum.processing,
            generated_by=user_id,
            cache_key=self._generate_cache_key(request.report_type, request.filters),
            cache_expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        try:
            # Generate report data
            data = await self._generate_report_data(
                request.report_type,
                request.filters
            )
            
            # Export to requested format
            exported_file = await self._export_report(
                data=data,
                report_type=request.report_type,
                file_format=request.file_format,
                filters=request.filters
            )
            
            # Save file
            file_asset = await self.file_service.save_report_file(
                file_data=exported_file,
                filename=f"{report.report_name}.{request.file_format.value}",
                content_type=self._get_content_type(request.file_format)
            )
            
            # Update report record
            report.file_asset_id = file_asset.asset_id
            report.file_size = len(exported_file)
            report.status = ReportStatusEnum.completed
            
            self.db.commit()
            self.db.refresh(report)
            
            # Send email if requested
            if request.send_email and request.recipient_emails:
                await self._send_report_email(
                    report=report,
                    recipients=request.recipient_emails
                )
            
            return report
            
        except Exception as e:
            # Update report status to failed
            report.status = ReportStatusEnum.failed
            report.error_message = str(e)
            self.db.commit()
            raise AppException(
                status_code=500,
                detail=f"Failed to generate report: {str(e)}"
            )
    
    async def _generate_report_data(
        self,
        report_type: ReportTypeEnum,
        filters: Dict[str, Any]
    ) -> Any:
        """Generate report data based on type"""
        
        # Sales & Revenue Reports
        if report_type == ReportTypeEnum.daily_sales_summary:
            return await self.sales_service.generate_sales_summary('daily', filters)
        
        elif report_type == ReportTypeEnum.weekly_sales_summary:
            return await self.sales_service.generate_sales_summary('weekly', filters)
        
        elif report_type == ReportTypeEnum.monthly_sales_summary:
            return await self.sales_service.generate_sales_summary('monthly', filters)
        
        elif report_type == ReportTypeEnum.yearly_sales_summary:
            return await self.sales_service.generate_sales_summary('yearly', filters)
        
        elif report_type == ReportTypeEnum.revenue_by_payment_mode:
            return await self.sales_service.generate_revenue_by_payment_mode(filters)
        
        elif report_type == ReportTypeEnum.sales_by_category:
            return await self.sales_service.generate_sales_by_category(filters)
        
        elif report_type == ReportTypeEnum.top_selling_medicines:
            limit = filters.get('limit', 10)
            return await self.sales_service.generate_top_selling_medicines(filters, limit)
        
        elif report_type == ReportTypeEnum.revenue_trends:
            return await self.sales_service.generate_revenue_trends(filters)
        
        elif report_type == ReportTypeEnum.profit_margin_analysis:
            return await self.sales_service.generate_profit_margin_analysis(filters)
        
        elif report_type == ReportTypeEnum.discount_impact_analysis:
            return await self.sales_service.generate_discount_impact_analysis(filters)
        
        elif report_type == ReportTypeEnum.coupon_effectiveness:
            return await self.sales_service.generate_coupon_effectiveness(filters)
        
        # Add more report types here
        else:
            raise AppException(
                status_code=400,
                detail=f"Report type {report_type.value} not implemented yet"
            )
    
    async def _export_report(
        self,
        data: Any,
        report_type: ReportTypeEnum,
        file_format: ReportFormatEnum,
        filters: Dict[str, Any]
    ) -> bytes:
        """Export report data to requested format"""
        
        if file_format == ReportFormatEnum.pdf:
            return await self.export_service.export_to_pdf(
                data=data,
                report_type=report_type,
                filters=filters
            )
        
        elif file_format == ReportFormatEnum.excel:
            return await self.export_service.export_to_excel(
                data=data,
                report_type=report_type
            )
        
        elif file_format == ReportFormatEnum.csv:
            return await self.export_service.export_to_csv(
                data=data,
                report_type=report_type
            )
        
        elif file_format == ReportFormatEnum.json:
            return json.dumps(data, default=str, indent=2).encode('utf-8')
        
        else:
            raise AppException(
                status_code=400,
                detail=f"Unsupported export format: {file_format.value}"
            )
    
    def _generate_cache_key(self, report_type: ReportTypeEnum, filters: Dict[str, Any]) -> str:
        """Generate cache key for report"""
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        hash_input = f"{report_type.value}:{filter_str}"
        return f"report:{hashlib.md5(hash_input.encode()).hexdigest()}"
    
    async def _get_cached_report(
        self,
        report_type: ReportTypeEnum,
        filters: Dict[str, Any]
    ) -> Optional[GeneratedReport]:
        """Check if cached report exists"""
        cache_key = self._generate_cache_key(report_type, filters)
        
        report = (
            self.db.query(GeneratedReport)
            .filter(
                GeneratedReport.cache_key == cache_key,
                GeneratedReport.status == ReportStatusEnum.completed,
                GeneratedReport.cache_expires_at > datetime.utcnow(),
                GeneratedReport.is_deleted == False
            )
            .first()
        )
        
        return report
    
    def _get_content_type(self, file_format: ReportFormatEnum) -> str:
        """Get content type for file format"""
        content_types = {
            ReportFormatEnum.pdf: "application/pdf",
            ReportFormatEnum.excel: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ReportFormatEnum.csv: "text/csv",
            ReportFormatEnum.json: "application/json"
        }
        return content_types.get(file_format, "application/octet-stream")
    
    async def _send_report_email(
        self,
        report: GeneratedReport,
        recipients: List[str]
    ):
        """Send report via email"""
        for recipient in recipients:
            try:
                # Get file data
                file_data = await self.file_service.get_file(report.file_asset_id)
                
                # Send email
                await self.mail_service.send_report_email(
                    to_email=recipient,
                    report_name=report.report_name,
                    report_type=report.report_type.value,
                    attachment_data=file_data,
                    attachment_filename=f"{report.report_name}.{report.file_format.value}"
                )
                
                # Log delivery
                delivery = ReportEmailDelivery(
                    report_id=report.report_id,
                    recipient_email=recipient,
                    sent_at=datetime.utcnow(),
                    delivery_status="sent"
                )
                self.db.add(delivery)
                
            except Exception as e:
                # Log failed delivery
                delivery = ReportEmailDelivery(
                    report_id=report.report_id,
                    recipient_email=recipient,
                    delivery_status="failed",
                    error_message=str(e)
                )
                self.db.add(delivery)
        
        self.db.commit()
    
    # ==================== Report Template Management ==================== #
    
    async def create_template(
        self,
        template_data: ReportTemplateCreate,
        user_id: int
    ) -> ReportTemplate:
        """Create a new report template"""
        
        # Check for duplicate name
        existing = (
            self.db.query(ReportTemplate)
            .filter(
                ReportTemplate.template_name == template_data.template_name,
                ReportTemplate.is_deleted == False
            )
            .first()
        )
        
        if existing:
            raise AppException(
                status_code=400,
                detail="Template with this name already exists"
            )
        
        template = ReportTemplate(
            **template_data.dict(),
            created_by=user_id,
            query_template=""  # Would be populated based on report type
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    async def update_template(
        self,
        template_id: int,
        template_data: ReportTemplateUpdate,
        user_id: int
    ) -> ReportTemplate:
        """Update an existing report template"""
        
        template = (
            self.db.query(ReportTemplate)
            .filter(
                ReportTemplate.template_id == template_id,
                ReportTemplate.is_deleted == False
            )
            .first()
        )
        
        if not template:
            raise AppException(status_code=404, detail="Template not found")
        
        # Update fields
        for field, value in template_data.dict(exclude_unset=True).items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    async def delete_template(self, template_id: int, user_id: int):
        """Soft delete a report template"""
        
        template = (
            self.db.query(ReportTemplate)
            .filter(
                ReportTemplate.template_id == template_id,
                ReportTemplate.is_deleted == False
            )
            .first()
        )
        
        if not template:
            raise AppException(status_code=404, detail="Template not found")
        
        template.is_deleted = True
        template.deleted_at = datetime.utcnow()
        template.deleted_by = user_id
        
        self.db.commit()
    
    async def get_templates(
        self,
        report_type: Optional[ReportTypeEnum] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get list of report templates"""
        
        query = self.db.query(ReportTemplate).filter(
            ReportTemplate.is_deleted == False
        )
        
        if report_type:
            query = query.filter(ReportTemplate.report_type == report_type)
        
        total = query.count()
        
        templates = (
            query
            .order_by(desc(ReportTemplate.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'templates': templates
        }
    
    # ==================== Report List & Stats ==================== #
    
    async def get_reports(
        self,
        user_id: Optional[int] = None,
        report_type: Optional[ReportTypeEnum] = None,
        status: Optional[ReportStatusEnum] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get list of generated reports"""
        
        query = self.db.query(GeneratedReport).filter(
            GeneratedReport.is_deleted == False
        )
        
        if user_id:
            query = query.filter(GeneratedReport.generated_by == user_id)
        
        if report_type:
            query = query.filter(GeneratedReport.report_type == report_type)
        
        if status:
            query = query.filter(GeneratedReport.status == status)
        
        total = query.count()
        
        reports = (
            query
            .order_by(desc(GeneratedReport.generated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'reports': reports
        }
    
    async def get_report_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get report generation statistics"""
        
        query = self.db.query(GeneratedReport).filter(
            GeneratedReport.is_deleted == False
        )
        
        if user_id:
            query = query.filter(GeneratedReport.generated_by == user_id)
        
        total_reports = query.count()
        
        # Reports by status
        by_status = dict(
            self.db.query(
                GeneratedReport.status,
                func.count(GeneratedReport.report_id)
            )
            .filter(GeneratedReport.is_deleted == False)
            .group_by(GeneratedReport.status)
            .all()
        )
        
        # Reports by type
        by_type = dict(
            self.db.query(
                GeneratedReport.report_type,
                func.count(GeneratedReport.report_id)
            )
            .filter(GeneratedReport.is_deleted == False)
            .group_by(GeneratedReport.report_type)
            .all()
        )
        
        # Time-based counts
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        reports_today = query.filter(
            GeneratedReport.generated_at >= today_start
        ).count()
        
        reports_this_week = query.filter(
            GeneratedReport.generated_at >= week_start
        ).count()
        
        reports_this_month = query.filter(
            GeneratedReport.generated_at >= month_start
        ).count()
        
        return {
            'total_reports': total_reports,
            'reports_today': reports_today,
            'reports_this_week': reports_this_week,
            'reports_this_month': reports_this_month,
            'by_status': {k.value: v for k, v in by_status.items()},
            'by_type': {k.value: v for k, v in by_type.items()},
            'by_format': {}  # Can be added similarly
        }
    
    async def delete_report(self, report_id: int, user_id: int):
        """Soft delete a generated report"""
        
        report = (
            self.db.query(GeneratedReport)
            .filter(
                GeneratedReport.report_id == report_id,
                GeneratedReport.is_deleted == False
            )
            .first()
        )
        
        if not report:
            raise AppException(status_code=404, detail="Report not found")
        
        report.is_deleted = True
        report.deleted_at = datetime.utcnow()
        report.deleted_by = user_id
        
        self.db.commit()