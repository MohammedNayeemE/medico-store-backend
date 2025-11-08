import csv
import io
import json
import os
import stat
from datetime import datetime, timedelta
from operator import or_
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from openpyxl import Workbook
from pandas.core.api import notna
from pydantic_settings.sources.providers.aws import import_aws_secrets_manager
from sqlalchemy import and_, asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload, selectinload

from app.core.database import async_session  # ✅ your async session factory
from app.core.exceptions import (
    BadRequestException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.inventory_management_models import (
    Alternative,
    Category,
    GSTSlab,
    Medicine,
    MedicineAlternative,
    MedicineBatch,
    MedicineCategory,
    MedicineImage,
    MedicineSideEffect,
    MedicineTag,
    SideEffect,
    Tag,
)
from app.models.order_management_models import OrderItem, RequestOrderItem
from app.models.user_management_models import FileAsset
from app.schemas.inventory_schemas import (
    AlternativeCreate,
    CategoryCreate,
    CategoryResponse,
    GSTSlabCreate,
    MedicineBatchCreate,
    MedicineCreate,
    MedicineImageCreate,
    SideEffectCreate,
    SideEffectResponse,
    TagCreate,
    TagResponse,
)
from app.services.cache_service import CacheService
from app.services.file_service import FileService


class InventoryManagementService:
    def __init__(self) -> None:
        self.file_manager = FileService()
        self.ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
        self.MAX_FILE_SIZE_MB = 10
        self.cache_service = CacheService()
        self.BASE_FILE_URL = "http://localhost:8000/api/file_routes/assets/"

    async def _attempt_reallocation_for_medicine(self, medicine_id: int):
        """
        Try to fulfill existing backorders for a given medicine when new stock arrives.
        Automatically reallocates available stock to backordered items.
        Runs in background (fresh DB session).
        """
        async with async_session() as db:  # ✅ create fresh session for background task
            try:
                print(
                    f"[Reallocation] Starting reallocation for medicine_id={medicine_id}"
                )
                # 1️⃣ Fetch all backordered order items for this medicine
                q = (
                    select(OrderItem)
                    .join(
                        RequestOrderItem,
                        RequestOrderItem.request_order_item_id
                        == OrderItem.request_order_item_id,
                    )
                    .filter(
                        OrderItem.is_backordered == True,
                        OrderItem.is_deleted == False,
                        RequestOrderItem.medicine_id == medicine_id,
                    )
                    .order_by(OrderItem.order_item_id.asc())  # oldest backorders first
                )
                res = await db.execute(q)
                backorders: List[OrderItem] = res.scalars().all()
                if not backorders:
                    print(
                        f"[Reallocation] No backorders found for medicine_id={medicine_id}"
                    )
                    return
                # 2️⃣ Get all available batches (including new one)
                batch_q = (
                    select(MedicineBatch)
                    .filter(
                        MedicineBatch.medicine_id == medicine_id,
                        MedicineBatch.is_deleted == False,
                        (
                            MedicineBatch.quantity
                            - func.coalesce(MedicineBatch.reserved_quantity, 0)
                        )
                        > 0,
                    )
                    .order_by(MedicineBatch.expiry_date.asc())
                    .with_for_update()
                )
                batches_res = await db.execute(batch_q)
                batches: List[MedicineBatch] = batches_res.scalars().all()
                if not batches:
                    print(
                        f"[Reallocation] No available batches for medicine_id={medicine_id}"
                    )
                    return
                # 3️⃣ Try allocating each backorder
                reallocated_count = 0
                for backorder in backorders:
                    needed = int(backorder.backordered_qty)
                    if needed <= 0:
                        continue
                    for batch in batches:
                        available = int(batch.quantity) - int(
                            batch.reserved_quantity or 0
                        )
                        if available <= 0:
                            continue
                        take = min(needed, available)
                        batch.reserved_quantity += take
                        # Convert this backorder into a reserved one
                        backorder.batch_id = batch.batch_id
                        backorder.quantity = take
                        backorder.is_backordered = False
                        backorder.backordered_qty = max(0, needed - take)
                        print(
                            f"[Reallocation] OrderItem {backorder.order_item_id} "
                            f"allocated {take} units from batch {batch.batch_id}"
                        )
                        needed -= take
                        reallocated_count += take

                        if needed <= 0:
                            break
                    # If partially fulfilled, keep remaining as backorder
                    if needed > 0:
                        backorder.backordered_qty = needed
                        backorder.is_backordered = True
                        print(
                            f"[Reallocation] OrderItem {backorder.order_item_id} "
                            f"partially fulfilled, {needed} still backordered"
                        )
                await db.commit()
                print(
                    f"[Reallocation] Completed reallocation for medicine_id={medicine_id}, "
                    f"total reallocated={reallocated_count}"
                )
            except Exception as e:
                print(f"[Reallocation Error] medicine_id={medicine_id}, error={e}")
                await db.rollback()
                raise InternalServerErrorException(
                    "internal server error : [attempt_reallocation_for_medicine]"
                )

    async def UPLOAD_MEDICINE_IMAGE(
        self,
        db: AsyncSession,
        user_id: int,
        file: UploadFile,
        bucket: AsyncIOMotorGridFSBucket,
        medicine_id: int,
    ):
        result = await self.file_manager.UPLOAD_SINGLE_FILE(
            bucket=bucket, db=db, file=file, user_id=user_id
        )
        asset_id = result["asset_id"]
        new_medicine_image = MedicineImage(
            medicine_id=medicine_id, file_asset_id=asset_id
        )
        db.add(asset_id)
        await db.commit()
        await db.refresh(new_medicine_image)
        return new_medicine_image

    async def UPLOAD_MEDICINE_IMAGES(
        self,
        db: AsyncSession,
        user_id: int,
        files: List[UploadFile],
        bucket: AsyncIOMotorGridFSBucket,
        medicine_id: int,
    ):
        try:
            result = await db.execute(
                select(Medicine.medicine_id).filter(Medicine.medicine_id == medicine_id)
            )
            medicine_obj = result.scalar_one_or_none()
            if not medicine_obj:
                raise HTTPException(status_code=404, detail="medicine id not found")
            asset_ids = await self.file_manager.UPLOAD_MULTIPLE_FILES(
                bucket=bucket, files=files, db=db, user_id=user_id
            )
            for items in asset_ids["data"]:
                new_medicine_image = MedicineImage(
                    medicine_id=medicine_id, file_asset_id=items["asset_id"]
                )
                db.add(new_medicine_image)
            await db.commit()
            return {"msg": "all the images are added"}
        except HTTPException:
            raise
        except Exception as e:
            print("--------------------------")
            print(f"[upload_medicine_images] : {e}")
            raise HTTPException(status_code=500)

    async def DOWNLOAD_TEMPLATE(self):
        try:
            headers = [
                "medicine_name",
                "generic_name",
                "manufacturer",
                "description",
                "is_prescribed",
                "weight",
                "hsn_code",
                "category_names",
                "tag_names",
                "side_effect_names",
                "alternative_names",
            ]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerow(
                [
                    "Paracetamol",
                    "Acetaminophen",
                    "Cipla",
                    "Pain relief",
                    "False",
                    "500",
                    "30049099",
                    "5,6",
                    "3",
                    "7",
                ]
            )
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=medicine_template.csv"
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------")
            print(f"DOWNLOAD_TEMPLATE : {e}")
            raise HTTPException(
                status_code=500, detail="internal server error : [DOWNLOAD_TEMPLATE]"
            )

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

    async def BULK_UPLOAD_MEDICINES(self, db: AsyncSession, file: UploadFile):
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}",
                )
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            try:
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse the file: {str(e)}",
                )
            required_columns = [
                "medicine_name",
                "generic_name",
                "manufacturer",
                "description",
                "is_prescribed",
                "weight",
                "hsn_code",
            ]
            missing_cols = [c for c in required_columns if c not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required columns: {', '.join(missing_cols)}",
                )
            inserted, errors = [], []
            for index, row in df.iterrows():
                try:
                    med = Medicine(
                        medicine_name=row["medicine_name"],
                        generic_name=row["generic_name"],
                        manufacturer=row["manufacturer"],
                        description=row["description"],
                        is_prescribed=bool(row["is_prescribed"]),
                        weight=row["weight"],
                        hsn_code=str(row["hsn_code"]),
                    )
                    db.add(med)
                    await db.flush()

                    def safe_split(value):
                        return [
                            int(v.strip()) for v in str(value).split(",") if v.strip()
                        ]

                    if pd.notna(row.get("category_ids")):
                        for cat_id in safe_split(row["category_ids"]):
                            db.add(
                                MedicineCategory(
                                    medicine_id=med.medicine_id, category_id=cat_id
                                )
                            )
                    if pd.notna(row.get("tags_ids")):
                        for tag_id in safe_split(row["tags_ids"]):
                            db.add(
                                MedicineTag(medicine_id=med.medicine_id, tag_id=tag_id)
                            )
                    if pd.notna(row.get("alternative_ids")):
                        for alt_id in safe_split(row["alternative_ids"]):
                            db.add(
                                MedicineAlternative(
                                    medicine_id=med.medicine_id, alternative_id=alt_id
                                )
                            )
                    if pd.notna(row.get("side_effect_ids")):
                        for sf_id in safe_split(row["side_effect_ids"]):
                            db.add(
                                MedicineSideEffect(
                                    medicine_id=med.medicine_id, side_effect_id=sf_id
                                )
                            )
                    inserted.append(row["medicine_name"])
                except Exception as e:
                    errors.append({"row": index, "error": str(e)})
            await db.commit()
            return {
                "msg": f"{len(inserted)} medicines uploaded successfully",
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------------")
            print(f"[bulk_upload_medicines] : {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def GET_MEDICINES(
        self,
        db: AsyncSession,
        name: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 10,
    ):
        try:
            cache_key = (
                f"medicines:{name}:{category}:{tag}:{min_price}:{max_price}:"
                f"{sort_by}:{sort_order}:{skip}:{limit}"
            )
            cached_data = await self.cache_service.get_cache(cache_key)
            if cached_data:
                print("cache-hit")
                return cached_data
            Batch = aliased(MedicineBatch)
            batch_subq = (
                select(
                    Batch.medicine_id,
                    Batch.selling_price,
                    Batch.quantity,
                    Batch.expiry_date,
                )
                .where(
                    Batch.medicine_id == Medicine.medicine_id,
                    Batch.is_deleted == False,
                )
                .order_by(
                    Batch.expiry_date.asc()
                )  # or Batch.created_at.desc() for latest batch
                .limit(1)
                .correlate(Medicine)
                .subquery()
            )
            query = (
                select(
                    Medicine,
                    batch_subq.c.selling_price,
                    batch_subq.c.quantity,
                    batch_subq.c.expiry_date,
                )
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
            if min_price is not None:
                query = query.where(batch_subq.c.selling_price >= min_price)
            if max_price is not None:
                query = query.where(batch_subq.c.selling_price <= max_price)
            valid_sort_columns = {
                "name": Medicine.medicine_name,
                "created_at": Medicine.created_at,
                "updated_at": Medicine.updated_at,
                "price": batch_subq.c.selling_price,
            }
            if sort_by:
                if sort_by not in valid_sort_columns:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid sort_by field: {sort_by}",
                    )
                sort_column = valid_sort_columns[sort_by]
                query = query.order_by(
                    desc(sort_column)
                    if sort_order.lower() == "desc"
                    else asc(sort_column)
                )
            else:
                query = query.order_by(asc(Medicine.medicine_name))
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            rows = result.all()
            response = [self._serialize_medicine(row) for row in rows]
            await self.cache_service.set_cache(cache_key, response)
            return response
        except HTTPException:
            raise
        except Exception as e:
            print(f"[GET_MEDICINES ERROR]: {e}")
            raise HTTPException(
                status_code=500, detail="Internal server error: [get_medicines]"
            )

    def _serialize_medicine(self, row):
        """Serialize Medicine + batch info into frontend-friendly dict"""
        medicine, selling_price, quantity, expiry_date = row
        thumbnail_url = f"{self.BASE_FILE_URL}/{medicine.image_asset_id if medicine.image_asset_id else -1}"
        low_stock: bool = True if int(quantity) < 50 else False
        return {
            "medicine_id": medicine.medicine_id,
            "medicine_name": medicine.medicine_name,
            "generic_name": medicine.generic_name,
            "description": medicine.description,
            "weight": float(medicine.weight) if medicine.weight else None,
            "selling_price": float(selling_price) if selling_price else None,
            "islowStock": low_stock,
            "expiry_date": str(expiry_date) if expiry_date else None,
            "thumbnail_url": thumbnail_url,
            "categories": [c.category_name for c in medicine.categories],
            "tags": [t.name for t in medicine.tags],
            "side_effects": [s.side_effect for s in medicine.side_effects],
            "alternatives": [a.name for a in medicine.alternatives],
            "created_at": str(medicine.created_at),
            "is_prescribed": medicine.is_prescribed,
            "updated_at": str(medicine.updated_at),
            "gst_slab": (
                float(medicine.gst_slab.gst_rate) if medicine.gst_slab else None
            ),
        }

    async def GET_MEDICINE_BY_ID(self, db: AsyncSession, medicine_id: int):
        try:
            cache_key = f"medicine_details:{medicine_id}"
            cached_data = await self.cache_service.get_cache(cache_key)
            if cached_data:
                print(f"Cache hit for medicine {medicine_id}")
                return cached_data
            query = (
                select(Medicine)
                .options(
                    joinedload(Medicine.images).joinedload(
                        MedicineImage.file_asset
                    ),  # Gallery
                    joinedload(Medicine.categories),
                    joinedload(Medicine.tags),
                    joinedload(Medicine.side_effects),
                    joinedload(Medicine.alternatives),
                    joinedload(Medicine.gst_slab),
                    joinedload(Medicine.batches),  # All batches
                )
                .where(
                    Medicine.medicine_id == medicine_id, Medicine.is_deleted == False
                )
            )
            result = await db.execute(query)
            medicine = result.scalar_one_or_none()
            if not medicine:
                raise HTTPException(status_code=404, detail="Medicine not found")
            response = self._serialize_medicine_details(medicine)
            await self.cache_service.set_cache(cache_key, response)
            return response
        except HTTPException:
            raise
        except Exception as e:
            print(f"[GET_MEDICINE_DETAILS ERROR]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [get_medicine_details]",
            )

    def _serialize_medicine_details(self, medicine: Medicine):
        thumbnail_url = f"{self.BASE_FILE_URL}/{medicine.image_asset_id if medicine.image_asset_id else -1}"
        gallery_images = [
            {
                "asset_id": img.file_asset_id,
                "url": f"{self.BASE_FILE_URL}/{img.file_asset_id}",
            }
            for img in medicine.images
        ]
        batches = [
            {
                "batch_id": b.batch_id,
                "batch_number": b.batch_number,
                "expiry_date": str(b.expiry_date),
                "quantity": b.quantity,
                "purchase_price": float(b.purchase_price),
                "selling_price": float(b.selling_price),
                "created_at": str(b.created_at),
            }
            for b in sorted(
                medicine.batches,
                key=lambda x: x.expiry_date or x.created_at,
            )
            if not b.is_deleted
        ]
        return {
            "medicine_id": medicine.medicine_id,
            "medicine_name": medicine.medicine_name,
            "generic_name": medicine.generic_name,
            "manufacturer": medicine.manufacturer,
            "description": medicine.description,
            "weight": float(medicine.weight) if medicine.weight else None,
            "thumbnail_url": thumbnail_url,
            "gallery_images": gallery_images,
            "is_prescribed": medicine.is_prescribed,
            "batches": batches,
            "categories": [c.category_name for c in medicine.categories],
            "tags": [t.name for t in medicine.tags],
            "side_effects": [s.side_effect for s in medicine.side_effects],
            "alternatives": [a.name for a in medicine.alternatives],
            "gst_slab": (
                float(medicine.gst_slab.gst_rate) if medicine.gst_slab else None
            ),
            "created_at": str(medicine.created_at),
            "updated_at": str(medicine.updated_at),
        }

    async def GET_CUSTOMER_MEDICINE_DETAILS(self, db: AsyncSession, medicine_id: int):
        """
        Fetch medicine details without heavy joins (batches, gst_slabs).
        Includes categories, tags, side effects, alternatives, and images.
        """
        try:
            cache_key = f"medicine_details_semi:{medicine_id}"
            cached_data = await self.cache_service.get_cache(cache_key)
            if cached_data:
                print(f"[Cache] Hit for light medicine details {medicine_id}")
                return cached_data
            query = (
                select(Medicine)
                .options(
                    joinedload(Medicine.images).joinedload(MedicineImage.file_asset),
                    joinedload(Medicine.categories),
                    joinedload(Medicine.tags),
                    joinedload(Medicine.side_effects),
                    joinedload(Medicine.alternatives),
                )
                .where(
                    Medicine.medicine_id == medicine_id,
                    Medicine.is_deleted == False,
                )
            )
            result = await db.execute(query)
            medicine = result.scalar_one_or_none()
            if not medicine:
                raise HTTPException(status_code=404, detail="Medicine not found")
            response = self._serialize_medicine_semi(medicine)
            await self.cache_service.set_cache(cache_key, response)
            return response
        except HTTPException:
            raise
        except Exception as e:
            print(f"[GET_MEDICINE_DETAILS_LIGHT ERROR]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [get_medicine_details_light]",
            )

    def _serialize_medicine_semi(self, medicine: Medicine) -> dict:
        """
        Serialize a Medicine object without batches and gst_slab.
        """
        return {
            "medicine_id": medicine.medicine_id,
            "medicine_name": medicine.medicine_name,
            "generic_name": medicine.generic_name,
            "manufacturer": medicine.manufacturer,
            "description": medicine.description,
            "is_prescribed": medicine.is_prescribed,
            "weight": float(medicine.weight),
            "hsn_code": medicine.hsn_code,
            "image_urls": [
                img.file_asset.file_url
                for img in (medicine.images or [])
                if getattr(img, "file_asset", None)
            ],
            "categories": [
                {"id": c.category_id, "name": c.category_name}
                for c in (medicine.categories or [])
            ],
            "tags": [{"id": t.tag_id, "name": t.name} for t in (medicine.tags or [])],
            "side_effects": [
                {"id": s.side_effect_id, "name": s.side_effect}
                for s in (medicine.side_effects or [])
            ],
            "alternatives": [
                {"id": a.alternative_id} for a in (medicine.alternatives or [])
            ],
        }

    async def GET_LIGHT_MEDICINES(
        self, db: AsyncSession, skip: int = 0, limit: int = 20
    ):
        try:
            cache_key = f"light_medicines:{skip}:{limit}"
            cached_data = await self.cache_service.get_cache(cache_key)
            if cached_data:
                print("cache-hit: [light_medicines]")
                return cached_data
            Batch = aliased(MedicineBatch)
            batch_subq = (
                select(Batch.medicine_id, Batch.selling_price)
                .where(
                    Batch.medicine_id == Medicine.medicine_id,
                    Batch.is_deleted == False,
                )
                .order_by(Batch.expiry_date.asc())  # nearest expiry
                .limit(1)
                .correlate(Medicine)
                .subquery()
            )
            query = (
                select(
                    Medicine,
                    batch_subq.c.selling_price,
                )
                .options(joinedload(Medicine.image).joinedload(FileAsset))
                .where(Medicine.is_deleted == False)
                .order_by(Medicine.medicine_name.asc())
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(query)
            rows = result.all()
            response = [self._serialize_light_medicine(row) for row in rows]
            await self.cache_service.set_cache(cache_key, response)
            return response
        except Exception as e:
            print(f"[GET_LIGHT_MEDICINES ERROR]: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: [get_light_medicines]",
            )

    def _serialize_light_medicine(self, row):
        medicine, selling_price = row
        thumbnail_url = (
            f"{self.BASE_FILE_URL}/{medicine.image_asset_id}"
            if medicine.image_asset_id
            else -1
        )
        return {
            "medicine_id": medicine.medicine_id,
            "medicine_name": medicine.medicine_name,
            "generic_name": medicine.generic_name,
            "thumbnail_url": thumbnail_url,
            "selling_price": float(selling_price) if selling_price else None,
        }

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

    async def LINK_MEDICINE_ALTERNATIVES(
        self, db: AsyncSession, medicine_id: int, alternative_IDS: AlternativeCreate
    ):
        try:
            medicine_q = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == medicine_id, Medicine.is_deleted == False
                )
            )
            medicine_obj = medicine_q.scalars().first()
            if not medicine_obj:
                raise HTTPException(status_code=404, detail="Medicine not found")
            if len(alternative_IDS.medicine_alternative_ids) == 0:
                raise BadRequestException("no alternative_ids provided")
            alternative_ids: List[int] = alternative_IDS.medicine_alternative_ids
            valid_meds_q = await db.execute(
                select(Medicine.medicine_id).filter(
                    Medicine.medicine_id.in_(alternative_ids),
                    Medicine.is_deleted == False,
                )
            )
            valid_medicine_ids = set(valid_meds_q.scalars().all())
            invalid_ids = set(alternative_ids) - valid_medicine_ids
            if invalid_ids:
                raise BadRequestException(
                    f"Invalid medicine IDs in alternatives: {list(invalid_ids)}"
                )
            if medicine_id in valid_medicine_ids:
                valid_medicine_ids.remove(medicine_id)  # cannot link medicine to itself
            if not valid_medicine_ids:
                raise BadRequestException(
                    "All provided alternative IDs are invalid or same as medicine_id"
                )
            for alt_medicine_id in valid_medicine_ids:
                existing_alt_q = await db.execute(
                    select(Alternative).filter(
                        Alternative.name == f"ALT-{alt_medicine_id}",
                        Alternative.is_deleted == False,
                    )
                )
                alternative = existing_alt_q.scalars().first()
                if not alternative:
                    alternative = Alternative(name=f"ALT-{alt_medicine_id}")
                    db.add(alternative)
                    await db.flush()
                link_q = await db.execute(
                    select(MedicineAlternative).filter(
                        and_(
                            MedicineAlternative.medicine_id == medicine_id,
                            MedicineAlternative.alternative_id
                            == alternative.alternative_id,
                            MedicineAlternative.is_deleted == False,
                        )
                    )
                )
                existing_link = link_q.scalars().first()
                if not existing_link:
                    db.add(
                        MedicineAlternative(
                            medicine_id=medicine_id,
                            alternative_id=alternative.alternative_id,
                        )
                    )
            await db.commit()
            return {
                "message": "Alternatives linked successfully",
                "linked_medicine_id": medicine_id,
                "alternative_ids": list(valid_medicine_ids),
            }
        except (BadRequestException, NotFoundException):
            raise
        except Exception as e:
            await db.rollback()
            print("---------------------")
            print(f"[link_medicine_alternatives] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [link_medicine_alternatives]",
            )

    async def LIST_ALL_MEDICINE_ALTERNATIVES(self, db: AsyncSession, medicine_id: int):
        try:
            medicine_q = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == medicine_id, Medicine.is_deleted == False
                )
            )
            medicine = medicine_q.scalars().first()
            if not medicine:
                raise NotFoundException("medicine_id not found")
            await db.refresh(medicine)
            alternatives = medicine.alternatives
            active_alternatives = [
                {"alternative_id": alt.alternative_id, "name": alt.name}
                for alt in alternatives
                if not alt.is_deleted
            ]
            return {
                "medicine_id": medicine.medicine_id,
                "medicine_name": medicine.medicine_name,
                "alternatives": active_alternatives,
                "count": len(active_alternatives),
            }
        except NotFoundException:
            raise
        except Exception as e:
            print("---------------------")
            print(f"[list_all_medicine_alternatives] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [list_all_medicine_alternatives]",
            )

    async def UPDATE_LINK_MEDICINES_TO_ALTERNATIVES(
        self,
        db: AsyncSession,
        alternative_ids: List[int],
        medicine_id: int,
        deleted_by: int,
    ):
        try:
            med_q = await db.execute(
                select(Medicine).filter(
                    Medicine.medicine_id == medicine_id,
                    Medicine.is_deleted == False,
                )
            )
            medicine = med_q.scalars().first()
            if not medicine:
                raise HTTPException(status_code=404, detail="Medicine not found")
            if not alternative_ids:
                raise HTTPException(
                    status_code=400, detail="No alternative IDs provided"
                )
            valid_meds_q = await db.execute(
                select(Medicine.medicine_id).filter(
                    Medicine.medicine_id.in_(alternative_ids),
                    Medicine.is_deleted == False,
                )
            )
            valid_medicine_ids = set(valid_meds_q.scalars().all())
            invalid_ids = set(alternative_ids) - valid_medicine_ids
            if invalid_ids:
                raise BadRequestException("Invalid medicine IDs: {list(invalid_ids)}")
            if medicine_id in valid_medicine_ids:
                valid_medicine_ids.remove(medicine_id)  # cannot link medicine to itself
            if not valid_medicine_ids:
                raise BadRequestException("No valid alternative medicine IDs provided")
            await db.execute(
                update(MedicineAlternative)
                .where(
                    MedicineAlternative.medicine_id == medicine_id,
                    MedicineAlternative.is_deleted == False,
                )
                .values(
                    is_deleted=True,
                    deleted_at=datetime.utcnow(),
                    deleted_by=deleted_by,
                )
            )
            for alt_medicine_id in valid_medicine_ids:
                existing_alt_q = await db.execute(
                    select(Alternative).filter(
                        Alternative.name == f"ALT-{alt_medicine_id}",
                        Alternative.is_deleted == False,
                    )
                )
                alternative = existing_alt_q.scalars().first()
                if not alternative:
                    alternative = Alternative(name=f"ALT-{alt_medicine_id}")
                    db.add(alternative)
                    await db.flush()
                db.add(
                    MedicineAlternative(
                        medicine_id=medicine_id,
                        alternative_id=alternative.alternative_id,
                    )
                )
            await db.commit()
            return {
                "message": "Medicine alternatives updated successfully",
                "medicine_id": medicine_id,
                "new_alternatives": list(valid_medicine_ids),
                "count": len(valid_medicine_ids),
            }
        except BadRequestException:
            raise
        except Exception as e:
            await db.rollback()
            print("---------------------")
            print(f"[update_link_medicines_to_alternatives] : {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [update_link_medicines_to_alternatives]",
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
        self,
        db: AsyncSession,
        batch_data: MedicineBatchCreate,
        background_tasks: BackgroundTasks,
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
            await db.flush()
            await db.commit()
            await db.refresh(new_batch)
            background_tasks.add_task(
                self._attempt_reallocation_for_medicine, medicine_id
            )
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

    async def GET_LOW_STOCK_ITEMS(
        self, db: AsyncSession, threshold: int, skip: int, limit: int
    ):
        """
        Get medicine batches where available stock (quantity - reserved_quantity)
        is less than or equal to the given threshold.
        """
        try:
            print(f"[Inventory] Fetching low-stock batches (threshold={threshold})")
            q = (
                select(MedicineBatch)
                .filter(
                    MedicineBatch.is_deleted == False,
                    (
                        MedicineBatch.quantity
                        - func.coalesce(MedicineBatch.reserved_quantity, 0)
                    )
                    <= threshold,
                )
                .order_by(MedicineBatch.expiry_date.asc())
                .offset(skip)
                .limit(limit)
            )
            res = await db.execute(q)
            batches = res.scalars().all()
            print(f"[Inventory] Found {len(batches)} low-stock batches")
            return batches
        except Exception as e:
            print(f"[Inventory Error] GET_LOW_STOCK_ITEMS failed: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [GET_LOW_STOCK_ITEMS]"
            )

    # ----------------------------------------------------------------------
    async def GET_EXPIRED_BATCHES(self, db: AsyncSession, skip: int, limit: int):
        """
        Get expired medicine batches (expiry_date < today).
        """
        try:
            today = datetime.now().date()
            print(f"[Inventory] Fetching expired batches before {today}")
            q = (
                select(MedicineBatch)
                .filter(
                    MedicineBatch.is_deleted == False,
                    MedicineBatch.expiry_date < today,
                )
                .order_by(MedicineBatch.expiry_date.asc())
                .offset(skip)
                .limit(limit)
            )
            res = await db.execute(q)
            batches = res.scalars().all()
            print(f"[Inventory] Found {len(batches)} expired batches")
            return batches
        except Exception as e:
            print(f"[Inventory Error] GET_EXPIRED_BATCHES failed: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [GET_EXPIRED_BATCHES]"
            )

    # ----------------------------------------------------------------------
    async def GET_EXPIRING_SOON(
        self, db: AsyncSession, days: int, skip: int, limit: int
    ):
        """
        Get medicine batches expiring within the next N days.
        """
        try:
            cutoff = datetime.now().date() + timedelta(days=days)
            print(f"[Inventory] Fetching batches expiring before {cutoff}")
            q = (
                select(MedicineBatch)
                .filter(
                    MedicineBatch.is_deleted == False,
                    MedicineBatch.expiry_date <= cutoff,
                )
                .order_by(MedicineBatch.expiry_date.asc())
                .offset(skip)
                .limit(limit)
            )
            res = await db.execute(q)
            batches = res.scalars().all()
            print(
                f"[Inventory] Found {len(batches)} batches expiring within {days} days"
            )
            return batches
        except Exception as e:
            print(f"[Inventory Error] GET_EXPIRING_SOON failed: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [GET_EXPIRING_SOON]"
            )

    # ----------------------------------------------------------------------
    async def GET_STOCK_SUMMARY(self, db: AsyncSession, skip: int, limit: int):
        """
        Get total available stock per medicine (quantity - reserved_quantity),
        aggregated across all batches.
        """
        try:
            print("[Inventory] Fetching stock summary (paginated)")

            q = (
                select(
                    Medicine.medicine_id,
                    Medicine.medicine_name,
                    func.sum(
                        MedicineBatch.quantity
                        - func.coalesce(MedicineBatch.reserved_quantity, 0)
                    ).label("available_stock"),
                )
                .join(MedicineBatch, Medicine.medicine_id == MedicineBatch.medicine_id)
                .filter(MedicineBatch.is_deleted == False)
                .group_by(Medicine.medicine_id, Medicine.medicine_name)
                .order_by(Medicine.medicine_name.asc())
                .offset(skip)
                .limit(limit)
            )

            res = await db.execute(q)
            summary = res.mappings().all()

            print(f"[Inventory] Retrieved {len(summary)} stock summary records")
            return summary

        except Exception as e:
            print(f"[Inventory Error] GET_STOCK_SUMMARY failed: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [GET_STOCK_SUMMARY]"
            )

    async def DOWNLOAD_CATEGORY_TEMPLATE(self):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Category Template"
            headers = ["category_name"]
            example_row = ["Pain Relief"]
            ws.append(headers)
            ws.append(example_row)
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": "attachment; filename=category_template.xlsx"
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("===================================")
            print(f"[DOWNLOAD_TEMPLATE - Category] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [DOWNLOAD_TEMPLATE - Category]",
            )

    async def BULK_UPLOAD_CATEGORIES(self, db: AsyncSession, file: UploadFile):
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
                )
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            try:
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse the file: {str(e)}",
                )
            required_columns = ["category_name"]
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column(s): {', '.join(missing_cols)}",
                )
            inserted, errors = [], []
            for index, row in df.iterrows():
                try:
                    category_name = str(row["category_name"]).strip()
                    if not category_name or pd.isna(category_name):
                        continue
                    existing = await db.execute(
                        select(Category).filter(Category.category_name == category_name)
                    )
                    if existing.scalar_one_or_none():
                        errors.append(
                            {
                                "row": index + 1,
                                "error": f"Category '{category_name}' already exists",
                            }
                        )
                        continue
                    new_category = Category(category_name=category_name)
                    db.add(new_category)
                    inserted.append(category_name)
                except Exception as e:
                    errors.append({"row": index + 1, "error": str(e)})
            await db.commit()
            return {
                "message": f"{len(inserted)} categories uploaded successfully",
                "inserted": inserted,
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------------")
            print(f"[BULK_UPLOAD_CATEGORIES] : {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

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

    async def DOWNLOAD_TAG_TEMPLATE(self):
        try:
            headers = ["name"]
            example_row = ["Antibiotic"]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerow(example_row)
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=tag_template.csv"
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("===================================")
            print(f"[DOWNLOAD_TAG_TEMPLATE] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [DOWNLOAD_TAG_TEMPLATE]",
            )

    async def BULK_UPLOAD_TAGS(self, db: AsyncSession, file: UploadFile):
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
                )
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            try:
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse the file: {str(e)}",
                )
            required_columns = ["name"]
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column(s): {', '.join(missing_cols)}",
                )
            inserted, errors = [], []
            for index, row in df.iterrows():
                try:
                    tag_name = str(row["name"]).strip()
                    if not tag_name or pd.isna(tag_name):
                        continue
                    existing = await db.execute(
                        select(Tag).filter(Tag.name == tag_name)
                    )
                    if existing.scalar_one_or_none():
                        errors.append(
                            {
                                "row": index + 1,
                                "error": f"Tag '{tag_name}' already exists",
                            }
                        )
                        continue
                    new_tag = Tag(name=tag_name)
                    db.add(new_tag)
                    inserted.append(tag_name)
                except Exception as e:
                    errors.append({"row": index + 1, "error": str(e)})
            await db.commit()
            return {
                "message": f"{len(inserted)} tags uploaded successfully",
                "inserted": inserted,
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------------")
            print(f"[BULK_UPLOAD_TAGS] : {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def DOWNLOAD_SIDE_EFFECT_TEMPLATE(self):
        try:
            headers = ["side_effect"]
            example_row = ["Nausea"]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerow(example_row)
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=side_effect_template.csv"
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("===================================")
            print(f"[DOWNLOAD_SIDE_EFFECT_TEMPLATE] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [DOWNLOAD_SIDE_EFFECT_TEMPLATE]",
            )

    async def BULK_UPLOAD_SIDE_EFFECTS(self, db: AsyncSession, file: UploadFile):
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
                )
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            try:
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse the file: {str(e)}",
                )
            required_columns = ["side_effect"]
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column(s): {', '.join(missing_cols)}",
                )
            inserted, errors = [], []
            for index, row in df.iterrows():
                try:
                    side_effect_name = str(row["side_effect"]).strip()
                    if not side_effect_name or pd.isna(side_effect_name):
                        continue
                    existing = await db.execute(
                        select(SideEffect).filter(
                            SideEffect.side_effect == side_effect_name
                        )
                    )
                    if existing.scalar_one_or_none():
                        errors.append(
                            {
                                "row": index + 1,
                                "error": f"Side effect '{side_effect_name}' already exists",
                            }
                        )
                        continue
                    new_side_effect = SideEffect(side_effect=side_effect_name)
                    db.add(new_side_effect)
                    inserted.append(side_effect_name)
                except Exception as e:
                    errors.append({"row": index + 1, "error": str(e)})
            await db.commit()
            return {
                "message": f"{len(inserted)} side effects uploaded successfully",
                "inserted": inserted,
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------------")
            print(f"[BULK_UPLOAD_SIDE_EFFECTS] : {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def DOWNLOAD_GST_SLAB_TEMPLATE(self):
        try:
            headers = ["hsn_code", "description", "gst_rate", "effective_from"]
            example_row = [
                "30049099",
                "Medicinal products",
                "12.00",
                "2024-01-01",
            ]
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerow(example_row)
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=gst_slab_template.csv"
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            print("===================================")
            print(f"[DOWNLOAD_GST_SLAB_TEMPLATE] Error: {e}")
            raise HTTPException(
                status_code=500,
                detail="internal server error : [DOWNLOAD_GST_SLAB_TEMPLATE]",
            )

    async def BULK_UPLOAD_GST_SLABS(self, db: AsyncSession, file: UploadFile):
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}",
                )
            file_content = await file.read()
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max allowed size is {self.MAX_FILE_SIZE_MB} MB.",
                )
            try:
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content))
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse the file: {str(e)}",
                )
            required_columns = ["hsn_code", "description", "gst_rate", "effective_from"]
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column(s): {', '.join(missing_cols)}",
                )
            inserted, errors = [], []
            for index, row in df.iterrows():
                try:
                    hsn_code = str(row["hsn_code"]).strip()
                    description = (
                        str(row["description"]).strip()
                        if pd.notna(row.get("description"))
                        else ""
                    )
                    gst_rate = (
                        float(row["gst_rate"]) if pd.notna(row.get("gst_rate")) else 0.0
                    )
                    effective_from_str = str(row["effective_from"]).strip()
                    if not hsn_code or pd.isna(hsn_code):
                        errors.append(
                            {"row": index + 1, "error": "HSN code is required"}
                        )
                        continue
                    # Parse date
                    try:
                        effective_from = pd.to_datetime(effective_from_str).date()
                    except:
                        errors.append(
                            {
                                "row": index + 1,
                                "error": f"Invalid date format: {effective_from_str}",
                            }
                        )
                        continue
                    existing = await db.execute(
                        select(GSTSlab).filter(GSTSlab.hsn_code == hsn_code)
                    )
                    if existing.scalar_one_or_none():
                        errors.append(
                            {
                                "row": index + 1,
                                "error": f"GST slab with HSN code '{hsn_code}' already exists",
                            }
                        )
                        continue
                    new_gst_slab = GSTSlab(
                        hsn_code=hsn_code,
                        description=description,
                        gst_rate=gst_rate,
                        effective_from=effective_from,
                    )
                    db.add(new_gst_slab)
                    inserted.append(hsn_code)
                except Exception as e:
                    errors.append({"row": index + 1, "error": str(e)})
            await db.commit()
            return {
                "message": f"{len(inserted)} GST slabs uploaded successfully",
                "inserted": inserted,
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as e:
            print("-------------------------------------------")
            print(f"[BULK_UPLOAD_GST_SLABS] : {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
