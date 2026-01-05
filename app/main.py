"""
FastAPI application entry point for LaTeX → HTML5 Converter.

This module initializes the FastAPI application with proper configuration,
middleware, and routing for the LaTeX to HTML5 conversion service.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from app.api import conversion, health
from app.config import settings
from app.middleware import LoggingMiddleware
from app.utils.shell import check_command_available

# Setup templates (will be initialized in lifespan)
templates: Jinja2Templates | None = None


def validate_tool_paths() -> None:
    """Validate that required external tools are available."""
    required_tools = {
        "pdflatex": settings.PDFLATEX_PATH,
        "latexmlc": settings.LATEXML_PATH,
        "dvisvgm": settings.DVISVGM_PATH,
    }

    missing_tools = []
    for tool_name, tool_path in required_tools.items():
        # Check if path exists
        if not Path(tool_path).exists():
            # Try to find in system PATH
            if not check_command_available(tool_name):
                missing_tools.append(f"{tool_name} (expected at {tool_path})")
                logger.warning(f"Tool not found: {tool_name} at {tool_path}")
            else:
                logger.info(f"Tool found in PATH: {tool_name}")
        else:
            logger.info(f"Tool validated: {tool_name} at {tool_path}")

    if missing_tools and settings.ENVIRONMENT == "production":
        raise RuntimeError(
            f"Required tools not found in production: {', '.join(missing_tools)}. "
            "Please ensure all LaTeX tools are installed."
        )
    elif missing_tools:
        logger.warning(
            f"Some tools not found (non-fatal in {settings.ENVIRONMENT}): "
            f"{', '.join(missing_tools)}"
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown events.

    Args:
        _app: FastAPI application instance (unused but required by FastAPI)
    """
    global templates  # pylint: disable=global-statement  # Global needed for lifespan initialization

    # Startup
    logger.info("Starting LaTeX → HTML5 Converter service")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize templates
    templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)
    logger.info(f"Templates initialized from: {settings.TEMPLATES_DIR}")

    # Validate tool paths
    try:
        validate_tool_paths()
    except RuntimeError as exc:
        logger.error(f"Tool validation failed: {exc}")
        raise

    # Start cleanup thread for conversion storage
    conversion.start_cleanup_thread()

    yield

    # Shutdown
    logger.info("Shutting down LaTeX → HTML5 Converter service")

    # Stop cleanup thread
    conversion.stop_cleanup_thread()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    fastapi_app = FastAPI(
        title="LaTeX → HTML5 Converter",
        description=(
            "FastAPI-based service converting LaTeX projects to clean "
            "HTML5 with ≥95% fidelity"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add middleware
    setup_middleware(fastapi_app)

    # Include routers
    setup_routers(fastapi_app)

    # Setup logging
    setup_logging()

    return fastapi_app


def setup_middleware(fastapi_app: FastAPI) -> None:
    """
    Configure middleware for the FastAPI application.

    Args:
        fastapi_app: FastAPI application instance
    """
    # CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted host middleware
    fastapi_app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # Custom logging middleware
    fastapi_app.add_middleware(LoggingMiddleware)  # type: ignore


def setup_routers(fastapi_app: FastAPI) -> None:
    """
    Include API routers in the FastAPI application.

    Args:
        fastapi_app: FastAPI application instance
    """

    # Web UI route
    @fastapi_app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request):
        """Serve the web UI."""
        if templates is None:
            raise RuntimeError("Templates not initialized")
        return templates.TemplateResponse("index.html", {"request": request})

    # API routes
    fastapi_app.include_router(health.router, prefix="/api/v1", tags=["health"])
    fastapi_app.include_router(conversion.router, prefix="/api/v1", tags=["conversion"])

    # Mount static files if directory exists
    static_dir = Path(settings.STATIC_DIR)
    if static_dir.exists():
        fastapi_app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


def setup_logging() -> None:
    """
    Configure logging with loguru.
    """
    logger.remove()  # Remove default handler

    # Add console handler
    logger.add(
        sink=lambda msg: print(msg, end=""),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # Add file handler for production
    if settings.ENVIRONMENT == "production":
        # Ensure logs directory exists
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logger.add(
            "logs/app.log",
            rotation="1 day",
            retention="30 days",
            level=settings.LOG_LEVEL,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} - {message}"
            ),
        )


# Create the FastAPI application instance
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
