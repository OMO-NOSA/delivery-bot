
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    api_title: str = "Delivery-Bot API"
    api_version: str = "0.1.0"
    allow_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # Optional GitHub Actions dispatch
    github_owner: str | None = None
    github_repo: str | None = None
    github_workflow: str = "pipeline.yml"
    github_ref: str = "main"
    github_token: str | None = None

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", env_file_encoding="utf-8")

settings = Settings()
