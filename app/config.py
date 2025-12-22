"""
Configuration settings for the LaTeX → HTML5 Converter application.

This module handles environment variables, application settings,
and configuration validation using Pydantic Settings.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    All settings can be overridden using environment variables
    with the same name (case-insensitive).
    """

    # Application settings
    APP_NAME: str = "LaTeX → HTML5 Converter"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS settings
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    # Logging settings
    LOG_LEVEL: str = "INFO"

    # File upload settings
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: list[str] = [".zip", ".tar.gz", ".tar"]
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"

    # Web UI settings
    TEMPLATES_DIR: str = "app/templates"
    STATIC_DIR: str = "app/static"

    # Asset handling settings
    ASSET_PATTERNS: list[str] = [
        "*.jpg",
        "*.jpeg",
        "*.png",
        "*.svg",
        "*.gif",
        "*.webp",
        "*.pdf",
    ]

    # External tools settings
    TECTONIC_PATH: str = "/usr/local/bin/tectonic"
    PDFLATEX_PATH: str = "/usr/bin/pdflatex"  # Docker default, override with env var
    LATEXML_PATH: str = "/usr/bin/latexmlc"  # Docker default, override with env var
    DVISVGM_PATH: str = "/usr/bin/dvisvgm"

    # Conversion settings
    CONVERSION_TIMEOUT: int = 300  # 5 minutes
    MAX_CONCURRENT_CONVERSIONS: int = 5
    CONVERSION_RETENTION_HOURS: int = 24  # How long to keep conversion results

    # LaTeX package settings
    CRITICAL_LATEX_PACKAGES: list[str] = [
        "amsmath",
        "amssymb",
        "amsfonts",
        "graphicx",
        "hyperref",
        "geometry",
        "inputenc",
        "fontenc",
    ]

    # Security settings
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-64-chars-required-now"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Validate secret key is changed in production."""
        environment = info.data.get("ENVIRONMENT", "development")
        if (
            environment == "production"
            and v == "dev-secret-key-change-in-production-min-64-chars-required-now"
        ):
            raise ValueError(
                "SECRET_KEY must be changed in production! "
                "Set SECRET_KEY environment variable to a secure random value."
            )
        # Only enforce length requirement in production to allow simpler dev keys.
        # Production tests should use ENVIRONMENT=production to validate security.
        if environment == "production" and len(v) < 64:
            raise ValueError(
                "SECRET_KEY must be at least 64 characters long for production security"
            )
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        allowed_envs = ["development", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"ENVIRONMENT must be one of {allowed_envs}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level setting."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v.upper()

    @field_validator("MAX_FILE_SIZE")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Validate maximum file size."""
        if v <= 0:
            raise ValueError("MAX_FILE_SIZE must be positive")
        if v > 500 * 1024 * 1024:  # 500MB
            raise ValueError("MAX_FILE_SIZE cannot exceed 500MB")
        return v

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings: Application settings instance
    """
    return settings


# Note: Environment-specific configurations should be set via environment variables
# Example .env files for each environment:
#
# Production (.env.production):
#   ENVIRONMENT=production
#   DEBUG=false
#   LOG_LEVEL=WARNING
#   ALLOWED_ORIGINS=["https://your-domain.com"]
#   ALLOWED_HOSTS=["your-domain.com"]
#
# Staging (.env.staging):
#   ENVIRONMENT=staging
#   DEBUG=false
#   LOG_LEVEL=INFO
#   ALLOWED_ORIGINS=["https://staging.your-domain.com"]
#   ALLOWED_HOSTS=["staging.your-domain.com"]
