"""
FastAPI application entry point for LaTeX → HTML5 Converter.

This module initializes the FastAPI application with proper configuration,
middleware, and routing for the LaTeX to HTML5 conversion service.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger
import uvicorn

from app.api import conversion, health
from app.config import settings
from app.middleware import LoggingMiddleware


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="LaTeX → HTML5 Converter",
        description="FastAPI-based service converting LaTeX projects to clean HTML5 with ≥95% fidelity",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Add middleware
    setup_middleware(app)

    # Include routers
    setup_routers(app)

    # Setup logging
    setup_logging()

    return app


def setup_middleware(app: FastAPI) -> None:
    """
    Configure middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

    # Custom logging middleware
    app.add_middleware(LoggingMiddleware)  # type: ignore


def setup_routers(app: FastAPI) -> None:
    """
    Include API routers in the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(conversion.router, prefix="/api/v1", tags=["conversion"])


def setup_logging() -> None:
    """
    Configure logging with loguru.
    """
    logger.remove()  # Remove default handler

    # Add console handler
    logger.add(
        sink=lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )

    # Add file handler for production
    if settings.ENVIRONMENT == "production":
        logger.add(
            "logs/app.log",
            rotation="1 day",
            retention="30 days",
            level=settings.LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )


# Create the FastAPI application instance
app = create_app()


@app.on_event("startup")
async def startup_event() -> None:
    """
    Application startup event handler.
    """
    logger.info("Starting LaTeX → HTML5 Converter service")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    Application shutdown event handler.
    """
    logger.info("Shutting down LaTeX → HTML5 Converter service")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
