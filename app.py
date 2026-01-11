from flask import Flask, send_file
from picamzero import Camera
import datetime
import base64

app = Flask(__name__)
cam = Camera()

@app.route("/tabilde", methods=["POST"])
def ta_bilde():
    # Ta bilde og lagre midlertidig

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img = f"/tmp/capture_{ts}.jpg"

    cam.take_photo(img)
    # Les bildet og base64-encode
    with open(img, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode("utf-8")

    return send_file(img, mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
