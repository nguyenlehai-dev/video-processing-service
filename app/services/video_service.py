import logging
import os
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session
from botocore.exceptions import ClientError

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.job import Job
from app.services.storage_service import (
    upload_file_to_storage,
    _get_r2_client,
    delete_file_from_storage,
    get_file_path,
    get_storage_backend,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _ensure_temp_dir():
    """Ensure temp directory exists."""
    os.makedirs(settings.TEMP_DIR, exist_ok=True)


def _get_temp_path(extension: str = ".mp4") -> str:
    """Generate a unique temp file path."""
    _ensure_temp_dir()
    return os.path.join(settings.TEMP_DIR, f"{uuid.uuid4()}{extension}")


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    """Run an FFmpeg command and return success state plus stderr."""
    try:
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            error = result.stderr or "Unknown FFmpeg error"
            logger.error(f"FFmpeg error: {error}")
            return False, error
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "FFmpeg processing timed out (10 minutes)"
    except Exception as exc:
        return False, str(exc)


def _get_video_duration(input_path: str) -> float:
    """Use ffprobe to get video duration in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as exc:
        logger.warning(f"Could not read duration for {input_path}: {exc}")
    return 0.0


def _has_audio(input_path: str) -> bool:
    """Use ffprobe to check if video has an audio stream."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return "audio" in result.stdout.lower()
    except Exception as exc:
        logger.warning(f"Could not check audio for {input_path}: {exc}")
    return False


def _add_silent_audio(input_path: str) -> str | None:
    """Add a silent audio track to a video without audio."""
    output_path = _get_temp_path(".mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    success, error = _run_ffmpeg(cmd)
    if success and os.path.exists(output_path):
        return output_path
    return None


def _normalize_merge_input(input_path: str) -> str | None:
    """Re-encode a merge segment to a consistent video/audio profile."""
    output_path = _get_temp_path(".mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        output_path,
    ]
    success, error = _run_ffmpeg(cmd)
    if success and os.path.exists(output_path):
        return output_path
    logger.warning("Failed to normalize merge input %s: %s", input_path, error)
    _cleanup_files([output_path])
    return None


def _cleanup_files(paths: list[str]):
    """Remove temporary files."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as exc:
            logger.warning(f"Failed to clean up {path}: {exc}")


def _generate_thumbnail(input_path: str) -> str | None:
    """Generate a JPEG thumbnail from a processed video."""
    thumbnail_path = _get_temp_path(".jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "thumbnail,scale=640:-1",
        "-frames:v", "1",
        thumbnail_path,
    ]
    success, error = _run_ffmpeg(cmd)
    if success and os.path.exists(thumbnail_path):
        return thumbnail_path
    logger.warning("Thumbnail generation failed for %s: %s", input_path, error)
    _cleanup_files([thumbnail_path])
    return None


def create_processing_job(
    db: Session,
    operation: str,
    user_id: str,
    params: dict | None = None,
    input_files: list[dict] | None = None,
    status: str = "pending",
) -> Job:
    """Create a new pending processing job."""
    job = Job(
        operation=operation,
        status=status,
        progress=0.0,
        params=params,
        input_files=input_files,
        user_id=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _start_job(db: Session, job: Job):
    job.status = "processing"
    job.progress = 5.0
    db.commit()


def _fail_job(db: Session, job: Job, error_message: str, started_at: float):
    job.status = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    job.duration = time.time() - started_at
    db.commit()


def _complete_job(
    db: Session,
    job: Job,
    output_path: str,
    started_at: float,
    thumbnail_path: str | None = None,
):
    file_size = os.path.getsize(output_path)
    ext = os.path.splitext(output_path)[1]
    object_name = f"output/{job.id}{ext}"
    try:
        download_url = upload_file_to_storage(output_path, object_name)
    except Exception as exc:
        logger.error(f"Storage upload failed for job {job.id}: {exc}")
        _fail_job(db, job, f"Failed to upload output file to storage: {exc}", started_at)
        return

    job.status = "completed"
    job.output_url = download_url
    job.output_filename = f"{job.operation}_{job.id[:8]}{ext}"
    job.file_size = file_size
    job.progress = 100.0
    job.completed_at = datetime.now(timezone.utc)
    job.duration = time.time() - started_at
    params = dict(job.params or {})
    params["has_audio"] = _has_audio(output_path)
    job.params = params

    if thumbnail_path and os.path.exists(thumbnail_path):
        thumbnail_object_name = f"output/{job.id}_thumbnail.jpg"
        try:
            thumbnail_url = upload_file_to_storage(thumbnail_path, thumbnail_object_name)
            params["thumbnail_url"] = thumbnail_url
            job.params = params
        except Exception as exc:
            logger.warning("Failed to upload thumbnail for job %s: %s", job.id, exc)

    db.commit()

    # Cleanup Input files from Cloudflare R2 securely
    if job.input_files:
        for f in job.input_files:
            object_key = f.get("object_key")
            if object_key:
                if f.get("managed") is False:
                    continue
                if object_key.startswith("http://") or object_key.startswith("https://"):
                    continue
                if object_key.startswith("output/"):
                    continue
                delete_file_from_storage(object_key)


def _copy_from_local_storage(key: str, local_path: str) -> None:
    source_path = get_file_path(os.path.basename(key))
    if not source_path:
        raise FileNotFoundError(f"Input object not found in local storage: {key}")
    shutil.copy2(source_path, local_path)


def _download_input_file(key: str, local_path: str, storage_backend: str) -> None:
    if key.startswith("http://") or key.startswith("https://"):
        import httpx

        try:
            with httpx.stream("GET", key, follow_redirects=True) as response:
                response.raise_for_status()
                with open(local_path, "wb") as target:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        target.write(chunk)
            return
        except Exception as exc:
            logger.error("Failed to download external url %s: %s", key, exc)
            raise RuntimeError(f"Failed to download external url: {key}") from exc

    if storage_backend == "r2":
        try:
            _get_r2_client().download_file(settings.R2_BUCKET_NAME, key, local_path)
            return
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(f"Input object not found in R2 storage: {key}") from exc
            raise RuntimeError(f"Failed to download input object from R2: {key}") from exc

    _copy_from_local_storage(key, local_path)



def _process_job(
    job_id: str,
    input_keys: list[str],
    runner: Callable[[list[str]], tuple[bool, str, str | None, str | None]],
):
    db = SessionLocal()
    started_at = time.time()
    output_path: str | None = None
    thumbnail_path: str | None = None
    local_input_paths = []

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        _start_job(db, job)
        
        # Download files from the active storage backend or an external URL first.
        storage_backend = get_storage_backend()
        for key in input_keys:
            ext = os.path.splitext(key.split("?")[0])[1] or ".mp4"
            local_path = _get_temp_path(ext)

            _download_input_file(key, local_path, storage_backend)
            local_input_paths.append(local_path)

        success, error, output_path, thumbnail_path = runner(local_input_paths)
        if not success or not output_path:
            _fail_job(db, job, error or "Unknown processing error", started_at)
            return

        job.progress = 90.0
        db.commit()
        _complete_job(db, job, output_path, started_at, thumbnail_path=thumbnail_path)
    except Exception as exc:
        logger.exception(f"Unexpected error while processing job {job_id}: {exc}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            _fail_job(db, job, str(exc), started_at)
    finally:
        cleanup_paths = list(local_input_paths)
        if output_path:
            cleanup_paths.append(output_path)
        if thumbnail_path:
            cleanup_paths.append(thumbnail_path)
        _cleanup_files(cleanup_paths)
        db.close()


def process_cut_job(job_id: str, object_key: str, start_time: str, end_time: str):
    def runner(local_paths):
        input_path = local_paths[0]
        output_path = _get_temp_path(".mp4")
        cmd = [
            "ffmpeg", "-y",
            "-ss", start_time,
            "-to", end_time,
            "-i", input_path,
            "-c:v", "libx264",
            "-crf", "16",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [object_key], runner)


def process_merge_job(job_id: str, object_keys: list[str]):
    def runner(local_paths):
        # Normalize every segment so concat keeps both video and audio reliably.
        prepared_paths = []
        intermediate_files = []
        
        for path in local_paths:
            if not _has_audio(path):
                logger.info(f"Video {path} has no audio. Adding silent audio track.")
                new_path = _add_silent_audio(path)
                if new_path:
                    prepared_paths.append(new_path)
                    intermediate_files.append(new_path)
                else:
                    prepared_paths.append(path)
            else:
                prepared_paths.append(path)

        normalized_paths = []
        for path in prepared_paths:
            normalized_path = _normalize_merge_input(path)
            if not normalized_path:
                _cleanup_files(intermediate_files)
                return False, "Failed to normalize one of the merge inputs.", None, None
            normalized_paths.append(normalized_path)
            intermediate_files.append(normalized_path)

        concat_path = _get_temp_path(".txt")
        intermediate_files.append(concat_path)
        
        with open(concat_path, "w", encoding="utf-8") as file:
            for path in normalized_paths:
                file.write(f"file '{path}'\n")
                
        output_path = _get_temp_path(".mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_path,
            "-c", "copy",
            output_path,
        ]
        success, error = _run_ffmpeg(cmd)
        _cleanup_files(intermediate_files)
        thumbnail_path = _generate_thumbnail(output_path) if success else None
        return success, error, output_path, thumbnail_path

    _process_job(job_id, object_keys, runner)


def process_add_audio_job(job_id: str, video_key: str, audio_key: str, replace: bool):
    def runner(local_paths):
        video_path = local_paths[0]
        audio_path = local_paths[1]
        output_path = _get_temp_path(".mp4")
        if replace:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first[a]",
                "-map", "0:v:0",
                "-map", "[a]",
                output_path,
            ]
        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [video_key, audio_key], runner)


def process_extract_audio_job(job_id: str, object_key: str, audio_format: str):
    def runner(local_paths):
        input_path = local_paths[0]
        if not _has_audio(input_path):
            return False, "Input video does not contain an audio stream to extract.", None, None

        codec_map = {
            "mp3": ("libmp3lame", ".mp3"),
            "wav": ("pcm_s16le", ".wav"),
            "aac": ("aac", ".aac"),
            "flac": ("flac", ".flac"),
        }
        codec, ext = codec_map.get(audio_format, ("libmp3lame", ".mp3"))
        output_path = _get_temp_path(ext)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-acodec", codec,
            output_path,
        ]
        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [object_key], runner)


def process_speed_job(job_id: str, object_key: str, speed: float, adjust_audio: bool):
    def runner(local_paths):
        input_path = local_paths[0]
        output_path = _get_temp_path(".mp4")
        video_filter = f"setpts={1 / speed}*PTS"
        has_audio = _has_audio(input_path)
        effective_adjust_audio = adjust_audio and has_audio

        if adjust_audio and not has_audio:
            logger.info("Video %s has no audio stream. Applying speed change to video only.", input_path)

        if effective_adjust_audio:
            audio_filter = f"atempo={speed}"
            if speed > 2.0:
                audio_filter = f"atempo=2.0,atempo={speed / 2.0}"
            elif speed < 0.5:
                audio_filter = f"atempo=0.5,atempo={speed / 0.5}"

            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-filter_complex",
                f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
                "-map", "[v]",
                "-map", "[a]",
                output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-filter:v", video_filter,
                "-an",
                output_path,
            ]

        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [object_key], runner)


def process_crop_job(job_id: str, object_key: str, width: int, height: int, x: int, y: int):
    def runner(local_paths):
        input_path = local_paths[0]
        output_path = _get_temp_path(".mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter:v", f"crop={width}:{height}:{x}:{y}",
            "-c:a", "copy",
            output_path,
        ]
        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [object_key], runner)


def process_resize_job(
    job_id: str,
    object_key: str,
    width: int,
    height: int,
    maintain_aspect: bool,
):
    def runner(local_paths):
        input_path = local_paths[0]
        output_path = _get_temp_path(".mp4")
        if maintain_aspect:
            scale_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            )
        else:
            scale_filter = f"scale={width}:{height}"

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", scale_filter,
            "-c:a", "copy",
            output_path,
        ]
        success, error = _run_ffmpeg(cmd)
        return success, error, output_path, None

    _process_job(job_id, [object_key], runner)


def process_extract_frames_job(
    job_id: str,
    object_key: str,
    first_frame: bool,
    last_frame: bool,
    timestamp: float | None
):
    def runner(local_paths):
        input_path = local_paths[0]
        output_zip_path = _get_temp_path(".zip")
        extracted_files = []
        errors = []

        if not first_frame and not last_frame and timestamp is None:
            return False, "At least one of first_frame, last_frame, or timestamp is required.", None, None

        duration = _get_video_duration(input_path) if last_frame else 0.0

        if first_frame:
            out_path = _get_temp_path(".jpg")
            cmd = ["ffmpeg", "-y", "-i", input_path, "-vframes", "1", "-q:v", "2", out_path]
            success, err = _run_ffmpeg(cmd)
            if success and os.path.exists(out_path):
                extracted_files.append(("first_frame.jpg", out_path))
            else:
                errors.append(f"First frame error: {err}")

        if last_frame and duration > 0:
            out_path = _get_temp_path(".jpg")
            seek_time = max(0.0, duration - 0.1)
            cmd = ["ffmpeg", "-y", "-ss", str(seek_time), "-i", input_path, "-vframes", "1", "-q:v", "2", out_path]
            success, err = _run_ffmpeg(cmd)
            if success and os.path.exists(out_path):
                extracted_files.append(("last_frame.jpg", out_path))
            else:
                errors.append(f"Last frame error: {err}")

        if timestamp is not None:
            out_path = _get_temp_path(".jpg")
            seek_time = max(0.0, float(timestamp))
            cmd = ["ffmpeg", "-y", "-ss", str(seek_time), "-i", input_path, "-vframes", "1", "-q:v", "2", out_path]
            success, err = _run_ffmpeg(cmd)
            if success and os.path.exists(out_path):
                extracted_files.append((f"frame_{timestamp}s.jpg", out_path))
            else:
                errors.append(f"Timestamp frame error: {err}")

        if not extracted_files:
            return False, f"Failed to extract any frames. Errors: {'; '.join(errors)}", None, None

        # Build ZIP Archive
        try:
            with zipfile.ZipFile(output_zip_path, 'w') as zipf:
                for arcname, fpath in extracted_files:
                    zipf.write(fpath, arcname)
        except Exception as e:
            return False, f"Failed to create ZIP archive: {str(e)}", None, None
        finally:
            for _, fpath in extracted_files:
                _cleanup_files([fpath])

        return True, "", output_zip_path, None

    _process_job(job_id, [object_key], runner)
