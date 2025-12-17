"""
Configuration settings for the Reconciliation Agent backend.
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-sonnet"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Application Settings
    APP_NAME: str = "Reconciliation Agent"
    APP_URL: str = "http://localhost:8080"
    DEBUG: bool = False

    # Agent Settings
    MAX_ITERATIONS: int = 5
    MATCH_RATE_THRESHOLD: float = 0.95

    # Code Execution Settings
    CODE_EXECUTION_TIMEOUT: int = 30  # seconds

    # Session Settings
    SESSION_TTL: int = 3600  # 1 hour in seconds

    # File Upload Settings
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set = {"csv", "xlsx", "xls", "pdf"}

    # CORS Settings
    CORS_ORIGINS: list = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
