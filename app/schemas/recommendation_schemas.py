from pydantic import BaseModel, Field


class RecommendationQuery(BaseModel):
    query: str = Field(..., example="I have fever and body pain")
    topK: int = Field(..., example=10, ge=1, le=100)
