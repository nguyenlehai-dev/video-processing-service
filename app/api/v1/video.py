import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_user_from_api_key
from app.services import video_service
from app.schemas.video import VideoProcessResponse
from app.schemas.job import JobResponse, JobListResponse
from app.models.user import User
from app.models.job import Job
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/video", tags=["Video Processing"])


def _save_upload(upload: UploadFile) -> str:
    """Save an uploaded file to temp directory and return the path."""
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    ext = os.path.splitext(upload.filename or ".mp4")[1] or ".mp4"
    temp_path = os.path.join(settings.TEMP_DIR, f"{uuid.uuid4()}{ext}")

    with open(temp_path, "wb") as f:
        content = upload.file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            os.remove(temp_path)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
            )
        f.write(content)

    return temp_path


@router.post("/cut", response_model=VideoProcessResponse)
async def cut_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Cut a segment from a video.

    - **video**: Video file to cut
    - **start_time**: Start time (format: HH:MM:SS or seconds)
    - **end_time**: End time (format: HH:MM:SS or seconds)
    """
    input_path = _save_upload(video)
    job = video_service.cut_video(db, input_path, start_time, end_time, user.id)
    return VideoProcessResponse(job_id=job.id, message="Video cut processing", status=job.status)


@router.post("/merge", response_model=VideoProcessResponse)
async def merge_videos(
    background_tasks: BackgroundTasks,
    videos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Merge multiple videos into one.

    - **videos**: Multiple video files to merge (in order)
    """
    if len(videos) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 videos required for merging",
        )

    input_paths = [_save_upload(v) for v in videos]
    job = video_service.merge_videos(db, input_paths, user.id)
    return VideoProcessResponse(job_id=job.id, message="Video merge processing", status=job.status)


@router.post("/add-audio", response_model=VideoProcessResponse)
async def add_audio(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    replace: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Add or replace audio in a video.

    - **video**: Video file
    - **audio**: Audio file to add
    - **replace**: If true, replace existing audio. If false, mix with existing audio.
    """
    video_path = _save_upload(video)
    audio_path = _save_upload(audio)
    job = video_service.add_audio_to_video(db, video_path, audio_path, replace, user.id)
    return VideoProcessResponse(job_id=job.id, message="Audio add processing", status=job.status)


@router.post("/extract-audio", response_model=VideoProcessResponse)
async def extract_audio(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    format: str = Form(default="mp3"),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Extract audio from a video.

    - **video**: Video file to extract audio from
    - **format**: Output audio format (mp3, wav, aac, flac)
    """
    if format not in ["mp3", "wav", "aac", "flac"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: mp3, wav, aac, flac",
        )

    input_path = _save_upload(video)
    job = video_service.extract_audio(db, input_path, format, user.id)
    return VideoProcessResponse(job_id=job.id, message="Audio extraction processing", status=job.status)


@router.post("/speed", response_model=VideoProcessResponse)
async def change_speed(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    speed: float = Form(default=1.0),
    adjust_audio: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Change video playback speed.

    - **video**: Video file
    - **speed**: Speed multiplier (0.25-4.0). 0.5 = half speed, 2.0 = double speed.
    - **adjust_audio**: Whether to adjust audio speed accordingly
    """
    if not (0.25 <= speed <= 4.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speed must be between 0.25 and 4.0",
        )

    input_path = _save_upload(video)
    job = video_service.change_speed(db, input_path, speed, adjust_audio, user.id)
    return VideoProcessResponse(job_id=job.id, message="Speed change processing", status=job.status)


@router.post("/crop", response_model=VideoProcessResponse)
async def crop_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    x: int = Form(default=0),
    y: int = Form(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Crop video to specified region.

    - **video**: Video file to crop
    - **width**: Crop width in pixels
    - **height**: Crop height in pixels
    - **x**: Horizontal offset from left
    - **y**: Vertical offset from top
    """
    input_path = _save_upload(video)
    job = video_service.crop_video(db, input_path, width, height, x, y, user.id)
    return VideoProcessResponse(job_id=job.id, message="Video crop processing", status=job.status)


@router.post("/resize", response_model=VideoProcessResponse)
async def resize_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    maintain_aspect: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """
    Resize video to specified dimensions.

    - **video**: Video file to resize
    - **width**: Target width in pixels
    - **height**: Target height in pixels
    - **maintain_aspect**: Whether to maintain aspect ratio (pad if necessary)
    """
    input_path = _save_upload(video)
    job = video_service.resize_video(db, input_path, width, height, maintain_aspect, user.id)
    return VideoProcessResponse(job_id=job.id, message="Video resize processing", status=job.status)


# ===== JOB TRACKING =====


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """List all processing jobs for the current user."""
    jobs = db.query(Job).filter(Job.user_id == user.id).order_by(
        Job.created_at.desc()
    ).offset(skip).limit(limit).all()
    total = db.query(Job).filter(Job.user_id == user.id).count()
    return JobListResponse(jobs=jobs, total=total)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    """Get the status and details of a processing job."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job
