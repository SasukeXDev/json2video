from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import moviepy.editor as mp
import requests
import os

app = FastAPI()

# ------------------------
# Pydantic model for meme
# ------------------------
class MemeJSON(BaseModel):
    top_text: str
    bottom_text: str
    duration: float = 5
    width: int = 1080
    height: int = 1920
    background_image: Optional[str] = None  # URL of image
    audio_url: Optional[str] = None

# ------------------------
# Utility to download files
# ------------------------
def download_file(url, filename):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(filename, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        return filename
    else:
        raise HTTPException(status_code=400, detail=f"Failed to download {url}")

# ------------------------
# Render meme video
# ------------------------
def render_meme(data: MemeJSON):
    width, height = data.width, data.height

    # Background clip
    if data.background_image:
        bg_path = "bg_image.png"
        download_file(data.background_image, bg_path)
        bg_clip = mp.ImageClip(bg_path).set_duration(data.duration)
        os.remove(bg_path)
    else:
        # solid black background
        bg_clip = mp.ColorClip(size=(width, height), color=(0,0,0), duration=data.duration)

    # Add top text
    top_clip = mp.TextClip(data.top_text, fontsize=80, color='white', size=(width-100, None), method='caption')
    top_clip = top_clip.set_position(("center", 50)).set_duration(data.duration)

    # Add bottom text
    bottom_clip = mp.TextClip(data.bottom_text, fontsize=80, color='white', size=(width-100, None), method='caption')
    bottom_clip = bottom_clip.set_position(("center", height-150)).set_duration(data.duration)

    # Overlay text on background
    final = mp.CompositeVideoClip([bg_clip, top_clip, bottom_clip])

    # Add audio if exists
    if data.audio_url:
        audio_file = "audio.mp3"
        download_file(data.audio_url, audio_file)
        audio_clip = mp.AudioFileClip(audio_file).subclip(0, data.duration)
        final = final.set_audio(audio_clip)
        os.remove(audio_file)

    output_file = "meme_reel.mp4"
    final.write_videofile(output_file, fps=30)
    return output_file

# ------------------------
# API endpoint
# ------------------------
@app.post("/generate_meme")
async def generate_meme(json_data: MemeJSON):
    try:
        video_path = render_meme(json_data)
        return {"message": "Meme video generated!", "video_path": video_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
