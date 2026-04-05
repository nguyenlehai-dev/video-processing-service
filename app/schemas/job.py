from pydantic import BaseModel
from datetime import datetime


class JobResponse(BaseModel):
    id: str
    operation: str
    status: str
    progress: float
    output_url: str | None = None
    output_filename: str | None = None
    error_message: str | None = None
    file_size: float | None = None
    duration: float | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
