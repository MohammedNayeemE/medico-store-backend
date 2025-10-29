import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, constr, field_validator


class MedicineCreate(BaseModel):
    medicine_name: str = Field(..., example="Paracetamol 500mg")
    generic_name: str = Field(..., example="Paracetamol")
    manufacturer: str = Field(..., example="Cipla Ltd.")
    description: str = Field(..., example="Used to relieve pain and reduce fever.")
    is_prescribed: bool = Field(default=False)
    weight: float = Field(..., example=500.0)
    hsn_code: str = Field(..., example="30049099")
    image_asset_id: Optional[int] = Field(None, example=1)

    category_ids: Optional[List[int]] = []
    tag_ids: Optional[List[int]] = []
    side_effect_ids: Optional[List[int]] = []
    alternative_ids: Optional[List[int]] = []


class MedicineResponse(MedicineCreate):
    medicine_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicineBatchCreate(BaseModel):
    medicine_id: int = Field(..., example=0)
    batch_number: str = Field(..., example="BATCH-001")
    expiry_date: date = Field(..., example="2026-12-31")
    quantity: int = Field(..., gt=0, example=100)
    purchase_price: float = Field(..., example=50.00)
    selling_price: float = Field(..., example=75.00)


class MedicineBatchResponse(MedicineBatchCreate):
    batch_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    category_name: str = Field(..., min_length=1, max_length=255)


class CategoryResponse(CategoryCreate):
    category_id: int

    model_config = ConfigDict(from_attributes=True)


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=234)


class TagReponse(TagCreate):
    tag_id: int
    model_config = ConfigDict(from_attributes=True)


class SideEffectCreate(BaseModel):
    side_effect: str = Field(..., min_length=1, max_length=253)


class SideEffectResponse(SideEffectCreate):
    side_effect_id: int
    model_config = ConfigDict(from_attributes=True)


class AlternativeCreate(BaseModel):
    name: str


class AlternativeResponse(AlternativeCreate):
    alternative_id: int
    model_config = ConfigDict(from_attributes=True)


class GSTSlabCreate(BaseModel):
    hsn_code: str
    description: str
    gst_rate: float
    effective_from: date


class GSTSlabResponse(GSTSlabCreate):

    model_config = ConfigDict(from_attributes=True)
