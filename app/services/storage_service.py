import os
import shutil
import logging
import mimetypes
import uuid
import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Output directory for processed videos
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "output")


class StorageUploadError(RuntimeError):
    """Raised when a file cannot be uploaded to the configured storage backend."""


def _delete_file_from_r2(object_name: str) -> None:
    client = _get_r2_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_name)


def _ensure_output_dir():
    """Ensure output directory exists."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_r2_client():
    """Build an S3-compatible client for Cloudflare R2."""
    endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name=settings.R2_REGION,
        config=Config(signature_version="s3v4"),
    )


def _can_use_r2() -> bool:
    required = [
        settings.R2_ACCOUNT_ID,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET_NAME,
        settings.R2_PUBLIC_URL,
    ]
    return all(required)


def get_storage_backend() -> str:
    """Resolve the active storage backend."""
    if settings.STORAGE_BACKEND == "local":
        return "local"
    if settings.STORAGE_BACKEND == "r2":
        if not _can_use_r2():
            raise RuntimeError("STORAGE_BACKEND=r2 but Cloudflare R2 is not fully configured")
        return "r2"
    return "r2" if _can_use_r2() else "local"


def validate_storage_configuration() -> str:
    """Validate storage configuration and return the active backend."""
    backend = get_storage_backend()
    if backend == "r2":
        logger.info("Storage backend configured: Cloudflare R2")
    else:
        logger.warning("Storage backend configured: local filesystem fallback")
    return backend


def probe_storage_health() -> dict[str, str | bool]:
    """
    Check whether the configured storage backend is usable.

    For R2 this performs a real write/delete roundtrip to validate object permissions.
    """
    backend = get_storage_backend()

    if backend == "local":
        _ensure_output_dir()
        return {
            "backend": "local",
            "ok": True,
            "message": f"Local storage ready at {OUTPUT_DIR}",
        }

    object_name = f"healthchecks/{uuid.uuid4()}.txt"
    client = _get_r2_client()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_name,
            Body=b"storage-healthcheck",
            ContentType="text/plain",
        )
        _delete_file_from_r2(object_name)
        return {
            "backend": "r2",
            "ok": True,
            "message": f"R2 write check passed for bucket {settings.R2_BUCKET_NAME}",
        }
    except Exception as exc:
        logger.error("R2 storage probe failed for bucket %s: %s", settings.R2_BUCKET_NAME, exc)
        return {
            "backend": "r2",
            "ok": False,
            "message": f"R2 write check failed for bucket {settings.R2_BUCKET_NAME}: {exc}",
        }


def _upload_file_to_r2(file_path: str, object_name: str) -> str:
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    client = _get_r2_client()
    try:
        client.upload_file(
            file_path,
            settings.R2_BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": content_type},
        )
    except (ClientError, BotoCoreError, OSError) as exc:
        raise StorageUploadError(
            f"Failed to upload {file_path} to {settings.R2_BUCKET_NAME}/{object_name}: {exc}"
        ) from exc
    base_url = settings.R2_PUBLIC_URL.rstrip("/")
    return f"{base_url}/{object_name}"

def delete_file_from_r2(object_name: str) -> bool:
    """Delete an object from R2 bucket."""
    if not _can_use_r2():
        return False
    client = _get_r2_client()
    try:
        client.delete_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_name
        )
        logger.info(f"Deleted {object_name} from R2 bucket {settings.R2_BUCKET_NAME}")
        return True
    except (ClientError, BotoCoreError) as exc:
        logger.error(f"Failed to delete {object_name} from R2: {exc}")
        return False

def _upload_file_to_local(file_path: str, object_name: str) -> str:
    _ensure_output_dir()

    filename = os.path.basename(object_name)
    dest_path = os.path.join(OUTPUT_DIR, filename)

    shutil.copy2(file_path, dest_path)
    file_size = os.path.getsize(dest_path)

    logger.info(f"Saved {file_path} to {dest_path} ({file_size} bytes)")
    download_path = f"/api/v1/video/download/{filename}"
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{download_path}"
    return download_path


def generate_presigned_put_url(object_name: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL for direct client upload to R2."""
    if not _can_use_r2():
        return None

    client = _get_r2_client()
    try:
        response = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.R2_BUCKET_NAME,
                'Key': object_name,
            },
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None


def upload_file_to_storage(file_path: str, object_name: str, content_type: str = None) -> str:
    """
    Save a processed file to the configured storage backend.

    Args:
        file_path: Local path to the temp file
        object_name: Relative path for storing (e.g., "output/job-id.mp4")

    Returns:
        Download URL path
    """
    backend = get_storage_backend()
    if backend == "r2":
        download_url = _upload_file_to_r2(file_path, object_name)
        logger.info(f"Uploaded {file_path} to R2 object {object_name}")
        return download_url
    return _upload_file_to_local(file_path, object_name)


def delete_file_from_storage(object_name: str) -> bool:
    """Delete a file from the active storage backend."""
    try:
        backend = get_storage_backend()
        if backend == "r2":
            _delete_file_from_r2(object_name)
            logger.info(f"Deleted R2 object {object_name}")
            return True

        filename = os.path.basename(object_name)
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        return False


def storage_object_exists(object_name: str) -> bool:
    """Check whether an input reference currently exists."""
    if object_name.startswith("http://") or object_name.startswith("https://"):
        try:
            response = httpx.head(object_name, follow_redirects=True, timeout=10.0)
            if response.status_code == 405:
                response = httpx.get(
                    object_name,
                    headers={"Range": "bytes=0-0"},
                    follow_redirects=True,
                    timeout=10.0,
                )
            return response.status_code < 400
        except Exception:
            return False

    backend = get_storage_backend()
    if backend == "r2":
        try:
            _get_r2_client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=object_name)
            return True
        except (ClientError, BotoCoreError):
            return False

    return get_file_path(os.path.basename(object_name)) is not None


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
