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
