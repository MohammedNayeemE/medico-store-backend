# app/recommendation/embeddings.py
import threading
from typing import Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_management_models import (
    Medicine,
)  # your SQLAlchemy models module

MODEL_NAME = "all-MiniLM-L6-v2"  # small & good
_lock = threading.Lock()


class EmbeddingService:
    def __init__(self, model_name=MODEL_NAME):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.medicine_embeddings: Dict[int, np.ndarray] = {}
        self.medicine_texts: Dict[int, str] = {}

    def load_model(self):
        with _lock:
            if self.model is None:
                self.model = SentenceTransformer(self.model_name)

    def encode(self, texts: List[str]):
        self.load_model()
        return np.array(
            self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        )

    async def build_index_from_db(self, session: AsyncSession):
        """
        Build in-memory index: key = medicine_id, value = vector
        Use fields: medicine_name + generic_name + description + tags + use cases
        """
        q = await session.execute(select(Medicine).where(Medicine.is_deleted == False))
        meds = q.scalars().all()
        texts = []
        ids = []
        for m in meds:
            tags = (
                [t.name for t in getattr(m, "tags", [])]
                if getattr(m, "tags", None)
                else []
            )
            usecases = (
                [uc.use_case for uc in getattr(m, "use_cases", [])]
                if getattr(m, "use_cases", None)
                else []
            )
            text = " ".join(
                filter(
                    None,
                    [
                        m.medicine_name,
                        m.generic_name,
                        m.description,
                        " ".join(tags),
                        " ".join(usecases),
                    ],
                )
            )
            texts.append(text)
            ids.append(m.medicine_id)
            self.medicine_texts[m.medicine_id] = text
        if texts:
            vectors = self.encode(texts)
            for mid, vec in zip(ids, vectors):
                self.medicine_embeddings[mid] = vec

    def query_similar(self, query: str, top_k: int = 20):
        if not self.medicine_embeddings:
            return []
        self.load_model()
        qvec = self.encode([query])[0]
        ids = list(self.medicine_embeddings.keys())
        mat = np.stack([self.medicine_embeddings[i] for i in ids], axis=0)
        sims = cosine_similarity([qvec], mat)[0]
        idx_sorted = sims.argsort()[::-1][:top_k]
        results = [(ids[i], float(sims[i])) for i in idx_sorted]
        return results


embedding_service = EmbeddingService()
