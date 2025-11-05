from typing import Optional

from pydantic import BaseModel, Field


class MedicineRequestCreate(BaseModel):
    requested_medicine_id: int = Field(..., description="ID of the requested medicine")
    note_text: Optional[str] = Field(
        None, description="Optional note text for the request"
    )
    note_img: Optional[str] = Field(
        None, description="Optional note image URL for the request"
    )


class MedicineRequestVerify(BaseModel):
    is_verified: bool = Field(
        ..., description="Whether the medicine request is verified or rejected"
    )
    response: Optional[str] = Field(
        None, description="Optional response message from admin"
    )
