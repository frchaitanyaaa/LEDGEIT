"""Train a YOLOv8 model on NEU-DET and register-ready metadata.

Usage:
  pip install -r requirements-yolo.txt
  python training/train.py --data datasets/neu-det-yolo/data.yaml --base yolov8n.pt --version 1.0.0 --epochs 100
Outputs models/yolov8{n|s}-neu-<version>.pt and prints metrics + SHA-256 for the Model Registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / "models"


def main() -> None:
    from ultralytics import YOLO

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--base", default="yolov8n.pt")
    ap.add_argument("--version", required=True)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()

    model = YOLO(a.base)
    model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, device=a.device, seed=42, deterministic=True)
    m = model.val(data=a.data, imgsz=a.imgsz)
    size = "n" if "8n" in a.base else "s" if "8s" in a.base else "x"
    dest = MODELS / f"yolov8{size}-neu-{a.version}.pt"
    shutil.copy2(Path(model.trainer.best), dest)
    metrics = {
        "mAP50": round(float(m.box.map50), 4),
        "mAP50_95": round(float(m.box.map), 4),
        "precision": round(float(m.box.mp), 4),
        "recall": round(float(m.box.mr), 4),
        "per_class_mAP50": {model.names[i]: round(float(v), 4) for i, v in enumerate(m.box.maps)},
    }
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    print(json.dumps({"file": dest.name, "weights_sha256": sha, "metrics": metrics}, indent=2))
    print("Copy `metrics` into models/manifest.json for this version, then `make seed` to register it.")


if __name__ == "__main__":
    main()
