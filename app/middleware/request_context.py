import contextvars
import uuid
# pyrefly: ignore [missing-import]
from starlette.middleware.base import BaseHTTPMiddleware
# pyrefly: ignore [missing-import]
from starlette.requests import Request
# pyrefly: ignore [missing-import]
from starlette.responses import Response

# Global ContextVar to store Request ID for the duration of the request
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates/extracts a unique Request ID for every incoming HTTP request,
    stores it in a context-local ContextVar, and returns it as a response header.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if X-Request-ID is already provided by a load balancer/proxy, otherwise generate
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Set request ID in the ContextVar
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
        finally:
            # Always reset the ContextVar token to avoid memory leaks
            request_id_var.reset(token)
            
        # Inject Request ID into the response headers
        response.headers["X-Request-ID"] = request_id
        return response
