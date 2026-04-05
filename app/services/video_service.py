import subprocess
import os
import uuid
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.job import Job
from app.services.storage_service import upload_file_to_r2
from app.config import get_settings

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
    """
    Run an FFmpeg command.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        if result.returncode != 0:
            error = result.stderr or "Unknown FFmpeg error"
            logger.error(f"FFmpeg error: {error}")
            return False, error
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "FFmpeg processing timed out (10 minutes)"
    except Exception as e:
        return False, str(e)


def _finalize_job(
    db: Session,
    job: Job,
    output_path: str,
    start_time: float,
    input_paths: list[str] | None = None,
):
    """Upload output to R2, update job, and clean up temp files."""
    try:
        # Get file size
        file_size = os.path.getsize(output_path)
        ext = os.path.splitext(output_path)[1]
        object_name = f"output/{job.id}{ext}"

        # Upload to R2
        public_url = upload_file_to_r2(output_path, object_name)

        if public_url:
            job.status = "completed"
            job.output_url = public_url
            job.output_filename = f"{job.operation}_{job.id[:8]}{ext}"
            job.file_size = file_size
            job.progress = 100.0
        else:
            job.status = "failed"
            job.error_message = "Failed to upload to R2 storage"

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        logger.error(f"Job {job.id} failed: {e}")

    finally:
        job.duration = time.time() - start_time
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Clean up temp files
        _cleanup_files([output_path] + (input_paths or []))


def _cleanup_files(paths: list[str]):
    """Remove temporary files."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Failed to clean up {path}: {e}")


def _create_job(db: Session, operation: str, user_id: str, params: dict = None) -> Job:
    """Create a new processing job."""
    job = Job(
        operation=operation,
        status="processing",
        progress=0.0,
        params=params,
        user_id=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ===== VIDEO PROCESSING FUNCTIONS =====


def cut_video(
    db: Session,
    input_path: str,
    start_time: str,
    end_time: str,
    user_id: str,
) -> Job:
    """Cut a video segment between start_time and end_time."""
    job = _create_job(db, "cut", user_id, {"start_time": start_time, "end_time": end_time})
    t0 = time.time()

    output_path = _get_temp_path(".mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", start_time,
        "-to", end_time,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]

    success, error = _run_ffmpeg(cmd)
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([input_path])
        return job

    _finalize_job(db, job, output_path, t0, [input_path])
    return job


def merge_videos(
    db: Session,
    input_paths: list[str],
    user_id: str,
) -> Job:
    """Merge multiple videos into one."""
    job = _create_job(db, "merge", user_id, {"file_count": len(input_paths)})
    t0 = time.time()

    # Create concat file
    concat_path = _get_temp_path(".txt")
    with open(concat_path, "w") as f:
        for path in input_paths:
            f.write(f"file '{path}'\n")

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
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files(input_paths + [concat_path])
        return job

    _finalize_job(db, job, output_path, t0, input_paths + [concat_path])
    return job


def add_audio_to_video(
    db: Session,
    video_path: str,
    audio_path: str,
    replace: bool,
    user_id: str,
) -> Job:
    """Add or replace audio track in a video."""
    job = _create_job(db, "add-audio", user_id, {"replace": replace})
    t0 = time.time()

    output_path = _get_temp_path(".mp4")

    if replace:
        # Replace existing audio entirely
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
        # Mix audio (overlay)
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
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([video_path, audio_path])
        return job

    _finalize_job(db, job, output_path, t0, [video_path, audio_path])
    return job


def extract_audio(
    db: Session,
    input_path: str,
    audio_format: str,
    user_id: str,
) -> Job:
    """Extract audio from a video file."""
    job = _create_job(db, "extract-audio", user_id, {"format": audio_format})
    t0 = time.time()

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
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([input_path])
        return job

    _finalize_job(db, job, output_path, t0, [input_path])
    return job


def change_speed(
    db: Session,
    input_path: str,
    speed: float,
    adjust_audio: bool,
    user_id: str,
) -> Job:
    """Change video playback speed."""
    job = _create_job(db, "speed", user_id, {"speed": speed, "adjust_audio": adjust_audio})
    t0 = time.time()

    output_path = _get_temp_path(".mp4")

    # Video speed: setpts=PTS/speed (inverse relationship)
    video_filter = f"setpts={1/speed}*PTS"

    if adjust_audio:
        audio_filter = f"atempo={speed}"
        # atempo only supports 0.5-2.0, chain for larger values
        if speed > 2.0:
            audio_filter = "atempo=2.0,atempo=" + str(speed / 2.0)
        elif speed < 0.5:
            audio_filter = "atempo=0.5,atempo=" + str(speed / 0.5)

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
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([input_path])
        return job

    _finalize_job(db, job, output_path, t0, [input_path])
    return job


def crop_video(
    db: Session,
    input_path: str,
    width: int,
    height: int,
    x: int,
    y: int,
    user_id: str,
) -> Job:
    """Crop video to specified dimensions and position."""
    job = _create_job(db, "crop", user_id, {"width": width, "height": height, "x": x, "y": y})
    t0 = time.time()

    output_path = _get_temp_path(".mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", f"crop={width}:{height}:{x}:{y}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = _run_ffmpeg(cmd)
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([input_path])
        return job

    _finalize_job(db, job, output_path, t0, [input_path])
    return job


def resize_video(
    db: Session,
    input_path: str,
    width: int,
    height: int,
    maintain_aspect: bool,
    user_id: str,
) -> Job:
    """Resize video to specified dimensions."""
    job = _create_job(db, "resize", user_id, {
        "width": width, "height": height, "maintain_aspect": maintain_aspect
    })
    t0 = time.time()

    output_path = _get_temp_path(".mp4")

    if maintain_aspect:
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
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
    if not success:
        job.status = "failed"
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        job.duration = time.time() - t0
        db.commit()
        _cleanup_files([input_path])
        return job

    _finalize_job(db, job, output_path, t0, [input_path])
    return job
