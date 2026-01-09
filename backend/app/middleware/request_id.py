"""Request ID middleware for tracking requests through the system."""

import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import set_request_id


class RequestIdMiddleware:
    """Pure ASGI middleware to generate and track request IDs."""

    def __init__(self, app: ASGIApp) -> None:
        """
        Initialize the middleware.

        Args:
            app: The ASGI application
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Process ASGI request and add request ID.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if request already has an ID (from load balancer/proxy)
        request_id = None
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == b"x-request-id":
                request_id = header_value.decode("latin1")
                break

        # Generate new ID if not present
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set request ID in context for logging
        set_request_id(request_id)

        # Add request ID to scope state for access in route handlers
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            """Add request ID to response headers."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)
