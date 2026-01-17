import time
import threading
from flask import Flask, jsonify, request, send_file
import subprocess
import shutil
import os

app = Flask(__name__)

# Check if rpicam-still is installed
RPICAM_STILL = shutil.which("rpicam-still") is not None

# Lock to prevent simultaneous camera access
CAMERA_LOCK = threading.Lock()


@app.route("/", methods=["GET"])
def home():
    """Health/status endpoint"""
    status = {
        "status": "ok",
        "timestamp": int(time.time()),
        "rpicam_still_available": RPICAM_STILL
    }
    return jsonify(status), 200


@app.route("/capture", methods=["GET", "POST"])
def capture():
    """
    Capture a full-resolution image.

    Query / form parameters:
      - shutter: exposure time in microseconds (int). Optional.
      - gain: analog gain (float). Optional, e.g., 4.0

    Returns JPEG image.
    """
    if not RPICAM_STILL:
        return jsonify({"error": "rpicam-still not available"}), 500

    # Parse shutter and gain
    shutter = request.values.get("shutter", None)
    gain = request.values.get("gain", None)

    try:
        shutter_val = int(shutter) if shutter else None
    except ValueError:
        return jsonify({"error": "invalid shutter value"}), 400

    try:
        gain_val = float(gain) if gain else None
    except ValueError:
        return jsonify({"error": "invalid gain value"}), 400

    # Unique filename using timestamp (milliseconds)
    timestamp = int(time.time() * 1000)
    filename = f"/tmp/capture_{timestamp}.jpg"

    # Build rpicam-still command
    cmd = [
        "rpicam-still",
        "-n",                 # no preview
        "--quality", "95",
        "-o", filename
    ]


    if shutter_val:
        cmd += ["--shutter", str(shutter_val)]
    if gain_val:
        cmd += ["--gain", str(gain_val)]

    # Take the picture (thread-safe)
    with CAMERA_LOCK:
        try:
            subprocess.run(cmd, check=True, timeout=30, stderr=subprocess.PIPE)
            response = send_file(filename, mimetype="image/jpeg", conditional=False)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "capture failed", "details": e.stderr.decode(errors="ignore")}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "capture timeout"}), 504

    # Optional: clean up temp file after a short delay
    def cleanup_file(f):
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass

    threading.Thread(target=lambda: (time.sleep(5), cleanup_file(filename))).start()

    return response


if __name__ == "__main__":
    # Development only; for production use Gunicorn + systemd
    app.run(host="0.0.0.0", port=5001)
