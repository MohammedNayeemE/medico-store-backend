from sqlalchemy import (
    DECIMAL,
    TIMESTAMP,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import (
    InvoicePaymentStatusEnum,
    IssueStatusEnum,
    OrderStatusEnum,
    PaymentStatusEnum,
)


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    member_id = Column(Integer, ForeignKey("family_members.member_id"))
    prescription_id = Column(
        Integer, ForeignKey("prescriptions.prescription_id", onupdate="CASCADE")
    )
    status = Column(
        Enum(OrderStatusEnum, name="order_status_enum"),
        nullable=False,
        server_default=OrderStatusEnum.pending.value,
    )
    total_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(TIMESTAMP(timezone=True))
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP(timezone=True))
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    # Relationships
    customer = relationship("User")
    member = relationship("FamilyMember")
    prescription = relationship("Prescription")
    deleted_user = relationship("User", foreign_keys=[deleted_by])
    order_items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")
    issues = relationship("Issue", back_populates="order")
    invoice = relationship("Invoice", back_populates="order", uselist=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer, ForeignKey("orders.order_id", onupdate="CASCADE"), nullable=False
    )
    batch_id = Column(
        Integer,
        ForeignKey("medicine_batches.batch_id", onupdate="CASCADE"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    order = relationship("Order", back_populates="order_items")
    batch = relationship("MedicineBatch")


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer, ForeignKey("orders.order_id", onupdate="CASCADE"), nullable=False
    )
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum(PaymentStatusEnum, name="payment_status_enum"),
        nullable=False,
        server_default=PaymentStatusEnum.pending.value,
    )
    paid_at = Column(TIMESTAMP(timezone=True))
    payment_mode = Column(String(50))
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    order = relationship("Order", back_populates="payments")


class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer, ForeignKey("orders.order_id", onupdate="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    invoice_number = Column(String(255), unique=True, nullable=False)
    issue_date = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    invoice_pdf_id = Column(
        Integer, ForeignKey("file_assets.asset_id", onupdate="CASCADE"), nullable=False
    )
    subtotal_amount = Column(DECIMAL(10, 3), nullable=False)
    total_tax = Column(DECIMAL(10, 3), nullable=False)
    gross_amount = Column(DECIMAL(10, 3), nullable=False)
    discount_amount = Column(DECIMAL(10, 3), nullable=False)
    payment_status = Column(
        Enum(InvoicePaymentStatusEnum, name="invoice_payment_status_enum"),
        nullable=False,
        server_default=InvoicePaymentStatusEnum.unpaid.value,
    )
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    order = relationship("Order", back_populates="invoice")
    user = relationship("User")
    invoice_pdf = relationship("FileAsset")
    invoice_items = relationship("InvoiceItem", back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    invoice_item_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(
        Integer, ForeignKey("invoices.invoice_id", onupdate="CASCADE"), nullable=False
    )
    medicine_id = Column(
        Integer, ForeignKey("medicines.medicine_id", onupdate="CASCADE"), nullable=False
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 3), nullable=False)
    gst_rate = Column(DECIMAL(5, 2), nullable=False)
    cgst = Column(DECIMAL(10, 3), default=0.0)
    sgst = Column(DECIMAL(10, 3), default=0.0)
    igst = Column(DECIMAL(10, 3), default=0.0)
    total_amount = Column(DECIMAL(10, 3), nullable=False)

    invoice = relationship("Invoice", back_populates="invoice_items")
    medicine = relationship("Medicine")


class IssueCategory(Base):
    __tablename__ = "issue_categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    issues = relationship("Issue", back_populates="category")


class Issue(Base):
    __tablename__ = "issues"

    issue_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    order_id = Column(Integer, ForeignKey("orders.order_id", onupdate="CASCADE"))
    category_id = Column(
        Integer,
        ForeignKey("issue_categories.category_id", onupdate="CASCADE"),
        nullable=False,
    )
    description = Column(Text, nullable=False)
    status = Column(
        Enum(IssueStatusEnum, name="issue_status_enum"),
        nullable=False,
        server_default=IssueStatusEnum.open.value,
    )
    assigned_to = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))
    opened_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at = Column(TIMESTAMP(timezone=True))
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    order = relationship("Order", back_populates="issues")
    category = relationship("IssueCategory", back_populates="issues")
    messages = relationship("IssueMessage", back_populates="issue")


class IssueMessage(Base):
    __tablename__ = "issue_messages"

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer, ForeignKey("issues.issue_id", onupdate="CASCADE"), nullable=False
    )
    sender_id = Column(
        Integer, ForeignKey("users.user_id", onupdate="CASCADE"), nullable=False
    )
    message = Column(Text, nullable=False)
    message_type = Column(String(50))
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    issue = relationship("Issue", back_populates="messages")
    attachments = relationship("IssueAttachment", back_populates="message")


class IssueAttachment(Base):
    __tablename__ = "issue_attachments"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer,
        ForeignKey("issue_messages.message_id", onupdate="CASCADE"),
        nullable=False,
    )
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(String(50))
    uploaded_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    message = relationship("IssueMessage", back_populates="attachments")


class DiscountType(Base):
    __tablename__ = "discount_types"

    discount_type_id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discounts = relationship("Discount", back_populates="discount_type")


class Discount(Base):
    __tablename__ = "discounts"

    discount_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    discount_type_id = Column(
        Integer,
        ForeignKey("discount_types.discount_type_id", onupdate="CASCADE"),
        nullable=False,
    )
    value = Column(DECIMAL(18, 3), nullable=False)
    start_date = Column(TIMESTAMP(timezone=True), nullable=False)
    end_date = Column(TIMESTAMP(timezone=True), nullable=False)
    min_purchase_amount = Column(DECIMAL(18, 3), default=0)
    max_discount_amount = Column(DECIMAL(18, 3))
    usage_limit = Column(Integer)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discount_type = relationship("DiscountType", back_populates="discounts")
    parameters = relationship("DiscountParameter", back_populates="discount")
    medicines = relationship("DiscountMedicine", back_populates="discount")
    categories = relationship("DiscountCategory", back_populates="discount")
    coupons = relationship("Coupon", back_populates="discount")


class DiscountParameter(Base):
    __tablename__ = "discount_parameters"

    parameter_id = Column(Integer, primary_key=True, autoincrement=True)
    discount_id = Column(
        Integer, ForeignKey("discounts.discount_id", onupdate="CASCADE"), nullable=False
    )
    param_key = Column(String(50), nullable=False)
    param_value = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discount = relationship("Discount", back_populates="parameters")


class DiscountMedicine(Base):
    __tablename__ = "discount_medicines"

    discount_id = Column(
        Integer,
        ForeignKey("discounts.discount_id", onupdate="CASCADE"),
        primary_key=True,
    )
    medicine_id = Column(
        Integer,
        ForeignKey("medicines.medicine_id", onupdate="CASCADE"),
        primary_key=True,
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discount = relationship("Discount", back_populates="medicines")
    medicine = relationship("Medicine")


class DiscountCategory(Base):
    __tablename__ = "discount_categories"

    discount_id = Column(
        Integer,
        ForeignKey("discounts.discount_id", onupdate="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("categories.category_id", onupdate="CASCADE"),
        primary_key=True,
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discount = relationship("Discount", back_populates="categories")
    category = relationship("Category")


class Coupon(Base):
    __tablename__ = "coupons"

    coupon_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    discount_id = Column(
        Integer, ForeignKey("discounts.discount_id", onupdate="CASCADE"), nullable=False
    )
    max_usage = Column(Integer)
    used_count = Column(Integer, default=0)
    valid_from = Column(TIMESTAMP(timezone=True), nullable=False)
    valid_to = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    discount = relationship("Discount", back_populates="coupons")
