import os, tempfile, json, requests
from flask import Flask, request, jsonify, send_file
from moviepy import (
    ImageClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, AudioFileClip, CompositeAudioClip
)
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
    clips, audios = [], []

    for scene in data["scenes"]:
        img = download_image(scene["image"])
        voice = make_voice(scene["text"])
        audios.append(AudioFileClip(voice))

        img_clip = (ImageClip(img)
                    .resize((WIDTH, HEIGHT))
                    .set_duration(AudioFileClip(voice).duration)
                    .fadein(0.5).fadeout(0.5))
        txt = (TextClip(scene["text"], fontsize=60, color="white", method="caption",
                        size=(900, None))
               .set_position(("center", "bottom"))
               .set_duration(img_clip.duration))

        clips.append(CompositeVideoClip([img_clip, txt]))

    video = concatenate_videoclips(clips)

    if "music" in data:
        bg = download_music(data["music"])
        music = AudioFileClip(bg).volumex(0.25).set_duration(video.duration)
        final_audio = CompositeAudioClip([video.audio, music])
        video = video.set_audio(final_audio)

    out = "final.mp4"
    video.write_videofile(out, fps=24, codec="libx264", audio_codec="aac")

    return send_file(out, mimetype="video/mp4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
