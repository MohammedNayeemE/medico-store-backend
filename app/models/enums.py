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
    pending = "pending"  # 🟡 User submitted request, waiting for admin review
    approved = "approved"  # 🟢 Admin approved and confirmed items/pricing
    awaiting_payment = (
        "awaiting_payment"  # 🟠 Payment link sent, waiting for customer payment
    )
    converted = "converted"  # 🔵 Successfully paid and converted into final order
    rejected = "rejected"  # 🔴 Admin rejected the request (invalid, out of stock, etc.)
    cancelled = "cancelled"


class NotificationType(str, Enum):
    info = "info"
    alert = "alert"
    request = "request"
