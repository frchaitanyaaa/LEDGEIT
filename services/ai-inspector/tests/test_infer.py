import base64
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.severity import decide, severity_for


def jpeg(defect: bool, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    img = np.full((200, 200), 120, np.float32) + rng.normal(0, 2, (200, 200))
    if defect:
        img[95:99, 20:180] -= 60  # long dark scratch
    buf = io.BytesIO()
    Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_and_models(client):
    assert client.get("/health").json()["status"] == "ok"
    models = client.get("/models").json()["models"]
    stubs = [m for m in models if m["backend"] == "stub"]
    assert len(stubs) == 2 and all(m["available"] and len(m["weights_sha256"]) == 64 for m in stubs)
    assert stubs[0]["weights_sha256"] != stubs[1]["weights_sha256"]


def test_infer_defect_and_good(client):
    bad = client.post("/infer", files={"image": ("a.jpg", jpeg(True), "image/jpeg")}).json()
    assert bad["decision"] == "FAIL"
    assert bad["defect_class"] == "scratches"
    assert bad["severity"] in ("MINOR", "MAJOR", "CRITICAL")
    assert len(bad["confidence"]) == 6 and bad["confidence"].startswith("0.")
    assert bad["boxes"] and all(isinstance(bad["boxes"][0][k], int) for k in ("x1", "y1", "x2", "y2"))
    png = base64.b64decode(bad["heatmap_png_b64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert bad["model"]["name"] == "ledgeit-defect-stub" and len(bad["model"]["weights_sha256"]) == 64
    assert "streak" in bad["explanation"]["summary"].lower()

    good = client.post("/infer", files={"image": ("b.jpg", jpeg(False), "image/jpeg")}).json()
    assert good["decision"] == "PASS" and good["severity"] == "NONE" and good["boxes"] == []


def test_deterministic_and_version_select(client):
    a = client.post("/infer", files={"image": ("a.jpg", jpeg(True), "image/jpeg")}).json()
    b = client.post("/infer", files={"image": ("a.jpg", jpeg(True), "image/jpeg")}).json()
    assert a["confidence"] == b["confidence"] and a["heatmap_png_b64"] == b["heatmap_png_b64"]
    v11 = client.post("/infer?version=1.1.0", files={"image": ("a.jpg", jpeg(True), "image/jpeg")}).json()
    assert v11["model"]["version"] == "1.1.0"
    assert client.post("/infer?version=9.9.9", files={"image": ("a.jpg", jpeg(True), "image/jpeg")}).status_code == 404


def test_bad_image(client):
    r = client.post("/infer", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422


def test_severity_rules():
    assert severity_for("crazing", 0.01, 0.9) == "MINOR"
    assert severity_for("scratches", 0.01, 0.9) == "MAJOR"
    assert severity_for("scratches", 0.15, 0.95) == "CRITICAL"
    assert severity_for("patches", 0.2, 0.5) == "MAJOR"
    assert severity_for("patches", 0.4, 0.5) == "CRITICAL"
    r = decide([(0, 0, 10, 10, "inclusion", 0.2)], 200, 200, 0.35)
    assert r["decision"] == "PASS" and r["confidence"] == "0.8000"
