import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_ROOT = Path(__file__).resolve().parent
TMP_ROOT = TEST_ROOT / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TMP_ROOT / 'test.db'}"
os.environ["TEMP_DIR"] = str(TMP_ROOT / "temp")
os.environ["STORAGE_BACKEND"] = "local"
os.environ["DEBUG"] = "false"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_test_state():
    temp_dir = TMP_ROOT / "temp"
    output_dir = Path(__file__).resolve().parents[1] / "data" / "output"

    for directory in [temp_dir, output_dir]:
        if directory.exists():
            for child in directory.iterdir():
                if child.is_file():
                    child.unlink()

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)
