from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Video Processing Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # Cloudflare R2 (S3-compatible)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "video-output"
    R2_PUBLIC_URL: str = ""  # e.g. https://pub-xxx.r2.dev
    R2_REGION: str = "auto"

    # Cloudflare Tunnel
    CLOUDFLARE_TUNNEL_TOKEN: str = ""

    # Storage
    STORAGE_BACKEND: str = "auto"  # auto, r2, local

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    TEMP_DIR: str = "/tmp/video-processing"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
