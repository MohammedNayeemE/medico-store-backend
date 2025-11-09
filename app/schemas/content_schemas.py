from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# Hero Section Schemas
class HeroSectionCreate(BaseModel):
    title: str
    description: str


class HeroSectionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class HeroSectionResponse(BaseModel):
    id: str
    title: str
    description: str
    image_1_id: Optional[str] = None
    image_1_url: Optional[str] = None
    image_2_id: Optional[str] = None
    image_2_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Banner Schemas
class BannerCreate(BaseModel):
    alt_text: Optional[str] = None
    link: Optional[str] = None
    order: int = 0


class BannerUpdate(BaseModel):
    alt_text: Optional[str] = None
    link: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class BannerResponse(BaseModel):
    id: str
    image_id: str
    image_url: Optional[str] = None
    alt_text: Optional[str] = None
    link: Optional[str] = None
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Best Features Schemas
class BestFeatureCreate(BaseModel):
    title: str
    description: str
    tags: List[str] = []
    icon: Optional[str] = None
    order: int = 0


class BestFeatureUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class BestFeatureResponse(BaseModel):
    id: str
    title: str
    description: str
    tags: List[str]
    icon: Optional[str] = None
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Category Schemas
class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    slug: str
    description: Optional[str] = None
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Promise Schemas
class PromiseCreate(BaseModel):
    title: str
    description: str
    icon: Optional[str] = None
    order: int = 0


class PromiseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


class PromiseResponse(BaseModel):
    id: str
    title: str
    description: str
    icon: Optional[str] = None
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Policy Schemas
class PolicyCreate(BaseModel):
    type: str
    title: str
    content: str
    version: str = "1.0"


class PolicyUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime