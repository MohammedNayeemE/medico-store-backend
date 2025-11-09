from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal


# ============= Dashboard Overview =============
class DashboardOverview(BaseModel):
    total_orders: int
    total_sales: Decimal
    total_products: int
    pending_request_orders: int
    open_issues: int
    pending_medicine_requests: int
    low_stock_count: int
    near_expiry_count: int


# ============= Order Statistics =============
class OrdersByDate(BaseModel):
    date: date
    count: int
    total_amount: Decimal


class OrderTrendData(BaseModel):
    daily_orders: List[OrdersByDate]
    weekly_orders: List[OrdersByDate]
    monthly_orders: List[OrdersByDate]


class OrderStatusBreakdown(BaseModel):
    status: str
    count: int
    percentage: float


class OrderStatistics(BaseModel):
    total_orders: int
    total_revenue: Decimal
    average_order_value: Decimal
    status_breakdown: List[OrderStatusBreakdown]
    orders_by_date: List[OrdersByDate]


# ============= Sales Analytics =============
class SalesByPeriod(BaseModel):
    period: str  # "2024-01", "2024-W01", "2024-01-15"
    total_sales: Decimal
    order_count: int
    average_order_value: Decimal


class TopSellingMedicine(BaseModel):
    medicine_id: int
    medicine_name: str
    total_quantity_sold: int
    total_revenue: Decimal
    order_count: int


class SalesAnalytics(BaseModel):
    total_sales: Decimal
    sales_by_day: List[SalesByPeriod]
    sales_by_week: List[SalesByPeriod]
    sales_by_month: List[SalesByPeriod]
    top_selling_medicines: List[TopSellingMedicine]


# ============= Category Distribution =============
class CategoryDistribution(BaseModel):
    category_id: int
    category_name: str
    product_count: int
    total_quantity_sold: int
    total_revenue: Decimal
    percentage: float


# ============= Inventory Alerts =============
class LowStockAlert(BaseModel):
    medicine_id: int
    medicine_name: str
    batch_id: int
    batch_number: str
    current_quantity: int
    reserved_quantity: int
    available_quantity: int
    reorder_threshold: int


class NearExpiryAlert(BaseModel):
    medicine_id: int
    medicine_name: str
    batch_id: int
    batch_number: str
    expiry_date: date
    days_until_expiry: int
    quantity: int


class InventoryAlerts(BaseModel):
    low_stock_items: List[LowStockAlert]
    near_expiry_items: List[NearExpiryAlert]


# ============= Pending Requests =============
class PendingRequestOrder(BaseModel):
    request_order_id: int
    customer_id: int
    customer_name: str
    customer_email: str
    status: str
    item_count: int
    estimated_total: Optional[Decimal]
    created_at: datetime


class PendingMedicineRequest(BaseModel):
    request_id: int
    user_id: int
    user_name: str
    user_email: str
    medicine_id: int
    medicine_name: str
    note_text: Optional[str]
    requested_time: datetime


class OpenIssue(BaseModel):
    issue_id: int
    customer_id: int
    customer_name: str
    customer_email: str
    category_name: str
    description: str
    status: str
    opened_at: datetime
    unread_messages: int


class PendingRequests(BaseModel):
    request_orders: List[PendingRequestOrder]
    medicine_requests: List[PendingMedicineRequest]
    open_issues: List[OpenIssue]


# ============= Product Statistics =============
class ProductStatistics(BaseModel):
    total_medicines: int
    total_categories: int
    total_batches: int
    prescribed_medicines: int
    non_prescribed_medicines: int
    medicines_with_low_stock: int
    medicines_near_expiry: int


# ============= Revenue Breakdown =============
class RevenueByPaymentMode(BaseModel):
    payment_mode: str
    total_amount: Decimal
    transaction_count: int
    percentage: float


class RevenueBreakdown(BaseModel):
    total_revenue: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    by_payment_mode: List[RevenueByPaymentMode]


# ============= Time Range Filter =============
class DateRangeFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period: Optional[str] = "30d"  # 7d, 30d, 90d, 1y, all


# ============= Complete Dashboard Response =============
class CompleteDashboard(BaseModel):
    overview: DashboardOverview
    order_statistics: OrderStatistics
    sales_analytics: SalesAnalytics
    category_distribution: List[CategoryDistribution]
    inventory_alerts: InventoryAlerts
    pending_requests: PendingRequests
    product_statistics: ProductStatistics
    revenue_breakdown: RevenueBreakdown
    generated_at: datetime