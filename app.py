from flask import Flask, send_file, jsonify
import subprocess
import datetime
import threading
import os

app = Flask(__name__)

CAMERA_CMD = "/usr/bin/rpicam-still"  # verify with `which rpicam-still`

def take_picture():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img = f"/tmp/capture_{ts}.jpg"

    subprocess.run(
        [
            CAMERA_CMD,
            "-n",
            "--width", "1280",
            "--height", "720",
            "--quality", "85",
            "-o", img
        ],
        check=True,
        timeout=6
    )

    return img

@app.route("/")
def index():
    return jsonify({"data": "Camera is ready!"})

@app.route("/tabilde", methods=["POST"])
def ta_bilde():
    img = take_picture()
    return send_file(img, mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
