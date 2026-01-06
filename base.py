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

@app.route("/convert", methods=["POST", "OPTIONS"])
def convert():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"status": "error", "message": "URL missing"}), 400

    video_url = data["url"]
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    out_dir = os.path.join(HLS_DIR, stream_id)
    playlist = os.path.join(out_dir, "index.m3u8")

    os.makedirs(out_dir, exist_ok=True)

    if os.path.exists(playlist):
        proto = request.headers.get("X-Forwarded-Proto", "https")
        return jsonify({
            "status": "success",
            "hls_link": f"{proto}://{request.host}/static/streams/{stream_id}/index.m3u8"
        })

    # -------- ULTIMATE CLEAN FFMPEG COMMAND --------
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        
        # 1. Connection settings
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
        
        # 2. Input
        "-i", video_url,

        # 3. Stream Selection (The Fix)
        "-map", "0:v:0",           # Take ONLY the first video stream
        "-map", "0:a",             # Take ALL audio streams
        "-sn",                     # EXPLICITLY DISABLE SUBTITLES
        "-dn",                     # EXPLICITLY DISABLE DATA/ATTACHMENTS (Fixes PNG error)
        "-ignore_unknown",         # Skip anything FFmpeg doesn't recognize
        
        # 4. Encoding
        "-c:v", "copy",            # No re-encoding video (Fast)
        "-c:a", "aac",             # Standard audio for HLS
        "-ac", "2",                # Stereo downmix for stability
        
        # 5. HLS Settings (Fixes Live Badge)
        "-f", "hls",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-hls_playlist_type", "vod", # Removes LIVE badge, adds timeline
        "-hls_flags", "independent_segments",
        
        "-hls_segment_filename", os.path.join(out_dir, "seg_%05d.ts"),
        playlist
    ]

    try:
        # Run in background
        subprocess.Popen(cmd)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # -------- WAIT UNTIL PLAYLIST FILE EXISTS --------
    # Check for the file periodically before responding
    ready = False
    for _ in range(15): # Wait up to 15 seconds
        if os.path.exists(playlist) and os.path.getsize(playlist) > 0:
            ready = True
            break
        time.sleep(1)

    if ready:
        proto = request.headers.get("X-Forwarded-Proto", "https")
        hls_url = f"{proto}://{request.host}/static/streams/{stream_id}/index.m3u8"
        return jsonify({"status": "success", "hls_link": hls_url})
    else:
        # If it still fails, it's likely a network/source issue
        return jsonify({"status": "error", "message": "FFmpeg failed to generate stream. Check source link."}), 500

@app.route("/static/streams/<path:filename>")
def serve_hls(filename):
    response = send_from_directory(HLS_DIR, filename)
    if filename.endswith(".m3u8"):
        response.headers["Content-Type"] = "application/vnd.apple.mpegurl"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
