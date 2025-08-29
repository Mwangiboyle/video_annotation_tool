# %%


import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from supabase import create_client, Client
from models import VideoCreate, AnnotationCreate, Annotation
from typing import List
import uvicorn
from fastapi.middleware.cors import CORSMiddleware


# Load env vars
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Video Timestamp Annotation Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, be more specific
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static/templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- API Endpoints (reuse from before) ---

@app.post("/videos")
def create_video(video: VideoCreate):
    data = supabase.table("videos").insert(video.model_dump()).execute()
    if not data.data:
        raise HTTPException(status_code=500, detail="Error inserting video")
    return data.data[0]

@app.get("/videos")
def list_videos():
    data = supabase.table("videos").select("*").execute()
    return data.data

@app.post("/videos/{video_id}/annotations", response_model=Annotation)
def add_annotation(video_id: str, annotation: AnnotationCreate):
    # Validation: prevent invalid timestamps
    if annotation.end_time <= annotation.start_time:
        raise HTTPException(
            status_code=400,
            detail="Invalid timestamps: end_time must be greater than start_time"
        )

    duration = annotation.end_time - annotation.start_time
    new_data = {**annotation.model_dump(), "video_id": video_id, "duration": duration}
    data = supabase.table("annotations").insert(new_data).execute()
    if not data.data:
        raise HTTPException(status_code=500, detail="Error inserting annotation")
    return data.data[0]

@app.put("/annotations/{annotation_id}", response_model=Annotation)
def update_annotation(annotation_id: str, annotation: AnnotationCreate):
    # Validation: prevent invalid timestamps
    if annotation.end_time <= annotation.start_time:
        raise HTTPException(
            status_code=400,
            detail="Invalid timestamps: end_time must be greater than start_time"
        )

    # Calculate duration
    duration = annotation.end_time - annotation.start_time
    update_data = {**annotation.model_dump(), "duration": duration}

    data = supabase.table("annotations").update(update_data).eq("id", annotation_id).execute()
    if not data.data:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return data.data[0]


@app.get("/videos/{video_id}/annotations")
def list_annotations(video_id: str):
    data = supabase.table("annotations").select("*").eq("video_id", video_id).execute()
    return data.data

if __name__ == "__main__":
    uvicorn.run(app, port=8000)

