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
    Create a standardized success response for API endpoints.
    
    This utility function creates a consistent JSON response structure for successful
    API operations. It automatically handles Pydantic models by converting them to
    dictionaries, and supports various data types including dicts, lists, and primitives.
    
    Args:
        data (Optional[Any]): The response data to include. Can be:
                             - Pydantic models (automatically converted to dict)
                             - Dict, list, or primitive types
                             - None (optional, defaults to None)
        message (str): A human-readable success message. Defaults to "Success".
        status_code (int): HTTP status code for the response. Defaults to 200.
                          Should be in the 2xx range for successful operations.
    
    Returns:
        JSONResponse: A FastAPI JSONResponse object with the following structure:
                     {
                         "success": True,
                         "message": str,
                         "data": Any
                     }
    
    Example Usage:
        ```python
        # With a Pydantic model
        user = UserSchema(id=1, name="John")
        return success_response(data=user, message="User retrieved successfully")
        
        # With a dictionary
        return success_response(data={"count": 10}, message="Items retrieved")
        
        # With a list
        return success_response(data=[1, 2, 3], message="List retrieved")
        
        # With no data
        return success_response(message="Operation completed", status_code=201)
        ```
    
    Note:
        - Pydantic models are automatically serialized using their .dict() method
        - The response follows a consistent structure across all endpoints
        - Status code should be appropriate for the operation (200, 201, 202, etc.)
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
    Create a standardized error response for API endpoints.
    
    This utility function creates a consistent JSON response structure for error
    conditions. It provides a unified format for error messages and optional
    error details that can help with debugging and client-side error handling.
    
    Args:
        message (str): A human-readable error message describing what went wrong.
                      Defaults to "An error occurred".
        status_code (int): HTTP status code for the error response. Defaults to 400.
                          Common values:
                          - 400: Bad Request
                          - 401: Unauthorized
                          - 403: Forbidden
                          - 404: Not Found
                          - 422: Validation Error
                          - 500: Internal Server Error
        details (Optional[Any]): Additional error details that can provide more
                                context about the error. Can be:
                                - Validation errors (dict/list)
                                - Exception messages
                                - Field-specific error information
                                - None (optional, defaults to None)
    
    Returns:
        JSONResponse: A FastAPI JSONResponse object with the following structure:
                     {
                         "success": False,
                         "message": str,
                         "details": Any (optional)
                     }
    
    Example Usage:
        ```python
        # Basic error
        return error_response(
            message="User not found",
            status_code=404
        )
        
        # With validation details
        return error_response(
            message="Validation failed",
            status_code=422,
            details={"email": "Invalid email format", "age": "Must be positive"}
        )
        
        # With exception details
        return error_response(
            message="Database error",
            status_code=500,
            details=str(exception)
        )
        ```
    
    Note:
        - The response follows a consistent error structure across all endpoints
        - The status_code should accurately reflect the error type
        - Details are optional and can be omitted for simple errors
        - HTTPException is not raised automatically; this just formats the response
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
    Recursively serialize MongoDB documents to JSON-serializable Python objects.
    
    Converts MongoDB-specific types (like ObjectId) and nested structures (dicts,
    lists) into standard Python types that can be serialized to JSON. This function
    handles ObjectId objects by converting them to strings, and recursively processes
    nested dictionaries and lists.
    
    Args:
        doc: The MongoDB document or value to serialize. Can be:
             - A MongoDB document (dict with ObjectId values)
             - A list of MongoDB documents
             - An ObjectId instance
             - Nested dictionaries or lists
             - Primitive types (str, int, float, bool, None)
    
    Returns:
        Any: A JSON-serializable version of the input:
             - ObjectId instances are converted to strings
             - Dicts are recursively processed
             - Lists are recursively processed
             - Primitive types are returned as-is
             - None is returned as None
    
    Example Usage:
        ```python
        # Single document with ObjectId
        doc = {"_id": ObjectId("..."), "name": "John"}
        serialized = serialize_mongo_doc(doc)
        # Returns: {"_id": "...", "name": "John"}
        
        # List of documents
        docs = [{"_id": ObjectId("..."), "name": "John"}]
        serialized = serialize_mongo_doc(docs)
        # Returns: [{"_id": "...", "name": "John"}]
        
        # Nested structure
        doc = {"_id": ObjectId("..."), "user": {"id": ObjectId("...")}}
        serialized = serialize_mongo_doc(doc)
        # Returns: {"_id": "...", "user": {"id": "..."}}
        ```
    
    Note:
        - This function is recursive and handles deeply nested structures
        - ObjectId values are converted to their string representation
        - The function does not modify the original document
        - Returns None if the input is None
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
    Decorator for FastAPI route handlers to automatically serialize MongoDB responses.
    
    This decorator wraps FastAPI route handlers that return MongoDB documents or
    collections. It automatically serializes the response data by converting ObjectId
    instances to strings and ensuring all nested structures are JSON-serializable.
    It also handles exceptions, re-raising HTTPException instances and converting
    other exceptions to HTTP 500 errors.
    
    Args:
        handler: The FastAPI route handler function to wrap. Should be an async
                function that returns MongoDB documents, lists of documents, or
                other serializable data.
    
    Returns:
        function: A wrapped version of the handler that automatically serializes
                 MongoDB responses and handles errors.
    
    Example Usage:
        ```python
        @router.get("/documents")
        @mongo_response
        async def get_documents(db = Depends(get_mongo_db)):
            collection = db["documents"]
            documents = await collection.find().to_list(length=100)
            return documents  # Automatically serialized
        ```
    
    Behavior:
        - Automatically serializes the handler's return value using serialize_mongo_doc
        - Re-raises HTTPException instances without modification
        - Converts other exceptions to HTTPException with status 500
        - Preserves the original function's name and metadata using functools.wraps
    
    Error Handling:
        - HTTPException: Re-raised as-is (allows proper error responses)
        - Other Exceptions: Converted to HTTPException with status 500 and error message
        - Serialization errors: Logged and converted to HTTP 500 errors
    
    Note:
        - The handler must be an async function
        - The decorator preserves the original function signature
        - HTTPException instances are not serialized, they are re-raised
        - Other exceptions are caught and converted to HTTP 500 responses
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
