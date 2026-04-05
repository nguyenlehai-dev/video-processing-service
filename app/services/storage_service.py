import boto3
from botocore.exceptions import ClientError
from app.config import get_settings
import os
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


def get_r2_client():
    """Create and return a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_file_to_r2(file_path: str, object_name: str) -> str | None:
    """
    Upload a file to Cloudflare R2.

    Args:
        file_path: Local path to the file
        object_name: S3 object key (path in the bucket)

    Returns:
        Public URL of the uploaded file, or None if failed
    """
    try:
        client = get_r2_client()
        content_type = _get_content_type(file_path)

        client.upload_file(
            file_path,
            settings.R2_BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": content_type},
        )

        # Construct public URL
        public_url = f"{settings.R2_PUBLIC_URL}/{object_name}"
        logger.info(f"Uploaded {file_path} to R2: {public_url}")
        return public_url

    except ClientError as e:
        logger.error(f"Failed to upload to R2: {e}")
        return None


def delete_file_from_r2(object_name: str) -> bool:
    """Delete a file from Cloudflare R2."""
    try:
        client = get_r2_client()
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=object_name)
        logger.info(f"Deleted {object_name} from R2")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete from R2: {e}")
        return False


def generate_presigned_url(object_name: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL for temporary access."""
    try:
        client = get_r2_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": object_name},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None


def _get_content_type(file_path: str) -> str:
    """Determine content type from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
    }
    return content_types.get(ext, "application/octet-stream")
