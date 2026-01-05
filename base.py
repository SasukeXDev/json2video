import os
import subprocess
import hashlib
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_DIR = os.path.join(BASE_DIR, "static", "streams")
os.makedirs(HLS_DIR, exist_ok=True)

FFMPEG_BIN = "ffmpeg"  # Render supports this if added in build command

# ---------------------------
# Convert Endpoint
# ---------------------------
@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"status": "error", "message": "URL missing"}), 400

    video_url = data["url"]
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    out_dir = os.path.join(HLS_DIR, stream_id)
    playlist = os.path.join(out_dir, "index.m3u8")

    os.makedirs(out_dir, exist_ok=True)

    # If already converted → reuse
    if os.path.exists(playlist):
        return jsonify({
            "status": "success",
            "hls_link": f"{request.host_url}static/streams/{stream_id}/index.m3u8"
        })

    # -------- SAFE FFMPEG COMMAND --------
    cmd = [
        FFMPEG_BIN, "-y",
        "-hide_banner", "-loglevel", "warning",

        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",

        "-i", video_url,

        "-map", "0:v:0",
        "-map", "0:a?",

        "-c:v", "copy",
        "-c:a", "aac",
        "-ac", "2",

        "-metadata:s:a:0", "language=eng",
        "-metadata:s:a:1", "language=hin",

        "-f", "hls",
        "-hls_time", "6",
        # change the et
        "-hls_playlist_type", "event",

        "-hls_flags", "independent_segments",

        "-hls_segment_filename",
        os.path.join(out_dir, "seg_%05d.ts"),

        playlist
    ]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # -------- WAIT UNTIL READY --------
    timeout = 12
    while timeout > 0:
        if os.path.exists(playlist):
            if any(f.endswith(".ts") for f in os.listdir(out_dir)):
                break
        time.sleep(1)
        timeout -= 1

    if not os.path.exists(playlist):
        return jsonify({"status": "error", "message": "FFmpeg failed"}), 500

    proto = request.headers.get("X-Forwarded-Proto", "https")
    host = request.headers.get("Host")

    hls_url = f"{proto}://{host}/static/streams/{stream_id}/index.m3u8"

    return jsonify({
        "status": "success",
        "hls_link": hls_url
    })



# ---------------------------
# Static HLS Serving
# ---------------------------
@app.route("/static/streams/<path:filename>")
def serve_hls(filename):
    response = send_from_directory(HLS_DIR, filename)
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Cache-Control": "no-cache",
        "Content-Type": "application/vnd.apple.mpegurl"
    })
    return response


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
