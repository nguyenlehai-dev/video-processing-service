from pydantic import BaseModel


class VideoCutRequest(BaseModel):
    start_time: str  # Format: HH:MM:SS or seconds
    end_time: str


class VideoMergeRequest(BaseModel):
    """For merge, multiple files are uploaded via form data."""
    pass


class VideoAddAudioRequest(BaseModel):
    replace: bool = False  # Replace existing audio or mix


class VideoExtractAudioRequest(BaseModel):
    format: str = "mp3"  # mp3, wav, aac


class VideoSpeedRequest(BaseModel):
    speed: float = 1.0   # 0.5 = half speed, 2.0 = double speed
    adjust_audio: bool = True


class VideoCropRequest(BaseModel):
    width: int
    height: int
    x: int = 0
    y: int = 0


class VideoResizeRequest(BaseModel):
    width: int
    height: int
    maintain_aspect: bool = True


class VideoProcessResponse(BaseModel):
    job_id: str
    message: str
    status: str = "pending"
    thumbnail_url: str | None = None
    has_audio: bool | None = None
    output_duration: float | None = None
