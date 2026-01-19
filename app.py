from flask import Flask, request, send_file, jsonify
from moviepy import *
from gtts import gTTS
import tempfile, os, requests, random

app = Flask(__name__)

def download_image(query):
    url = f"https://source.unsplash.com/1280x720/?{query}"
    img = requests.get(url, timeout=15).content
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    open(path, "wb").write(img)
    return path

def make_tts(text):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    gTTS(text=text, lang="en").save(path)
    return path

def create_video(data, out_path):
    clips = []
    subtitles = []

    w, h = data.get("width",1280), data.get("height",720)
    fps = data.get("fps",30)
    bg_music = data.get("music")

    for i, sc in enumerate(data["scenes"]):
        img_path = download_image(sc.get("image_query","nature"))
        dur = sc.get("duration",4)
        txt = sc.get("text","")
        anim = sc.get("animation","fade")
        voice = sc.get("voice",True)

        base = ImageClip(img_path).resize((w,h)).set_duration(dur)

        if anim=="fade":
            base = base.crossfadein(0.5).crossfadeout(0.5)
        if anim=="slide":
            base = base.set_position(lambda t:(int(-w + t*w/dur),0))

        layers = [base]

        if txt:
            sub = TextClip(txt, fontsize=50, color="white", size=(w-100,None), method="caption")\
                  .set_position("center").set_duration(dur)
            layers.append(sub)
            subtitles.append((i*dur, txt))

        if voice:
            v = make_tts(txt)
            layers[0] = layers[0].set_audio(AudioFileClip(v))

        clips.append(CompositeVideoClip(layers))

    video = concatenate_videoclips(clips)

    if bg_music:
        music = AudioFileClip(bg_music).volumex(0.2).set_duration(video.duration)
        video = video.set_audio(CompositeAudioClip([video.audio, music]))

    video.write_videofile(out_path, fps=fps, codec="libx264")

@app.route("/json2video", methods=["POST"])
def json2video():
    data = request.get_json()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    create_video(data, tmp)
    return send_file(tmp, as_attachment=True, download_name="video.mp4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
