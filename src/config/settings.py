import os
from src.config.loader import config

class Settings:
    @property
    def DATABASE_URL(self) -> str:
        return config.database_url

    @property
    def LM_STUDIO_BASE_URL(self) -> str:
        return config.base_url

    @property
    def LM_STUDIO_API_KEY(self) -> str:
        return "lm-studio"

    @property
    def LM_STUDIO_MODEL(self) -> str:
        return config.default_model

    @property
    def LM_STUDIO_TIMEOUT(self) -> float:
        return config.timeout

    @property
    def LOG_LEVEL(self) -> str:
        return config.log_level

    @property
    def LOG_FILE_PATH(self) -> str:
        return config.log_file_path

settings = Settings()

