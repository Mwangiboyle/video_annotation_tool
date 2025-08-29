from pydantic import BaseModel
from typing import Optional, List

class VideoCreate(BaseModel):
    title: str
    video_url: Optional[str] = None

class Video(VideoCreate):
    id: int

class AnnotationCreate(BaseModel):
    start_time: float
    end_time: float
    description: str

class Annotation(AnnotationCreate):
    id: int
    video_id: int




