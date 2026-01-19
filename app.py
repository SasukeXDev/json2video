import os
import tempfile
import json
import requests
import re
from flask import Flask, request, send_file
from io import BytesIO
from PIL import Image
from gtts import gTTS

# MoviePy imports
from moviepy.editor import ImageSequenceClip, concatenate_videoclips, CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip

app = Flask(__name__)

WIDTH, HEIGHT = 1080, 1920   # 9:16 reels
FPS = 24

# ---------- MUSIC (NCS) ----------
def download_music(query):
    try:
        url = f"https://ncs.io/search?q={query.replace(' ', '%20')}"
        html = requests.get(url, timeout=10).text
        links = re.findall(r'href="(/music/[^"]+)"', html)

        if not links:
            return None

        track_page = "https://ncs.io" + links[0]
        page = requests.get(track_page).text
        mp3 = re.search(r'href="(https://[^"]+\.mp3)"', page)

        if not mp3:
            return None

        path = tempfile.mktemp(suffix=".mp3")
        open(path, "wb").write(requests.get(mp3.group(1)).content)
        return path
    except Exception as e:
        print("[WARN] NCS music download failed:", e)
        return None


# ---------- IMAGE ----------
def download_image(query, path):
    """
    Downloads an image for the query from placeholder service.
    Fallback to black image if fails.
    """
    try:
        # Use placeholder.com instead of Unsplash (always works)
        # 1080x1920 resolution
        url = f"https://via.placeholder.com/1080x1920.png?text={query.replace(' ','+')}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        img = Image.open(BytesIO(resp.content))
        img = img.convert("RGB")
        img.save(path)
        return True
    except Exception as e:
        print(f"[WARN] Image download failed for '{query}':", e)
        # fallback: black image
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        img.save(path)
        return False


# ---------- TTS ----------
def make_voice(text, path):
    gTTS(text=text, lang="en").save(path)


# ---------- API ----------
@app.route("/json2video", methods=["POST"])
def json2video():
    data = request.json
    temp_dir = tempfile.mkdtemp()

    frames = []
    audio_tracks = []

    total_time = 0

    # Background Music
    bg_music = download_music(data.get("music","")) if "music" in data else None

    for i, scene in enumerate(data.get("scenes", [])):
        text = scene.get("text", f"Scene {i+1}")
        duration = scene.get("duration", 3)

        # TTS
        tts_file = os.path.join(temp_dir, f"tts_{i}.mp3")
        make_voice(text, tts_file)
        audio_tracks.append(AudioFileClip(tts_file))

        # Image
        img_path = os.path.join(temp_dir, f"img_{i}.jpg")
        download_image(scene.get("image", f"Scene{i+1}"), img_path)

        clip = ImageSequenceClip([img_path], durations=[duration])
        frames.append(clip)
        total_time += duration

    if not frames:
        return "No scenes provided", 400

    video = concatenate_videoclips(frames, method="compose")

    # Position TTS audio
    audios = []
    current_time = 0
    for i, a in enumerate(audio_tracks):
        a = a.set_start(current_time)
        audios.append(a)
        current_time += frames[i].duration

    # Add background music
    if bg_music:
        bg = AudioFileClip(bg_music).volumex(0.25).set_duration(total_time)
        audios.append(bg)

    final_audio = CompositeAudioClip(audios)
    final_video = video.set_audio(final_audio)

    out = os.path.join(temp_dir, "final.mp4")
    final_video.write_videofile(out, fps=FPS, codec="libx264", audio_codec="aac")

    return send_file(out, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
