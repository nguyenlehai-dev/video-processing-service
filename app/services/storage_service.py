import os
import shutil
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Output directory for processed videos
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "output")


def _ensure_output_dir():
    """Ensure output directory exists."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def upload_file_to_storage(file_path: str, object_name: str) -> str | None:
    """
    Save a processed file to local storage.

    Args:
        file_path: Local path to the temp file
        object_name: Relative path for storing (e.g., "output/job-id.mp4")

    Returns:
        Download URL path, or None if failed
    """
    try:
        _ensure_output_dir()

        # Extract just the filename from object_name
        filename = os.path.basename(object_name)
        dest_path = os.path.join(OUTPUT_DIR, filename)

        # Copy file to output directory
        shutil.copy2(file_path, dest_path)
        file_size = os.path.getsize(dest_path)

        logger.info(f"Saved {file_path} to {dest_path} ({file_size} bytes)")

        # Return the API download URL path
        download_url = f"/api/v1/video/download/{filename}"
        return download_url

    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return None


def delete_file_from_storage(object_name: str) -> bool:
    """Delete a file from local storage."""
    try:
        filename = os.path.basename(object_name)
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        return False


def get_file_path(filename: str) -> str | None:
    """Get the full path of a stored file."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return file_path
    return None


def get_output_dir() -> str:
    """Get the output directory path."""
    _ensure_output_dir()
    return OUTPUT_DIR
