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

class ScriptGenerateRequest(BaseModel):
    duration: float
    annotation: str

class VoiceScriptCreate(BaseModel):
    video_id: str
    annotation_id: Optional[str] = None
    duration: float
    original_annotation: str
    generated_script: str
    order_index: Optional[int] = None

class VoiceScript(VoiceScriptCreate):
    id: str
    created_at: str
