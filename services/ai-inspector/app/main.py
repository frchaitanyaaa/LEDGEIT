"""AI Inspector service: POST /infer (multipart image) -> decision, boxes, heatmap, model identity."""

from __future__ import annotations

import base64
import os
import time

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from .backends import available_models, load_manifest, make_backend

BACKEND_KIND = os.environ.get("MODEL_BACKEND", "stub")
DEFAULT_VERSION = os.environ.get("MODEL_VERSION")  # None -> first matching manifest entry

app = FastAPI(title="LEDGEIT AI Inspector", version="0.1.0")
_backends: dict[str, object] = {}


def get_backend(version: str | None):
    key = version or DEFAULT_VERSION or "default"
    if key not in _backends:
        try:
            _backends[key] = make_backend(None, version or DEFAULT_VERSION, BACKEND_KIND)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(404, str(e)) from e
    return _backends[key]


def model_info(b) -> dict:
    return {"name": b.entry["name"], "version": b.entry["version"], "weights_sha256": b.weights_sha256}


@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND_KIND}


@app.get("/model")
def model(version: str | None = Query(default=None)):
    b = get_backend(version)
    return {**model_info(b), "backend": BACKEND_KIND}


@app.get("/models")
def models():
    return {"backend": BACKEND_KIND, "models": available_models(), "manifest_size": len(load_manifest())}


@app.post("/infer")
async def infer(image: UploadFile = File(...), version: str | None = Query(default=None)):
    data = await image.read()
    if not data:
        raise HTTPException(422, "empty image")
    b = get_backend(version)
    t0 = time.perf_counter()
    try:
        inf = b.infer(data)
    except Exception as e:  # bad image bytes
        raise HTTPException(422, f"cannot process image: {e}") from e
    latency = int((time.perf_counter() - t0) * 1000)
    return {
        **inf.result,
        "explanation": {"method": inf.explanation_method, "summary": inf.summary},
        "heatmap_png_b64": base64.b64encode(inf.heatmap).decode(),
        "width": inf.width,
        "height": inf.height,
        "model": model_info(b),
        "latency_ms": latency,
    }
