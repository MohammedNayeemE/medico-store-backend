import logging
import traceback
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
    UnauthorizedException,
)

logger = logging.getLogger(__name__)


class ExceptionMiddleware(BaseHTTPMiddleware):
    """
    Global exception middleware that catches and handles all exceptions
    across the application, providing consistent error responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Intercept all requests and handle exceptions globally.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler in the chain

        Returns:
            Response: JSON response with error details or the normal response
        """
        try:
            response = await call_next(request)
            return response
        except RequestValidationError as e:
            # Handle FastAPI request validation errors (422)
            return self._handle_validation_error(e, request)
        except ValidationError as e:
            # Handle Pydantic validation errors
            return self._handle_pydantic_validation_error(e, request)
        except NotFoundException as e:
            # Handle custom NotFoundException
            return self._handle_http_exception(e, request)
        except BadRequestException as e:
            # Handle custom BadRequestException
            return self._handle_http_exception(e, request)
        except UnauthorizedException as e:
            # Handle custom UnauthorizedException
            return self._handle_http_exception(e, request)
        except ForbiddenException as e:
            # Handle custom ForbiddenException
            return self._handle_http_exception(e, request)
        except ConflictException as e:
            # Handle custom ConflictException
            return self._handle_http_exception(e, request)
        except InternalServerErrorException as e:
            # Handle custom InternalServerErrorException
            return self._handle_http_exception(e, request)
        except AppException as e:
            # Handle custom AppException
            return self._handle_http_exception(e, request)
        except HTTPException as e:
            # Handle standard FastAPI HTTPException
            return self._handle_http_exception(e, request)
        except SQLAlchemyError as e:
            # Handle database errors
            return self._handle_database_error(e, request)
        except Exception as e:
            # Handle any other unexpected exceptions
            return self._handle_generic_exception(e, request)

    def _handle_validation_error(
        self, error: RequestValidationError, request: Request
    ) -> JSONResponse:
        """
        Handle FastAPI request validation errors (422).

        Args:
            error: The RequestValidationError exception
            request: The HTTP request object

        Returns:
            JSONResponse: Formatted error response
        """
        errors = []
        for err in error.errors():
            field = " -> ".join(str(loc) for loc in err.get("loc", []))
            errors.append(
                {
                    "field": field,
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )

        error_message = "Validation error: Invalid request data"
        if errors:
            first_error = errors[0]
            error_message = f"Validation error: {first_error.get('field', 'unknown')} - {first_error.get('message', 'Invalid value')}"

        logger.warning(
            f"Validation error on {request.method} {request.url.path}: {error_message}",
            extra={"errors": errors, "client_ip": self._get_client_ip(request)},
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": error_message,
                "details": errors,
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )

    def _handle_pydantic_validation_error(
        self, error: ValidationError, request: Request
    ) -> JSONResponse:
        """
        Handle Pydantic validation errors.

        Args:
            error: The ValidationError exception
            request: The HTTP request object

        Returns:
            JSONResponse: Formatted error response
        """
        errors = []
        for err in error.errors():
            field = " -> ".join(str(loc) for loc in err.get("loc", []))
            errors.append(
                {
                    "field": field,
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )

        error_message = "Validation error: Invalid data format"
        if errors:
            first_error = errors[0]
            error_message = f"Validation error: {first_error.get('field', 'unknown')} - {first_error.get('message', 'Invalid value')}"

        logger.warning(
            f"Pydantic validation error on {request.method} {request.url.path}: {error_message}",
            extra={"errors": errors, "client_ip": self._get_client_ip(request)},
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": error_message,
                "details": errors,
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )

    def _handle_http_exception(
        self, error: HTTPException, request: Request
    ) -> JSONResponse:
        """
        Handle HTTPException and custom exception classes.

        Args:
            error: The HTTPException or custom exception
            request: The HTTP request object

        Returns:
            JSONResponse: Formatted error response
        """
        # Extract error details from the exception
        detail = error.detail
        status_code = error.status_code

        # Handle different detail formats
        if isinstance(detail, dict):
            # Custom exceptions already have structured detail
            error_message = detail.get("error", detail.get("message", "An error occurred"))
            error_code = detail.get("error_code")
            error_details = detail.get("details")
            response_content = {
                "success": False,
                "message": error_message,
                "status_code": status_code,
            }
            if error_code:
                response_content["error_code"] = error_code
            if error_details:
                response_content["details"] = error_details
        elif isinstance(detail, str):
            # Simple string detail
            response_content = {
                "success": False,
                "message": detail,
                "status_code": status_code,
            }
        else:
            # Fallback for other types
            response_content = {
                "success": False,
                "message": str(detail) if detail else "An error occurred",
                "status_code": status_code,
            }

        # Log the error
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        logger.log(
            log_level,
            f"HTTP {status_code} on {request.method} {request.url.path}: {response_content.get('message')}",
            extra={
                "status_code": status_code,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # Include headers if present
        headers = error.headers if hasattr(error, "headers") and error.headers else None

        return JSONResponse(
            status_code=status_code,
            content=response_content,
            headers=headers,
        )

    def _handle_database_error(
        self, error: SQLAlchemyError, request: Request
    ) -> JSONResponse:
        """
        Handle database/SQLAlchemy errors.

        Args:
            error: The SQLAlchemyError exception
            request: The HTTP request object

        Returns:
            JSONResponse: Formatted error response
        """
        error_message = "A database error occurred"
        error_details = None

        if settings.DEBUG:
            # Include detailed error information in debug mode
            error_message = f"Database error: {str(error)}"
            error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        else:
            # Generic message in production
            error_message = "A database error occurred. Please try again later."

        # Log the full error with traceback
        logger.error(
            f"Database error on {request.method} {request.url.path}: {str(error)}",
            exc_info=True,
            extra={
                "error_type": type(error).__name__,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": error_message,
                "details": error_details,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

    def _handle_generic_exception(
        self, error: Exception, request: Request
    ) -> JSONResponse:
        """
        Handle any other unexpected exceptions.

        Args:
            error: The generic Exception
            request: The HTTP request object

        Returns:
            JSONResponse: Formatted error response
        """
        error_message = "An unexpected error occurred"
        error_details = None

        if settings.DEBUG:
            # Include detailed error information in debug mode
            error_message = f"Unexpected error: {str(error)}"
            error_details = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc().split("\n"),
            }
        else:
            # Generic message in production
            error_message = "An unexpected error occurred. Please try again later."

        # Log the full error with traceback
        logger.error(
            f"Unexpected error on {request.method} {request.url.path}: {str(error)}",
            exc_info=True,
            extra={
                "error_type": type(error).__name__,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "path": str(request.url.path),
                "method": request.method,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": error_message,
                "details": error_details,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Args:
            request: The HTTP request object

        Returns:
            str: Client IP address or "unknown"
        """
        if request.client:
            return request.client.host
        return "unknown"

