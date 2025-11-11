# app/crud/report_crud.py
from math import ceil

from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory_management_models import (
    Category,
    Medicine,
    MedicineBatch,
    MedicineCategory,
)
from app.models.order_management_models import Order, OrderItem, Payment
from app.models.user_management_models import CustomerProfile, User


# ---------- SALES REPORT ----------
async def crud_get_sales_report(db: AsyncSession):
    """
    Get sales performance per medicine.
    """
    stmt = (
        select(
            Medicine.medicine_id,
            Medicine.medicine_name,
            func.sum(OrderItem.quantity).label("sold_units"),
            func.avg(MedicineBatch.purchase_price).label("avg_cost"),
            func.avg(MedicineBatch.selling_price).label("avg_price"),
        )
        .join(MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id)
        .join(OrderItem, OrderItem.batch_id == MedicineBatch.batch_id)
        .join(Order, Order.order_id == OrderItem.order_id)
        .where(Order.is_deleted == False)
        .group_by(Medicine.medicine_id)
        .order_by(desc("sold_units"))
    )

    result = await db.execute(stmt)
    return result.all()


# ---------- ORDER REPORT ----------
async def crud_get_order_report(db: AsyncSession):
    stmt = (
        select(Order, Payment, CustomerProfile)
        .join(Payment, Payment.order_id == Order.order_id)
        .join(CustomerProfile, CustomerProfile.user_id == Order.customer_id)
        .where(Order.is_deleted == False)
        .order_by(desc(Order.created_at))
    )

    result = await db.execute(stmt)
    return result.all()


async def crud_get_product_report(db: AsyncSession):
    stmt = (
        select(
            Medicine.medicine_id,
            Medicine.generic_name,
            Category.category_name,
            Medicine.is_prescribed,
            func.coalesce(func.sum(MedicineBatch.quantity), 0).label("stock"),
        )
        .join(MedicineCategory, Medicine.medicine_id == MedicineCategory.medicine_id)
        .join(Category, Category.category_id == MedicineCategory.category_id)
        .outerjoin(MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id)
        .where(Medicine.is_deleted == False, Category.is_deleted == False)
        .group_by(Medicine.medicine_id, Category.category_id)
    )
    result = await db.execute(stmt)
    return result.all()


# ---------- USER REPORT ----------
async def crud_get_user_report(db: AsyncSession):
    stmt = (
        select(User, CustomerProfile)
        .join(CustomerProfile, CustomerProfile.user_id == User.user_id)
        .where(User.is_deleted == False)
    )
    result = await db.execute(stmt)
    return result.all()


# ---------- CATEGORY SALES ----------
async def crud_get_category_sales(db: AsyncSession):
    stmt = (
        select(Category.category_name, func.sum(OrderItem.quantity).label("total_sold"))
        .join(MedicineCategory, Category.category_id == MedicineCategory.category_id)
        .join(Medicine, MedicineCategory.medicine_id == Medicine.medicine_id)
        .join(MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id)
        .join(OrderItem, MedicineBatch.batch_id == OrderItem.batch_id)
        .group_by(Category.category_id)
        .order_by(desc("total_sold"))
    )
    result = await db.execute(stmt)
    return result.all()


# ---------- SALES TIMELINE ----------
async def crud_get_sales_timeline(db: AsyncSession):
    stmt = (
        select(
            cast(Order.created_at, Date).label("date"),
            func.count(Order.order_id).label("total_orders"),
            func.sum(Order.total_amount).label("total_amount"),
        )
        .group_by(cast(Order.created_at, Date))
        .order_by(cast(Order.created_at, Date))
    )
    result = await db.execute(stmt)
    return result.all()
