# app/services/report_service.py
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import report_crud
from app.models.inventory_management_models import (
    Category,
    Medicine,
    MedicineBatch,
    MedicineCategory,
)


async def get_sales_report_service(db):
    data = await report_crud.crud_get_sales_report(db)
    if not data:
        raise HTTPException(status_code=404, detail="No sales data found")
    total_revenue = total_cost = total_profit = 0
    report = []
    for medicine_id, name, sold_units, avg_cost, avg_price in data:
        revenue = float(avg_price or 0) * (sold_units or 0)
        cost = float(avg_cost or 0) * (sold_units or 0)
        profit = revenue - cost
        margin = (profit / cost * 100) if cost > 0 else 0
        total_revenue += revenue
        total_cost += cost
        total_profit += profit
        report.append(
            {
                "medicine_id": f"MED{medicine_id}",
                "medicine_name": name,
                "sold_units": sold_units,
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "margin_percent": round(margin, 2),
            }
        )
    return {
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "total_profit": round(total_profit, 2),
            "overall_margin_percent": (
                round((total_profit / total_cost * 100), 2) if total_cost > 0 else 0
            ),
        },
        "details": report,
    }


async def get_order_report_service(db):
    orders = await report_crud.crud_get_order_report(db)
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found")
    result = []
    for order, payment, customer in orders:
        result.append(
            {
                "order_id": f"ORD{order.order_id}",
                "customer_name": customer.name,
                "amount": float(order.total_amount),
                "payment_mode": payment.payment_mode,
                "status": order.status.value,
                "created_at": order.created_at,
            }
        )
    return result


async def get_product_report_service(db):
    data = await report_crud.crud_get_product_report(db)
    if not data:
        raise HTTPException(status_code=404, detail="No products found")

    result = []
    for med_id, name, category, is_prescribed, stock in data:
        result.append(
            {
                "medicine_id": f"MED{med_id}",
                "medicine_name": name,
                "category": category,
                "is_prescribed": is_prescribed,
                "stock": int(stock),
            }
        )
    return result


async def get_user_report_service(db):
    data = await report_crud.crud_get_user_report(db)
    if not data:
        raise HTTPException(status_code=404, detail="No users found")
    return [
        {
            "user_id": user.user_id,
            "name": profile.name,
            "email": profile.email,
            "is_active": user.is_active,
            "registered_at": user.created_at,
        }
        for user, profile in data
    ]


async def get_category_sales_service(db):
    data = await report_crud.crud_get_category_sales(db)
    if not data:
        raise HTTPException(status_code=404, detail="No category sales found")
    return [
        {
            "category_name": category_name,
            "total_sold": int(total_sold),
        }
        for category_name, total_sold in data
    ]


async def get_sales_timeline_service(db):
    data = await report_crud.crud_get_sales_timeline(db)
    if not data:
        raise HTTPException(status_code=404, detail="No timeline data found")
    return [
        {
            "date": row.date,
            "total_orders": row.total_orders,
            "total_amount": float(row.total_amount or 0),
        }
        for row in data
    ]
