from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.schemas.dashboard_schemas import (
    DashboardOverview,
    OrderStatistics,
    SalesAnalytics,
    CategoryDistribution,
    InventoryAlerts,
    PendingRequests,
    ProductStatistics,
    RevenueBreakdown,
    CompleteDashboard,
    OrderTrendData,
    OrdersByDate
)
from app.services.dashboard_service import DashboardService
from app.api.dependecies.get_db_sessions import get_postgres as get_db
from app.api.dependecies.auth import get_current_user  # Assuming admin auth

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service(db: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


# ============= COMPLETE DASHBOARD =============
@router.get("/", response_model=CompleteDashboard)
async def get_complete_dashboard(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get complete dashboard with all statistics (Admin only)
    
    **Period options:**
    - 7d: Last 7 days
    - 30d: Last 30 days (default)
    - 90d: Last 90 days
    - 1y: Last year
    - all: All time
    """
    return await service.get_complete_dashboard(period)


# ============= OVERVIEW =============
@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get high-level dashboard overview
    
    Includes:
    - Total orders
    - Total sales
    - Total products
    - Pending request orders
    - Open issues
    - Pending medicine requests
    - Low stock alerts count
    - Near expiry alerts count
    """
    return await service.get_dashboard_overview(period)


# ============= ORDER STATISTICS =============
@router.get("/orders/statistics", response_model=OrderStatistics)
async def get_order_statistics(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get comprehensive order statistics
    
    Includes:
    - Total orders
    - Total revenue
    - Average order value
    - Order status breakdown
    - Orders by date
    """
    return await service.get_order_statistics(period)


@router.get("/orders/by-date", response_model=List[OrdersByDate])
async def get_orders_by_date(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get orders grouped by date"""
    stats = await service.get_order_statistics(period)
    return stats.orders_by_date


# ============= SALES ANALYTICS =============
@router.get("/sales", response_model=SalesAnalytics)
async def get_sales_analytics(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get detailed sales analytics
    
    Includes:
    - Total sales
    - Sales by day/week/month
    - Top selling medicines
    """
    return await service.get_sales_analytics(period)


@router.get("/sales/trends", response_model=SalesAnalytics)
async def get_sales_trends(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get sales trends over time"""
    return await service.get_sales_analytics(period)


# ============= CATEGORY DISTRIBUTION =============
@router.get("/categories/distribution", response_model=List[CategoryDistribution])
async def get_category_distribution(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get sales distribution by category
    
    Shows:
    - Product count per category
    - Total quantity sold
    - Total revenue
    - Percentage of total sales
    """
    return await service.get_category_distribution(period)


# ============= INVENTORY ALERTS =============
@router.get("/inventory/alerts", response_model=InventoryAlerts)
async def get_inventory_alerts(
    low_stock_threshold: int = Query(10, description="Low stock threshold"),
    expiry_days: int = Query(60, description="Days until expiry warning"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get inventory alerts
    
    Includes:
    - Low stock items (below threshold)
    - Near expiry items (expiring within specified days)
    """
    return await service.get_inventory_alerts(low_stock_threshold, expiry_days)


@router.get("/inventory/low-stock", response_model=InventoryAlerts)
async def get_low_stock_alerts(
    threshold: int = Query(10, description="Stock level threshold"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get only low stock alerts"""
    alerts = await service.get_inventory_alerts(threshold, 60)
    return InventoryAlerts(low_stock_items=alerts.low_stock_items, near_expiry_items=[])


@router.get("/inventory/near-expiry", response_model=InventoryAlerts)
async def get_near_expiry_alerts(
    days: int = Query(60, description="Days until expiry"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get only near expiry alerts"""
    alerts = await service.get_inventory_alerts(10, days)
    return InventoryAlerts(low_stock_items=[], near_expiry_items=alerts.near_expiry_items)


# ============= PENDING REQUESTS =============
@router.get("/pending", response_model=PendingRequests)
async def get_pending_requests(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get all pending items requiring attention
    
    Includes:
    - Pending request orders (waiting for approval)
    - Pending medicine requests
    - Open issues
    """
    return await service.get_pending_requests()


@router.get("/pending/request-orders", response_model=PendingRequests)
async def get_pending_request_orders(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get only pending request orders"""
    requests = await service.get_pending_requests()
    return PendingRequests(
        request_orders=requests.request_orders,
        medicine_requests=[],
        open_issues=[]
    )


@router.get("/pending/medicine-requests", response_model=PendingRequests)
async def get_pending_medicine_requests(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get only pending medicine requests"""
    requests = await service.get_pending_requests()
    return PendingRequests(
        request_orders=[],
        medicine_requests=requests.medicine_requests,
        open_issues=[]
    )


@router.get("/pending/issues", response_model=PendingRequests)
async def get_open_issues(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Get only open issues"""
    requests = await service.get_pending_requests()
    return PendingRequests(
        request_orders=[],
        medicine_requests=[],
        open_issues=requests.open_issues
    )


# ============= PRODUCT STATISTICS =============
@router.get("/products/statistics", response_model=ProductStatistics)
async def get_product_statistics(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get product/medicine statistics
    
    Includes:
    - Total medicines
    - Total categories
    - Total batches
    - Prescribed vs non-prescribed medicines
    - Medicines with low stock
    - Medicines near expiry
    """
    return await service.get_product_statistics()


# ============= REVENUE BREAKDOWN =============
@router.get("/revenue", response_model=RevenueBreakdown)
async def get_revenue_breakdown(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get revenue breakdown
    
    Includes:
    - Total revenue
    - Paid amount
    - Pending amount
    - Revenue by payment mode (cash, card, UPI, etc.)
    """
    return await service.get_revenue_breakdown(period)


# ============= QUICK STATS =============
@router.get("/quick-stats")
async def get_quick_stats(
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Get quick statistics for dashboard widgets
    
    Returns key metrics in a simplified format
    """
    overview = await service.get_dashboard_overview("30d")
    
    return {
        "total_orders": overview.total_orders,
        "total_sales": float(overview.total_sales),
        "total_products": overview.total_products,
        "alerts": {
            "pending_approvals": overview.pending_request_orders,
            "open_issues": overview.open_issues,
            "medicine_requests": overview.pending_medicine_requests,
            "low_stock": overview.low_stock_count,
            "near_expiry": overview.near_expiry_count
        }
    }


# ============= EXPORT DATA (Optional) =============
@router.get("/export/sales")
async def export_sales_data(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    format: str = Query("json", description="Export format: json, csv"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """
    Export sales data for reporting
    
    Supports JSON and CSV formats
    """
    sales = await service.get_sales_analytics(period)
    
    if format == "csv":
        # You can implement CSV export using pandas or csv module
        return {"message": "CSV export not implemented yet"}
    
    return sales


@router.get("/export/orders")
async def export_orders_data(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 1y, all"),
    format: str = Query("json", description="Export format: json, csv"),
    service: DashboardService = Depends(get_dashboard_service),
    current_user = Depends(get_current_user)
):
    """Export orders data for reporting"""
    orders = await service.get_order_statistics(period)
    
    if format == "csv":
        return {"message": "CSV export not implemented yet"}
    
    return orders