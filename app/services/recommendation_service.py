import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory_management_models import Medicine, MedicineUseCase, UseCase
from app.services.cache_service import CacheService
from app.services.embedding_service import embedding_service
from app.utils.preprocessor import extract_symptoms_from_query, symptoms_to_use_cases


class RecommendationService:
    def __init__(self) -> None:
        self.cache_service = CacheService()

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def _recommendation_key(self, query_hash: str) -> str:
        return f"recommendation:{query_hash}"

    def _embed_key(self, query_hash: str) -> str:
        return f"embedding:candidates:{query_hash}"

    def _medicine_payload_key(self, med_id: int) -> str:
        return f"medicine:{med_id}:payload"

    async def _fetch_medicines_by_use_cases(
        self, db: AsyncSession, use_cases: List[str]
    ):
        if not use_cases:
            return []
        uc_lower = [x.lower() for x in use_cases]
        stmt = (
            select(Medicine)
            .options(
                selectinload(Medicine.tags),
                selectinload(Medicine.categories),
                selectinload(Medicine.side_effects),
                selectinload(Medicine.alternatives),
            )
            .join(MedicineUseCase, Medicine.medicine_id == MedicineUseCase.medicine_id)
            .join(UseCase, MedicineUseCase.use_case_id == UseCase.use_case_id)
            .where(func.lower(UseCase.use_case).in_(uc_lower))
            .where(Medicine.is_deleted == False)
        )
        q = await db.execute(stmt)
        meds = q.scalars().unique().all()
        return meds

    def _build_medicine_payload(self, m: Medicine) -> Dict[str, Any]:
        tags = (
            [t.name for t in getattr(m, "tags", [])] if getattr(m, "tags", None) else []
        )
        categories = (
            [c.category_name for c in getattr(m, "categories", [])]
            if getattr(m, "categories", None)
            else []
        )
        side_effects = (
            [s.side_effect for s in getattr(m, "side_effects", [])]
            if getattr(m, "side_effects", None)
            else []
        )
        alternatives = (
            [a.name for a in getattr(m, "alternatives", [])]
            if getattr(m, "alternatives", None)
            else []
        )
        return {
            "medicine_id": m.medicine_id,
            "medicine_name": m.medicine_name,
            "generic_name": m.generic_name,
            "manufacturer": m.manufacturer,
            "description": m.description,
            "tags": tags,
            "categories": categories,
            "side_effects": side_effects,
            "alternatives": alternatives,
        }

    def _score_medicine(
        self,
        base_payload: Dict[str, Any],
        matched_use_cases: List[str],
        embed_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        score = 0.0
        reasons = []
        # -----------------------------------
        # 1. Use-case match (strongest signal)
        # -----------------------------------
        # try both tags + categories + name + description
        use_case_strength = 2.5  # previously 2.0
        for uc in matched_use_cases:
            uc_lower = uc.lower()
            in_tags = any(uc_lower in t.lower() for t in base_payload.get("tags", []))
            in_categories = any(
                uc_lower in c.lower() for c in base_payload.get("categories", [])
            )
            in_name = uc_lower in (base_payload.get("medicine_name") or "").lower()
            in_descr = uc_lower in (base_payload.get("description") or "").lower()
            if in_tags or in_categories or in_name or in_descr:
                score += use_case_strength
                reasons.append(f"use-case matched: '{uc}'")
        # -----------------------------------
        # 2. Tag quality scoring
        # -----------------------------------
        # good tags → small boosts (max 1.5)
        tag_count = len(base_payload.get("tags", []))
        score += min(tag_count * 0.15, 1.5)
        if tag_count > 0:
            reasons.append(f"tag relevance +{min(tag_count * 0.15, 1.5):.2f}")
        # -----------------------------------
        # 3. Category relevance (boost)
        # -----------------------------------
        category_count = len(base_payload.get("categories", []))
        score += min(category_count * 0.25, 2.0)
        if category_count > 0:
            reasons.append(f"category relevance +{min(category_count * 0.25, 2.0):.2f}")
        # -----------------------------------
        # 4. Side-effect penalty (smarter)
        # -----------------------------------
        se_list = base_payload.get("side_effects", [])
        se_count = len(se_list)
        # mild side effects → -0.2 each
        # severe side effects → -1 each (if you want severity-based scoring later)
        penalty = se_count * 0.3 * -1
        score += penalty
        if se_count:
            reasons.append(
                f"side-effect penalty {penalty:.2f} ({se_count} side effects)"
            )
        # -----------------------------------
        # 6. Embedding similarity (strong signal)
        # -----------------------------------
        if embed_score is not None:
            # normalize embeddings (0–1 → weight 5)
            embed_weight = embed_score * 5.0
            score += embed_weight
            reasons.append(f"semantic similarity boost +{embed_weight:.2f}")
        # -----------------------------------
        # Final
        # -----------------------------------
        return {
            "score": round(float(score), 3),
            "reasons": reasons,
        }

    async def RECOMMEND(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 10,
        embedding_candidates: int = 100,
    ):
        query_hash = self._hash_query(query)
        recommendation_key = self._recommendation_key(query_hash)
        cached_result = await self.cache_service.get_cache(recommendation_key)
        if cached_result:
            return cached_result
        emb_key = self._embed_key(query_hash)
        embeded_results = await self.cache_service.get_cache(emb_key)
        if embeded_results:
            embeded_scores = {medicine_id: sim for medicine_id, sim in embeded_results}
            candidate_ids = list(embeded_scores.keys())
        else:
            try:
                if not embedding_service.medicine_embeddings:
                    await embedding_service.build_index_from_db(db)

                embeded_results = embedding_service.query_similar(
                    query, top_k=embedding_candidates
                )
                embeded_scores = {
                    medicine_id: sim for medicine_id, sim in embeded_results
                }
                candidate_ids = list(embeded_scores.keys())
                await self.cache_service.set_cache(emb_key, embeded_results, ttl=1800)
                if not candidate_ids:
                    return {"error": "No semantic medicines found"}
            except Exception as e:
                print(f"Embedding Error : {e}")
                return {"error": "embedding failure"}
        stmt = (
            select(Medicine)
            .options(
                selectinload(Medicine.tags),
                selectinload(Medicine.categories),
                selectinload(Medicine.side_effects),
                selectinload(Medicine.alternatives),
            )
            .where(Medicine.medicine_id.in_(candidate_ids))
            .where(Medicine.is_deleted == False)
        )
        result = await db.execute(stmt)
        medicines = result.scalars().unique().all()
        symptom_matches = extract_symptoms_from_query(query)
        matched_symptoms = [s for s, _ in symptom_matches]
        matched_use_cases = symptoms_to_use_cases(matched_symptoms)
        medicine_scores: List[Dict] = []
        for medicine in medicines:
            payload_key = self._medicine_payload_key(medicine.medicine_id)
            cached_payload = await self.cache_service.get_cache(payload_key)
            if cached_payload:
                payload = cached_payload
            else:
                payload = self._build_medicine_payload(medicine)
                await self.cache_service.set_cache(
                    payload_key,
                    payload,
                    ttl=86400,  # 24 hrs
                )
            embed_score = embeded_scores.get(medicine.medicine_id)
            score_obj = self._score_medicine(payload, matched_use_cases, embed_score)
            payload["score"] = score_obj["score"]
            payload["reasons"] = score_obj["reasons"]
            medicine_scores.append(payload)
        sorted_scores = sorted(medicine_scores, key=lambda x: x["score"], reverse=True)
        final_response = {
            "query": query,
            "matched_symptoms": matched_symptoms,
            "matched_use_cases": matched_use_cases,
            "recommendations": sorted_scores[:top_k],
        }
        await self.cache_service.set_cache(
            recommendation_key,
            final_response,
            ttl=3600,  # 1 hour
        )
        return final_response
