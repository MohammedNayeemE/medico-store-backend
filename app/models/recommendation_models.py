from typing import List, Optional

from pydantic import BaseModel


class MedicineOut(BaseModel):
    medicine_id: int
    medicine_name: str
    generic_name: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    categories: List[str] = []
    side_effects: List[str] = []
    alternatives: List[str] = []
    score: float
    reason: List[str] = []


class RecommendResponse(BaseModel):
    query: str
    matched_symptoms: List[str]
    matched_use_cases: List[str]
    recommendations: List[MedicineOut]
