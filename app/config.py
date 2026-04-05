from pydantic_settings import BaseSettings
from functools import lru_cache
import os


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

    # Storage: files saved locally at ./data/output/

    # Cloudflare Tunnel
    CLOUDFLARE_TUNNEL_TOKEN: str = ""

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    TEMP_DIR: str = "/tmp/video-processing"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
