"""
Delivery-Bot API Configuration Module.

This module provides configuration management for the Delivery-Bot API using
Pydantic Settings. It handles environment variables, configuration validation,
and provides type-safe access to all application settings.

Environment Variables:
    APP_API_TITLE: Title for the FastAPI application (default: Delivery-Bot API)
    APP_API_VERSION: Version string for the API (default: 0.1.0)
    APP_LOG_LEVEL: Logging level (default: INFO)
    APP_ALLOW_ORIGINS: CORS allowed origins (default: ["*"])
    APP_GITHUB_OWNER: GitHub organization or username
    APP_GITHUB_REPO: GitHub repository name for workflow dispatch
    APP_GITHUB_WORKFLOW: GitHub workflow filename (default: pipeline.yml)
    APP_GITHUB_REF: GitHub ref/branch for workflow dispatch (default: main)
    APP_GITHUB_TOKEN: GitHub personal access token for API access
    APP_GITHUB_AUTO_CREATE_WORKFLOW: Auto-create workflows if they don't exist
                                     (default: true)

Author: Nosa Omorodion
Version: 0.2.0
"""

import logging
from enum import Enum
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Application configuration settings.

    Manages all configurable aspects of the Delivery-Bot API using Pydantic
    Settings for type validation and environment variable integration.

    Attributes:
        api_title (str): Title for the FastAPI application
        api_version (str): Version string for the API
        allow_origins (list[str]): CORS allowed origins list
        log_level (LogLevel): Logging level for the application

    GitHub Integration (Optional):
        github_owner (str | None): GitHub organization or username
        github_repo (str | None): Repository name for workflow dispatch
        github_workflow (str): Workflow file name to trigger
        github_ref (str): Git reference (branch/tag) for workflow
        github_token (str | None): GitHub token for API authentication

    Configuration:
        - Environment variables are prefixed with "APP_"
        - Configuration can be loaded from .env file
        - All fields have sensible defaults for development

    Note:
        GitHub integration is only enabled when owner, repo, and token
        are all configured. Missing any of these will disable the feature.
    """

    # Basic API configuration
    api_title: str = Field(
        default="Delivery-Bot API", description="Title for the FastAPI application"
    )
    api_version: str = Field(default="0.1.0", description="Version string for the API")
    allow_origins: List[str] = Field(
        default=["*"], description="CORS allowed origins list"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO, description="Logging level for the application"
    )

    # Optional GitHub Actions integration
    github_owner: Optional[str] = Field(
        default=None, description="GitHub organization or username"
    )
    github_repo: Optional[str] = Field(
        default=None, description="GitHub repository name for workflow dispatch"
    )
    github_workflow: str = Field(
        default="pipeline.yml", description="GitHub workflow filename"
    )
    github_ref: str = Field(
        default="main", description="GitHub ref/branch for workflow dispatch"
    )
    github_token: Optional[str] = Field(
        default=None, description="GitHub personal access token for API access"
    )
    github_auto_create_workflow: bool = Field(
        default=True, description="Auto-create workflows if they don't exist"
    )

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v) -> str:
        """Validate and normalize log level configuration."""
        if isinstance(v, str):
            # Convert to uppercase for case-insensitive handling
            return v.upper()
        return v

    @property
    def github_integration_enabled(self) -> bool:
        """Check if GitHub integration is fully configured."""
        return all([self.github_owner, self.github_repo, self.github_token])

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.log_level == LogLevel.ERROR or self.log_level == LogLevel.CRITICAL

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.log_level == LogLevel.DEBUG or self.log_level == LogLevel.INFO

    def validate_environment_specific_rules(self) -> None:
        """Validate environment-specific configuration rules."""
        if self.is_production:
            if self.allow_origins == ["*"]:
                logging.warning(
                    "Production environment detected with wildcard CORS origins. "
                    "Consider restricting to specific domains."
                )
            if not self.github_token:
                logging.warning(
                    "Production environment detected without GitHub token. "
                    "GitHub integration will be disabled."
                )

    def log_configuration(self) -> None:
        """Log current configuration for debugging."""
        config_info = {
            "api_title": self.api_title,
            "api_version": self.api_version,
            "log_level": self.log_level.value,
            "github_integration": self.github_integration_enabled,
            "cors_origins": self.allow_origins,
        }
        logging.info("Configuration loaded successfully", extra={"config": config_info})


@lru_cache()
def get_settings() -> Settings:
    """Create cached settings instance to avoid repeated environment variable reads."""
    return Settings()


# Initialize settings and logging
settings = get_settings()

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.log_level.value),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("cicd")
settings.log_configuration()
