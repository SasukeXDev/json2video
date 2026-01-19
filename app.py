import os, tempfile, json, requests
from flask import Flask, request, jsonify, send_file

# Compatible with MoviePy 1.x and 2.x
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip

from PIL import Image
from gtts import gTTS
import yt_dlp


app = Flask(__name__)

WIDTH, HEIGHT = 1080, 1920   # 9:16 reels

# ---------- MUSIC ----------
def download_music(query):
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{query}"])
    return out

# ---------- IMAGE ----------
def download_image(query):
    url = f"https://source.unsplash.com/1080x1920/?{query}"
    img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    with open(img, "wb") as f:
        f.write(requests.get(url).content)
    return img

# ---------- TTS ----------
def make_voice(text):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    gTTS(text=text, lang="en").save(path)
    return path

# ---------- API ----------
@app.route("/json2video", methods=["POST"])
def json2video():
    data = request.json

    WIDTH, HEIGHT = 1080, 1920
    FPS = 24
    temp_dir = tempfile.mkdtemp()

    frames = []
    audio_tracks = []

    total_time = 0

    # Background Music (YouTube auto)
    bg_music = None
    if "music" in data:
        bg_music = download_music(data["music"])

    for i, scene in enumerate(data["scenes"]):
        text = scene.get("text", f"Scene {i+1}")
        duration = scene.get("duration", 3)

        # TTS
        tts_file = os.path.join(temp_dir, f"tts_{i}.mp3")
        gTTS(text=text, lang="en").save(tts_file)
        audio_tracks.append(AudioFileClip(tts_file))

        # Image
        img_url = f"https://source.unsplash.com/1080x1920/?{scene.get('image','nature')}"
        img_path = os.path.join(temp_dir, f"img_{i}.jpg")
        img_data = requests.get(img_url).content
        open(img_path, "wb").write(img_data)

        img = Image.open(img_path).convert("RGB").resize((WIDTH, HEIGHT))
        img.save(img_path)

        clip = ImageSequenceClip([img_path], durations=[duration])
        frames.append(clip)
        total_time += duration

    video = concatenate_videoclips(frames, method="compose")

    audios = [a.set_start(sum(frames[:i], start=0).duration) for i, a in enumerate(audio_tracks)]
    if bg_music:
        audios.append(AudioFileClip(bg_music).volumex(0.25).set_duration(total_time))

    final_audio = CompositeAudioClip(audios)
    final_video = video.set_audio(final_audio)

    out = os.path.join(temp_dir, "final.mp4")
    final_video.write_videofile(out, fps=FPS, codec="libx264", audio_codec="aac")

    return send_file(out, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
