"""
Configuration settings for the LaTeX → HTML5 Converter application.

This module handles environment variables, application settings,
and configuration validation using Pydantic Settings.
"""


from pydantic import validator
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

    # External tools settings
    TECTONIC_PATH: str = "tectonic"
    LATEXML_PATH: str = "latexml"
    DVISVGM_PATH: str = "dvisvgm"

    # Conversion settings
    CONVERSION_TIMEOUT: int = 300  # 5 minutes
    MAX_CONCURRENT_CONVERSIONS: int = 5

    # Security settings
    SECRET_KEY: str = "your-secret-key-change-in-production"

    @validator("ENVIRONMENT")
    def validate_environment(self, v: str) -> str:
        """Validate environment setting."""
        allowed_envs = ["development", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"ENVIRONMENT must be one of {allowed_envs}")
        return v

    @validator("LOG_LEVEL")
    def validate_log_level(self, v: str) -> str:
        """Validate log level setting."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v.upper()

    @validator("MAX_FILE_SIZE")
    def validate_max_file_size(self, v: int) -> int:
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


# Environment-specific configurations
if settings.ENVIRONMENT == "production":
    # Production-specific settings
    settings.DEBUG = False
    settings.LOG_LEVEL = "WARNING"
    settings.ALLOWED_ORIGINS = ["https://your-domain.com"]
    settings.ALLOWED_HOSTS = ["your-domain.com"]
elif settings.ENVIRONMENT == "staging":
    # Staging-specific settings
    settings.DEBUG = False
    settings.LOG_LEVEL = "INFO"
    settings.ALLOWED_ORIGINS = ["https://staging.your-domain.com"]
    settings.ALLOWED_HOSTS = ["staging.your-domain.com"]
