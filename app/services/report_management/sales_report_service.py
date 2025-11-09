
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, case, extract
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.inventory_management_models import Medicine, MedicineBatch, Category
from app.models.order_management_models import (
    Order, OrderItem, Payment, Invoice, InvoiceItem,
    Discount, Coupon
)
from app.models.enums import OrderStatusEnum, PaymentStatusEnum
from app.services.cache_service import CacheService


class SalesReportService:
    """Service for generating sales and revenue reports"""
    
    def __init__(self, db: Session, cache_service: CacheService):
        self.db = db
        self.cache_service = cache_service
    
    # ==================== Helper Methods ==================== #
    
    def _generate_cache_key(self, report_type: str, filters: Dict[str, Any]) -> str:
        """Generate unique cache key for report"""
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        hash_input = f"{report_type}:{filter_str}"
        return f"report:{hashlib.md5(hash_input.encode()).hexdigest()}"
    
    def _apply_date_filter(self, query, date_column, filters: Dict[str, Any]):
        """Apply date range filters to query"""
        if filters.get('date_from'):
            query = query.filter(date_column >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(date_column <= filters['date_to'])
        return query
    
    def _get_base_order_query(self, filters: Dict[str, Any]):
        """Get base query for orders with common filters"""
        query = self.db.query(Order).filter(
            Order.is_deleted == False,
            Order.status.in_([
                OrderStatusEnum.confirmed,
                OrderStatusEnum.shipped,
                OrderStatusEnum.delivered
            ])
        )
        
        # Apply date filters
        query = self._apply_date_filter(query, Order.created_at, filters)
        
        # Apply customer filter
        if filters.get('customer_ids'):
            query = query.filter(Order.customer_id.in_(filters['customer_ids']))
        
        # Apply amount filters
        if filters.get('min_amount'):
            query = query.filter(Order.total_amount >= filters['min_amount'])
        if filters.get('max_amount'):
            query = query.filter(Order.total_amount <= filters['max_amount'])
        
        return query
    
    def _decimal_to_float(self, value: Any) -> float:
        """Convert Decimal to float safely"""
        return float(value) if value is not None else 0.0
    
    # ==================== Daily/Weekly/Monthly/Yearly Sales Summary ==================== #
    
    async def generate_sales_summary(
        self,
        period: str,  # 'daily', 'weekly', 'monthly', 'yearly'
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate sales summary for specified period
        Returns: List of sales data grouped by period
        """
        cache_key = self._generate_cache_key(f"sales_summary_{period}", filters)
        
        # Check cache
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # Determine grouping based on period
        if period == 'daily':
            date_trunc = func.date_trunc('day', Order.created_at)
        elif period == 'weekly':
            date_trunc = func.date_trunc('week', Order.created_at)
        elif period == 'monthly':
            date_trunc = func.date_trunc('month', Order.created_at)
        elif period == 'yearly':
            date_trunc = func.date_trunc('year', Order.created_at)
        else:
            raise AppException(status_code=400, detail="Invalid period specified")
        
        # Build query
        base_query = self._get_base_order_query(filters)
        
        # Join with OrderItems and MedicineBatch for profit calculation
        query = (
            self.db.query(
                date_trunc.label('period'),
                func.count(Order.order_id).label('total_orders'),
                func.sum(Order.total_amount).label('total_revenue'),
                func.avg(Order.total_amount).label('avg_order_value'),
                func.sum(Invoice.discount_amount).label('total_discounts'),
                func.sum(Invoice.total_tax).label('total_tax'),
                func.sum(
                    (OrderItem.price - MedicineBatch.purchase_price) * OrderItem.quantity
                ).label('total_profit')
            )
            .join(Invoice, Order.order_id == Invoice.order_id)
            .join(OrderItem, Order.order_id == OrderItem.order_id)
            .join(MedicineBatch, OrderItem.batch_id == MedicineBatch.batch_id)
            .filter(Order.order_id.in_(base_query.with_entities(Order.order_id)))
            .group_by(date_trunc)
            .order_by(date_trunc.desc())
        )
        
        results = query.all()
        
        # Format response
        data = [
            {
                'date': row.period.isoformat() if row.period else None,
                'total_orders': row.total_orders or 0,
                'total_revenue': self._decimal_to_float(row.total_revenue),
                'avg_order_value': self._decimal_to_float(row.avg_order_value),
                'total_discounts': self._decimal_to_float(row.total_discounts),
                'total_tax': self._decimal_to_float(row.total_tax),
                'total_profit': self._decimal_to_float(row.total_profit),
                'profit_margin': (
                    self._decimal_to_float(row.total_profit) / 
                    self._decimal_to_float(row.total_revenue) * 100
                ) if row.total_revenue else 0
            }
            for row in results
        ]
        
        # Cache for 1 hour
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Revenue by Payment Mode ==================== #
    
    async def generate_revenue_by_payment_mode(
        self,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate revenue breakdown by payment mode"""
        cache_key = self._generate_cache_key("revenue_by_payment_mode", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        base_query = self._get_base_order_query(filters)
        
        # Query grouped by payment mode
        query = (
            self.db.query(
                Payment.payment_mode,
                func.count(Order.order_id).label('total_orders'),
                func.sum(Order.total_amount).label('total_revenue'),
                func.avg(Order.total_amount).label('avg_order_value')
            )
            .join(Payment, Order.order_id == Payment.order_id)
            .filter(
                Order.order_id.in_(base_query.with_entities(Order.order_id)),
                Payment.status == PaymentStatusEnum.completed
            )
            .group_by(Payment.payment_mode)
        )
        
        # Apply payment mode filter if specified
        if filters.get('payment_mode'):
            query = query.filter(Payment.payment_mode.in_(filters['payment_mode']))
        
        results = query.all()
        
        # Calculate total for percentage
        total_revenue = sum(self._decimal_to_float(row.total_revenue) for row in results)
        
        data = [
            {
                'payment_mode': row.payment_mode or 'Unknown',
                'total_orders': row.total_orders or 0,
                'total_revenue': self._decimal_to_float(row.total_revenue),
                'avg_order_value': self._decimal_to_float(row.avg_order_value),
                'percentage': (
                    self._decimal_to_float(row.total_revenue) / total_revenue * 100
                ) if total_revenue > 0 else 0
            }
            for row in results
        ]
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Sales by Medicine Category ==================== #
    
    async def generate_sales_by_category(
        self,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate sales breakdown by medicine category"""
        cache_key = self._generate_cache_key("sales_by_category", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        base_query = self._get_base_order_query(filters)
        
        # Query with category joins
        query = (
            self.db.query(
                Category.category_id,
                Category.category_name,
                func.count(func.distinct(Order.order_id)).label('total_orders'),
                func.sum(OrderItem.quantity).label('total_quantity'),
                func.sum(OrderItem.price * OrderItem.quantity).label('total_revenue')
            )
            .join(OrderItem, Order.order_id == OrderItem.order_id)
            .join(MedicineBatch, OrderItem.batch_id == MedicineBatch.batch_id)
            .join(Medicine, MedicineBatch.medicine_id == Medicine.medicine_id)
            .join(Medicine.categories)
            .filter(
                Order.order_id.in_(base_query.with_entities(Order.order_id)),
                Category.is_deleted == False
            )
            .group_by(Category.category_id, Category.category_name)
            .order_by(func.sum(OrderItem.price * OrderItem.quantity).desc())
        )
        
        # Apply category filter if specified
        if filters.get('category_ids'):
            query = query.filter(Category.category_id.in_(filters['category_ids']))
        
        results = query.all()
        
        # Calculate total for percentage
        total_revenue = sum(self._decimal_to_float(row.total_revenue) for row in results)
        
        data = [
            {
                'category_id': row.category_id,
                'category_name': row.category_name,
                'total_orders': row.total_orders or 0,
                'total_quantity': row.total_quantity or 0,
                'total_revenue': self._decimal_to_float(row.total_revenue),
                'percentage': (
                    self._decimal_to_float(row.total_revenue) / total_revenue * 100
                ) if total_revenue > 0 else 0
            }
            for row in results
        ]
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Top Selling Medicines ==================== #
    
    async def generate_top_selling_medicines(
        self,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate top N selling medicines report"""
        cache_key = self._generate_cache_key(f"top_selling_medicines_{limit}", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        base_query = self._get_base_order_query(filters)
        
        query = (
            self.db.query(
                Medicine.medicine_id,
                Medicine.medicine_name,
                Medicine.generic_name,
                Medicine.manufacturer,
                func.sum(OrderItem.quantity).label('total_quantity'),
                func.count(func.distinct(Order.order_id)).label('total_orders'),
                func.sum(OrderItem.price * OrderItem.quantity).label('total_revenue')
            )
            .join(OrderItem, Order.order_id == OrderItem.order_id)
            .join(MedicineBatch, OrderItem.batch_id == MedicineBatch.batch_id)
            .join(Medicine, MedicineBatch.medicine_id == Medicine.medicine_id)
            .filter(
                Order.order_id.in_(base_query.with_entities(Order.order_id)),
                Medicine.is_deleted == False
            )
            .group_by(
                Medicine.medicine_id,
                Medicine.medicine_name,
                Medicine.generic_name,
                Medicine.manufacturer
            )
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        
        # Apply medicine filter if specified
        if filters.get('medicine_ids'):
            query = query.filter(Medicine.medicine_id.in_(filters['medicine_ids']))
        
        results = query.all()
        
        data = [
            {
                'rank': idx + 1,
                'medicine_id': row.medicine_id,
                'medicine_name': row.medicine_name,
                'generic_name': row.generic_name,
                'manufacturer': row.manufacturer,
                'total_quantity': row.total_quantity or 0,
                'total_orders': row.total_orders or 0,
                'total_revenue': self._decimal_to_float(row.total_revenue)
            }
            for idx, row in enumerate(results)
        ]
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Revenue Trends (YoY Comparison) ==================== #
    
    async def generate_revenue_trends(
        self,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate revenue trends with year-over-year comparison"""
        cache_key = self._generate_cache_key("revenue_trends", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # Get current period data
        current_query = self._get_base_order_query(filters)
        current_stats = (
            self.db.query(
                func.sum(Order.total_amount).label('total_revenue'),
                func.count(Order.order_id).label('total_orders'),
                func.avg(Order.total_amount).label('avg_order_value')
            )
            .filter(Order.order_id.in_(current_query.with_entities(Order.order_id)))
            .first()
        )
        
        # Calculate previous period dates
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        
        if date_from and date_to:
            period_days = (date_to - date_from).days
            prev_date_to = date_from - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=period_days)
            
            # Get previous period data
            prev_filters = filters.copy()
            prev_filters['date_from'] = prev_date_from
            prev_filters['date_to'] = prev_date_to
            
            prev_query = self._get_base_order_query(prev_filters)
            prev_stats = (
                self.db.query(
                    func.sum(Order.total_amount).label('total_revenue'),
                    func.count(Order.order_id).label('total_orders'),
                    func.avg(Order.total_amount).label('avg_order_value')
                )
                .filter(Order.order_id.in_(prev_query.with_entities(Order.order_id)))
                .first()
            )
            
            # Calculate growth rates
            current_revenue = self._decimal_to_float(current_stats.total_revenue)
            prev_revenue = self._decimal_to_float(prev_stats.total_revenue) if prev_stats else 0
            
            revenue_growth = (
                ((current_revenue - prev_revenue) / prev_revenue * 100)
                if prev_revenue > 0 else 0
            )
            
            order_growth = (
                ((current_stats.total_orders - prev_stats.total_orders) / 
                 prev_stats.total_orders * 100)
                if prev_stats and prev_stats.total_orders > 0 else 0
            )
        else:
            revenue_growth = 0
            order_growth = 0
            prev_stats = None
        
        data = {
            'current_period': {
                'total_revenue': self._decimal_to_float(current_stats.total_revenue),
                'total_orders': current_stats.total_orders or 0,
                'avg_order_value': self._decimal_to_float(current_stats.avg_order_value)
            },
            'previous_period': {
                'total_revenue': self._decimal_to_float(prev_stats.total_revenue) if prev_stats else 0,
                'total_orders': prev_stats.total_orders if prev_stats else 0,
                'avg_order_value': self._decimal_to_float(prev_stats.avg_order_value) if prev_stats else 0
            } if prev_stats else None,
            'growth': {
                'revenue_growth_percentage': round(revenue_growth, 2),
                'order_growth_percentage': round(order_growth, 2)
            }
        }
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Profit Margin Analysis ==================== #
    
    async def generate_profit_margin_analysis(
        self,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate profit margin analysis by medicine"""
        cache_key = self._generate_cache_key("profit_margin_analysis", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        base_query = self._get_base_order_query(filters)
        
        query = (
            self.db.query(
                Medicine.medicine_id,
                Medicine.medicine_name,
                Medicine.generic_name,
                func.avg(MedicineBatch.purchase_price).label('avg_purchase_price'),
                func.avg(MedicineBatch.selling_price).label('avg_selling_price'),
                func.sum(OrderItem.quantity).label('total_quantity'),
                func.sum(
                    (OrderItem.price - MedicineBatch.purchase_price) * OrderItem.quantity
                ).label('total_profit'),
                func.sum(OrderItem.price * OrderItem.quantity).label('total_revenue')
            )
            .join(OrderItem, Order.order_id == OrderItem.order_id)
            .join(MedicineBatch, OrderItem.batch_id == MedicineBatch.batch_id)
            .join(Medicine, MedicineBatch.medicine_id == Medicine.medicine_id)
            .filter(
                Order.order_id.in_(base_query.with_entities(Order.order_id)),
                Medicine.is_deleted == False
            )
            .group_by(
                Medicine.medicine_id,
                Medicine.medicine_name,
                Medicine.generic_name
            )
            .order_by(func.sum(
                (OrderItem.price - MedicineBatch.purchase_price) * OrderItem.quantity
            ).desc())
        )
        
        if filters.get('medicine_ids'):
            query = query.filter(Medicine.medicine_id.in_(filters['medicine_ids']))
        
        results = query.all()
        
        data = [
            {
                'medicine_id': row.medicine_id,
                'medicine_name': row.medicine_name,
                'generic_name': row.generic_name,
                'avg_purchase_price': self._decimal_to_float(row.avg_purchase_price),
                'avg_selling_price': self._decimal_to_float(row.avg_selling_price),
                'total_quantity_sold': row.total_quantity or 0,
                'total_profit': self._decimal_to_float(row.total_profit),
                'total_revenue': self._decimal_to_float(row.total_revenue),
                'profit_margin_percentage': (
                    self._decimal_to_float(row.total_profit) / 
                    self._decimal_to_float(row.total_revenue) * 100
                ) if row.total_revenue and self._decimal_to_float(row.total_revenue) > 0 else 0
            }
            for row in results
        ]
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Discount Impact Analysis ==================== #
    
    async def generate_discount_impact_analysis(
        self,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze the impact of discounts on revenue"""
        cache_key = self._generate_cache_key("discount_impact_analysis", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        base_query = self._get_base_order_query(filters)
        
        # Get orders with and without discounts
        stats = (
            self.db.query(
                func.count(Order.order_id).label('total_orders'),
                func.sum(Invoice.subtotal_amount).label('total_subtotal'),
                func.sum(Invoice.discount_amount).label('total_discounts'),
                func.sum(Invoice.gross_amount).label('total_gross'),
                func.count(
                    case((Invoice.discount_amount > 0, 1))
                ).label('orders_with_discount')
            )
            .join(Invoice, Order.order_id == Invoice.order_id)
            .filter(Order.order_id.in_(base_query.with_entities(Order.order_id)))
            .first()
        )
        
        total_orders = stats.total_orders or 0
        orders_with_discount = stats.orders_with_discount or 0
        orders_without_discount = total_orders - orders_with_discount
        
        data = {
            'total_orders': total_orders,
            'orders_with_discount': orders_with_discount,
            'orders_without_discount': orders_without_discount,
            'discount_adoption_rate': (
                orders_with_discount / total_orders * 100
            ) if total_orders > 0 else 0,
            'total_subtotal': self._decimal_to_float(stats.total_subtotal),
            'total_discounts': self._decimal_to_float(stats.total_discounts),
            'total_gross': self._decimal_to_float(stats.total_gross),
            'avg_discount_per_order': (
                self._decimal_to_float(stats.total_discounts) / total_orders
            ) if total_orders > 0 else 0,
            'discount_percentage': (
                self._decimal_to_float(stats.total_discounts) / 
                self._decimal_to_float(stats.total_subtotal) * 100
            ) if stats.total_subtotal and self._decimal_to_float(stats.total_subtotal) > 0 else 0
        }
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data
    
    # ==================== Coupon Effectiveness Report ==================== #
    
    async def generate_coupon_effectiveness(
        self,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze coupon usage and effectiveness"""
        cache_key = self._generate_cache_key("coupon_effectiveness", filters)
        
        cached_data = await self.cache_service.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # This would require tracking coupon usage in orders
        # For now, return coupon statistics from the Coupon table
        query = (
            self.db.query(
                Coupon.coupon_id,
                Coupon.code,
                Coupon.used_count,
                Coupon.max_usage,
                Discount.name.label('discount_name'),
                Discount.value.label('discount_value')
            )
            .join(Discount, Coupon.discount_id == Discount.discount_id)
            .filter(
                Coupon.is_deleted == False,
                Discount.is_deleted == False
            )
        )
        
        # Apply date filters on coupon validity
        if filters.get('date_from'):
            query = query.filter(Coupon.valid_from <= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(Coupon.valid_to >= filters['date_to'])
        
        results = query.all()
        
        data = [
            {
                'coupon_id': row.coupon_id,
                'coupon_code': row.code,
                'discount_name': row.discount_name,
                'discount_value': self._decimal_to_float(row.discount_value),
                'times_used': row.used_count or 0,
                'max_usage': row.max_usage,
                'usage_rate': (
                    (row.used_count / row.max_usage * 100)
                    if row.max_usage and row.max_usage > 0 else 0
                )
            }
            for row in results
        ]
        
        await self.cache_service.set(cache_key, json.dumps(data, default=str), ttl=3600)
        
        return data