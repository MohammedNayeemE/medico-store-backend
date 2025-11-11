from enum import Enum


class OrderStatusEnum(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    returned = "returned"


class PaymentStatusEnum(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class InvoicePaymentStatusEnum(str, Enum):
    unpaid = "unpaid"
    paid = "paid"


class ReviewStatusEnum(str, Enum):
    visible = "visible"
    hidden = "hidden"
    flagged = "flagged"
    deleted = "deleted"


class PrescriptionStatusEnum(str, Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class IssueStatusEnum(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class RequestStatusEnum(str, Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class RequestOrderStatusEnum(str, Enum):
    pending = "pending"
    pending_customer_confirmation = "pending_customer_confirmation"
    approved = "approved"
    rejected = "rejected"
    customer_rejected = "customer_rejected"
    cancelled = "cancelled"
    converted_to_order = "converted_to_order"


class NotificationType(str, Enum):
    info = "info"
    alert = "alert"
    request = "request"


class ReportTypeEnum(str, Enum):
    """Types of reports available"""

    # Sales & Revenue
    daily_sales_summary = "daily_sales_summary"
    weekly_sales_summary = "weekly_sales_summary"
    monthly_sales_summary = "monthly_sales_summary"
    yearly_sales_summary = "yearly_sales_summary"
    revenue_by_payment_mode = "revenue_by_payment_mode"
    sales_by_category = "sales_by_category"
    top_selling_medicines = "top_selling_medicines"
    revenue_trends = "revenue_trends"
    profit_margin_analysis = "profit_margin_analysis"
    discount_impact_analysis = "discount_impact_analysis"
    coupon_effectiveness = "coupon_effectiveness"

    # Inventory
    stock_level_report = "stock_level_report"
    low_stock_alert = "low_stock_alert"
    expiry_report = "expiry_report"
    dead_stock_analysis = "dead_stock_analysis"
    batch_wise_stock = "batch_wise_stock"
    inventory_valuation = "inventory_valuation"
    stock_movement = "stock_movement"
    medicine_turnover_ratio = "medicine_turnover_ratio"

    # Order Management
    order_status_summary = "order_status_summary"
    order_fulfillment_rate = "order_fulfillment_rate"
    average_order_value = "average_order_value"
    order_conversion_rate = "order_conversion_rate"
    backorder_report = "backorder_report"
    cancelled_orders_analysis = "cancelled_orders_analysis"
    delivery_performance = "delivery_performance"
    payment_status_report = "payment_status_report"

    # Customer Analytics
    new_customer_acquisition = "new_customer_acquisition"
    customer_segmentation = "customer_segmentation"
    top_customers_by_revenue = "top_customers_by_revenue"
    customer_retention_rate = "customer_retention_rate"
    prescription_upload_trends = "prescription_upload_trends"
    customer_geographic_distribution = "customer_geographic_distribution"
    customer_lifetime_value = "customer_lifetime_value"

    # Operational
    medicine_request_analysis = "medicine_request_analysis"
    prescription_verification = "prescription_verification"
    issue_complaint_report = "issue_complaint_report"
    issue_resolution_time = "issue_resolution_time"
    staff_performance = "staff_performance"
    peak_hours_analysis = "peak_hours_analysis"

    # Financial
    gst_report = "gst_report"
    invoice_summary = "invoice_summary"
    payment_collection = "payment_collection"
    outstanding_payments = "outstanding_payments"
    tax_liability = "tax_liability"
    supplier_payment = "supplier_payment"


class ReportFormatEnum(str, Enum):
    """Report export formats"""

    pdf = "pdf"
    excel = "excel"
    csv = "csv"
    json = "json"


class ReportStatusEnum(str, Enum):
    """Report generation status"""

    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cached = "cached"
