from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.db.base import Base
from app.db.session import engine
from app.models import User, ApiKey, Job  # noqa: F401 - Import for table creation
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## Video Processing Service API

Dịch vụ xử lý video sử dụng FFmpeg, hỗ trợ các chức năng:
- 🎬 **Cắt video** - Cắt đoạn video theo thời gian
- 🔗 **Ghép video** - Nối nhiều video lại
- 🔊 **Ghép âm thanh** - Thêm/thay audio
- 🎵 **Tách âm thanh** - Trích xuất audio
- ⚡ **Tăng/giảm tốc độ** - Thay đổi playback speed
- ✂️ **Crop video** - Cắt vùng hiển thị
- 📐 **Resize video** - Thay đổi kích thước

### Authentication
- **Management endpoints** (auth, users, api-keys): Sử dụng JWT Bearer token
- **Video endpoints**: Sử dụng API Key qua header `X-API-Key`
        """,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create database tables
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # Create temp directory
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    # Include routers
    app.include_router(v1_router)

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
