from flask import Flask, jsonify, request, send_file
import tempfile
import subprocess
import shutil
import os
import time

app = Flask(__name__)

LIBCAMERA_JPEG = shutil.which("libcamera-jpeg") is not None

@app.route("/", methods=["GET"])
def home():
    """Health/status endpoint"""
    status = {
        "status": "ok",
        "timestamp": int(time.time()),
        "libcamera_jpeg_available": LIBCAMERA_JPEG
    }
    return jsonify(status), 200

@app.route("/capture", methods=["GET", "POST"])
def capture():
    """
    Capture a full-resolution image.
    Query / form parameter:
      - shutter: exposure time in microseconds (int). Optional.
    Returns JPEG image.
    """
    shutter = request.values.get("shutter", None)
    try:
        shutter_val = int(shutter) if shutter is not None else None
    except ValueError:
        return jsonify({"error": "invalid shutter value"}), 400

    # Use libcamera-jpeg if available (reliable on Raspberry Pi OS with libcamera stack)
    if not LIBCAMERA_JPEG:
        return jsonify({"error": "libcamera-jpeg not available on this system"}), 500

    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmpf.close()
    filename = tmpf.name

    cmd = ["libcamera-jpeg", "-o", filename, "--nopreview"]
    # If shutter provided, pass it through (microseconds)
    if shutter_val is not None and shutter_val > 0:
        cmd += ["--shutter", str(shutter_val)]
    # Let libcamera select native (full) resolution by not specifying width/height
    # Optional: increase quality
    cmd += ["--quality", "95"]

    try:
        subprocess.run(cmd, check=True, timeout=30, stderr=subprocess.PIPE)
        return send_file(filename, mimetype="image/jpeg")
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
    # Bind to all interfaces so device can be reached on local network
    app.run(host="0.0.0.0", port=5001)
