from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory_management_models import Medicine, MedicineUseCase, UseCase
from app.services.embedding_service import embedding_service
from app.utils.preprocessor import extract_symptoms_from_query, symptoms_to_use_cases


class RecommendationService:
    def __init__(self) -> None:
        pass

    async def _fetch_medicines_by_use_cases(
        self, session: AsyncSession, use_cases: List[str]
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
        q = await session.execute(stmt)
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
        """
        Scoring rules (tunable):
        - +2 per matched use_case present in medicine use_cases (we'll inspect length)
        - +1 per matched tag overlap (if tag names appear in query/usecases)
        - -0.5 per side effect present (to penalize)
        - +0.01 * stock
        - optional: add embedding similarity weight
        """
        score = 0.0
        reasons = []
        # use case match count: we assume medicine.use_cases is loaded if available
        med_use_cases = base_payload.get(
            "categories", []
        )  # fallback if use_cases not loaded; ideally fetch use_cases
        # but we will use tags and description instead:
        # simple heuristic: if any use case string is present in tags or description -> count
        for uc in matched_use_cases:
            uc_lower = uc.lower()
            in_tags = any(uc_lower in t.lower() for t in base_payload.get("tags", []))
            in_name_or_descr = (
                base_payload.get("medicine_name")
                and uc_lower in (base_payload.get("medicine_name") or "").lower()
            ) or (
                base_payload.get("description")
                and uc_lower in (base_payload.get("description") or "").lower()
            )
            if in_tags or in_name_or_descr:
                score += 2.0
                reasons.append(f"matches use case '{uc}' in tags/description")
        # tag overlap (example: if use_case words appear in tags)
        # small boost for tags count
        score += 0.1 * len(base_payload.get("tags", []))
        # side-effect penalty
        se_count = len(base_payload.get("side_effects", []))
        score -= 0.5 * se_count
        if se_count:
            reasons.append(f"penalized for {se_count} side effects")
        # stock add small weight
        stock = base_payload.get("stock", 0) or 0
        score += 0.01 * stock
        if embed_score is not None:
            score += (
                float(embed_score) * 3.0
            )  # weight of embedding similarity (tunable)
            reasons.append(f"embedding similarity {embed_score:.3f}")
        return {"score": float(score), "reasons": reasons}

    async def RECOMMEND(
        self,
        query: str,
        session: AsyncSession,
        use_embedding: bool = False,
        top_k: int = 10,
    ):
        sym_matches = extract_symptoms_from_query(query)
        matched_symptoms = [s for s, sc in sym_matches]
        matched_use_cases = symptoms_to_use_cases(matched_symptoms)
        meds = await self._fetch_medicines_by_use_cases(session, matched_use_cases)
        payloads = []
        for m in meds:
            payload = self._build_medicine_payload(m)
            payloads.append((m.medicine_id, payload))
        embed_scores = {}
        if use_embedding:
            try:
                if not embedding_service.medicine_embeddings:
                    await embedding_service.build_index_from_db(session)
                embed_results = embedding_service.query_similar(query, top_k=500)
                embed_scores = {mid: sim for mid, sim in embed_results}
            except Exception as e:
                print("Embedding service error:", e)
                embed_scores = {}
        scored = []
        for mid, payload in payloads:
            embed_score = embed_scores.get(mid)
            scobj = self._score_medicine(payload, matched_use_cases, embed_score)
            payload["score"] = scobj["score"]
            payload["reason"] = scobj["reasons"]
            scored.append(payload)
        scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "matched_symptoms": matched_symptoms,
            "matched_use_cases": matched_use_cases,
            "recommendations": scored_sorted[:top_k],
        }
