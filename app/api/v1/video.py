import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Form, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_user_from_api_key
from app.services import video_service
from app.services.storage_service import get_file_path, generate_presigned_put_url
from app.schemas.video import VideoProcessResponse
from app.schemas.job import JobResponse, JobListResponse, JobInitRequest, JobInitResponse, JobProgressRequest
from app.models.user import User
from app.models.job import Job
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/video", tags=["Video Processing"])

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
    
    import urllib.parse
    for filename in request.filenames:
        if filename.startswith("http://") or filename.startswith("https://"):
            parsed = urllib.parse.urlparse(filename)
            if "plenxai.com" in filename or "plxeditor.com" in filename or "r2.dev" in filename:
                # Bypass upload and use existing keys
                object_key = parsed.path.lstrip("/")
                upload_urls.append("") # Mark as no upload
                object_keys.append(object_key)
                input_files.append({"filename": filename.split("/")[-1], "object_key": object_key})
                continue
            else:
                raise HTTPException(status_code=400, detail=f"External URLs not supported yet: {filename}")

        ext = os.path.splitext(filename)[1] or ".mp4"
        object_key = f"input/{job_id}_{str(uuid.uuid4())[:8]}{ext}"
        presigned_url = generate_presigned_put_url(object_key)
        
        if not presigned_url:
            raise HTTPException(status_code=500, detail="Could not generate presigned URL for storage")
            
        upload_urls.append(presigned_url)
        object_keys.append(object_key)
        input_files.append({"filename": filename, "object_key": object_key})
        
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

@router.post("/cut", response_model=VideoProcessResponse)
async def cut_video(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"start_time": start_time, "end_time": end_time}
    job.status = "pending"
    job.progress = 0.0
    db.commit()
    
    background_tasks.add_task(video_service.process_cut_job, job.id, job.input_files[0]["object_key"], start_time, end_time)
    return VideoProcessResponse(job_id=job.id, message="Video cut job processing started", status=job.status)

@router.post("/merge", response_model=VideoProcessResponse)
async def merge_videos(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"file_count": len(job.input_files)}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_merge_job, job.id, [f["object_key"] for f in job.input_files])
    return VideoProcessResponse(job_id=job.id, message="Video merge job accepted", status=job.status)

@router.post("/add-audio", response_model=VideoProcessResponse)
async def add_audio(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    replace: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"replace": replace}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_add_audio_job, job.id, job.input_files[0]["object_key"], job.input_files[1]["object_key"], replace)
    return VideoProcessResponse(job_id=job.id, message="Add-audio job accepted", status=job.status)

@router.post("/extract-audio", response_model=VideoProcessResponse)
async def extract_audio(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    format: str = Form(default="mp3"),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"format": format}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_extract_audio_job, job.id, job.input_files[0]["object_key"], format)
    return VideoProcessResponse(job_id=job.id, message="Extract-audio job accepted", status=job.status)

@router.post("/speed", response_model=VideoProcessResponse)
async def change_speed(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    speed: float = Form(default=1.0),
    adjust_audio: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"speed": speed, "adjust_audio": adjust_audio}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_speed_job, job.id, job.input_files[0]["object_key"], speed, adjust_audio)
    return VideoProcessResponse(job_id=job.id, message="Speed job accepted", status=job.status)

@router.post("/crop", response_model=VideoProcessResponse)
async def crop_video(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    x: int = Form(default=0),
    y: int = Form(default=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"width": width, "height": height, "x": x, "y": y}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_crop_job, job.id, job.input_files[0]["object_key"], width, height, x, y)
    return VideoProcessResponse(job_id=job.id, message="Crop job accepted", status=job.status)

@router.post("/resize", response_model=VideoProcessResponse)
async def resize_video(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    maintain_aspect: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.params = {"width": width, "height": height, "maintain_aspect": maintain_aspect}
    job.status = "pending"
    db.commit()
    
    background_tasks.add_task(video_service.process_resize_job, job.id, job.input_files[0]["object_key"], width, height, maintain_aspect)
    return VideoProcessResponse(job_id=job.id, message="Resize job accepted", status=job.status)

@router.post("/extract-frames", response_model=VideoProcessResponse)
async def extract_frames(
    background_tasks: BackgroundTasks,
    job_id: str = Form(...),
    first_frame: bool = Form(default=False),
    last_frame: bool = Form(default=False),
    timestamp: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_user_from_api_key),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
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
        
    # Reset status
    job.status = "pending"
    job.progress = 0.0
    job.error_message = None
    job.output_url = None
    job.completed_at = None
    db.commit()

    # Route based on operation
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
        # Invalid operation
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
