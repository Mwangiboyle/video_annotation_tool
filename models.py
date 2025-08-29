# %%

from pydantic import BaseModel
from typing import Optional

class VideoCreate(BaseModel):
    title: str
    video_url: Optional[str] = None

class Video(VideoCreate):
    id: str   # UUID in Supabase

class AnnotationCreate(BaseModel):
    start_time: float
    end_time: float
    description: str

class Annotation(AnnotationCreate):
    id: str
    video_id: str
    duration: float   # new field





