import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("auth_service.access")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs incoming HTTP requests, response status codes,
    and total request processing duration (with timing in milliseconds).
    Also attaches the 'X-Process-Time-Ms' header to outgoing responses.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = f"?{request.url.query}" if request.url.query else ""

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Attach execution timing header to response
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

            log_msg = (
                f"{client_host} - \"{method} {path}{query}\" "
                f"{response.status_code} - {duration_ms:.2f}ms"
            )

            if response.status_code >= 500:
                logger.error(log_msg)
            elif response.status_code >= 400:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{client_host} - \"{method} {path}{query}\" "
                f"FAILED with {type(exc).__name__}: {exc} - {duration_ms:.2f}ms"
            )
            raise exc
