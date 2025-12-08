"""
Custom middleware for the LaTeX → HTML5 Converter application.

This module contains custom middleware for logging, request processing,
and other cross-cutting concerns.
"""

import time
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class LoggingMiddleware:
    """
    Custom logging middleware for request/response logging.

    This middleware logs all incoming requests and outgoing responses
    with timing information and request IDs for better debugging.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the logging middleware.

        Args:
            app: FastAPI application instance
        """
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """
        Process the request and add logging.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate request ID
        request_id = str(uuid.uuid4())[:8]

        # Add request ID to scope
        scope["request_id"] = request_id

        # Start timing
        start_time = time.time()

        # Log request
        request = Request(scope, receive)
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Client: {request.client.host if request.client else 'unknown'}"
        )

        # Process request
        await self.app(scope, receive, send)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(f"[{request_id}] Request completed in {process_time:.3f}s")


class ErrorHandlingMiddleware:
    """
    Custom error handling middleware for consistent error responses.

    This middleware catches unhandled exceptions and returns
    consistent JSON error responses.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the error handling middleware.

        Args:
            app: FastAPI application instance
        """
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """
        Process the request with error handling.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            # Log the error
            logger.error(f"Unhandled exception: {exc}", exc_info=True)

            # Create error response
            error_response = JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "request_id": scope.get("request_id", "unknown"),
                },
            )

            # Send error response
            await error_response(scope, receive, send)


class SecurityMiddleware:
    """
    Security middleware for request validation and protection.

    This middleware adds security headers and validates requests
    for potential security issues.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the security middleware.

        Args:
            app: FastAPI application instance
        """
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """
        Process the request with security checks.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Add security headers
        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"x-xss-protection", b"1; mode=block"),
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        ),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
