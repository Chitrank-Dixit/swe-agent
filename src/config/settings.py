import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./coach.db"

    # LLM (LM Studio or OpenAI compatible API)
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"
    LM_STUDIO_MODEL: str = "qwen/qwen3.5-9b"
    LM_STUDIO_TIMEOUT: float = 30.0

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "coach_workflow.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
