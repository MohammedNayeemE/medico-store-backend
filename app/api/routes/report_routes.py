import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres as get_db
from app.api.dependecies.get_db_sessions import get_redis_client
from app.core.exceptions import InternalServerErrorException
from app.models.enums import ReportFormatEnum, ReportStatusEnum, ReportTypeEnum
from app.models.user_management_models import User
from app.schemas.report_schemas import (
    GeneratedReportResponse,
    ReportGenerateRequest,
    ReportListResponse,
    ReportScheduleCreate,
    ReportScheduleResponse,
    ReportScheduleUpdate,
    ReportStatsResponse,
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportTemplateUpdate,
)
from app.services.cache_service import CacheService
from app.services.file_service import FileService
from app.services.mail_service import MailService
from app.services.report_management.report_service import ReportService
from app.utils.response_utils import error_response, success_response

router = APIRouter(prefix="/reports", tags=["Report Management"])


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    """Dependency to get report service"""
    cache_service = CacheService(Depends(get_redis_client))
    file_service = FileService()
    mail_service = MailService()
    return ReportService(db, cache_service, file_service, mail_service)


# ==================== Report Generation ==================== #


@router.post("/generate", response_model=dict)
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Generate a new report

    - **report_type**: Type of report to generate
    - **report_name**: Optional custom name for the report
    - **file_format**: Export format (PDF, Excel, CSV, JSON)
    - **filters**: Report-specific filters (date_from, date_to, etc.)
    - **send_email**: Whether to send report via email
    - **recipient_emails**: Email recipients if send_email is True
    - **use_cache**: Use cached report if available

    **Permissions Required:** Any authenticated user (customers can generate their own reports, admins can generate all reports)
    """
    try:
        # Generate report (async operation)
        report = await report_service.generate_report(
            request=request, user_id=current_user.user_id
        )

        return {
            "data": {
                "report_id": report.report_id,
                "report_name": report.report_name,
                "status": report.status.value,
                "message": "Report generation initiated successfully",
            },
            "message": "Report generated successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/types", response_model=dict)
async def get_report_types(current_user: User = Depends(get_current_user)):
    """
    Get list of available report types with descriptions

    **Permissions Required:** Any authenticated user
    """
    report_types = [
        {
            "type": rt.value,
            "name": rt.value.replace("_", " ").title(),
            "category": (
                "Sales & Revenue"
                if rt.value.startswith(
                    (
                        "daily",
                        "weekly",
                        "monthly",
                        "yearly",
                        "revenue",
                        "sales",
                        "top",
                        "profit",
                        "discount",
                        "coupon",
                    )
                )
                else (
                    "Inventory"
                    if rt.value.startswith(
                        (
                            "stock",
                            "low",
                            "expiry",
                            "dead",
                            "batch",
                            "inventory",
                            "medicine_turnover",
                        )
                    )
                    else (
                        "Order Management"
                        if rt.value.startswith(
                            (
                                "order",
                                "backorder",
                                "cancelled",
                                "delivery",
                                "payment_status",
                                "average",
                            )
                        )
                        else (
                            "Customer Analytics"
                            if rt.value.startswith(
                                (
                                    "new_customer",
                                    "customer",
                                    "prescription_upload",
                                    "top_customers",
                                )
                            )
                            else (
                                "Operational"
                                if rt.value.startswith(
                                    (
                                        "medicine_request",
                                        "prescription_verification",
                                        "issue",
                                        "staff",
                                        "peak",
                                    )
                                )
                                else "Financial"
                            )
                        )
                    )
                )
            ),
        }
        for rt in ReportTypeEnum
    ]

    # Group by category
    grouped = {}
    for rt in report_types:
        category = rt["category"]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(rt)

    return {"data": grouped, "message": "Report types retrieved successfully"}


# ==================== Report Management ==================== #


@router.get("/", response_model=dict)
async def get_reports(
    report_type: Optional[ReportTypeEnum] = Query(
        None, description="Filter by report type"
    ),
    status: Optional[ReportStatusEnum] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Get list of generated reports

    **Permissions Required:**
    - Customers can view their own reports
    - Admins can view all reports
    """
    try:
        # If user is not admin, filter by their user_id
        user_id = (
            None
            if current_user.role.role_name in ["admin", "super_admin"]
            else current_user.user_id
        )

        result = await report_service.get_reports(
            user_id=user_id,
            report_type=report_type,
            status=status,
            page=page,
            page_size=page_size,
        )

        # Add download URLs
        for report in result["reports"]:
            if report.file_asset_id and report.status == ReportStatusEnum.completed:
                report.download_url = f"/api/reports/{report.report_id}/download"

        return {"data": result, "message": "Report types retrieved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=dict)
async def get_report_stats(
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Get report generation statistics

    **Permissions Required:** Any authenticated user
    """
    try:
        user_id = (
            None
            if current_user.role.role_name in ["admin", "super_admin"]
            else current_user.user_id
        )

        stats = await report_service.get_report_stats(user_id=user_id)

        return {"data": stats, "message": "Report types retrieved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}", response_model=dict)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get report details by ID

    **Permissions Required:**
    - Owner of the report
    - Admin users
    """
    from app.models.report_management_models import GeneratedReport

    report = (
        db.query(GeneratedReport)
        .filter(
            GeneratedReport.report_id == report_id, GeneratedReport.is_deleted == False
        )
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check permissions
    if current_user.role.role_name not in ["admin", "super_admin"]:
        if report.generated_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Add download URL
    download_url = None
    if report.file_asset_id and report.status == ReportStatusEnum.completed:
        download_url = f"/api/reports/{report_id}/download"

    return {
        "data": {
            **GeneratedReportResponse.from_orm(report).dict(),
            "download_url": download_url,
        },
        "message": "Report types retrieved successfully",
    }


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Download generated report file

    **Permissions Required:**
    - Owner of the report
    - Admin users
    """
    from fastapi.responses import StreamingResponse

    from app.models.report_management_models import GeneratedReport

    report = (
        db.query(GeneratedReport)
        .filter(
            GeneratedReport.report_id == report_id, GeneratedReport.is_deleted == False
        )
        .first()
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check permissions
    if current_user.role.role_name not in ["admin", "super_admin"]:
        if report.generated_by != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

    if report.status != ReportStatusEnum.completed:
        raise HTTPException(status_code=400, detail="Report is not ready for download")

    if not report.file_asset_id:
        raise HTTPException(status_code=404, detail="Report file not found")

    try:
        # Get file from FileService
        file_data = await report_service.file_service.get_file(report.file_asset_id)

        # Determine content type
        content_types = {
            ReportFormatEnum.pdf: "application/pdf",
            ReportFormatEnum.excel: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ReportFormatEnum.csv: "text/csv",
            ReportFormatEnum.json: "application/json",
        }
        content_type = content_types.get(report.file_format, "application/octet-stream")

        # Return file
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={report.report_name}.{report.file_format.value}"
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download report: {str(e)}"
        )


@router.delete("/{report_id}", response_model=dict)
async def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Delete a generated report (soft delete)

    **Permissions Required:**
    - Owner of the report
    - Admin users
    """
    try:
        await report_service.delete_report(report_id, current_user.user_id)
        return {"msg": "Report deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Report Templates ==================== #


@router.post("/templates", response_model=dict)
async def create_template(
    template_data: ReportTemplateCreate,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Create a new report template

    **Permissions Required:** Admin only
    """
    try:
        template = await report_service.create_template(
            template_data=template_data, user_id=current_user.user_id
        )

        return success_response(
            data=ReportTemplateResponse.from_orm(template).dict(),
            message="Report template created successfully",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=dict)
async def get_templates(
    report_type: Optional[ReportTypeEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Get list of report templates

    **Permissions Required:** Any authenticated user
    """
    try:
        result = await report_service.get_templates(
            report_type=report_type, page=page, page_size=page_size
        )

        return success_response(
            data=result, message="Report templates retrieved successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}", response_model=dict)
async def update_template(
    template_id: int,
    template_data: ReportTemplateUpdate,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Update an existing report template

    **Permissions Required:** Admin only
    """
    try:
        template = await report_service.update_template(
            template_id=template_id,
            template_data=template_data,
            user_id=current_user.user_id,
        )

        return success_response(
            data=ReportTemplateResponse.from_orm(template).dict(),
            message="Report template updated successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}", response_model=dict)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(get_report_service),
):
    """
    Delete a report template (soft delete)

    **Permissions Required:** Admin only
    """
    try:
        await report_service.delete_template(template_id, current_user.user_id)

        return success_response(message="Report template deleted successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
