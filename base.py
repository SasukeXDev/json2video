import os
import subprocess
import hashlib
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_OUTPUT_DIR = os.path.join(BASE_DIR, "static", "streams")
os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

@app.route('/convert', methods=['POST', 'OPTIONS'])
def convert():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.get_json()
    video_url = data.get('url')
    
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    output_path = os.path.join(HLS_OUTPUT_DIR, stream_id)
    playlist_file = os.path.join(output_path, 'index.m3u8')
    
    # Ensure folder exists
    os.makedirs(output_path, exist_ok=True)

    # Force HTTPS for Render
    base_server_url = request.host_url.rstrip('/').replace('http://', 'https://')

    if not os.path.exists(playlist_file):
        # UPDATED FFMPEG COMMAND
        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-i', video_url,
            '-map', '0:v:0',           # Map first video track
            '-map', '0:a?',             # Map all audio tracks
            '-map', '0:s?',             # Map all subtitle tracks
            '-c:v', 'copy',             # Fast copy video
            '-c:a', 'aac',              # Audio to AAC
            '-c:s', 'webvtt',           # Try to convert subtitles to webvtt
            '-ignore_unknown',          # Ignore streams that can't be converted (fixes the crash)
            '-f', 'hls', 
            '-hls_time', '10', 
            '-hls_list_size', '0',
            '-hls_segment_filename', os.path.join(output_path, 'seg_%03d.ts'),
            playlist_file
        ]
        
        # Start conversion
        subprocess.Popen(cmd)

    return jsonify({
        "status": "success",
        "hls_link": f"{base_server_url}/static/streams/{stream_id}/index.m3u8"
    }), 200

@app.route('/static/streams/<path:filename>')
def custom_static(filename):
    # This ensures the .m3u8 and .ts files are served with the correct headers
    response = send_from_directory(HLS_OUTPUT_DIR, filename)
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Content-Type", "application/vnd.apple.mpegurl" if filename.endswith('.m3u8') else "video/MP2T")
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
