import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Security, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.dependecies.auth import get_current_user  # Assuming you have auth
from app.api.dependecies.get_db_sessions import get_mongo_db
from app.schemas.content_schemas import (
    BannerCreate,
    BannerResponse,
    BannerUpdate,
    BestFeatureCreate,
    BestFeatureResponse,
    BestFeatureUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    HeroSectionCreate,
    HeroSectionResponse,
    HeroSectionUpdate,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    PromiseCreate,
    PromiseResponse,
    PromiseUpdate,
)
from app.services.content_services import ContentService
from app.utils.response_utils import mongo_response

router = APIRouter(prefix="/content", tags=["Content Management"])


def get_content_service(
    db: AsyncIOMotorClient = Depends(get_mongo_db),
) -> ContentService:
    return ContentService(db)


# ============= HERO SECTION ROUTES =============
@router.post(
    "/hero",
)
@mongo_response
async def create_hero_section(
    data: HeroSectionCreate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),  # Admin only
):
    """Create hero section (Admin only)"""
    hero_data = data.dict()
    hero_data["is_active"] = True
    result = await service.create_hero_section(hero_data)
    return await service.get_hero_section()


@router.get(
    "/hero",
)
@mongo_response
async def get_hero_section(service: ContentService = Depends(get_content_service)):
    """Get active hero section (Public)"""
    hero = await service.get_hero_section()
    if not hero:
        raise HTTPException(status_code=404, detail="Hero section not found")
    return hero


@router.put(
    "/hero/{hero_id}",
)
@mongo_response
async def update_hero_section(
    hero_id: str,
    data: HeroSectionUpdate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update hero section (Admin only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    await service.update_hero_section(hero_id, update_data)
    return await service.get_hero_section()


@router.post(
    "/hero/{hero_id}/image/{image_num}",
)
@mongo_response
async def upload_hero_image(
    hero_id: str,
    image_num: int,
    file: UploadFile = File(...),
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Upload hero section image (Admin only). image_num should be 1 or 2"""
    if image_num not in [1, 2]:
        raise HTTPException(status_code=400, detail="image_num must be 1 or 2")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    return await service.upload_hero_image(hero_id, image_num, file)


# ============= BANNER ROUTES =============
@router.post(
    "/banners",
)
@mongo_response
async def create_banner(
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    order: int = Form(0),
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Create banner (Admin only) - Max 5 active banners"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    banner_data = {
        "alt_text": alt_text,
        "link": link,
        "order": order,
        "is_active": True,
    }
    return await service.create_banner(file, banner_data)


@router.get(
    "/banners",
)
@mongo_response
async def get_banners(
    active_only: bool = True, service: ContentService = Depends(get_content_service)
):
    """Get all banners (Public for active, Admin for all)"""
    return await service.get_banners(active_only)


@router.put(
    "/banners/{banner_id}",
)
@mongo_response
async def update_banner(
    banner_id: str,
    data: BannerUpdate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update banner (Admin only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    return await service.update_banner(banner_id, update_data)


@router.delete("/banners/{banner_id}")
async def delete_banner(
    banner_id: str,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Delete banner (Admin only)"""
    await service.delete_banner(banner_id)
    return {"message": "Banner deleted successfully"}


# ============= BEST FEATURES ROUTES =============
@router.post(
    "/features",
)
@mongo_response
async def create_feature(
    data: BestFeatureCreate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Create best feature (Admin only)"""
    feature_data = data.dict()
    feature_data["is_active"] = True
    return await service.create_feature(feature_data)


@router.get(
    "/features",
)
@mongo_response
async def get_features(
    active_only: bool = True, service: ContentService = Depends(get_content_service)
):
    """Get all features (Public for active)"""
    return await service.get_features(active_only)


@router.put(
    "/features/{feature_id}",
)
@mongo_response
async def update_feature(
    feature_id: str,
    data: BestFeatureUpdate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update feature (Admin only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    return await service.update_feature(feature_id, update_data)


@router.delete("/features/{feature_id}")
async def delete_feature(
    feature_id: str,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Delete feature (Admin only)"""
    await service.delete_feature(feature_id)
    return {"message": "Feature deleted successfully"}


# ============= CATEGORY ROUTES =============
@router.post(
    "/categories",
)
@mongo_response
async def create_category(
    name: str = Form(...),
    slug: str = Form(...),
    description: Optional[str] = Form(None),
    order: int = Form(0),
    file: Optional[UploadFile] = File(None),
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Create category (Admin only)"""
    if file and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    category_data = {
        "name": name,
        "slug": slug,
        "description": description,
        "order": order,
        "is_active": True,
    }
    return await service.create_category(category_data, file)


@router.get(
    "/categories",
)
@mongo_response
async def get_categories(
    active_only: bool = True, service: ContentService = Depends(get_content_service)
):
    """Get all categories (Public for active)"""
    return await service.get_categories(active_only)


@router.put(
    "/categories/{category_id}",
)
@mongo_response
async def update_category(
    category_id: str,
    name: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(None),
    is_active: Optional[bool] = Form(None),
    file: Optional[UploadFile] = File(None),
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update category (Admin only)"""
    if file and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    update_data = {}
    if name is not None:
        update_data["name"] = name
    if slug is not None:
        update_data["slug"] = slug
    if description is not None:
        update_data["description"] = description
    if order is not None:
        update_data["order"] = order
    if is_active is not None:
        update_data["is_active"] = is_active

    return await service.update_category(category_id, update_data, file)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Delete category (Admin only)"""
    await service.delete_category(category_id)
    return {"message": "Category deleted successfully"}


# ============= PROMISE ROUTES =============
@router.post(
    "/promises",
)
@mongo_response
async def create_promise(
    data: PromiseCreate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Create promise (Admin only)"""
    promise_data = data.dict()
    promise_data["is_active"] = True
    return await service.create_promise(promise_data)


@router.get(
    "/promises",
)
@mongo_response
async def get_promises(
    active_only: bool = True, service: ContentService = Depends(get_content_service)
):
    """Get all promises (Public for active)"""
    return await service.get_promises(active_only)


@router.put(
    "/promises/{promise_id}",
)
@mongo_response
async def update_promise(
    promise_id: str,
    data: PromiseUpdate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update promise (Admin only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    return await service.update_promise(promise_id, update_data)


@router.delete("/promises/{promise_id}")
async def delete_promise(
    promise_id: str,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Delete promise (Admin only)"""
    await service.delete_promise(promise_id)
    return {"message": "Promise deleted successfully"}


# ============= POLICY ROUTES =============
@router.post(
    "/policies",
)
@mongo_response
async def create_policy(
    data: PolicyCreate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Create policy (Admin only)"""
    policy_data = data.dict()
    policy_data["is_active"] = True
    return await service.create_policy(policy_data)


@router.get(
    "/policies",
)
@mongo_response
async def get_all_policies(service: ContentService = Depends(get_content_service)):
    """Get all active policies (Public)"""
    return await service.get_policies()


@router.get(
    "/policies/{policy_type}",
)
@mongo_response
async def get_policy(
    policy_type: str, service: ContentService = Depends(get_content_service)
):
    """Get policy by type (Public)"""
    policy = await service.get_policy_by_type(policy_type)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_type}' not found")
    return policy


@router.put(
    "/policies/{policy_id}",
)
@mongo_response
async def update_policy(
    policy_id: str,
    data: PolicyUpdate,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Update policy (Admin only)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    return await service.update_policy(policy_id, update_data)


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    service: ContentService = Depends(get_content_service),
    current_user=Security(get_current_user, scopes=["content:write"]),
):
    """Delete policy (Admin only)"""
    await service.delete_policy(policy_id)
    return {"message": "Policy deleted successfully"}


# ============= IMAGE SERVING ROUTE =============
@router.get("/images/{file_id}")
@mongo_response
async def get_image(
    file_id: str, service: ContentService = Depends(get_content_service)
):
    """Serve images from GridFS (Public)"""
    grid_out = await service.get_image_stream(file_id)

    # Get content type from metadata
    content_type = (
        grid_out.metadata.get("content_type", "image/jpeg")
        if grid_out.metadata
        else "image/jpeg"
    )

    async def file_iterator():
        while chunk := await grid_out.read(1024 * 1024):  # Read 1MB at a time
            yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename={grid_out.filename}",
            "Cache-Control": "public, max-age=31536000",
        },
    )
