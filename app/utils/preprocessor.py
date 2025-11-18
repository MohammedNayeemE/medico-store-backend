import re
from typing import List, Tuple

from rapidfuzz import fuzz

from .symptom_map import SYMPTOM_TO_USECASE

MIN_SCORE = 70  # fuzzy match threshold


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_symptoms_from_query(query: str) -> List[Tuple[str, int]]:
    """
    Return list of (symptom_key, score) matched from symptom map.
    """
    q = normalize_text(query)
    matched = []
    for symptom in SYMPTOM_TO_USECASE.keys():
        score = fuzz.partial_ratio(symptom, q)
        if score >= MIN_SCORE:
            matched.append((symptom, int(score)))
    for token in q.split():
        if token in SYMPTOM_TO_USECASE and (token, 100) not in matched:
            matched.append((token, 100))
    matched_unique = {}
    for s, sc in matched:
        if s not in matched_unique or sc > matched_unique[s]:
            matched_unique[s] = sc
    return sorted(list(matched_unique.items()), key=lambda x: x[1], reverse=True)


def symptoms_to_use_cases(symptom_keys: List[str]) -> List[str]:
    uc = set()
    for s in symptom_keys:
        uc.update(SYMPTOM_TO_USECASE.get(s, []))
    return list(uc)
