import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("request")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        response: Response = await call_next(request)
        duration = time.time() - start_time
        print(f"{request.method} {request.url} completed in {duration:.4f}s")
        # logger.info(
        #     f"{request.method} {request.url.path} "
        #     f"completed_in={duration:.2f}ms status={response.status_code}"
        # )
        return response
