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

    # Debug incoming raw params
    print("Incoming params:", {"shutter_raw": shutter, "gain_raw": gain})

    try:
        shutter_val = int(shutter) if shutter else None
    except ValueError:
        return jsonify({"error": "invalid shutter value"}), 400

    try:
        gain_val = float(gain) if gain else None
    except ValueError:
        return jsonify({"error": "invalid gain value"}), 400

    # Heuristic: convert common units to microseconds if caller sent seconds or ms by mistake.
    # - If <=30 treat as seconds (e.g. "2" -> 2 seconds).
    # - If <=30000 treat as milliseconds (e.g. "2000" -> 2000 ms).
    if shutter_val is not None:
        if shutter_val <= 30:
            print("Interpreting shutter as seconds; converting to microseconds")
            shutter_val = int(shutter_val * 1_000_000)
        elif shutter_val <= 30000:
            print("Interpreting shutter as milliseconds; converting to microseconds")
            shutter_val = int(shutter_val * 1000)

    # Safety cap (e.g. 600 seconds = 600_000_000 µs)
    if shutter_val is not None and shutter_val > 600_000_000:
        return jsonify({"error": "shutter value too large"}), 400

    # Unique filename using timestamp (milliseconds)
    timestamp = int(time.time() * 1000)
    filename = f"/tmp/capture_{timestamp}.jpg"

    # Build rpicam-still command
    cmd = [
        "rpicam-still",
        "-n",                 # no preview
        "--quality", "95",
        "-o", filename,
        "--immediate",
        "-w", "3280",
        "-h", "2464"
    ]

    # Always add shutter if provided
    if shutter_val is not None:
        cmd.extend(["--shutter", str(shutter_val)])

    # Only add gain and awbgains when shutter > 1,000,000 (long exposure)
    if shutter_val is not None and shutter_val > 1000000:
        # use provided gain if present, otherwise default to 4.0
        if gain_val is not None:
            cmd.extend(["--gain", str(gain_val)])
        else:
            cmd.extend(["--gain", "4.0"])
        cmd.extend(["--awbgains", "1,0.6"])


    print(f"Executing command: {' '.join(cmd)}")

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
