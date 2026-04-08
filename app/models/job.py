from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Float, func
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operation = Column(String, nullable=False)  # cut, merge, add-audio, etc.
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)       # 0-100
    input_files = Column(JSON, nullable=True)   # List of input file info
    output_url = Column(String, nullable=True)   # R2 public URL after completion
    output_filename = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    params = Column(JSON, nullable=True)         # Processing parameters
    file_size = Column(Float, nullable=True)     # Output file size in bytes
    duration = Column(Float, nullable=True)      # Processing duration in seconds
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")

    @property
    def thumbnail_url(self) -> str | None:
        if isinstance(self.params, dict):
            return self.params.get("thumbnail_url")
        return None
