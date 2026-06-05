from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me-in-production"

    database_url: str = "postgresql+psycopg://lms:lms@localhost:5432/lms"

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    library_timezone: str = "Asia/Kolkata"

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
