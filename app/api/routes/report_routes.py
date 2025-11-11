# app/api/routes/report.py
from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.report_management import report_service as service
from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres 

router = APIRouter(prefix="/reports", tags=["Report Management"])


@router.get("/sales")
async def get_sales_report(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_sales_report_service(db)


@router.get("/orders")
async def get_order_report(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_order_report_service(db)


@router.get("/products")
async def get_product_report(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_product_report_service(db)


@router.get("/users")
async def get_user_report(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_user_report_service(db)


@router.get("/categories")
async def get_category_sales(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_category_sales_service(db)


@router.get("/timeline")
async def get_sales_timeline(db: AsyncSession = Depends(get_postgres), current_user=Security(get_current_user, scopes=["reports:read"])):
    return await service.get_sales_timeline_service(db)
