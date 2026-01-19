import os
import tempfile
from flask import Flask, request, send_file
from PIL import Image
from gtts import gTTS
from io import BytesIO
import requests

from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips

app = Flask(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 24


# ---------- IMAGE ----------
def download_image(query, path):
    """Download image or fallback to black"""
    try:
        url = f"https://via.placeholder.com/1080x1920.png?text={query.replace(' ', '+')}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img.save(path)
    except:
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        img.save(path)


# ---------- TTS ----------
def make_tts(text, path):
    gTTS(text=text, lang="en").save(path)


# ---------- API ----------
@app.route("/json2video", methods=["POST"])
def json2video():
    data = request.json
    temp_dir = tempfile.mkdtemp()

    clips = []
    audio_tracks = []
    total_duration = 0

    scenes = data.get("scenes", [])
    if not scenes:
        return {"error": "No scenes provided"}, 400

    for i, scene in enumerate(scenes):
        text = scene.get("text", f"Scene {i+1}")
        duration = scene.get("duration", 3)
        image_query = scene.get("image", f"Scene{i+1}")

        # Image
        img_path = os.path.join(temp_dir, f"img_{i}.jpg")
        download_image(image_query, img_path)
        clip = ImageSequenceClip([img_path], durations=[duration])
        clips.append(clip)

        # TTS
        tts_path = os.path.join(temp_dir, f"tts_{i}.mp3")
        make_tts(text, tts_path)
        audio = AudioFileClip(tts_path).set_start(total_duration)
        audio_tracks.append(audio)

        total_duration += duration

    video = concatenate_videoclips(clips, method="compose")
    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        video = video.set_audio(final_audio)

    out_path = os.path.join(temp_dir, "output.mp4")
    video.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac")

    return send_file(out_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
