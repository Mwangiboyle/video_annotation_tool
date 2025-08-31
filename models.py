# %%

from pydantic import BaseModel
from typing import Optional, Literal

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
    # Audio-related fields
    has_audio: Optional[bool] = False
    audio_base64: Optional[str] = None
    audio_filename: Optional[str] = None
    audio_voice: Optional[str] = None
    audio_speed: Optional[float] = None
    audio_size_bytes: Optional[int] = None

class AudioGenerateRequest(BaseModel):
    text: Optional[str] = None  # If not provided, will use script text
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy"
    speed: float = 1.0  # 0.25 to 4.0

class AudioResponse(BaseModel):
    audio_base64: str
    filename: str
    size_bytes: int
    voice: str
    speed: float
    text_length: int
