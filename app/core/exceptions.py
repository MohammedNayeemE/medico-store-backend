from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": detail, "status_code": status.HTTP_404_NOT_FOUND},
        )


class BadRequestException(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": detail, "status_code": status.HTTP_400_BAD_REQUEST},
        )


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Unauthorized access"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": detail, "status_code": status.HTTP_401_UNAUTHORIZED},
        )


class ForbiddenException(HTTPException):
    def __init__(
        self, detail: str = "You do not have permission to perform this action"
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": detail, "status_code": status.HTTP_403_FORBIDDEN},
        )


class ConflictException(HTTPException):
    def __init__(self, detail: str = "Conflict detected"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": detail, "status_code": status.HTTP_409_CONFLICT},
        )


class InternalServerErrorException(HTTPException):
    def __init__(self, detail: str = "An unexpected error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": detail,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )


class AppException(HTTPException):
    """
    A generic, flexible exception class for application-level errors.
    Can be used when none of the specific exceptions (NotFound, BadRequest, etc.)
    apply, or when you need to include extra context in the error response.
    """

    def __init__(
        self,
        message: str = "An application error occurred",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: Optional[str] = None,
        details: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        error_payload = {
            "error": message,
            "status_code": status_code,
        }

        if error_code:
            error_payload["error_code"] = error_code

        if details:
            error_payload["details"] = details

        super().__init__(
            status_code=status_code,
            detail=error_payload,
            headers=headers,
        )
