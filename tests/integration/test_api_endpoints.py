import io

import numpy as np
from PIL import Image


def make_png_bytes(w=4, h=4, color=(128, 64, 32)) -> bytes:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = color
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_auth_validate(client, auth_header):
    r = client.post("/auth/validate", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "user_id" in data


essentials = {}


def test_upload_and_list(client, auth_header):
    png = make_png_bytes()
    files = {"file": ("sample.png", png, "image/png")}
    r = client.post("/images/upload", headers=auth_header, files=files)
    assert r.status_code == 201, r.text
    data = r.json()["image"]
    essentials["image_id"] = data["id"]

    r2 = client.get("/images", headers=auth_header)
    assert r2.status_code == 200
    images = r2.json()["images"]
    assert any(img["id"] == essentials["image_id"] for img in images)


def test_histogram_endpoint(client, auth_header):
    img_id = essentials["image_id"]
    body = {"image_id": img_id, "params": {}}
    r = client.post("/processing/histogram", headers=auth_header, json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["operation"] == "histogram"
    assert isinstance(data["bins"], list)


def test_process_brightness_and_history(client, auth_header):
    img_id = essentials["image_id"]
    body = {"image_id": img_id, "params": {"factor": 0.1, "ext": "png"}}
    r = client.post("/processing/brightness", headers=auth_header, json=body)
    assert r.status_code == 200, r.text
    data = r.json()["image"]
    assert data["original_id"] == img_id

    r2 = client.get("/history", headers=auth_header)
    assert r2.status_code == 200
    hist = r2.json()["history"]
    assert any(h["operation"] == "brightness" for h in hist)

