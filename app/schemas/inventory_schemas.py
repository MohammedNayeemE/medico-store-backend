import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    confloat,
    conint,
    constr,
    field_validator,
    model_validator,
)


class MedicineCreate(BaseModel):
    medicine_name: constr(min_length=2, max_length=255) = Field(
        ...,
        example="Paracetamol 500mg",
        description="Full name of the medicine with dosage",
    )
    generic_name: constr(min_length=2, max_length=255) = Field(
        ...,
        example="Paracetamol",
        description="Generic (chemical) name of the medicine",
    )
    manufacturer: constr(min_length=2, max_length=255) = Field(
        ..., example="Cipla Ltd.", description="Manufacturer or pharmaceutical company"
    )
    description: constr(min_length=5, max_length=1000) = Field(
        ...,
        example="Used to relieve pain and reduce fever.",
        description="Medicine description",
    )
    is_prescribed: bool = Field(
        default=False, example=False, description="Whether a prescription is required"
    )
    weight: confloat(gt=0, le=10000) = Field(
        ..., example=500.0, description="Weight or dosage amount (e.g., mg or ml)"
    )
    hsn_code: constr(pattern=r"^\d{8}$") = Field(
        ..., example="30049099", description="8-digit HSN code for GST classification"
    )
    image_asset_id: Optional[int] = Field(
        None, example=1, description="Reference to primary image asset ID"
    )

    category_ids: Optional[List[conint(gt=0)]] = Field(
        default_factory=list, example=[1, 2], description="List of category IDs"
    )
    tag_ids: Optional[List[conint(gt=0)]] = Field(
        default_factory=list, example=[3, 5], description="List of tag IDs"
    )
    side_effect_ids: Optional[List[conint(gt=0)]] = Field(
        default_factory=list, example=[4, 6], description="List of side effect IDs"
    )
    alternative_ids: Optional[List[conint(gt=0)]] = Field(
        default_factory=list,
        example=[7, 8],
        description="List of alternative medicine IDs",
    )

    @field_validator("medicine_name")
    def no_special_chars(cls, v):
        if not re.match(r"^[a-zA-Z0-9\s\-\.]+$", v):
            raise ValueError("medicine_name must not contain special characters")
        return v


class MedicineImageCreate(BaseModel):
    medicine_id: conint(gt=0) = Field(..., example=101)
    file_asset_id: conint(gt=0) = Field(..., example=55)


class MedicineImageResponse(MedicineImageCreate):
    id: int = Field(..., example=1)
    model_config = ConfigDict(from_attributes=True)


class MedicineResponse(MedicineCreate):
    medicine_id: int = Field(..., example=101)
    created_at: datetime = Field(..., example="2025-11-08T10:00:00Z")
    model_config = ConfigDict(from_attributes=True)


class MedicineResponse(MedicineCreate):
    medicine_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicineBatchCreate(BaseModel):
    medicine_id: conint(gt=0) = Field(..., example=101)
    batch_number: constr(min_length=3, max_length=100, pattern=r"^[A-Z0-9\-]+$") = (
        Field(..., example="BATCH-001", description="Unique batch identifier")
    )
    expiry_date: date = Field(..., example="2026-12-31")
    quantity: conint(gt=0, le=100000) = Field(
        ..., example=100, description="Total quantity of medicine units in this batch"
    )
    purchase_price: confloat(gt=0, le=100000) = Field(
        ..., example=50.00, description="Purchase price per unit"
    )
    selling_price: confloat(gt=0, le=200000) = Field(
        ..., example=75.00, description="Selling price per unit"
    )

    @model_validator(mode="after")
    def validate_expiry(cls, values):
        expiry = values.expiry_date
        if expiry <= date.today():
            raise ValueError("expiry_date must be a future date")
        return values


class MedicineBatchResponse(MedicineBatchCreate):
    batch_id: int = Field(..., example=5001)
    created_at: datetime = Field(..., example="2025-11-08T10:00:00Z")
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    category_name: constr(min_length=2, max_length=255) = Field(
        ..., example="Pain Relief", description="Name of the medicine category"
    )


class CategoryResponse(CategoryCreate):
    category_id: int = Field(..., example=1)
    model_config = ConfigDict(from_attributes=True)


class TagCreate(BaseModel):
    name: constr(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9\s\-]+$") = Field(
        ..., example="Analgesic", description="Descriptive tag for medicine"
    )


class TagResponse(TagCreate):
    tag_id: int = Field(..., example=1)
    model_config = ConfigDict(from_attributes=True)


class SideEffectCreate(BaseModel):
    side_effect: constr(min_length=2, max_length=255) = Field(
        ..., example="Nausea", description="Possible side effect name"
    )


class SideEffectResponse(SideEffectCreate):
    side_effect_id: int = Field(..., example=3)
    model_config = ConfigDict(from_attributes=True)


class AlternativeCreate(BaseModel):
    medicine_alternative_ids: List[conint(gt=0)] = Field(
        ...,
        example=[2, 3],
        description="List of medicine IDs that can be used as alternatives",
    )


class AlternativeResponse(AlternativeCreate):
    alternative_id: int = Field(..., example=10)
    model_config = ConfigDict(from_attributes=True)


class GSTSlabCreate(BaseModel):
    hsn_code: constr(pattern=r"^\d{8}$") = Field(..., example="30049099")
    description: constr(min_length=3, max_length=255) = Field(
        ...,
        example="Medicaments not elsewhere specified",
        description="GST Slab description",
    )
    gst_rate: confloat(ge=0, le=100) = Field(..., example=12.0)
    effective_from: date = Field(..., example="2024-01-01")

    @model_validator(mode="after")
    def validate_date(cls, values):
        if values.effective_from > date.today() + timedelta(days=3650):
            raise ValueError("effective_from date too far in the future")
        return values


class GSTSlabResponse(GSTSlabCreate):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------
# 📋 Prescription Verification
# ------------------------------------------------------------


class VerifyPrescription(BaseModel):
    prescription_id: conint(gt=0) = Field(..., example=501)
    is_verified: bool = Field(..., example=True)
    notes: Optional[constr(max_length=500)] = Field(
        None, example="Prescription verified and approved by Dr. Sharma."
    )
