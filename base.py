from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import os
import hashlib

app = Flask(__name__)
# Allow cross-origin requests from your frontend domain
CORS(app)

# Use absolute path for reliability on servers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_OUTPUT_DIR = os.path.join(BASE_DIR, "static", "streams")

if not os.path.exists(HLS_OUTPUT_DIR):
    os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    video_url = data.get('url')
    
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    # Create a unique ID for this stream
    stream_id = hashlib.md5(video_url.encode()).hexdigest()
    output_path = os.path.join(HLS_OUTPUT_DIR, stream_id)
    playlist_file = os.path.join(output_path, 'index.m3u8')
    
    # Get the base URL of this backend server
    # This ensures the link works even if the domain changes
    base_server_url = request.host_url.rstrip('/')

    if not os.path.exists(playlist_file):
        os.makedirs(output_path, exist_ok=True)
        
        # FFmpeg command to extract all audio/subs and convert to HLS
        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-i', video_url,
            '-map', '0:v:0', '-map', '0:a?', '-map', '0:s?',
            '-c:v', 'copy', '-c:a', 'aac', '-c:s', 'webvtt',
            '-f', 'hls', '-hls_time', '10', '-hls_list_size', '0',
            '-hls_segment_filename', os.path.join(output_path, 'seg_%03d.ts'),
            playlist_file
        ]
        
        # Run in background
        subprocess.Popen(cmd)

    return jsonify({
        "status": "processing",
        "stream_id": stream_id,
        "hls_link": f"{base_server_url}/static/streams/{stream_id}/index.m3u8"
    })

# Route to serve the static files (important for some server configs)
@app.route('/static/streams/<path:path>')
def serve_streams(path):
    return send_from_directory(HLS_OUTPUT_DIR, path)

if __name__ == '__main__':
    # Bind to 0.0.0.0 and dynamic port for deployment
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
