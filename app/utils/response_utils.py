# app/utils/response_utils.py
from functools import wraps
from fastapi import HTTPException
from bson import ObjectId


def serialize_mongo_doc(doc):
    """
    Recursively convert MongoDB documents (ObjectId, nested dicts/lists)
    into JSON-serializable Python dicts.
    """
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_mongo_doc(d) for d in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, (dict, list)):
                new_doc[k] = serialize_mongo_doc(v)
            else:
                new_doc[k] = v
        return new_doc
    return doc


def mongo_response(handler):
    """
    Decorator for FastAPI route handlers.
    Converts MongoDB docs/lists into JSON-safe data before returning.
    """

    @wraps(handler)
    async def wrapper(*args, **kwargs):
        try:
            result = await handler(*args, **kwargs)
            return serialize_mongo_doc(result)
        except HTTPException:
            raise
        except Exception as e:
            print("❌ Serialization error:", e)
            raise HTTPException(status_code=500, detail=str(e))

    return wrapper
