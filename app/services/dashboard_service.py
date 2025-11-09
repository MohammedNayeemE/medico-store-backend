from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, cast, Date
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from app.models.inventory_management_models import (
    Medicine, MedicineBatch, Category, MedicineCategory, MedicineRequest
)
from app.models.order_management_models import (
    Order, OrderItem, Payment, Invoice, Issue, RequestOrder, RequestOrderItem
)
from app.models.enums import (
    OrderStatusEnum, IssueStatusEnum, RequestOrderStatusEnum, 
    PaymentStatusEnum, RequestStatusEnum
)
from app.schemas.dashboard_schemas import *


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============= HELPER METHODS =============
    def _get_date_range(self, period: Optional[str] = "30d") -> Tuple[datetime, datetime]:
        """Get date range based on period string"""
        end_date = datetime.now()
        
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        elif period == "all":
            start_date = datetime(2000, 1, 1)
        else:
            start_date = end_date - timedelta(days=30)
        
        return start_date, end_date

    # ============= OVERVIEW STATISTICS =============
    async def get_dashboard_overview(self, period: str = "30d") -> DashboardOverview:
        """Get high-level dashboard overview"""
        start_date, end_date = self._get_date_range(period)
        
        # Total orders
        total_orders_query = select(func.count(Order.order_id)).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        )
        total_orders = (await self.db.execute(total_orders_query)).scalar() or 0
        
        # Total sales
        total_sales_query = select(func.sum(Order.total_amount)).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        )
        total_sales = (await self.db.execute(total_sales_query)).scalar() or Decimal(0)
        
        # Total products
        total_products_query = select(func.count(Medicine.medicine_id)).where(
            Medicine.is_deleted == False
        )
        total_products = (await self.db.execute(total_products_query)).scalar() or 0
        
        # Pending request orders
        pending_requests_query = select(func.count(RequestOrder.request_order_id)).where(
            and_(
                RequestOrder.is_deleted == False,
                RequestOrder.status == RequestOrderStatusEnum.pending
            )
        )
        pending_request_orders = (await self.db.execute(pending_requests_query)).scalar() or 0
        
        # Open issues
        open_issues_query = select(func.count(Issue.issue_id)).where(
            and_(
                Issue.is_deleted == False,
                Issue.status == IssueStatusEnum.open
            )
        )
        open_issues = (await self.db.execute(open_issues_query)).scalar() or 0
        
        # Pending medicine requests
        pending_medicine_requests_query = select(func.count(MedicineRequest.request_id)).where(
            and_(
                MedicineRequest.is_deleted == False,
                MedicineRequest.status == RequestStatusEnum.pending
            )
        )
        pending_medicine_requests = (await self.db.execute(pending_medicine_requests_query)).scalar() or 0
        
        # Low stock items (quantity - reserved_quantity < 10)
        low_stock_query = select(func.count(MedicineBatch.batch_id)).where(
            and_(
                MedicineBatch.is_deleted == False,
                (MedicineBatch.quantity - MedicineBatch.reserved_quantity) < 10
            )
        )
        low_stock_count = (await self.db.execute(low_stock_query)).scalar() or 0
        
        # Near expiry items (expires within 60 days)
        expiry_threshold = date.today() + timedelta(days=60)
        near_expiry_query = select(func.count(MedicineBatch.batch_id)).where(
            and_(
                MedicineBatch.is_deleted == False,
                MedicineBatch.expiry_date <= expiry_threshold,
                MedicineBatch.expiry_date >= date.today()
            )
        )
        near_expiry_count = (await self.db.execute(near_expiry_query)).scalar() or 0
        
        return DashboardOverview(
            total_orders=total_orders,
            total_sales=total_sales,
            total_products=total_products,
            pending_request_orders=pending_request_orders,
            open_issues=open_issues,
            pending_medicine_requests=pending_medicine_requests,
            low_stock_count=low_stock_count,
            near_expiry_count=near_expiry_count
        )

    # ============= ORDER STATISTICS =============
    async def get_order_statistics(self, period: str = "30d") -> OrderStatistics:
        """Get comprehensive order statistics"""
        start_date, end_date = self._get_date_range(period)
        
        # Total orders and revenue
        stats_query = select(
            func.count(Order.order_id).label("total_orders"),
            func.sum(Order.total_amount).label("total_revenue")
        ).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        )
        stats_result = (await self.db.execute(stats_query)).first()
        total_orders = stats_result.total_orders or 0
        total_revenue = stats_result.total_revenue or Decimal(0)
        average_order_value = total_revenue / total_orders if total_orders > 0 else Decimal(0)
        
        # Status breakdown
        status_query = select(
            Order.status,
            func.count(Order.order_id).label("count")
        ).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        ).group_by(Order.status)
        
        status_results = (await self.db.execute(status_query)).all()
        status_breakdown = [
            OrderStatusBreakdown(
                status=row.status.value,
                count=row.count,
                percentage=round((row.count / total_orders * 100) if total_orders > 0 else 0, 2)
            )
            for row in status_results
        ]
        
        # Orders by date
        orders_by_date_query = select(
            cast(Order.created_at, Date).label("date"),
            func.count(Order.order_id).label("count"),
            func.sum(Order.total_amount).label("total_amount")
        ).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        ).group_by(cast(Order.created_at, Date)).order_by(cast(Order.created_at, Date))
        
        date_results = (await self.db.execute(orders_by_date_query)).all()
        orders_by_date = [
            OrdersByDate(
                date=row.date,
                count=row.count,
                total_amount=row.total_amount
            )
            for row in date_results
        ]
        
        return OrderStatistics(
            total_orders=total_orders,
            total_revenue=total_revenue,
            average_order_value=average_order_value,
            status_breakdown=status_breakdown,
            orders_by_date=orders_by_date
        )

    # ============= SALES ANALYTICS =============
    async def get_sales_analytics(self, period: str = "30d") -> SalesAnalytics:
        """Get detailed sales analytics"""
        start_date, end_date = self._get_date_range(period)
        
        # Total sales
        total_sales_query = select(func.sum(Order.total_amount)).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        )
        total_sales = (await self.db.execute(total_sales_query)).scalar() or Decimal(0)
        
        # Sales by day
        daily_sales_query = select(
            cast(Order.created_at, Date).label("date"),
            func.sum(Order.total_amount).label("total_sales"),
            func.count(Order.order_id).label("order_count"),
            func.avg(Order.total_amount).label("avg_order_value")
        ).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        ).group_by(cast(Order.created_at, Date)).order_by(cast(Order.created_at, Date))
        
        daily_results = (await self.db.execute(daily_sales_query)).all()
        sales_by_day = [
            SalesByPeriod(
                period=str(row.date),
                total_sales=row.total_sales,
                order_count=row.order_count,
                average_order_value=row.avg_order_value
            )
            for row in daily_results
        ]
        
        # Top selling medicines
        top_medicines_query = select(
            Medicine.medicine_id,
            Medicine.medicine_name,
            func.sum(OrderItem.quantity).label("total_quantity"),
            func.sum(OrderItem.price * OrderItem.quantity).label("total_revenue"),
            func.count(func.distinct(Order.order_id)).label("order_count")
        ).join(
            MedicineBatch, OrderItem.batch_id == MedicineBatch.batch_id
        ).join(
            Medicine, MedicineBatch.medicine_id == Medicine.medicine_id
        ).join(
            Order, OrderItem.order_id == Order.order_id
        ).where(
            and_(
                Order.is_deleted == False,
                OrderItem.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        ).group_by(
            Medicine.medicine_id, Medicine.medicine_name
        ).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(10)
        
        top_results = (await self.db.execute(top_medicines_query)).all()
        top_selling_medicines = [
            TopSellingMedicine(
                medicine_id=row.medicine_id,
                medicine_name=row.medicine_name,
                total_quantity_sold=row.total_quantity,
                total_revenue=row.total_revenue,
                order_count=row.order_count
            )
            for row in top_results
        ]
        
        return SalesAnalytics(
            total_sales=total_sales,
            sales_by_day=sales_by_day,
            sales_by_week=[],  # Can be calculated if needed
            sales_by_month=[],  # Can be calculated if needed
            top_selling_medicines=top_selling_medicines
        )

    # ============= CATEGORY DISTRIBUTION =============
    async def get_category_distribution(self, period: str = "30d") -> List[CategoryDistribution]:
        """Get sales distribution by category"""
        start_date, end_date = self._get_date_range(period)
        
        # Get category statistics
        category_query = select(
            Category.category_id,
            Category.category_name,
            func.count(func.distinct(Medicine.medicine_id)).label("product_count"),
            func.sum(OrderItem.quantity).label("total_quantity_sold"),
            func.sum(OrderItem.price * OrderItem.quantity).label("total_revenue")
        ).join(
            MedicineCategory, Category.category_id == MedicineCategory.category_id
        ).join(
            Medicine, MedicineCategory.medicine_id == Medicine.medicine_id
        ).join(
            MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id
        ).join(
            OrderItem, MedicineBatch.batch_id == OrderItem.batch_id, isouter=True
        ).join(
            Order, OrderItem.order_id == Order.order_id, isouter=True
        ).where(
            and_(
                Category.is_deleted == False,
                MedicineCategory.is_deleted == False,
                or_(
                    Order.created_at.is_(None),
                    and_(
                        Order.created_at >= start_date,
                        Order.created_at <= end_date,
                        Order.is_deleted == False
                    )
                )
            )
        ).group_by(
            Category.category_id, Category.category_name
        ).order_by(
            func.sum(OrderItem.quantity).desc().nullslast()
        )
        
        results = (await self.db.execute(category_query)).all()
        
        total_revenue = sum(row.total_revenue or 0 for row in results)
        
        return [
            CategoryDistribution(
                category_id=row.category_id,
                category_name=row.category_name,
                product_count=row.product_count,
                total_quantity_sold=row.total_quantity_sold or 0,
                total_revenue=row.total_revenue or Decimal(0),
                percentage=round((row.total_revenue / total_revenue * 100) if total_revenue > 0 else 0, 2)
            )
            for row in results
        ]

    # ============= INVENTORY ALERTS =============
    async def get_inventory_alerts(self, low_stock_threshold: int = 10, expiry_days: int = 60) -> InventoryAlerts:
        """Get low stock and near expiry alerts"""
        
        # Low stock items
        low_stock_query = select(
            Medicine.medicine_id,
            Medicine.medicine_name,
            MedicineBatch.batch_id,
            MedicineBatch.batch_number,
            MedicineBatch.quantity,
            MedicineBatch.reserved_quantity,
            (MedicineBatch.quantity - MedicineBatch.reserved_quantity).label("available_quantity")
        ).join(
            MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id
        ).where(
            and_(
                Medicine.is_deleted == False,
                MedicineBatch.is_deleted == False,
                (MedicineBatch.quantity - MedicineBatch.reserved_quantity) < low_stock_threshold
            )
        ).order_by(
            (MedicineBatch.quantity - MedicineBatch.reserved_quantity).asc()
        )
        
        low_stock_results = (await self.db.execute(low_stock_query)).all()
        low_stock_items = [
            LowStockAlert(
                medicine_id=row.medicine_id,
                medicine_name=row.medicine_name,
                batch_id=row.batch_id,
                batch_number=row.batch_number,
                current_quantity=row.quantity,
                reserved_quantity=row.reserved_quantity,
                available_quantity=row.available_quantity,
                reorder_threshold=low_stock_threshold
            )
            for row in low_stock_results
        ]
        
        # Near expiry items
        expiry_threshold = date.today() + timedelta(days=expiry_days)
        near_expiry_query = select(
            Medicine.medicine_id,
            Medicine.medicine_name,
            MedicineBatch.batch_id,
            MedicineBatch.batch_number,
            MedicineBatch.expiry_date,
            MedicineBatch.quantity
        ).join(
            MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id
        ).where(
            and_(
                Medicine.is_deleted == False,
                MedicineBatch.is_deleted == False,
                MedicineBatch.expiry_date <= expiry_threshold,
                MedicineBatch.expiry_date >= date.today()
            )
        ).order_by(MedicineBatch.expiry_date.asc())
        
        near_expiry_results = (await self.db.execute(near_expiry_query)).all()
        near_expiry_items = [
            NearExpiryAlert(
                medicine_id=row.medicine_id,
                medicine_name=row.medicine_name,
                batch_id=row.batch_id,
                batch_number=row.batch_number,
                expiry_date=row.expiry_date,
                days_until_expiry=(row.expiry_date - date.today()).days,
                quantity=row.quantity
            )
            for row in near_expiry_results
        ]
        
        return InventoryAlerts(
            low_stock_items=low_stock_items,
            near_expiry_items=near_expiry_items
        )

    # ============= PENDING REQUESTS =============
    async def get_pending_requests(self) -> PendingRequests:
        """Get all pending requests, medicine requests, and open issues"""
        from app.models.user_management_models import User
        
        # Pending request orders
        request_orders_query = select(RequestOrder).options(
            joinedload(RequestOrder.customer),
            joinedload(RequestOrder.items)
        ).where(
            and_(
                RequestOrder.is_deleted == False,
                RequestOrder.status == RequestOrderStatusEnum.pending
            )
        ).order_by(RequestOrder.created_at.desc())
        
        request_orders_results = (await self.db.execute(request_orders_query)).unique().scalars().all()
        
        request_orders = [
            PendingRequestOrder(
                request_order_id=ro.request_order_id,
                customer_id=ro.customer_id,
                customer_name=ro.customer.full_name if ro.customer else "Unknown",
                customer_email=ro.customer.email if ro.customer else "Unknown",
                status=ro.status.value,
                item_count=len(ro.items),
                estimated_total=sum(item.estimated_price or Decimal(0) for item in ro.items),
                created_at=ro.created_at
            )
            for ro in request_orders_results
        ]
        
        # Pending medicine requests
        medicine_requests_query = select(MedicineRequest).options(
            joinedload(MedicineRequest.user),
            joinedload(MedicineRequest.requested_medicine)
        ).where(
            and_(
                MedicineRequest.is_deleted == False,
                MedicineRequest.status == RequestStatusEnum.pending
            )
        ).order_by(MedicineRequest.requested_time.desc())
        
        medicine_requests_results = (await self.db.execute(medicine_requests_query)).unique().scalars().all()
        
        medicine_requests = [
            PendingMedicineRequest(
                request_id=mr.request_id,
                user_id=mr.user_id,
                user_name=mr.user.full_name if mr.user else "Unknown",
                user_email=mr.user.email if mr.user else "Unknown",
                medicine_id=mr.requested_medicine_id,
                medicine_name=mr.requested_medicine.medicine_name if mr.requested_medicine else "Unknown",
                note_text=mr.note_text,
                requested_time=mr.requested_time
            )
            for mr in medicine_requests_results
        ]
        
        # Open issues
        issues_query = select(Issue).options(
            joinedload(Issue.category)
        ).where(
            and_(
                Issue.is_deleted == False,
                Issue.status == IssueStatusEnum.open
            )
        ).order_by(Issue.opened_at.desc())
        
        issues_results = (await self.db.execute(issues_query)).unique().scalars().all()
        
        open_issues = [
            OpenIssue(
                issue_id=issue.issue_id,
                customer_id=issue.customer_id,
                customer_name="Customer",  # You may need to join User table
                customer_email="customer@example.com",
                category_name=issue.category.name if issue.category else "Unknown",
                description=issue.description[:200],  # Truncate
                status=issue.status.value,
                opened_at=issue.opened_at,
                unread_messages=0  # Would need to count messages
            )
            for issue in issues_results
        ]
        
        return PendingRequests(
            request_orders=request_orders,
            medicine_requests=medicine_requests,
            open_issues=open_issues
        )

    # ============= PRODUCT STATISTICS =============
    async def get_product_statistics(self) -> ProductStatistics:
        """Get product/medicine statistics"""
        
        # Total medicines
        total_medicines_query = select(func.count(Medicine.medicine_id)).where(
            Medicine.is_deleted == False
        )
        total_medicines = (await self.db.execute(total_medicines_query)).scalar() or 0
        
        # Total categories
        total_categories_query = select(func.count(Category.category_id)).where(
            Category.is_deleted == False
        )
        total_categories = (await self.db.execute(total_categories_query)).scalar() or 0
        
        # Total batches
        total_batches_query = select(func.count(MedicineBatch.batch_id)).where(
            MedicineBatch.is_deleted == False
        )
        total_batches = (await self.db.execute(total_batches_query)).scalar() or 0
        
        # Prescribed medicines
        prescribed_query = select(func.count(Medicine.medicine_id)).where(
            and_(
                Medicine.is_deleted == False,
                Medicine.is_prescribed == True
            )
        )
        prescribed_medicines = (await self.db.execute(prescribed_query)).scalar() or 0
        
        non_prescribed_medicines = total_medicines - prescribed_medicines
        
        # Low stock and near expiry
        alerts = await self.get_inventory_alerts()
        
        return ProductStatistics(
            total_medicines=total_medicines,
            total_categories=total_categories,
            total_batches=total_batches,
            prescribed_medicines=prescribed_medicines,
            non_prescribed_medicines=non_prescribed_medicines,
            medicines_with_low_stock=len(alerts.low_stock_items),
            medicines_near_expiry=len(alerts.near_expiry_items)
        )

    # ============= REVENUE BREAKDOWN =============
    async def get_revenue_breakdown(self, period: str = "30d") -> RevenueBreakdown:
        """Get revenue breakdown by payment mode"""
        start_date, end_date = self._get_date_range(period)
        
        # Total revenue
        total_revenue_query = select(func.sum(Order.total_amount)).where(
            and_(
                Order.is_deleted == False,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        )
        total_revenue = (await self.db.execute(total_revenue_query)).scalar() or Decimal(0)
        
        # Paid vs Pending
        paid_query = select(func.sum(Payment.amount)).where(
            and_(
                Payment.is_deleted == False,
                Payment.status == PaymentStatusEnum.completed,
                Payment.paid_at >= start_date,
                Payment.paid_at <= end_date
            )
        )
        paid_amount = (await self.db.execute(paid_query)).scalar() or Decimal(0)
        pending_amount = total_revenue - paid_amount
        
        # By payment mode
        by_mode_query = select(
            Payment.payment_mode,
            func.sum(Payment.amount).label("total_amount"),
            func.count(Payment.payment_id).label("transaction_count")
        ).where(
            and_(
                Payment.is_deleted == False,
                Payment.status == PaymentStatusEnum.completed,
                Payment.paid_at >= start_date,
                Payment.paid_at <= end_date
            )
        ).group_by(Payment.payment_mode)
        
        mode_results = (await self.db.execute(by_mode_query)).all()
        
        by_payment_mode = [
            RevenueByPaymentMode(
                payment_mode=row.payment_mode or "Unknown",
                total_amount=row.total_amount,
                transaction_count=row.transaction_count,
                percentage=round((row.total_amount / paid_amount * 100) if paid_amount > 0 else 0, 2)
            )
            for row in mode_results
        ]
        
        return RevenueBreakdown(
            total_revenue=total_revenue,
            paid_amount=paid_amount,
            pending_amount=pending_amount,
            by_payment_mode=by_payment_mode
        )

    # ============= COMPLETE DASHBOARD =============
    async def get_complete_dashboard(self, period: str = "30d") -> CompleteDashboard:
        """Get all dashboard data in one call"""
        
        overview = await self.get_dashboard_overview(period)
        order_statistics = await self.get_order_statistics(period)
        sales_analytics = await self.get_sales_analytics(period)
        category_distribution = await self.get_category_distribution(period)
        inventory_alerts = await self.get_inventory_alerts()
        pending_requests = await self.get_pending_requests()
        product_statistics = await self.get_product_statistics()
        revenue_breakdown = await self.get_revenue_breakdown(period)
        
        return CompleteDashboard(
            overview=overview,
            order_statistics=order_statistics,
            sales_analytics=sales_analytics,
            category_distribution=category_distribution,
            inventory_alerts=inventory_alerts,
            pending_requests=pending_requests,
            product_statistics=product_statistics,
            revenue_breakdown=revenue_breakdown,
            generated_at=datetime.now()
        )