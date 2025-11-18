# app/recommendation/symptom_map.py
SYMPTOM_TO_USECASE = {
    "fever": ["fever"],
    "high temperature": ["fever"],
    "chills": ["fever"],
    "headache": ["headache"],
    "migraine": ["headache"],
    "body pain": ["pain relief"],
    "muscle pain": ["pain relief"],
    "back pain": ["pain relief"],
    "cold": ["cold & cough"],
    "cough": ["cold & cough"],
    "sore throat": ["cold & cough"],
    "vomiting": ["vomiting"],
    "nausea": ["nausea/vomiting"],
    "allergy": ["allergic reactions"],
    "acid reflux": ["acidity"],
    "acidity": ["acidity"],
    # add more
}
