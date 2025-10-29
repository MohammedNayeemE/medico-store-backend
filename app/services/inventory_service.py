from datetime import datetime
from operator import or_
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.inventory_management_models import (
    Alternative,
    Category,
    GSTSlab,
    Medicine,
    MedicineAlternative,
    MedicineBatch,
    MedicineCategory,
    MedicineSideEffect,
    MedicineTag,
    SideEffect,
    Tag,
)
from app.schemas.inventory_schemas import (
    AlternativeCreate,
    CategoryCreate,
    CategoryResponse,
    GSTSlabCreate,
    MedicineBatchCreate,
    MedicineCreate,
    SideEffectCreate,
    SideEffectResponse,
    TagCreate,
    TagReponse,
)


class InventoryManagementService:
    def __init__(self) -> None:
        pass

    async def CREATE_MEDICINE(self, db: AsyncSession, medicine_data: MedicineCreate):
        try:
            new_medicine = Medicine(
                medicine_name=medicine_data.medicine_name,
                generic_name=medicine_data.generic_name,
                manufacturer=medicine_data.manufacturer,
                description=medicine_data.description,
                is_prescribed=medicine_data.is_prescribed,
                weight=medicine_data.weight,
                hsn_code=medicine_data.hsn_code,
                image_asset_id=medicine_data.image_asset_id,
            )
            db.add(new_medicine)
            await db.flush()
            if medicine_data.category_ids:
                for cat_id in medicine_data.category_ids:
                    new_med_cat = MedicineCategory(
                        medicine_id=new_medicine.medicine_id, category_id=cat_id
                    )
                    db.add(new_med_cat)
            if medicine_data.tag_ids:
                for tag_id in medicine_data.tag_ids:
                    new_med_tag = MedicineTag(
                        medicine_id=new_medicine.medicine_id, tag_id=tag_id
                    )
                    db.add(new_med_tag)
            if medicine_data.side_effect_ids:
                for sf_id in medicine_data.side_effect_ids:
                    new_med_sf = MedicineSideEffect(
                        medicine_id=new_medicine.medicine_id, side_effect_id=sf_id
                    )
                    db.add(new_med_sf)
            if medicine_data.alternative_ids:
                for alt_id in medicine_data.alternative_ids:
                    new_med_alt = MedicineAlternative(
                        medicine_id=new_medicine.medicine_id, alternative_id=alt_id
                    )
                    db.add(new_med_alt)
            await db.commit()
            await db.refresh(new_medicine)
            return new_medicine
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[create_medicine] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_medicine]"
            )

    async def GET_MEDICINES(
        self,
        db: AsyncSession,
        name: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            query = (
                select(Medicine)
                .options(
                    joinedload(Medicine.categories),
                    joinedload(Medicine.tags),
                    joinedload(Medicine.side_effects),
                    joinedload(Medicine.alternatives),
                    joinedload(Medicine.gst_slab),
                )
                .where(Medicine.is_deleted == False)
            )
            if name:
                query = query.where(
                    or_(
                        Medicine.medicine_name.ilike(f"%{name}%"),
                        Medicine.generic_name.ilike(f"%{name}%"),
                    )
                )
            if category:
                query = query.join(Medicine.categories).where(
                    Category.category_name.ilike(f"%{category}%")
                )
            if tag:
                query = query.join(Medicine.tags).where(Tag.name.ilike(f"%{tag}%"))
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            medicines = result.scalars().unique().all()
            if not medicines:
                return []
            return medicines
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[get_medicines] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_medicines]"
            )

    async def GET_MEDICINE_BY_ID(self, db: AsyncSession, medicine_id: int):
        try:
            result = await db.execute(
                select(Medicine).where(Medicine.medicine_id == medicine_id)
            )
            medicine = result.scalar_one_or_none()
            if not medicine:
                raise HTTPException(status_code=404, detail="medicine not found")
            return medicine
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[get_medicine_by_id] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_medicine_by_id]"
            )

    async def UPDATE_MEDICINE(
        self, db: AsyncSession, medicine_id: int, medicine_data: MedicineCreate
    ):
        try:
            result = await db.execute(
                select(Medicine)
                .options(
                    selectinload(Medicine.categories),
                    selectinload(Medicine.tags),
                    selectinload(Medicine.side_effects),
                    selectinload(Medicine.alternatives),
                )
                .filter(Medicine.medicine_id == medicine_id)
            )
            medicine = result.scalar_one_or_none()
            if not medicine:
                raise HTTPException(status_code=404, detail="medicine id not found")
            update_fields = [
                "medicine_name",
                "generic_name",
                "description",
                "manufacturer",
                "is_prescribed",
                "weight",
                "hsn_code",
                "image_asset_id",
            ]
            for field in update_fields:
                value = getattr(medicine_data, field, None)
                if value is not None:
                    setattr(medicine, field, value)
            if getattr(medicine_data, "category_ids", None) is not None:
                result = await db.execute(
                    select(Category).filter(
                        Category.category_id.in_(medicine_data.category_ids)
                    )
                )
                medicine.categories = result.scalars().all()
            if getattr(medicine_data, "tag_ids", None) is not None:
                result = await db.execute(
                    select(Tag).filter(Tag.tag_id.in_(medicine_data.tag_ids))
                )
                medicine.tags = result.scalars().all()
            if getattr(medicine_data, "side_effect_ids", None) is not None:
                result = await db.execute(
                    select(SideEffect).filter(
                        SideEffect.side_effect_id.in_(medicine_data.side_effect_ids)
                    )
                )
                medicine.side_effects = result.scalars().all()
            if getattr(medicine_data, "alternative_ids", None) is not None:
                result = await db.execute(
                    select(Medicine).filter(
                        Medicine.medicine_id.in_(medicine_data.alternative_ids)
                    )
                )
                medicine.alternatives = result.scalars().all()
            await db.commit()
            await db.refresh(medicine)
            return medicine
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[update_medicine] : {e}")
            await db.rollback()
            raise HTTPException(
                status_code=500, detail="internal server error : [update_medicine]"
            )

    async def SOFT_DELETE_MEDICINE(
        self, db: AsyncSession, medicine_id: int, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(Medicine).filter(Medicine.medicine_id == medicine_id)
            )
            medicine = result.scalar_one_or_none()
            if not medicine:
                raise HTTPException(status_code=404, detail="medicine not found")
            medicine.deleted_by = deleted_by
            medicine.is_deleted = True
            await db.commit()
            await db.refresh(medicine)
            return JSONResponse(
                status_code=200,
                content={"msg": f"{medicine_id} deleted successfully by {deleted_by}"},
            )
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[soft_delete_medicine] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [soft_delete_medicine]"
            )

    async def LINK_MEDICINE_CATEGORIES(
        self, db: AsyncSession, medicine_id: int, category_ids: List[int]
    ):
        try:
            pass
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[link_medicine_categories] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [link_medicine_categories]",
            )

    async def LINK_MEDICINE_TAGS(
        self, db: AsyncSession, medicine_id: int, tag_ids: List[int]
    ):
        try:
            pass
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[link_medicine_tags] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [link_medicine_tags]"
            )

    async def LINK_MEDICINE_SIDE_EFFECTS(
        self, db: AsyncSession, medicine_id: int, side_effect_ids: List[int]
    ):
        try:
            pass
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[link_medicine_side_effects] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [link_medicine_side_effects]",
            )

    async def LINK_MEDICINE_ALTERNATIVES(
        self, db: AsyncSession, medicine_id: int, alternative_ids: List[int]
    ):
        try:
            pass
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[link_medicine_alternatives] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [link_medicine_alternatives]",
            )

    async def GET_MEDICINE_BATCHES(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        medicine_id: int | None = None,
    ):
        try:
            query = select(MedicineBatch).where(MedicineBatch.is_deleted == False)
            if medicine_id:
                query = query.where(MedicineBatch.medicine_id == medicine_id)
            query.offset(skip).limit(limit)
            result = await db.execute(query)
            batches = result.scalars().all()
            return batches
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[get_medicine_batches] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_medicine_batches]"
            )

    async def CREATE_MEDICINE_BATCH(
        self, db: AsyncSession, batch_data: MedicineBatchCreate
    ):
        try:
            medicine_id = batch_data.medicine_id
            result = await db.execute(
                select(Medicine).filter(Medicine.medicine_id == medicine_id)
            )
            medicine_obj = result.scalar_one_or_none()
            if not medicine_obj:
                raise HTTPException(status_code=404, detail="medicine_id not found")
            new_batch = MedicineBatch(
                medicine_id=batch_data.medicine_id,
                batch_number=batch_data.batch_number,
                expiry_date=batch_data.expiry_date,
                quantity=batch_data.quantity,
                purchase_price=batch_data.purchase_price,
                selling_price=batch_data.selling_price,
            )
            db.add(new_batch)
            await db.commit()
            await db.refresh(new_batch)
            return new_batch
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[create_medicine_batch] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [create_medicine_batch]",
            )

    async def GET_BATCH_BY_ID(self, db: AsyncSession, batch_id: int):
        try:
            result = await db.execute(
                select(MedicineBatch).filter(MedicineBatch.batch_id == batch_id)
            )
            batch_obj = result.scalar_one_or_none()
            if not batch_obj:
                raise HTTPException(status_code=404, detail="batch_id not found")
            return batch_obj
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[get_batch_by_id] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [get_batch_by_id]",
            )

    async def UPDATE_BATCH(
        self, db: AsyncSession, batch_id: int, batch_data: MedicineBatchCreate
    ):
        try:
            result = await db.execute(
                select(MedicineBatch).filter(MedicineBatch.batch_id == batch_id)
            )
            batch_obj = result.scalar_one_or_none()
            batch_obj.medicine_id = batch_data.medicine_id
            batch_obj.batch_number = batch_data.batch_number
            batch_obj.expiry_date = batch_data.expiry_date
            batch_obj.quantity = batch_data.quantity
            batch_obj.purchase_price = batch_data.purchase_price
            batch_obj.selling_price = batch_data.selling_price
            await db.commit()
            await db.refresh(batch_obj)
            return batch_obj
        except HTTPException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[update_batch] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [update_batch]",
            )

    async def SOFT_DELETE_BATCH(self, db: AsyncSession, batch_id: int, deleted_by: int):
        try:
            result = await db.execute(
                select(MedicineBatch).filter(MedicineBatch.batch_id == batch_id)
            )
            batch_obj = result.scalar_one_or_none()
            if not batch_obj:
                raise HTTPException(status_code=404, detail="batch_id not found")
            if batch_obj.is_deleted:
                raise HTTPException(
                    status_code=400, detail="this batch is already deleted"
                )
            batch_obj.is_deleted = True
            batch_obj.deleted_by = deleted_by
            await db.commit()
            await db.refresh(batch_obj)
            return JSONResponse(
                status_code=200, content={"msg": f"{batch_id} this batch is deleted"}
            )
        except HTTPException:
            raise
        except Exception as e:
            print("------------------------")
            print(f"[soft_delete_batch]: {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [soft_delete_batch]"
            )

    async def CREATE_CATEGORY(self, db: AsyncSession, category_data: CategoryCreate):
        try:
            result = await db.execute(
                select(Category).filter(
                    Category.category_name == category_data.category_name
                )
            )
            category_obj = result.scalar_one_or_none()
            if category_obj:
                raise HTTPException(
                    status_code=400,
                    detail="the category already exits , pls give unqiue name",
                )
            new_category = Category(category_name=category_data.category_name)
            db.add(new_category)
            await db.commit()
            await db.refresh(new_category)
            return new_category
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[create_category] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_category]"
            )

    async def GET_ALL_CATEGORIES(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ):
        try:
            result = await db.execute(
                select(Category)
                .filter(Category.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            categories_obj = result.scalars().all()
            count_result = await db.execute(
                select(func.count()).filter(Category.is_deleted == False)
            )
            total = len(count_result.scalars().all())
            data = [
                CategoryResponse.from_orm(cat).model_dump() for cat in categories_obj
            ]
            return JSONResponse(
                status_code=200,
                content={"msg": {"totalCount": total, "data": data}},
            )
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[get_all_categories] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [get_all_categories]"
            )

    async def GET_CATEGORY_BY_ID(self, db: AsyncSession, category_id: int):
        try:
            result = await db.execute(
                select(Category).filter(Category.category_id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category or category.is_deleted:
                raise HTTPException(status_code=404, detail="Category not found")
            return category
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[get_category_by_id] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [get_category_by_id]"
            )

    async def UPDATE_CATEGORY(
        self, db: AsyncSession, category_id: int, category_data: CategoryCreate
    ):
        try:
            result = await db.execute(
                select(Category).filter(Category.category_id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category or category.is_deleted:
                raise HTTPException(status_code=404, detail="Category not found")
            if category_data.category_name:
                existing = await db.execute(
                    select(Category).filter(
                        Category.category_name == category_data.category_name,
                        Category.category_id != category_id,
                    )
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(
                        status_code=400, detail="Category name already exists."
                    )
                category.category_name = category_data.category_name
            await db.commit()
            await db.refresh(category)
            return category
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[update_category] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [update_category]"
            )

    async def SOFT_DELETE_CATEGORY(
        self, db: AsyncSession, category_id: int, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(Category).filter(Category.category_id == category_id)
            )
            category = result.scalar_one_or_none()
            if not category or category.is_deleted:
                raise HTTPException(status_code=404, detail="Category not found")
            category.is_deleted = True
            category.deleted_at = datetime.utcnow()
            category.deleted_by = deleted_by
            await db.commit()
            return JSONResponse(
                status_code=200,
                content={"msg": f"{category_id} deleted successfully by {deleted_by}"},
            )
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------")
            print(f"[soft_delete_category] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error: [soft_delete_category]"
            )

    async def CREATE_TAG(self, db: AsyncSession, tag_data: TagCreate):
        try:
            result = await db.execute(select(Tag).filter(Tag.name == tag_data.name))
            tag_obj = result.scalar_one_or_none()
            if tag_obj:
                raise HTTPException(
                    status_code=400,
                    detail="the tag already exists, please provide a unique name",
                )
            new_tag = Tag(name=tag_data.name)
            db.add(new_tag)
            await db.commit()
            await db.refresh(new_tag)
            return new_tag
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[create_tag] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_tag]"
            )

    async def LIST_ALL_TAGS(self, db: AsyncSession, skip: int, limit: int):
        try:
            result = await db.execute(
                select(Tag).filter(Tag.is_deleted == False).offset(skip).limit(limit)
            )
            tags = result.scalars().all()
            count_result = await db.execute(
                select(func.count()).filter(Tag.is_deleted == False)
            )
            data = [TagReponse.from_orm(tag).model_dump() for tag in tags]
            total = count_result.scalar_one()
            return JSONResponse(
                status_code=200, content={"msg": {"totalCount": total, "data": data}}
            )
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[list_all_tags] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [list_all_tags]"
            )

    async def UPDATE_TAG(self, db: AsyncSession, tag_id: int, tag_data: TagCreate):
        try:
            result = await db.execute(select(Tag).filter(Tag.tag_id == tag_id))
            tag_obj = result.scalar_one_or_none()
            if not tag_obj or tag_obj.is_deleted:
                raise HTTPException(status_code=404, detail="tag not found")
            if tag_data.name:
                dup_result = await db.execute(
                    select(Tag).filter(Tag.name == tag_data.name, Tag.tag_id != tag_id)
                )
                if dup_result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=400,
                        detail="the tag name already exists, please provide a unique name",
                    )
                tag_obj.name = tag_data.name
            await db.commit()
            await db.refresh(tag_obj)
            return tag_obj

        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[update_tag] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [update_tag]"
            )

    async def SOFT_DELETE_TAG(self, db: AsyncSession, tag_id: int, deleted_by: int):
        try:
            result = await db.execute(select(Tag).filter(Tag.tag_id == tag_id))
            tag_obj = result.scalar_one_or_none()
            if not tag_obj or tag_obj.is_deleted:
                raise HTTPException(status_code=404, detail="tag not found")
            tag_obj.is_deleted = True
            tag_obj.deleted_at = datetime.utcnow()
            tag_obj.deleted_by = deleted_by
            await db.commit()
            return JSONResponse(
                status_code=200, content={"msg": "tag deleted successfully"}
            )
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[soft_delete_tag] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [soft_delete_tag]"
            )

    async def GET_TAG_DETAILS_BY_ID(self, db: AsyncSession, tag_id: int):
        try:
            result = await db.execute(select(Tag).filter(Tag.tag_id == tag_id))
            tag_obj = result.scalar_one_or_none()
            if not tag_obj or tag_obj.is_deleted:
                raise HTTPException(status_code=404, detail="tag not found")
            return tag_obj
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[get_tag_details] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [get_tag_details]"
            )

    async def CREATE_SIDE_EFFECT(
        self, db: AsyncSession, side_effect_data: SideEffectCreate
    ):
        try:
            result = await db.execute(
                select(SideEffect).filter(
                    SideEffect.side_effect == side_effect_data.side_effect
                )
            )
            side_effect_obj = result.scalar_one_or_none()
            if side_effect_obj:
                raise HTTPException(
                    status_code=400,
                    detail="the side effect already exists, please provide a unique name",
                )
            new_side_effect = SideEffect(side_effect=side_effect_data.side_effect)
            db.add(new_side_effect)
            await db.commit()
            await db.refresh(new_side_effect)
            return new_side_effect
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[create_side_effect] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [create_side_effect]"
            )

    async def LIST_ALL_SIDE_EFFECTS(self, db: AsyncSession, skip: int, limit: int):
        try:
            result = await db.execute(
                select(SideEffect)
                .filter(SideEffect.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            side_effects = result.scalars().all()
            count_result = await db.execute(
                select(func.count()).filter(SideEffect.is_deleted == False)
            )
            total = len(count_result.scalars().all())
            data = [
                SideEffectResponse.from_orm(sfe).model_dump() for sfe in side_effects
            ]
            return JSONResponse(
                status_code=200,
                content={"msg": {"totalCount": total, "data": data}},
            )
        except Exception as e:
            print("-----------------------------")
            print(f"[list_all_side_effects] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [list_all_side_effects]",
            )

    async def GET_SIDE_EFFECT_BY_ID(self, db: AsyncSession, side_effect_id: int):
        try:
            result = await db.execute(
                select(SideEffect).filter(SideEffect.side_effect_id == side_effect_id)
            )
            side_effect_obj = result.scalar_one_or_none()
            if not side_effect_obj or side_effect_obj.is_deleted:
                raise HTTPException(status_code=404, detail="side effect not found")
            return side_effect_obj
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[get_side_effect_by_id] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [get_side_effect_by_id]",
            )

    async def UPDATE_SIDE_EFFECT(
        self, db: AsyncSession, side_effect_id: int, side_effect_data: SideEffectCreate
    ):
        try:
            result = await db.execute(
                select(SideEffect).filter(SideEffect.side_effect_id == side_effect_id)
            )
            side_effect_obj = result.scalar_one_or_none()
            if not side_effect_obj or side_effect_obj.is_deleted:
                raise HTTPException(status_code=404, detail="side effect not found")
            if side_effect_data.side_effect:
                dup_result = await db.execute(
                    select(SideEffect).filter(
                        SideEffect.side_effect == side_effect_data.side_effect,
                        SideEffect.side_effect_id != side_effect_id,
                    )
                )
                if dup_result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=400,
                        detail="the side effect name already exists, please provide a unique name",
                    )
                side_effect_obj.side_effect = side_effect_data.side_effect
            await db.commit()
            await db.refresh(side_effect_obj)
            return side_effect_obj
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[update_side_effect] : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [update_side_effect]"
            )

    async def SOFT_DELETE_SIDE_EFFECT(
        self, db: AsyncSession, side_effect_id: int, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(SideEffect).filter(SideEffect.side_effect_id == side_effect_id)
            )
            side_effect_obj = result.scalar_one_or_none()
            if not side_effect_obj or side_effect_obj.is_deleted:
                raise HTTPException(status_code=404, detail="side effect not found")
            side_effect_obj.is_deleted = True
            side_effect_obj.deleted_at = datetime.utcnow()
            side_effect_obj.deleted_by = deleted_by
            await db.commit()
            return JSONResponse(
                status_code=200, content={"msg": "deleted successfully"}
            )
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[soft_delete_side_effect] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [soft_delete_side_effect]",
            )

    async def CREATE_ALTERNATIVE(
        self, db: AsyncSession, alternative_data: AlternativeCreate
    ):
        try:
            result = await db.execute(
                select(Alternative).filter(Alternative.name == alternative_data.name)
            )
            existing_alternative = result.scalar_one_or_none()
            if existing_alternative:
                raise HTTPException(
                    status_code=400,
                    detail="Alternative already exists, please use a unique name.",
                )
            new_alternative = Alternative(name=alternative_data.name)
            db.add(new_alternative)
            await db.commit()
            await db.refresh(new_alternative)
            return new_alternative
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[CREATE_ALTERNATIVE] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [CREATE_ALTERNATIVE]"
            )

    async def LIST_ALL_ALTERNATIVES(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ):
        try:
            result = await db.execute(
                select(Alternative)
                .filter(Alternative.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            alternatives = result.scalars().all()
            return alternatives
        except Exception as e:
            print("-----------------------------")
            print(f"[LIST_ALL_ALTERNATIVES] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [LIST_ALL_ALTERNATIVES]"
            )

    async def GET_ALTERNATIVE_BY_ID(self, db: AsyncSession, alternative_id: int):
        try:
            result = await db.execute(
                select(Alternative).filter(
                    Alternative.alternative_id == alternative_id,
                    Alternative.is_deleted == False,
                )
            )
            alternative = result.scalar_one_or_none()
            if not alternative:
                raise HTTPException(status_code=404, detail="Alternative not found.")
            return alternative
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[GET_ALTERNATIVE_BY_ID] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [GET_ALTERNATIVE_BY_ID]"
            )

    async def UPDATE_ALTERNATIVE(
        self, db: AsyncSession, alternative_id: int, alternative_data: AlternativeCreate
    ):
        try:
            result = await db.execute(
                select(Alternative).filter(Alternative.alternative_id == alternative_id)
            )
            alternative_obj = result.scalar_one_or_none()
            if not alternative_obj:
                raise HTTPException(status_code=404, detail="Alternative not found.")
            if alternative_data.name is not None:
                alternative_obj.name = alternative_data.name
            await db.commit()
            await db.refresh(alternative_obj)
            return alternative_obj
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[UPDATE_ALTERNATIVE] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [UPDATE_ALTERNATIVE]"
            )

    async def SOFT_DELETE_ALTERNATIVE(
        self, db: AsyncSession, alternative_id: int, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(Alternative).filter(Alternative.alternative_id == alternative_id)
            )
            alternative_obj = result.scalar_one_or_none()
            if not alternative_obj:
                raise HTTPException(status_code=404, detail="Alternative not found.")
            alternative_obj.is_deleted = True
            alternative_obj.deleted_at = datetime.utcnow()
            alternative_obj.deleted_by = deleted_by
            await db.commit()
            await db.refresh(alternative_obj)
            return {"message": "Alternative deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[SOFT_DELETE_ALTERNATIVE] : {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [SOFT_DELETE_ALTERNATIVE]",
            )

    async def CREATE_GST_SLAB(self, db: AsyncSession, gst_slab_data: GSTSlabCreate):
        try:
            result = await db.execute(
                select(GSTSlab).filter(GSTSlab.hsn_code == gst_slab_data.hsn_code)
            )
            existing_slab = result.scalar_one_or_none()
            if existing_slab:
                raise HTTPException(
                    status_code=400,
                    detail="GST slab with this HSN code already exists.",
                )
            new_slab = GSTSlab(
                hsn_code=gst_slab_data.hsn_code,
                description=gst_slab_data.description,
                gst_rate=gst_slab_data.gst_rate,
                effective_from=gst_slab_data.effective_from,
            )
            db.add(new_slab)
            await db.commit()
            await db.refresh(new_slab)
            return new_slab
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[CREATE_GST_SLAB] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [CREATE_GST_SLAB]"
            )

    async def LIST_ALL_GST_SLABS(
        self, db: AsyncSession, skip: int = 0, limit: int = 10
    ):
        try:
            result = await db.execute(
                select(GSTSlab)
                .filter(GSTSlab.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            slabs = result.scalars().all()
            return slabs
        except Exception as e:
            print("-----------------------------")
            print(f"[LIST_ALL_GST_SLABS] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [LIST_ALL_GST_SLABS]"
            )

    async def GET_GST_SLAB_BY_HSN(self, db: AsyncSession, hsn_code: str):
        try:
            result = await db.execute(
                select(GSTSlab).filter(
                    GSTSlab.hsn_code == hsn_code, GSTSlab.is_deleted == False
                )
            )
            slab = result.scalar_one_or_none()
            if not slab:
                raise HTTPException(status_code=404, detail="GST slab not found.")
            return slab
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[GET_GST_SLAB_BY_HSN] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [GET_GST_SLAB_BY_HSN]"
            )

    async def UPDATE_GST_SLAB(
        self, db: AsyncSession, hsn_code: str, gst_slab_data: GSTSlabCreate
    ):
        try:
            result = await db.execute(
                select(GSTSlab).filter(GSTSlab.hsn_code == hsn_code)
            )
            slab = result.scalar_one_or_none()
            if not slab:
                raise HTTPException(status_code=404, detail="GST slab not found.")
            if gst_slab_data.description is not None:
                slab.description = gst_slab_data.description
            if gst_slab_data.gst_rate is not None:
                slab.gst_rate = gst_slab_data.gst_rate
            if gst_slab_data.effective_from is not None:
                slab.effective_from = gst_slab_data.effective_from
            await db.commit()
            await db.refresh(slab)
            return slab
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[UPDATE_GST_SLAB] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [UPDATE_GST_SLAB]"
            )

    async def SOFT_DELETE_GST_SLAB(
        self, db: AsyncSession, hsn_code: str, deleted_by: int
    ):
        try:
            result = await db.execute(
                select(GSTSlab).filter(GSTSlab.hsn_code == hsn_code)
            )
            slab = result.scalar_one_or_none()
            if not slab:
                raise HTTPException(status_code=404, detail="GST slab not found.")
            slab.is_deleted = True
            slab.deleted_at = datetime.utcnow()
            slab.deleted_by = deleted_by
            await db.commit()
            await db.refresh(slab)
            return JSONResponse(
                status_code=200, content={"msg": f"{hsn_code} deleted_by {deleted_by}"}
            )
        except HTTPException:
            raise
        except Exception as e:
            print("-----------------------------")
            print(f"[SOFT_DELETE_GST_SLAB] : {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [SOFT_DELETE_GST_SLAB]"
            )
