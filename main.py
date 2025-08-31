# %%


import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from supabase import create_client, Client
from models import VideoCreate, AnnotationCreate, Annotation, ScriptGenerateRequest, VoiceScriptCreate, VoiceScript, AudioGenerateRequest
from typing import List
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import openai
import base64
import uuid
from io import BytesIO


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

@app.delete("/annotations/{annotation_id}")
def delete_annotation(annotation_id: str):
    data = supabase.table("annotations").delete().eq("id", annotation_id).execute()
    if not data.data:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"message": "Annotation deleted successfully"}

# --- Voice Scripts Endpoints ---

@app.post("/voice-scripts", response_model=VoiceScript)
def save_voice_script(script: VoiceScriptCreate):
    data = supabase.table("voice_scripts").insert(script.model_dump()).execute()
    if not data.data:
        raise HTTPException(status_code=500, detail="Error saving voice script")
    return data.data[0]

@app.get("/videos/{video_id}/voice-scripts")
def list_voice_scripts(video_id: str):
    data = supabase.table("voice_scripts").select("*").eq("video_id", video_id).order("order_index").execute()
    return data.data

@app.put("/voice-scripts/{script_id}", response_model=VoiceScript)
def update_voice_script(script_id: str, script_data: dict):
    data = supabase.table("voice_scripts").update(script_data).eq("id", script_id).execute()
    if not data.data:
        raise HTTPException(status_code=404, detail="Voice script not found")
    return data.data[0]

@app.delete("/voice-scripts/{script_id}")
def delete_voice_script(script_id: str):
    data = supabase.table("voice_scripts").delete().eq("id", script_id).execute()
    if not data.data:
        raise HTTPException(status_code=404, detail="Voice script not found")
    return {"message": "Voice script deleted successfully"}

@app.get("/videos/{video_id}/combined-script")
def get_combined_script(video_id: str):
    """Get all voice scripts for a video combined into one"""
    data = supabase.table("voice_scripts").select("*").eq("video_id", video_id).order("order_index").execute()
    scripts = data.data

    if not scripts:
        return {"combined_script": "", "total_duration": 0, "script_count": 0}

    combined_text = "\n\n".join([script["generated_script"] for script in scripts])
    total_duration = sum([script["duration"] for script in scripts])

    return {
        "combined_script": combined_text,
        "total_duration": total_duration,
        "script_count": len(scripts),
        "scripts": scripts
    }

# --- OpenAI Script Generation Endpoint ---

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

# --- NEW: Audio Generation Endpoints ---

@app.post("/generate-audio")
async def generate_audio(request: AudioGenerateRequest):
    """Generate audio from text using OpenAI's text-to-speech API"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # Generate audio using OpenAI's TTS API
        response = openai.audio.speech.create(
            model="tts-1",  # or "tts-1-hd" for higher quality
            voice=request.voice,  # alloy, echo, fable, onyx, nova, shimmer
            input=request.text,
            response_format="mp3",
            speed=request.speed  # 0.25 to 4.0, default is 1.0
        )

        # Convert the audio response to base64
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Generate a unique filename
        audio_filename = f"audio_{uuid.uuid4().hex}.mp3"

        return {
            "audio_base64": audio_base64,
            "filename": audio_filename,
            "size_bytes": len(audio_data),
            "voice": request.voice,
            "speed": request.speed,
            "text_length": len(request.text)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@app.post("/voice-scripts/{script_id}/generate-audio")
async def generate_audio_for_script(script_id: str, request: AudioGenerateRequest):
    """Generate audio for a specific voice script and save it to the database"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # First, get the voice script
        script_data = supabase.table("voice_scripts").select("*").eq("id", script_id).execute()
        if not script_data.data:
            raise HTTPException(status_code=404, detail="Voice script not found")

        script = script_data.data[0]

        # Use the script text if no custom text provided
        text_to_convert = request.text if request.text else script["generated_script"]

        # Generate audio using OpenAI's TTS API
        response = openai.audio.speech.create(
            model="tts-1",  # or "tts-1-hd" for higher quality
            voice=request.voice,
            input=text_to_convert,
            response_format="mp3",
            speed=request.speed
        )

        # Convert the audio response to base64
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Generate a unique filename
        audio_filename = f"script_{script_id}_{uuid.uuid4().hex}.mp3"

        # Update the voice script with audio data
        update_data = {
            "audio_base64": audio_base64,
            "audio_filename": audio_filename,
            "audio_voice": request.voice,
            "audio_speed": request.speed,
            "audio_size_bytes": len(audio_data),
            "has_audio": True
        }

        updated_script = supabase.table("voice_scripts").update(update_data).eq("id", script_id).execute()

        if not updated_script.data:
            raise HTTPException(status_code=500, detail="Error updating script with audio data")

        return {
            "message": "Audio generated and saved successfully",
            "script_id": script_id,
            "audio_filename": audio_filename,
            "audio_base64": audio_base64,
            "size_bytes": len(audio_data),
            "voice": request.voice,
            "speed": request.speed,
            "script_data": updated_script.data[0]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio for script: {str(e)}")

@app.get("/voice-scripts/{script_id}/audio")
async def get_script_audio(script_id: str):
    """Get the audio data for a specific voice script"""
    try:
        script_data = supabase.table("voice_scripts").select("*").eq("id", script_id).execute()

        if not script_data.data:
            raise HTTPException(status_code=404, detail="Voice script not found")

        script = script_data.data[0]

        if not script.get("has_audio") or not script.get("audio_base64"):
            raise HTTPException(status_code=404, detail="No audio available for this script")

        return {
            "audio_base64": script["audio_base64"],
            "filename": script["audio_filename"],
            "voice": script["audio_voice"],
            "speed": script["audio_speed"],
            "size_bytes": script["audio_size_bytes"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audio: {str(e)}")

@app.delete("/voice-scripts/{script_id}/audio")
async def delete_script_audio(script_id: str):
    """Delete the audio data for a specific voice script"""
    try:
        # Remove audio data from the script
        update_data = {
            "audio_base64": None,
            "audio_filename": None,
            "audio_voice": None,
            "audio_speed": None,
            "audio_size_bytes": None,
            "has_audio": False
        }

        updated_script = supabase.table("voice_scripts").update(update_data).eq("id", script_id).execute()

        if not updated_script.data:
            raise HTTPException(status_code=404, detail="Voice script not found")

        return {"message": "Audio deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting audio: {str(e)}")

# --- Batch Audio Generation ---

@app.post("/videos/{video_id}/generate-all-audio")
async def generate_audio_for_all_scripts(video_id: str, request: AudioGenerateRequest):
    """Generate audio for all voice scripts in a video"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # Get all voice scripts for the video
        scripts_data = supabase.table("voice_scripts").select("*").eq("video_id", video_id).order("order_index").execute()

        if not scripts_data.data:
            raise HTTPException(status_code=404, detail="No voice scripts found for this video")

        results = []
        errors = []

        for script in scripts_data.data:
            try:
                # Generate audio for each script
                response = openai.audio.speech.create(
                    model="tts-1",
                    voice=request.voice,
                    input=script["generated_script"],
                    response_format="mp3",
                    speed=request.speed
                )

                # Convert to base64
                audio_data = response.content
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                audio_filename = f"script_{script['id']}_{uuid.uuid4().hex}.mp3"

                # Update the script
                update_data = {
                    "audio_base64": audio_base64,
                    "audio_filename": audio_filename,
                    "audio_voice": request.voice,
                    "audio_speed": request.speed,
                    "audio_size_bytes": len(audio_data),
                    "has_audio": True
                }

                supabase.table("voice_scripts").update(update_data).eq("id", script["id"]).execute()

                results.append({
                    "script_id": script["id"],
                    "filename": audio_filename,
                    "size_bytes": len(audio_data),
                    "success": True
                })

            except Exception as e:
                errors.append({
                    "script_id": script["id"],
                    "error": str(e),
                    "success": False
                })

        return {
            "message": f"Processed {len(scripts_data.data)} scripts",
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "voice": request.voice,
            "speed": request.speed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in batch audio generation: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
