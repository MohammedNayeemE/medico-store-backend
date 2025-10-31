from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.order_management_models import (
    Coupon,
    Discount,
    DiscountCategory,
    DiscountMedicine,
    DiscountParameter,
    DiscountType,
)
from app.schemas.discount_schemas import (
    CouponCreate,
    DiscountCreate,
    DiscountParamterCreate,
    DiscountTypeCreate,
    DiscountTypeUpdate,
    DiscountUpdate,
)


class DiscountService:
    def __init__(self) -> None:
        pass

    async def LIST_DISCOUNT_TYPE(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ):
        try:
            result = await db.execute(
                select(DiscountType)
                .filter(DiscountType.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            discount_types = result.scalars().all()
            return discount_types
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[list_discount_type] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [list_discount_type]"
            )

    async def CREATE_DISCOUNT_TYPE(
        self, db: AsyncSession, discount_type_data: DiscountTypeCreate
    ):
        try:
            existing = await db.execute(
                select(DiscountType).filter(
                    DiscountType.type_name == discount_type_data.type_name
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=404, detail="the same discount type name already exists"
                )
            new_discount_type = DiscountType(
                type_name=discount_type_data.type_name,
                description=discount_type_data.description,
            )
            db.add(new_discount_type)
            await db.commit()
            await db.refresh(new_discount_type)
            return new_discount_type
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[create_discount_type] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_discount_type]"
            )

    async def UPDATE_DISCOUNT_TYPE(
        self, db: AsyncSession, discount_type_data: DiscountTypeUpdate, id: int
    ):
        try:
            result = await db.execute(
                select(DiscountType).where(
                    DiscountType.discount_type_id == id,
                    DiscountType.is_deleted == False,
                )
            )
            discount_type = result.scalar_one_or_none()
            if not discount_type:
                raise HTTPException(status_code=404, detail="Discount type not found.")
            if discount_type_data.type_name:
                discount_type.type_name = discount_type_data.type_name
            if discount_type_data.description:
                discount_type.description = discount_type_data.description
            await db.commit()
            await db.refresh(discount_type)
            return discount_type
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[update_discount_type]: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [update_discount_type]"
            )

    async def SOFT_DELETE_DISCOUNT_TYPE(
        self, discount_type_id: int, db: AsyncSession, user_id: int
    ):
        try:
            result = await db.execute(
                select(DiscountType).where(
                    DiscountType.discount_type_id == discount_type_id,
                    DiscountType.is_deleted == False,
                )
            )
            discount_type = result.scalar_one_or_none()
            if not discount_type:
                raise HTTPException(status_code=404, detail="Discount type not found.")
            discount_type.is_deleted = True
            discount_type.deleted_at = datetime.utcnow()
            discount_type.deleted_by = user_id
            await db.commit()
            return {"message": f"Discount type ID {id} deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[soft_delete_discount_type]: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [soft_delete_discount_type]",
            )

    async def LIST_ALL_DISCOUNTS(
        self, db: AsyncSession, skip: int, limit: int, is_active: bool | None = None
    ):
        try:
            query = select(Discount).where(Discount.is_deleted == False)
            if is_active is not None:
                now = datetime.utcnow()
                if is_active:
                    query = query.where(
                        Discount.start_date <= now, Discount.end_date >= now
                    )
                else:
                    query = query.where(
                        (Discount.end_date < now) | (Discount.start_date > now)
                    )
            query.offset(skip).limit(limit)
            result = await db.execute(query)
            discounts = result.scalars().unique().all()
            return discounts
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[list_all_discounts] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [list_all_discounts]"
            )

    async def GET_DISCOUNT_DETAILS(self, db: AsyncSession, discount_id: int):
        try:
            result = await db.execute(
                select(Discount).where(
                    Discount.discount_id == discount_id, Discount.is_deleted == False
                )
            )
            discount = result.scalar_one_or_none()
            if not discount:
                raise HTTPException(status_code=404, detail="Discount not found")
            return discount
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[get_discount_details] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_discount_details]"
            )

    async def CREATE_DISCOUNT(self, db: AsyncSession, discount_data: DiscountCreate):
        try:
            new_discount = Discount(
                name=discount_data.name,
                description=discount_data.description,
                discount_type_id=discount_data.discount_type_id,
                value=discount_data.value,
                start_date=discount_data.start_date,
                end_date=discount_data.end_date,
                min_purchase_amount=discount_data.min_purchase_amount,
                max_discount_amount=discount_data.max_discount_amount,
                usage_limit=discount_data.usage_limit,
            )
            db.add(new_discount)
            await db.flush()
            if discount_data.category_ids:
                for cat_id in discount_data.category_ids:
                    db.add(
                        DiscountCategory(
                            discount_id=new_discount.discount_id, category_id=cat_id
                        )
                    )
            if discount_data.medicine_ids:
                for med_id in discount_data.medicine_ids:
                    db.add(
                        DiscountMedicine(
                            discount_id=new_discount.discount_id, medicine_id=med_id
                        )
                    )
            if discount_data.parameters:
                for param in discount_data.parameters:
                    db.add(
                        DiscountParameter(
                            discount_id=new_discount.discount_id,
                            param_key=param.get("key"),
                            param_value=param.get("value"),
                        )
                    )
            await db.commit()
            await db.refresh(new_discount)
            return new_discount
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[create_discount] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_discount]"
            )

    async def UPDATE_DISCOUNT(
        self,
        db: AsyncSession,
        discount_id: int,
        discount_data: DiscountUpdate,
        user_id: int,
    ):
        try:
            result = await db.execute(
                select(Discount).where(
                    Discount.discount_id == discount_id, Discount.is_deleted == False
                )
            )
            discount = result.scalar_one_or_none()
            if not discount:
                raise HTTPException(status_code=404, detail="Discount not found")
            for field, value in discount_data.model_dump(exclude_unset=True).items():
                if hasattr(discount, field) and field not in [
                    "category_ids",
                    "medicine_ids",
                    "parameters",
                ]:
                    setattr(discount, field, value)
            if discount_data.category_ids is not None:
                await db.execute(
                    update(DiscountCategory)
                    .where(DiscountCategory.discount_id == discount_id)
                    .values(
                        is_deleted=True,
                        deleted_at=datetime.utcnow(),
                        deleted_by=user_id,
                    )
                )
                for cat_id in discount_data.category_ids:
                    db.add(
                        DiscountCategory(discount_id=discount_id, category_id=cat_id)
                    )
            if discount_data.medicine_ids is not None:
                await db.execute(
                    update(DiscountMedicine)
                    .where(DiscountMedicine.discount_id == discount_id)
                    .values(
                        is_deleted=True,
                        deleted_at=datetime.utcnow(),
                        deleted_by=user_id,
                    )
                )
                for med_id in discount_data.medicine_ids:
                    db.add(
                        DiscountMedicine(discount_id=discount_id, medicine_id=med_id)
                    )
            if discount_data.parameters is not None:
                await db.execute(
                    update(DiscountParameter)
                    .where(DiscountParameter.discount_id == discount_id)
                    .values(
                        is_deleted=True,
                        deleted_at=datetime.utcnow(),
                        deleted_by=user_id,
                    )
                )
                for param in discount_data.parameters:
                    db.add(
                        DiscountParameter(
                            discount_id=discount_id,
                            param_key=param.get("key"),
                            param_value=param.get("value"),
                        )
                    )
            discount.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(discount)
            return discount
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[UPDATE_DISCOUNT] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [UPDATE_DISCOUNT]"
            )

    async def SOFT_DELETE_DISCOUNT(
        self, db: AsyncSession, discount_id: int, user_id: int
    ):
        try:
            result = await db.execute(
                select(Discount).where(
                    Discount.discount_id == discount_id, Discount.is_deleted == False
                )
            )
            discount = result.scalar_one_or_none()
            if not discount:
                raise HTTPException(status_code=404, detail="Discount not found")
            discount.is_deleted = True
            discount.deleted_at = datetime.utcnow()
            discount.deleted_by = user_id
            await db.commit()
            return {"message": f"Discount ID {discount_id} deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[soft_delete_discount] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [soft_delete_discount]"
            )

    async def GET_PARAMETERS(self, db: AsyncSession, discount_id: int):
        try:
            result = await db.execute(
                select(DiscountParameter).where(
                    DiscountParameter.discount_id == discount_id,
                    DiscountParameter.is_deleted == False,
                )
            )
            discount_params = result.scalars().all()
            return discount_params
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[get_parameters] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_parameters]"
            )

    async def ADD_PARAMETER(
        self, db: AsyncSession, discount_id: int, parameter_data: DiscountParamterCreate
    ):
        try:
            new_param = DiscountParameter(
                discount_id=discount_id,
                param_key=parameter_data.param_key,
                param_value=parameter_data.param_value,
            )
            db.add(new_param)
            await db.commit()
            await db.refresh(new_param)
            return new_param
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[get_parameters] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_parameters]"
            )

    async def DELETE_PARAMETER(self, db: AsyncSession, parameter_id: int, user_id: int):
        try:
            result = await db.execute(
                select(DiscountParameter).where(
                    DiscountParameter.parameter_id == parameter_id
                )
            )
            parameter_obj = result.scalar_one_or_none()
            if not parameter_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found"
                )
            if parameter_obj.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parameter already deleted",
                )
            parameter_obj.is_deleted = True
            parameter_obj.deleted_at = datetime.utcnow()
            parameter_obj.deleted_by = user_id
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[delete_parameter] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [delete_parameter]"
            )

    async def UPDATE_PARAMETER(
        self, parameter_id: int, data: DiscountParamterCreate, db: AsyncSession
    ):
        try:
            result = await db.execute(
                select(DiscountParameter).where(
                    DiscountParameter.parameter_id == parameter_id,
                    DiscountParameter.is_deleted == False,
                )
            )
            parameter = result.scalars().first()
            if not parameter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Parameter not found"
                )
            if data.param_key is not None:
                parameter.param_key = data.param_key
            if data.param_value is not None:
                parameter.param_value = data.param_value
            await db.commit()
            await db.refresh(parameter)
            return parameter
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[delete_parameter] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [delete_parameter]"
            )

    async def ASSIGN_DISCOUNT_MEDICINES(
        self, discount_id: int, medicine_ids: List[int], db: AsyncSession
    ):
        try:
            for mid in medicine_ids:
                result = await db.execute(
                    select(DiscountMedicine).where(
                        DiscountMedicine.discount_id == discount_id,
                        DiscountMedicine.medicine_id == mid,
                    )
                )
                existing = result.scalars().first()
                if existing and not existing.is_deleted:
                    continue  # already assigned and active
                elif existing and existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.deleted_by = None
                else:
                    db.add(DiscountMedicine(discount_id=discount_id, medicine_id=mid))
            await db.commit()
            return {"message": "Medicines assigned successfully"}
        except Exception as e:
            print("-----------------------")
            print(f"[assign_discount_medicines] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [assign_discount_medicines]",
            )

    async def REMOVE_DISCOUNT_MEDICINE(
        self, discount_id: int, medicine_id: int, db: AsyncSession, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(DiscountMedicine).where(
                    DiscountMedicine.discount_id == discount_id,
                    DiscountMedicine.medicine_id == medicine_id,
                    DiscountMedicine.is_deleted == False,
                )
            )
            record = result.scalars().first()
            if not record:
                raise HTTPException(status_code=404, detail="Relation not found")
            record.is_deleted = True
            record.deleted_at = datetime.utcnow()
            record.deleted_by = deleted_by
            await db.commit()
            return {"message": "Medicine unassigned from discount"}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[remove_discount_medicine] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [remove_discount_medicine]",
            )

    async def ASSIGN_DISCOUNT_CATEGORIES(
        self, discount_id: int, category_ids: List[int], db: AsyncSession
    ):
        try:
            for cid in category_ids:
                result = await db.execute(
                    select(DiscountCategory).where(
                        DiscountCategory.discount_id == discount_id,
                        DiscountCategory.category_id == cid,
                    )
                )
                existing = result.scalars().first()
                if existing and not existing.is_deleted:
                    continue
                elif existing and existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.deleted_by = None
                else:
                    db.add(DiscountCategory(discount_id=discount_id, category_id=cid))
            await db.commit()
            return {"message": "Categories assigned successfully"}
        except Exception as e:
            print("-----------------------")
            print(f"[assign_discount_categories] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [assign_discount_categories]",
            )

    async def REMOVE_DISCOUNT_CATEGORY(
        self, discount_id: int, category_id: int, db: AsyncSession, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(DiscountCategory).where(
                    DiscountCategory.discount_id == discount_id,
                    DiscountCategory.category_id == category_id,
                    DiscountCategory.is_deleted == False,
                )
            )
            record = result.scalars().first()
            if not record:
                raise HTTPException(status_code=404, detail="Relation not found")
            record.is_deleted = True
            record.deleted_at = datetime.utcnow()
            record.deleted_by = deleted_by
            await db.commit()
            return {"message": "Category unassigned from discount"}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[remove_discount_category] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [remove_discount_category]",
            )

    async def CREATE_COUPON(self, data: CouponCreate, db: AsyncSession):
        try:
            result = await db.execute(select(Coupon).where(Coupon.code == data.code))
            existing = result.scalars().first()
            if existing:
                raise HTTPException(
                    status_code=400, detail="Coupon code already exists"
                )
            coupon = Coupon(
                code=data.code,
                discount_id=data.discount_id,
                max_usage=data.max_usage,
                valid_from=data.valid_from,
                valid_to=data.valid_to,
            )
            db.add(coupon)
            await db.commit()
            await db.refresh(coupon)
            return coupon
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[create_coupon] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_coupon]"
            )

    async def VALIDATE_COUPON(self, code: str, db: AsyncSession):
        try:
            result = await db.execute(
                select(Coupon).where(Coupon.code == code, Coupon.is_deleted == False)
            )
            coupon = result.scalars().first()
            if not coupon:
                return {"valid": False, "message": "Invalid coupon code"}
            now = datetime.utcnow()
            if coupon.valid_from > now or coupon.valid_to < now:
                return {"valid": False, "message": "Coupon expired or not yet valid"}
            if coupon.max_usage and coupon.used_count >= coupon.max_usage:
                return {"valid": False, "message": "Coupon usage limit reached"}
            remaining = (
                coupon.max_usage - coupon.used_count if coupon.max_usage else None
            )
            return {
                "valid": True,
                "message": "Coupon is valid",
                "remaining_uses": remaining,
            }
        except Exception as e:
            print("-----------------------")
            print(f"[validate_coupon] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [validate_coupon]"
            )

    async def INCREMENT_COUPON_USAGE(
        self, coupon_id: int, db: AsyncSession, delta: int
    ):
        try:
            result = await db.execute(
                select(Coupon).where(Coupon.coupon_id == coupon_id)
            )
            coupon = result.scalars().first()
            if not coupon or coupon.is_deleted:
                raise HTTPException(status_code=404, detail="Coupon not found")
            if coupon.max_usage and coupon.used_count >= coupon.max_usage:
                raise HTTPException(
                    status_code=400, detail="Coupon usage limit reached"
                )
            coupon.used_count += delta
            await db.commit()
            await db.refresh(coupon)
            return coupon
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[increment_coupon_usage] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [increment_coupon_usage]",
            )

    async def GET_COUPON_DETAILS(self, coupon_id: int, db: AsyncSession):
        try:
            result = await db.execute(
                select(Coupon).where(
                    Coupon.coupon_id == coupon_id, Coupon.is_deleted == False
                )
            )
            coupon = result.scalars().first()
            if not coupon:
                raise HTTPException(status_code=404, detail="Coupon not found")
            return coupon
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[get_coupon_details] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_coupon_details]"
            )

    async def SOFT_DELETE_COUPON(
        self, coupon_id: int, db: AsyncSession, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(Coupon).where(Coupon.coupon_id == coupon_id)
            )
            coupon = result.scalars().first()
            if not coupon or coupon.is_deleted:
                raise HTTPException(status_code=404, detail="Coupon not found")
            coupon.is_deleted = True
            coupon.deleted_at = datetime.utcnow()
            coupon.deleted_by = deleted_by
            await db.commit()
            return {"message": "Coupon soft deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------")
            print(f"[soft_delete_coupon] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [soft_delete_coupon]"
            )
