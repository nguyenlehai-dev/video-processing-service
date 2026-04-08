import os
import uuid
import tempfile
import urllib.parse
import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Form, BackgroundTasks, status, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_user_from_api_key
from app.services import video_service
from app.services.storage_service import (
    get_file_path,
    generate_presigned_put_url,
    get_storage_backend,
    upload_file_to_storage,
    storage_object_exists,
)
from app.schemas.video import VideoProcessResponse
from app.schemas.job import JobResponse, JobListResponse, JobInitRequest, JobInitResponse, JobProgressRequest
from app.models.user import User
from app.models.job import Job
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/video", tags=["Video Processing"])


def _validate_upload_size(filename: str, size_bytes: int) -> None:
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File {filename} exceeds max upload size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )


def _normalize_hostname(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.split("@")[-1].split(":")[0].lower()


def _is_domain_allowed(url: str) -> bool:
    whitelist = [domain.strip().lower() for domain in settings.ALLOWED_DOMAIN_WHITELIST.split(",") if domain.strip()]
    if "*" in whitelist or not whitelist:
        return True

    hostname = _normalize_hostname(url)
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in whitelist)


def _build_local_upload_token(job_id: str, object_key: str) -> str:
    payload = f"{job_id}:{object_key}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _build_local_upload_url(job_id: str, input_index: int, object_key: str) -> str:
    token = _build_local_upload_token(job_id, object_key)
    return f"/api/v1/video/jobs/{job_id}/upload/{input_index}?token={token}"

@router.post("/jobs/init", response_model=JobInitResponse)
async def init_upload_job(
    request: JobInitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    upload_urls = []
    object_keys = []
    input_files = []
    
    job_id = str(uuid.uuid4())
    
    for filename in request.filenames:
        if filename.startswith("http://") or filename.startswith("https://"):
            parsed = urllib.parse.urlparse(filename)
            if _is_domain_allowed(filename):
                r2_domain = urllib.parse.urlparse(settings.R2_PUBLIC_URL).netloc
                
                if parsed.netloc == r2_domain:
                    object_key = parsed.path.lstrip("/")
                else:
                    object_key = filename
                    
                upload_urls.append("") 
                object_keys.append(object_key)
                
                filename_clean = filename.split("/")[-1].split("?")[0] or "video.mp4"
                input_files.append(
                    {
                        "filename": filename_clean,
                        "object_key": object_key,
                        "managed": False,
                    }
                )
                continue
            else:
                raise HTTPException(status_code=400, detail=f"Domain not in whitelist: {filename}")

        ext = os.path.splitext(filename)[1] or ".mp4"
        object_key = f"input/{job_id}_{str(uuid.uuid4())[:8]}{ext}"
        presigned_url = generate_presigned_put_url(object_key)

        if not presigned_url and get_storage_backend() == "local":
            presigned_url = _build_local_upload_url(job_id, len(input_files), object_key)

        if not presigned_url:
            raise HTTPException(status_code=500, detail="Could not generate presigned URL for storage")
            
        upload_urls.append(presigned_url)
        object_keys.append(object_key)
        input_files.append(
            {
                "filename": filename,
                "object_key": object_key,
                "managed": True,
            }
        )
        
    if not input_files:
        raise HTTPException(status_code=400, detail="Must provide at least one filename or file_url")

    job = Job(
        id=job_id,
        operation=request.tool_name,
        status="uploading",
        progress=0.0,
        user_id=user.id,
        input_files=input_files,
    )
    db.add(job)
    db.commit()
    return JobInitResponse(job_id=job.id, upload_urls=upload_urls, object_keys=object_keys)

@router.put("/jobs/{job_id}/upload-progress")
async def update_job_progress(
    job_id: str,
    request: JobProgressRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "uploading":
        job.progress = float(request.progress)
        db.commit()
    return {"status": "ok"}


@router.put("/jobs/{job_id}/upload/{input_index}")
async def upload_job_file(
    job_id: str,
    input_index: int,
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if input_index < 0 or input_index >= len(job.input_files or []):
        raise HTTPException(status_code=404, detail="Upload target not found")

    input_file = job.input_files[input_index]
    object_key = input_file.get("object_key")
    if not object_key or input_file.get("managed") is not True:
        raise HTTPException(status_code=400, detail="Upload target is not managed by this service")

    expected_token = _build_local_upload_token(job_id, object_key)
    if not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid upload token")

    filename = input_file.get("filename") or os.path.basename(object_key)
    ext = os.path.splitext(filename)[1] or ".mp4"
    content = await request.body()
    _validate_upload_size(filename, len(content))

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        upload_file_to_storage(
            tmp_path,
            object_key,
            content_type=request.headers.get("content-type"),
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def resolve_job_inputs(
    db: Session,
    user: User,
    tool_name: str,
    job_id: str | None = None,
    video_url: str | None = None,
    video: UploadFile | None = None,
    audio_url: str | None = None,
    audio: UploadFile | None = None,
    video_urls: list[str] | None = None,
    videos: list[UploadFile] | None = None,
) -> Job:
    """Helper to dynamically fetch an existing Job OR create one via File/URL bypassing."""
    if job_id:
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    if not any([video_url, video, audio_url, audio, video_urls, videos]):
        raise HTTPException(status_code=400, detail="Must provide job_id, url parameters, or file uploads")

    new_job_id = str(uuid.uuid4())
    input_files = []
    
    async def process_single_input(url_val: str | None, file_val: UploadFile | None):
        if url_val:
            parsed = urllib.parse.urlparse(url_val)
            if _is_domain_allowed(url_val):
                r2_domain = urllib.parse.urlparse(settings.R2_PUBLIC_URL).netloc
                
                if parsed.netloc == r2_domain:
                    object_key = parsed.path.lstrip("/")
                else:
                    object_key = url_val
                    
                filename_clean = url_val.split("/")[-1].split("?")[0] or "video.mp4"
                return {
                    "filename": filename_clean,
                    "object_key": object_key,
                    "managed": False,
                }
            else:
                raise HTTPException(status_code=400, detail=f"Domain not in whitelist: {url_val}")
        elif file_val:
            ext = os.path.splitext(file_val.filename)[1] or ".mp4"
            object_key = f"input/{new_job_id}_{str(uuid.uuid4())[:8]}{ext}"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                content = await file_val.read()
                _validate_upload_size(file_val.filename, len(content))
                tmp.write(content)
                tmp_path = tmp.name
                
            try:
                upload_file_to_storage(tmp_path, object_key, content_type=file_val.content_type)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            return {
                "filename": file_val.filename,
                "object_key": object_key,
                "managed": True,
            }
        return None

    if video_url or video:
        res = await process_single_input(video_url, video)
        if res: input_files.append(res)
        
    if audio_url or audio:
        res = await process_single_input(audio_url, audio)
        if res: input_files.append(res)
        
    if video_urls:
        for url in video_urls:
            res = await process_single_input(url, None)
            if res: input_files.append(res)
            
    if videos:
        for f in videos:
            res = await process_single_input(None, f)
            if res: input_files.append(res)
            
    if not input_files:
        raise HTTPException(status_code=400, detail="Could not resolve any input files")

    job = Job(
        id=new_job_id,
        operation=tool_name,
        status="pending",
        progress=0.0,
        user_id=user.id,
        input_files=input_files,
    )
    db.add(job)
    db.commit()
    return job

@router.post("/cut", response_model=VideoProcessResponse)
async def cut_video(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "cut", job_id=job_id, video_url=video_url, video=video)
    job.params = {"start_time": start_time, "end_time": end_time}
    job.status = "pending"
    job.progress = 0.0
    db.commit()
    
    background_tasks.add_task(video_service.process_cut_job, job.id, job.input_files[0]["object_key"], start_time, end_time)
    return VideoProcessResponse(job_id=job.id, message="Video cut job processing started", status=job.status)

@router.post("/merge", response_model=VideoProcessResponse)
async def merge_videos(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_urls: list[str] | None = Form(None),
    videos: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "merge", job_id=job_id, video_urls=video_urls, videos=videos)
    job.params = {"file_count": len(job.input_files)}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_merge_job, job.id, [f["object_key"] for f in job.input_files])
    return VideoProcessResponse(job_id=job.id, message="Video merge job accepted", status=job.status)

@router.post("/add-audio", response_model=VideoProcessResponse)
async def add_audio(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    audio_url: str | None = Form(None),
    audio: UploadFile | None = File(None),
    replace: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "add-audio", job_id=job_id, video_url=video_url, video=video, audio_url=audio_url, audio=audio)
    if len(job.input_files) < 2:
        raise HTTPException(status_code=400, detail="Add-audio requires resolving both video and audio files")
    job.params = {"replace": replace}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_add_audio_job, job.id, job.input_files[0]["object_key"], job.input_files[1]["object_key"], replace)
    return VideoProcessResponse(job_id=job.id, message="Add-audio job accepted", status=job.status)

@router.post("/extract-audio", response_model=VideoProcessResponse)
async def extract_audio(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    format: str = Form(default="mp3"),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "extract-audio", job_id=job_id, video_url=video_url, video=video)
    job.params = {"format": format}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_extract_audio_job, job.id, job.input_files[0]["object_key"], format)
    return VideoProcessResponse(job_id=job.id, message="Extract-audio job accepted", status=job.status)

@router.post("/speed", response_model=VideoProcessResponse)
async def change_speed(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    speed: float = Form(default=1.0),
    adjust_audio: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "speed", job_id=job_id, video_url=video_url, video=video)
    job.params = {"speed": speed, "adjust_audio": adjust_audio}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_speed_job, job.id, job.input_files[0]["object_key"], speed, adjust_audio)
    return VideoProcessResponse(job_id=job.id, message="Speed job accepted", status=job.status)

@router.post("/crop", response_model=VideoProcessResponse)
async def crop_video(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    width: int = Form(...),
    height: int = Form(...),
    x: int = Form(default=0),
    y: int = Form(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "crop", job_id=job_id, video_url=video_url, video=video)
    job.params = {"width": width, "height": height, "x": x, "y": y}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_crop_job, job.id, job.input_files[0]["object_key"], width, height, x, y)
    return VideoProcessResponse(job_id=job.id, message="Crop job accepted", status=job.status)

@router.post("/resize", response_model=VideoProcessResponse)
async def resize_video(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    width: int = Form(...),
    height: int = Form(...),
    maintain_aspect: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = await resolve_job_inputs(db, user, "resize", job_id=job_id, video_url=video_url, video=video)
    job.params = {"width": width, "height": height, "maintain_aspect": maintain_aspect}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_resize_job, job.id, job.input_files[0]["object_key"], width, height, maintain_aspect)
    return VideoProcessResponse(job_id=job.id, message="Resize job accepted", status=job.status)

@router.post("/extract-frames", response_model=VideoProcessResponse)
async def extract_frames(
    background_tasks: BackgroundTasks,
    job_id: str | None = Form(None),
    video_url: str | None = Form(None),
    video: UploadFile | None = File(None),
    first_frame: bool = Form(default=False),
    last_frame: bool = Form(default=False),
    timestamp: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    if not first_frame and not last_frame and timestamp is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of first_frame, last_frame, or timestamp is required",
        )

    job = await resolve_job_inputs(db, user, "extract-frames", job_id=job_id, video_url=video_url, video=video)
    job.params = {"first_frame": first_frame, "last_frame": last_frame, "timestamp": timestamp}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_extract_frames_job, job.id, job.input_files[0]["object_key"], first_frame, last_frame, timestamp)
    return VideoProcessResponse(job_id=job.id, message="Extract frames job accepted", status=job.status)

@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    jobs = db.query(Job).filter(Job.user_id == user.id).order_by(
        Job.created_at.desc()
    ).offset(skip).limit(limit).all()
    total = db.query(Job).filter(Job.user_id == user.id).count()
    return JobListResponse(jobs=jobs, total=total)

async def _get_job_or_404(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    return await _get_job_or_404(job_id, db, user)


@router.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status_legacy(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    return await _get_job_or_404(job_id, db, user)

@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status not in ["failed", "pending"]:
        raise HTTPException(status_code=400, detail="Only failed or pending jobs can be retried")
        
    if not job.params or not job.input_files:
        raise HTTPException(status_code=400, detail="Job does not have enough parameters to retry")

    missing_inputs = [
        input_file["object_key"]
        for input_file in job.input_files
        if input_file.get("object_key")
        and not (
            input_file["object_key"].startswith("http://")
            or input_file["object_key"].startswith("https://")
        )
        and not storage_object_exists(input_file["object_key"])
    ]
    if missing_inputs:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry because input is missing from storage: {missing_inputs[0]}",
        )
        
    job.status = "pending"
    job.progress = 0.0
    job.error_message = None
    job.output_url = None
    job.completed_at = None
    db.commit()

    p = job.params
    op = job.operation
    
    if op == "cut":
        background_tasks.add_task(video_service.process_cut_job, job.id, job.input_files[0]["object_key"], p.get("start_time"), p.get("end_time"))
    elif op == "merge":
        background_tasks.add_task(video_service.process_merge_job, job.id, [f["object_key"] for f in job.input_files])
    elif op == "add-audio":
        background_tasks.add_task(video_service.process_add_audio_job, job.id, job.input_files[0]["object_key"], job.input_files[1]["object_key"], p.get("replace"))
    elif op == "extract-audio":
        background_tasks.add_task(video_service.process_extract_audio_job, job.id, job.input_files[0]["object_key"], p.get("format"))
    elif op == "speed":
        background_tasks.add_task(video_service.process_speed_job, job.id, job.input_files[0]["object_key"], p.get("speed"), p.get("adjust_audio"))
    elif op == "crop":
        background_tasks.add_task(video_service.process_crop_job, job.id, job.input_files[0]["object_key"], p.get("width"), p.get("height"), p.get("x"), p.get("y"))
    elif op == "resize":
        background_tasks.add_task(video_service.process_resize_job, job.id, job.input_files[0]["object_key"], p.get("width"), p.get("height"), p.get("maintain_aspect"))
    elif op == "extract-frames":
        background_tasks.add_task(video_service.process_extract_frames_job, job.id, job.input_files[0]["object_key"], p.get("first_frame"), p.get("last_frame"), p.get("timestamp"))
    else:
        job.status = "failed"
        job.error_message = "Unknown operation"
        db.commit()
        raise HTTPException(status_code=400, detail="Unknown operation type")
        
    return job

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = get_file_path(filename)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )
