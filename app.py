from flask import Flask, request, send_file, jsonify
import yt_dlp
import os
import uuid

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route("/")
def home():
    return {"status": "API running"}

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "Video URL required"}), 400

    video_url = data["url"]
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    ydl_opts = {
        "outtmpl": filepath,
        "format": "mp4",
        "noplaylist": True,
        "quiet": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return send_file(
            filepath,
            as_attachment=True,
            download_name="video.mp4"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
