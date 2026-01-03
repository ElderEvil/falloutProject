"""Request ID middleware for tracking requests through the system."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and track request IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add request ID.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with X-Request-ID header
        """
        # Check if request already has an ID (from load balancer/proxy)
        request_id = request.headers.get("X-Request-ID")

        # Generate new ID if not present
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set request ID in context for logging
        set_request_id(request_id)

        # Add request ID to request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
