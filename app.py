from flask import Flask, jsonify, request, send_file
import tempfile
import subprocess
import shutil
import os
import time
import threading

app = Flask(__name__)

# Check for rpicam-still instead of libcamera-jpeg
RPICAM_STILL = shutil.which("rpicam-still") is not None

# Prevent concurrent camera access
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
    Query / form parameter:
      - shutter: exposure time in microseconds (int). Optional.
      - gain: analog gain (float). Optional, e.g., 4.0
    Returns JPEG image.
    """
    if not RPICAM_STILL:
        return jsonify({"error": "rpicam-still not available on this system"}), 500

    shutter = request.values.get("shutter", None)
    gain = request.values.get("gain", None)

    try:
        shutter_val = int(shutter) if shutter is not None else None
    except ValueError:
        return jsonify({"error": "invalid shutter value"}), 400

    try:
        gain_val = float(gain) if gain is not None else None
    except ValueError:
        return jsonify({"error": "invalid gain value"}), 400

    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmpf.close()
    filename = tmpf.name

    cmd = [
        "rpicam-still",
        "-n",                 # no preview
        "--quality", "95",
        "-o", filename
    ]

    if shutter_val is not None and shutter_val > 0:
        cmd += ["--shutter", str(shutter_val)]
    if gain_val is not None and gain_val > 0:
        cmd += ["--gain", str(gain_val)]

    # Only allow one capture at a time
    with CAMERA_LOCK:
        try:
            subprocess.run(cmd, check=True, timeout=30, stderr=subprocess.PIPE)
            return send_file(filename, mimetype="image/jpeg", conditional=False)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "capture failed", "details": e.stderr.decode(errors="ignore")}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "capture timeout"}), 504
        finally:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception:
                pass

if __name__ == "__main__":
    # Development only; use Gunicorn + systemd in production
    app.run(host="0.0.0.0", port=5001)
