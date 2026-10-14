"""Inference backends. `stub` = classical CV (always available); `yolo` = Ultralytics + EigenCAM."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from .imaging import heatmap_png, load_gray
from .severity import decide, summarize

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


@dataclass
class Inference:
    result: dict
    explanation_method: str
    summary: str
    heatmap: bytes
    width: int
    height: int


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> list[dict]:
    return json.loads((MODELS_DIR / "manifest.json").read_text())["models"]


class StubBackend:
    """Background subtraction + connected components. Deterministic and image-driven."""

    def __init__(self, entry: dict):
        self.entry = entry
        self.path = MODELS_DIR / entry["file"]
        self.params = json.loads(self.path.read_text())
        self.weights_sha256 = file_sha256(self.path)

    @staticmethod
    def _shape(comp: np.ndarray) -> tuple[float, float]:
        """(elongation, length) from the principal axes of the component's pixel cloud."""
        ys, xs = np.nonzero(comp)
        if len(xs) < 3:
            return 1.0, float(len(xs))
        ev = np.sort(np.linalg.eigvalsh(np.cov(np.stack([xs, ys]).astype(np.float64))))
        elong = float(np.sqrt(ev[1] / max(ev[0], 1e-3)))
        return elong, float(4 * np.sqrt(ev[1]))

    def _classify_image(self, comps: list[np.ndarray], signed: np.ndarray) -> str:
        """Image-level class from all components together (NEU-DET has one class per image)."""
        shapes = [self._shape(c) for c in comps]
        areas = [int(c.sum()) for c in comps]
        signs = [float(signed[c].mean()) for c in comps]
        dark = sum(1 for s in signs if s < 0)
        linear = [i for i, (e, _) in enumerate(shapes) if e >= 4.0]
        if linear and max(shapes[i][1] for i in linear) >= 60 and len(comps) <= 2:
            return "scratches"
        if len(linear) >= 2 or (linear and len(comps) <= 3 and dark == len(comps) and max(areas) < 400
                                and shapes[linear[0]][1] < 60):
            return "crazing"
        big = int(np.argmax(areas))
        if signs[big] > 0 and (areas[big] > 500 or sum(a for a, sg in zip(areas, signs) if sg > 0) > 700):
            return "patches"
        ys, xs = np.nonzero(comps[big])
        fill = areas[big] / float((np.ptp(ys) + 1) * (np.ptp(xs) + 1))
        if len(comps) <= 2 and signs[big] < 0 and fill < 0.3 and areas[big] > 60:
            return "crazing"
        if len(comps) >= 6 and np.median(areas) < 60:
            return "pitted_surface"
        if len(comps) >= 3 and dark >= len(comps) - 1:
            return "rolled-in_scale"
        return "inclusion" if dark else "patches"

    def infer(self, data: bytes) -> Inference:
        p = self.params
        g = load_gray(data)
        hgt, wid = g.shape
        bg = ndimage.gaussian_filter(g, p["blur_sigma"])
        signed = g - bg
        resid = np.abs(signed)
        z = (resid - np.median(resid)) / (1.4826 * np.median(np.abs(resid - np.median(resid))) + 1e-6)
        mask = ndimage.binary_closing(z > p["residual_z"], iterations=2)
        mask = ndimage.binary_opening(mask, iterations=1)
        labels, n = ndimage.label(mask)
        dets = []
        sizes = ndimage.sum(mask, labels, range(1, n + 1)) if n else []
        big = [i + 1 for i, s in enumerate(sizes) if s >= p["min_area"]]
        comps = [labels == lab for lab in big]
        cls = self._classify_image(comps, signed) if comps else None
        for comp in comps:
            ys, xs = np.nonzero(comp)
            strength = float(z[comp].mean())
            conf = float(1 / (1 + np.exp(-(strength - p["residual_z"] - 0.6) * 1.4)))
            conf = min(0.9990, max(0.0, conf * min(1.0, 0.55 + comp.sum() / 400)))
            dets.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, cls, conf))
        # PASS confidence: how far the strongest residual (after light smoothing) sits below the detection level.
        peak = float(ndimage.gaussian_filter(np.clip(z, 0, None), 1.5).max())
        anomaly = 1 / (1 + np.exp(-(peak - p["residual_z"] + 0.4) * 2.2))
        result = decide(dets, wid, hgt, p["detect_threshold"], pass_confidence=min(0.9990, max(0.5, 1 - anomaly)))
        sal = ndimage.gaussian_filter(np.clip(z, 0, None), 3)
        return Inference(result, "ResidualSaliency", summarize(result["boxes"], wid, hgt),
                         heatmap_png(sal, g), wid, hgt)


class YoloBackend:  # pragma: no cover - requires weights + ultralytics
    """Ultralytics YOLOv8 + EigenCAM. Install `requirements-yolo.txt` and place weights in models/."""

    def __init__(self, entry: dict, detect_threshold: float = 0.25):
        from ultralytics import YOLO

        self.entry = entry
        self.path = MODELS_DIR / entry["file"]
        if not self.path.exists():
            raise FileNotFoundError(f"weights not found: {self.path}")
        self.weights_sha256 = file_sha256(self.path)
        self.model = YOLO(str(self.path))
        self.threshold = detect_threshold

    def infer(self, data: bytes) -> Inference:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        wid, hgt = img.size
        res = self.model.predict(img, verbose=False, conf=0.05)[0]
        names = res.names
        dets = []
        for b in res.boxes:
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
            dets.append((x1, y1, x2, y2, names[int(b.cls)], float(b.conf)))
        result = decide(dets, wid, hgt, self.threshold)
        g = np.asarray(img.convert("L"), dtype=np.float32)
        try:
            sal, method = self._eigencam(img), "EigenCAM"
        except Exception:  # fall back to box mask if CAM fails
            sal, method = np.zeros_like(g), "BoxMask"
            for d in result["boxes"]:
                sal[d["y1"]:d["y2"], d["x1"]:d["x2"]] += float(d["conf"])
            sal = ndimage.gaussian_filter(sal, 6)
        return Inference(result, method, summarize(result["boxes"], wid, hgt), heatmap_png(sal, g), wid, hgt)

    def _eigencam(self, img) -> np.ndarray:
        import torch

        feats = {}
        layer = self.model.model.model[-2]
        hook = layer.register_forward_hook(lambda m, i, o: feats.__setitem__("a", o))
        try:
            self.model.predict(img, verbose=False)
        finally:
            hook.remove()
        a = feats["a"][0].detach().float()  # C,H,W
        c, h, w = a.shape
        flat = a.reshape(c, -1).T
        flat = flat - flat.mean(0)
        _, _, vh = torch.linalg.svd(flat, full_matrices=False)
        cam = (flat @ vh[0]).reshape(h, w).abs().cpu().numpy()
        from PIL import Image as _I

        cam = np.asarray(_I.fromarray(cam).resize(img.size, _I.BILINEAR))
        return cam


def make_backend(name: str | None, version: str | None, kind: str = "stub"):
    entries = [e for e in load_manifest() if e["backend"] == kind]
    if name:
        entries = [e for e in entries if e["name"] == name]
    if version:
        entries = [e for e in entries if e["version"] == version]
    if not entries:
        raise ValueError(f"no {kind} model matches name={name} version={version}")
    entry = entries[0]
    return StubBackend(entry) if kind == "stub" else YoloBackend(entry)


def available_models() -> list[dict]:
    """Manifest entries enriched with weights_sha256 when the weights file exists."""
    out = []
    for e in load_manifest():
        p = MODELS_DIR / e["file"]
        out.append({**e, "available": p.exists(), "weights_sha256": file_sha256(p) if p.exists() else None})
    return out
