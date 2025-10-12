"""
Health check endpoints for the LaTeX → HTML5 Converter application.

This module provides health check endpoints for monitoring
and service discovery.
"""

import platform
from datetime import datetime

import psutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings

router = APIRouter()


@router.get("/healthz")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.

    Returns:
        JSONResponse: Health status and basic information
    """
    try:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/health")
async def detailed_health_check() -> JSONResponse:
    """
    Detailed health check endpoint with system information.

    Returns:
        JSONResponse: Detailed health status and system metrics
    """
    try:
        # Get system information
        system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0]
        }

        # Get system metrics
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }

        # Check external dependencies
        dependencies_status = await check_dependencies()

        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "timestamp": datetime.utcnow().isoformat(),
                "system": system_info,
                "metrics": system_metrics,
                "dependencies": dependencies_status
            }
        )
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


async def check_dependencies() -> dict[str, bool]:
    """
    Check the status of external dependencies.

    Returns:
        dict: Status of external dependencies
    """
    dependencies = {
        "tectonic": False,
        "latexml": False,
        "dvisvgm": False
    }

    try:
        # Check Tectonic
        import subprocess
        result = subprocess.run(
            [settings.TECTONIC_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=5, check=False
        )
        dependencies["tectonic"] = result.returncode == 0
    except Exception:
        dependencies["tectonic"] = False

    try:
        # Check LaTeXML
        result = subprocess.run(
            [settings.LATEXML_PATH, "--VERSION"],
            capture_output=True,
            text=True,
            timeout=5, check=False
        )
        dependencies["latexml"] = result.returncode == 0
    except Exception:
        dependencies["latexml"] = False

    try:
        # Check dvisvgm
        result = subprocess.run(
            [settings.DVISVGM_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=5, check=False
        )
        dependencies["dvisvgm"] = result.returncode == 0
    except Exception:
        dependencies["dvisvgm"] = False

    return dependencies


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness check endpoint for Kubernetes/Docker health checks.

    Returns:
        JSONResponse: Readiness status
    """
    try:
        # Check if all critical dependencies are available
        dependencies = await check_dependencies()

        # Consider service ready if at least Tectonic and LaTeXML are available
        critical_deps = ["tectonic", "latexml"]
        ready = all(dependencies[dep] for dep in critical_deps)

        if ready:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ready",
                    "service": settings.APP_NAME,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": settings.APP_NAME,
                "missing_dependencies": [
                    dep for dep, status in dependencies.items()
                    if not status
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")
