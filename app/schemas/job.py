from pydantic import BaseModel, ConfigDict
from datetime import datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    operation: str
    status: str
    progress: float
    output_url: str | None = None
    thumbnail_url: str | None = None
    has_audio: bool | None = None
    output_duration: float | None = None
    output_filename: str | None = None
    error_message: str | None = None
    file_size: float | None = None
    duration: float | None = None
    created_at: datetime
    completed_at: datetime | None = None
    params: dict | None = None
    input_files: list | None = None


class JobInitRequest(BaseModel):
    tool_name: str
    filenames: list[str]


class JobInitResponse(BaseModel):
    job_id: str
    upload_urls: list[str]
    object_keys: list[str]


class JobProgressRequest(BaseModel):
    progress: int


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
