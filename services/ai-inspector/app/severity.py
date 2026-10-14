"""Map detections to decision, severity and confidence (shared by every backend)."""

from __future__ import annotations

from decimal import Decimal

from ledgeit_proof import fmt_decimal

CLASSES = ["crazing", "inclusion", "patches", "pitted_surface", "rolled-in_scale", "scratches"]

# Base severity per NEU-DET class: cosmetic vs structural.
BASE_SEVERITY = {
    "crazing": "MINOR",
    "patches": "MINOR",
    "rolled-in_scale": "MINOR",
    "pitted_surface": "MAJOR",
    "inclusion": "MAJOR",
    "scratches": "MAJOR",
}
LEVELS = ["NONE", "MINOR", "MAJOR", "CRITICAL"]


def severity_for(cls: str, area_ratio: float, conf: float) -> str:
    """Bump severity when the defect covers a large share of the surface."""
    level = LEVELS.index(BASE_SEVERITY.get(cls, "MAJOR"))
    if area_ratio >= 0.12:
        level += 1
    if area_ratio >= 0.30 or (cls in ("inclusion", "scratches") and area_ratio >= 0.08 and conf >= 0.9):
        level += 1
    return LEVELS[min(level, 3)]


def summarize(boxes: list[dict], width: int, height: int) -> str:
    if not boxes:
        return "No anomalous region above threshold; surface texture consistent with reference."
    b = max(boxes, key=lambda x: float(x["conf"]))
    cx, cy = (b["x1"] + b["x2"]) / 2 / width, (b["y1"] + b["y2"]) / 2 / height
    v = "upper" if cy < 0.33 else "lower" if cy > 0.66 else "middle"
    h = "left" if cx < 0.33 else "right" if cx > 0.66 else "center"
    w, hh = b["x2"] - b["x1"], b["y2"] - b["y1"]
    shape = "Linear streak" if max(w, hh) > 3.5 * max(1, min(w, hh)) else "Compact anomaly"
    extra = f" (+{len(boxes) - 1} more region{'s' if len(boxes) > 2 else ''})" if len(boxes) > 1 else ""
    return f"{shape} classified as {b['cls']} in {v}-{h} region{extra}"


def decide(dets: list[tuple[int, int, int, int, str, float]], width: int, height: int, threshold: float,
           pass_confidence: float | None = None) -> dict:
    """dets: (x1, y1, x2, y2, cls, conf). Returns the `result` part of the record (strings for decimals)."""
    kept = [d for d in dets if d[5] >= threshold]
    kept.sort(key=lambda d: -d[5])
    boxes = [{"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "cls": c, "conf": fmt_decimal(conf)}
             for x1, y1, x2, y2, c, conf in kept]
    if not kept:
        top = max((d[5] for d in dets), default=0.0)
        conf = pass_confidence if pass_confidence is not None else max(0.5, 1.0 - top)
        return {"decision": "PASS", "defect_class": None, "severity": "NONE",
                "confidence": fmt_decimal(conf), "boxes": []}
    x1, y1, x2, y2, cls, conf = kept[0]
    area = sum((d[2] - d[0]) * (d[3] - d[1]) for d in kept) / float(width * height)
    sev = max((severity_for(d[4], area, d[5]) for d in kept), key=LEVELS.index)
    return {"decision": "FAIL", "defect_class": cls, "severity": sev,
            "confidence": fmt_decimal(Decimal(str(conf))), "boxes": boxes}
