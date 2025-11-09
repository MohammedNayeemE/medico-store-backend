# app/utils/response_utils.py
from functools import wraps
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def success_response(
    data: Optional[Any] = None,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    """
    Standard success response wrapper for API routes.
    Accepts any kind of data (dict, list, Pydantic model, etc.)
    and returns a unified JSON structure.
    """
    if hasattr(data, "dict"):  # Handle Pydantic models
        data = data.dict()

    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
        },
    )


def error_response(
    message: str = "An error occurred",
    status_code: int = 400,
    details: Optional[Any] = None,
) -> JSONResponse:
    """
    Standard error response wrapper for API routes.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "details": details,
        },
    )


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
