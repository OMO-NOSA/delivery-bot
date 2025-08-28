
"""
Configuration Management for Delivery-Bot API.

This module handles application configuration using Pydantic Settings for
type-safe configuration loading from environment variables and .env files.
All configuration values can be overridden using environment variables with
the "APP_" prefix.

The configuration supports:
- Basic API settings (title, version, CORS)
- Logging configuration
- Optional GitHub Actions integration
- Environment-based configuration overrides

Environment Variables:
    APP_API_TITLE: Override the API title
    APP_API_VERSION: Override the API version
    APP_ALLOW_ORIGINS: JSON array of allowed CORS origins
    APP_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
    APP_GITHUB_OWNER: GitHub organization/user for Actions integration
    APP_GITHUB_REPO: GitHub repository name for Actions integration
    APP_GITHUB_WORKFLOW: GitHub workflow filename (default: pipeline.yml)
    APP_GITHUB_REF: GitHub ref/branch for workflow dispatch (default: main)
    APP_GITHUB_TOKEN: GitHub personal access token for API access
    APP_GITHUB_AUTO_CREATE_WORKFLOW: Auto-create workflows if they don't exist (default: true)

Author: Nosa Omorodion
Version: 0.1.0
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.

    Manages all configurable aspects of the Delivery-Bot API using Pydantic
    Settings for type validation and environment variable integration.

    Attributes:
        api_title (str): Title for the FastAPI application
        api_version (str): Version string for the API
        allow_origins (list[str]): CORS allowed origins list
        log_level (str): Logging level for the application

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
    api_title: str = "Delivery-Bot API"
    api_version: str = "0.1.0"
    allow_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # Optional GitHub Actions integration
    github_owner: str | None = None
    github_repo: str | None = None
    github_workflow: str = "pipeline.yml"
    github_ref: str = "main"
    github_token: str | None = None
    github_auto_create_workflow: bool = True

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8"
    )


# Global settings instance
settings = Settings()

# Debug: Log what was loaded
import logging
logger = logging.getLogger("cicd")
logger.info(
    "Configuration loaded",
    extra={
        "props": {
            "github_owner": settings.github_owner,
            "github_repo": settings.github_repo,
            "github_token": "***MASKED***" if settings.github_token else None,
            "github_workflow": settings.github_workflow,
            "github_ref": settings.github_ref,
            "github_auto_create_workflow": settings.github_auto_create_workflow,
            "env_file": ".env",
            "env_prefix": "APP_"
        }
    }
)
