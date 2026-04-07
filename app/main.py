from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.db.base import Base
from app.db.session import engine
from app.models import User, ApiKey, Job  # noqa: F401 - Import for table creation
from app.services.storage_service import probe_storage_health, validate_storage_configuration
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    active_storage = validate_storage_configuration()
    logger.info(f"Application started with storage backend: {active_storage}")
    storage_probe = probe_storage_health()
    app.state.storage_probe = storage_probe
    if storage_probe["ok"]:
        logger.info(str(storage_probe["message"]))
    else:
        logger.error(str(storage_probe["message"]))

    if settings.SECRET_KEY == "change-this-to-a-random-secret-key":
        logger.warning("SECRET_KEY is using the default placeholder value")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
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
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(v1_router)

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check():
        storage_probe = probe_storage_health()
        app.state.storage_probe = storage_probe
        return {
            "status": "healthy" if storage_probe["ok"] else "degraded",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "storage_backend": validate_storage_configuration(),
            "storage_ok": storage_probe["ok"],
            "storage_message": storage_probe["message"],
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
