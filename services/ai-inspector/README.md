# ai-inspector

FastAPI service that inspects an image and returns the decision the edge device seals into its record.

```bash
pip install -r requirements.txt            # + requirements-yolo.txt for MODEL_BACKEND=yolo
uvicorn app.main:app --port 8001           # MODEL_BACKEND=stub|yolo  MODEL_VERSION=1.0.0
pytest
```

| Endpoint | |
|---|---|
| `POST /infer?version=` | multipart `image` → `{decision, defect_class, severity, confidence, boxes[], explanation{method,summary}, heatmap_png_b64, model{name,version,weights_sha256}, latency_ms}` |
| `GET /model` | active model identity |
| `GET /models` | manifest with availability + weights hashes |

Models are listed in `models/manifest.json`. Weights (`*.pt`) are git-ignored; stub "weights" are the JSON
parameter files. Training: `training/prepare_neu_det.py` then `training/train.py`. See [MODEL_CARD.md](MODEL_CARD.md).
