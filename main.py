# %%
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from supabase import create_client, Client
from models import VideoCreate, AnnotationCreate, Annotation, ScriptGenerateRequest
from typing import List
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import openai


# Load env vars
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

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

@app.get("/script-generator", response_class=HTMLResponse)
def script_generator(request: Request):
    return templates.TemplateResponse("script_generator.html", {"request": request})

# --- API Endpoints (existing) ---

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

# --- New OpenAI Script Generation Endpoint ---

@app.post("/generate-script")
async def generate_script(request: ScriptGenerateRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # Create prompt for OpenAI
        prompt = f"""
        Create a voice script for a video segment with the following details:

        Duration: {request.duration} seconds
        Description/Context: {request.annotation}

        Additional requirements:
        - The script should be exactly {request.duration} seconds when read at a normal pace (approximately 150-180 words per minute)
        - Make it engaging and natural for voice narration
        - Focus on the key points mentioned in the description
        - Include appropriate pauses and transitions

        Please provide only the script text, no additional formatting or explanations.
        """

        # Use OpenAI API (updated for newer versions)
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # or "gpt-4" if you prefer
            messages=[
                {"role": "system", "content": "You are a professional scriptwriter specializing in voice-over scripts for video content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        script = response.choices[0].message.content.strip()

        return {
            "script": script,
            "duration": request.duration,
            "annotation": request.annotation,
            "estimated_word_count": len(script.split())
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating script: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
if __name__ == "__main__":
    uvicorn.run(app, port=8000)

