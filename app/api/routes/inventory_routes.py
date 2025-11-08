from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Path, Query, Security, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user, oauth2_scheme
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.user_management_models import User
from app.schemas.inventory_schemas import (
    AlternativeCreate,
    CategoryCreate,
    GSTSlabCreate,
    MedicineBatchCreate,
    MedicineCreate,
    SideEffectCreate,
    TagCreate,
)
from app.services.file_service import FileService
from app.services.inventory_service import InventoryManagementService

router = APIRouter(prefix="/inventory", tags=["Inventory"])
inventory_manager = InventoryManagementService()
file_manager = FileService()

medicine_router = APIRouter(prefix="/medicines", tags=["Medicines"])
category_router = APIRouter(prefix="/categories", tags=["Categories"])
tags_router = APIRouter(prefix="/tags", tags=["Tags"])
alternates_router = APIRouter(prefix="/alternatives", tags=["Medicine Alternatives"])
batches_router = APIRouter(prefix="/batches", tags=["Medicine Batches"])
side_effects_router = APIRouter(prefix="/side-effects", tags=["Medicine SideEffects"])
gst_router = APIRouter(prefix="/gst-slabs", tags=["GST Slabs"])


@router.get("/dev", description="Health check endpoint for Inventory routes")
async def get_root_dev():
    return JSONResponse(status_code=200, content={"msg": "this route is working"})


@medicine_router.post(
    "/upload-thumbnail-image/{medicine_id}",
    description="Upload a single medicine image",
)
async def upload_thumbnail_image(
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    file: UploadFile = File(...),
    medicine_id: int = Path(...),
):
    result = await inventory_manager.UPLOAD_MEDICINE_IMAGE(
        db=db,
        user_id=current_user.user_id,
        file=file,
        bucket=bucket,
        medicine_id=medicine_id,
    )
    return result


@medicine_router.post(
    "/upload-mulitple-images/{medicine_id}",
    description="Upload Multiple Images for the medicine",
)
async def upload_mulitple_images(
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    files: List[UploadFile] = File(...),
    medicine_id: int = Path(...),
):
    result = await inventory_manager.UPLOAD_MEDICINE_IMAGES(
        db=db,
        user_id=current_user.user_id,
        bucket=bucket,
        files=files,
        medicine_id=medicine_id,
    )
    return result


@medicine_router.get("/download-template", description="download the medicine template")
async def download_template():
    result = await inventory_manager.DOWNLOAD_TEMPLATE()
    return result


@medicine_router.post("/create", description="Create a new medicine entry")
async def create_medicine(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: MedicineCreate = Body(...),
):
    result = await inventory_manager.CREATE_MEDICINE(db=db, medicine_data=medicine_data)
    return result


@medicine_router.post(
    "/bulk-upload-medicines", description="Bulk upload the medicine data"
)
async def bulk_upload_medicine(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: UploadFile = File(...),
):
    result = await inventory_manager.BULK_UPLOAD_MEDICINES(db=db, file=medicine_data)
    return result


@medicine_router.get(
    "/",
    description="List medicines with optional filters and pagination for the shopping page",
)
async def get_all_medicines(
    db: AsyncSession = Depends(get_postgres),
    search: Optional[str] = Query(None, description="Search by name or description"),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: Optional[str] = Query("name", description="Sort by 'price' or 'name'"),
    order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_MEDICINES(
        db=db,
        name=search,
        category=category,
        tag=tag,
        sort_by=sort_by,
        sort_order=order,
        skip=skip,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
    )
    return result


@medicine_router.get(
    "/light", description="List all the medicines with minimal data to optimise the api"
)
async def get_all_light_medicines(
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
):
    result = await inventory_manager.GET_LIGHT_MEDICINES(db=db, skip=skip, limit=limit)
    return result


@medicine_router.get(
    "/{medicine_id}", description="Get details of a specific medicine by ID"
)
async def get_medicine_details(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_MEDICINE_BY_ID(db=db, medicine_id=medicine_id)
    return result


@medicine_router.put("/{medicine_id}", description="Update an existing medicine by ID")
async def update_medicine(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    medicine_data: MedicineCreate = Body(...),
):
    result = await inventory_manager.UPDATE_MEDICINE(
        db=db, medicine_id=medicine_id, medicine_data=medicine_data
    )
    return result


@medicine_router.delete("/{medicine_id}", description="Soft delete a medicine by ID")
async def soft_delete_medicine(
    medicine_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_MEDICINE(
        db=db, medicine_id=medicine_id, deleted_by=current_user.user_id
    )
    return result


@medicine_router.get(
    "/customer/medicines",
    description="List all available medicines with search, filters, and pagination",
)
async def list_medicines_for_customer(
    db: AsyncSession = Depends(get_postgres),
    search: Optional[str] = Query(None, description="Search by name or description"),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: Optional[str] = Query("name", description="Sort by 'price' or 'name'"),
    order: Optional[str] = Query("asc", description="Sort order: 'asc' or 'desc'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_AVAILABLE_MEDICINES_FOR_CUSTOMER(
        db=db,
        name=search,
        category=category,
        tag=tag,
        sort_by=sort_by,
        sort_order=order,
        skip=skip,
        limit=limit,
    )
    return result


@medicine_router.get(
    "/customer/medicines/{medicine_id}",
    description="Get detailed information about a specific medicine",
)
async def get_medicine_details_for_customer(
    db: AsyncSession = Depends(get_postgres),
    medicine_id: int = Path(...),
):
    pass
    # result = await inventory_manager.GET_MEDICINE_DETAILS_FOR_CUSTOMER(
    #     db=db, medicine_id=medicine_id
    # )
    # return result


@medicine_router.get(
    "/customer/medicines/{medicine_id}/related",
    description="Fetch related or similar medicines based on category or tags",
)
async def get_related_medicines(
    db: AsyncSession = Depends(get_postgres),
    medicine_id: int = Path(...),
):
    pass
    # result = await inventory_manager.GET_RELATED_MEDICINES(
    #     db=db, medicine_id=medicine_id
    # )
    # return result


@category_router.post("/", description="Create a new category")
async def create_category(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    category_data: CategoryCreate = Body(...),
):
    result = await inventory_manager.CREATE_CATEGORY(db=db, category_data=category_data)
    return result


@category_router.get("/", description="List all categories with pagination")
async def list_all_categories(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.GET_ALL_CATEGORIES(db=db, skip=skip, limit=limit)
    return result


@category_router.get("/{category_id}", description="Get category details by ID")
async def get_category_details(
    category_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_CATEGORY_BY_ID(db=db, category_id=category_id)
    return result


@category_router.put("/{category_id}", description="Update a category by ID")
async def update_category(
    category_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    category_data: CategoryCreate = Body(...),
):
    result = await inventory_manager.UPDATE_CATEGORY(
        db=db, category_id=category_id, category_data=category_data
    )
    return result


@category_router.delete("/{category_id}", description="Soft delete a category by ID")
async def soft_delete_category(
    category_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_CATEGORY(
        db=db, category_id=category_id, deleted_by=current_user.user_id
    )
    return result


@tags_router.post("/", description="Create a new tag")
async def create_tag(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    tag_data: TagCreate = Body(...),
):
    result = await inventory_manager.CREATE_TAG(db=db, tag_data=tag_data)
    return result


@tags_router.get("/", description="List all tags with pagination")
async def list_all_tags(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_TAGS(db=db, skip=skip, limit=limit)
    return result


@tags_router.get("/{tag_id}", description="Get tag details by ID")
async def get_tag_details(
    tag_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_TAG_DETAILS_BY_ID(db=db, tag_id=tag_id)
    return result


@tags_router.put("/{tag_id}", description="Update a tag by ID")
async def update_tag(
    tag_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    tag_data: TagCreate = Body(...),
):
    result = await inventory_manager.UPDATE_TAG(db=db, tag_id=tag_id, tag_data=tag_data)
    return result


@tags_router.delete("/{tag_id}", description="Soft delete a tag by ID")
async def soft_delete_tag(
    tag_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_TAG(
        db=db, tag_id=tag_id, deleted_by=current_user.user_id
    )
    return result


@side_effects_router.post("/", description="Create a side effect entry")
async def create_side_effect(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_data: SideEffectCreate = Body(...),
):
    result = await inventory_manager.CREATE_SIDE_EFFECT(
        db=db, side_effect_data=side_effect_data
    )
    return result


@side_effects_router.get("/", description="List all side effects with pagination")
async def list_all_side_effects(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_SIDE_EFFECTS(
        db=db, skip=skip, limit=limit
    )
    return result


@side_effects_router.get(
    "/{side_effect_id}", description="Get side effect details by ID"
)
async def get_side_effects_by_id(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_id: int = Path(...),
):
    result = await inventory_manager.GET_SIDE_EFFECT_BY_ID(
        db=db, side_effect_id=side_effect_id
    )
    return result


@side_effects_router.put("/{side_effect_id}", description="Update a side effect by ID")
async def update_side_effect(
    side_effect_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    side_effect_data: SideEffectCreate = Body(...),
):
    result = await inventory_manager.UPDATE_SIDE_EFFECT(
        db=db, side_effect_id=side_effect_id, side_effect_data=side_effect_data
    )
    return result


@side_effects_router.delete(
    "/{side_effect_id}", description="Soft delete a side effect by ID"
)
async def soft_delete_side_effect(
    side_effect_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_SIDE_EFFECT(
        db=db, side_effect_id=side_effect_id, deleted_by=current_user.user_id
    )
    return result


@alternates_router.post("/{medicine_id}/alternatives")
async def link_medicine_to_alternatives(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    alternative_data: AlternativeCreate = Body(...),
):
    result = await inventory_manager.LINK_MEDICINE_ALTERNATIVES(
        db=db, medicine_id=medicine_id, alternative_ids=alternative_data
    )
    return result


@alternates_router.get("/{medicine_id}")
async def get_medicine_alternatives(
    medicine_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.LIST_ALL_MEDICINE_ALTERNATIVES(
        db=db, medicine_id=medicine_id
    )
    return result


@alternates_router.put("/{medicine_id}")
async def update_link_medicine_to_alternatives(
    medicine_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    alternative_ids: List[int] = Body(...),
):
    result = await inventory_manager.UPDATE_LINK_MEDICINES_TO_ALTERNATIVES(
        db=db,
        alternative_ids=alternative_ids,
        medicine_id=medicine_id,
        deleted_by=current_user.user_id,
    )
    return result


# @alternates_router.get("/", description="List all alternatives with pagination")
# async def list_all_alternatives(
#     current_user=Security(get_current_user, scopes=["admin:read"]),
#     db: AsyncSession = Depends(get_postgres),
#     skip: int = Query(0, ge=0),
#     limit: int = Query(10, le=100),
# ):
#     result = await inventory_manager.LIST_ALL_ALTERNATIVES(
#         db=db, skip=skip, limit=limit
#     )
#     return result
#
#
# @alternates_router.put("/{alternative_id}", description="Update an alternative by ID")
# async def update_alternative(
#     alternative_id: int = Path(...),
#     current_user=Security(get_current_user, scopes=["admin:write"]),
#     db: AsyncSession = Depends(get_postgres),
#     alternative_data: AlternativeCreate = Body(...),
# ):
#     result = await inventory_manager.UPDATE_ALTERNATIVE(
#         db=db, alternative_id=alternative_id, alternative_data=alternative_data
#     )
#     return result
#
#
# @alternates_router.delete(
#     "/{alternative_id}", description="Soft delete an alternative by ID"
# )
# async def soft_delete_alternative(
#     alternative_id: int = Path(...),
#     current_user: User = Security(get_current_user, scopes=["admin:write"]),
#     db: AsyncSession = Depends(get_postgres),
# ):
#     result = await inventory_manager.SOFT_DELETE_ALTERNATIVE(
#         db=db, alternative_id=alternative_id, deleted_by=current_user.user_id
#     )
#     return result
#


@gst_router.post("/", description="Create a GST slab entry")
async def create_gst_slab(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    gst_slab_data: GSTSlabCreate = Body(...),
):
    result = await inventory_manager.CREATE_GST_SLAB(db=db, gst_slab_data=gst_slab_data)
    return result


@gst_router.get("/", description="List all GST slabs with pagination")
async def list_all_gst_slabs(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
):
    result = await inventory_manager.LIST_ALL_GST_SLABS(db=db, skip=skip, limit=limit)
    return result


@gst_router.get("/{hsn_code}", description="Get a GST slab by HSN code")
async def get_gst_slab(
    hsn_code: str = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_GST_SLAB_BY_HSN(db=db, hsn_code=hsn_code)
    return result


@gst_router.put("/{hsn_code}", description="Update a GST slab by HSN code")
async def update_gst_slab(
    hsn_code: str = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    gst_slab_data: GSTSlabCreate = Body(...),
):
    result = await inventory_manager.UPDATE_GST_SLAB(
        db=db, hsn_code=hsn_code, gst_slab_data=gst_slab_data
    )
    return result


@gst_router.delete("/{hsn_code}", description="Soft delete a GST slab by HSN code")
async def soft_delete_gst_slab(
    hsn_code: str = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_GST_SLAB(
        db=db, hsn_code=hsn_code, deleted_by=current_user.user_id
    )
    return result


# Batches Routes


@batches_router.post("/", description="Create a medicine batch entry")
async def create_batch(
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    batch_data: MedicineBatchCreate = Body(...),
):
    result = await inventory_manager.CREATE_MEDICINE_BATCH(db=db, batch_data=batch_data)
    return result


@batches_router.get(
    "/", description="List medicine batches filtered by medicine and pagination"
)
async def list_all_batches(
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    medicine_id: int = Query(None),
):
    result = await inventory_manager.GET_MEDICINE_BATCHES(
        db=db, skip=skip, limit=limit, medicine_id=medicine_id
    )
    return result


@batches_router.get("/{batch_id}", description="Get batch details by ID")
async def get_batch_by_id(
    batch_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:read"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.GET_BATCH_BY_ID(db=db, batch_id=batch_id)
    return result


@batches_router.put("/{batch_id}", description="Update a batch by ID")
async def update_batch(
    batch_id: int = Path(...),
    current_user=Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
    batch_data: MedicineBatchCreate = Body(...),
):
    result = await inventory_manager.UPDATE_BATCH(
        db=db, batch_id=batch_id, batch_data=batch_data
    )
    return result


@batches_router.delete("/{batch_id}", description="Soft delete a batch by ID")
async def soft_delete_batch(
    batch_id: int = Path(...),
    current_user: User = Security(get_current_user, scopes=["admin:write"]),
    db: AsyncSession = Depends(get_postgres),
):
    result = await inventory_manager.SOFT_DELETE_BATCH(
        db=db, batch_id=batch_id, deleted_by=current_user.user_id
    )
    return result


# Family Members Routes


router.include_router(medicine_router)
router.include_router(category_router)
router.include_router(tags_router)
router.include_router(alternates_router)
router.include_router(batches_router)
router.include_router(side_effects_router)
router.include_router(gst_router)
