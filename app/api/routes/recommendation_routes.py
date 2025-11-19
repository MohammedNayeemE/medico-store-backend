from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.exceptions import BadRequestException
from app.models.user_management_models import User
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
rc_service = RecommendationService()


@router.post("/")
async def recommend_endpoint(
    payload: dict = Body(...), session: AsyncSession = Depends(get_postgres)
):
    """
    ```
    Request body expected:
    {
      "query": "I have fever and body pain",
      "use_embedding": true,
      "top_k": 10
    }
    ```
    """
    query = payload.get("query")
    if not query:
        raise BadRequestException("query is required")
    use_embedding = payload.get("use_embedding", False)
    top_k = int(payload.get("top_k", 10))
    result = await rc_service.RECOMMEND(
        query, session, use_embedding=use_embedding, top_k=top_k
    )
    recommendations = []
    for r in result["recommendations"]:
        recommendations.append(
            {
                "medicine_name": r["medicine_name"],
                "generic_name": r.get("generic_name"),
                "manufacturer": r.get("manufacturer"),
                "description": r.get("description"),
                "tags": r.get("tags", []),
                "categories": r.get("categories", []),
                "side_effects": r.get("side_effects", []),
                "alternatives": r.get("alternatives", []),
            }
        )
    return {
        "query": result["query"],
        "matched_symptoms": result["matched_symptoms"],
        "matched_use_cases": result["matched_use_cases"],
        "recommendations": recommendations,
    }
