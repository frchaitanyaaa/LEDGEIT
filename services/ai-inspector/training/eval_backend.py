"""Evaluate an inference backend on real NEU-DET images with ground truth (works for stub now, YOLO later).

Every NEU-DET image contains a defect, so the useful numbers are: detection recall (decision == FAIL), class accuracy,
localisation hit-rate (a predicted box overlaps a ground-truth box with IoU >= 0.5) and latency. PASS behaviour on
defect-free surfaces cannot be measured with this dataset alone - use `--clean-dir` with defect-free images/crops
(false-FAIL rate) once you have them.

Usage (from services/ai-inspector):
  python training/eval_backend.py --src <NEU-DET dir> [--kind stub|yolo] [--version 1.0.0] [--limit 600] [--clean-dir DIR]
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.backends import make_backend  # noqa: E402


def gt_boxes(xml: Path) -> list[tuple[float, float, float, float, str]]:
    out = []
    for o in ET.parse(xml).getroot().iter("object"):
        b = o.find("bndbox")
        out.append((*(float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")), o.findtext("name").strip().lower()))
    return out


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--kind", default="stub", choices=["stub", "yolo"])
    ap.add_argument("--name", default=None)
    ap.add_argument("--version", default=None)
    ap.add_argument("--limit", type=int, default=0, help="max images (0 = all)")
    ap.add_argument("--clean-dir", default=None, help="defect-free images to measure false-FAIL rate")
    a = ap.parse_args()

    be = make_backend(a.name, a.version, a.kind)
    print(f"model: {be.entry['name']}@{be.entry['version']} ({a.kind}) weights {be.weights_sha256[:12]}...")
    imgs = {p.stem: p for p in Path(a.src).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")}
    pairs = sorted((imgs[x.stem], x) for x in Path(a.src).rglob("*.xml") if x.stem in imgs)
    if a.limit:
        step = max(1, len(pairs) // a.limit)
        pairs = pairs[::step][:a.limit]

    lat, fails, cls_ok, loc_ok = [], 0, 0, 0
    per = defaultdict(lambda: Counter())
    confusion = Counter()
    for img, xml in pairs:
        gt = gt_boxes(xml)
        truth = gt[0][4]
        t0 = time.perf_counter()
        r = be.infer(img.read_bytes()).result
        lat.append((time.perf_counter() - t0) * 1000)
        per[truth]["n"] += 1
        if r["decision"] == "FAIL":
            fails += 1
            per[truth]["detected"] += 1
            if r["defect_class"] == truth:
                cls_ok += 1
                per[truth]["class_ok"] += 1
            confusion[(truth, r["defect_class"])] += 1
            pred = [(b["x1"], b["y1"], b["x2"], b["y2"]) for b in r["boxes"]]
            if any(iou(p, g[:4]) >= 0.5 for p in pred for g in gt):
                loc_ok += 1
                per[truth]["loc_ok"] += 1
    n = len(pairs)
    print(f"\n{n} real NEU-DET images")
    print(f"detection recall (FAIL on defective): {fails}/{n} = {100 * fails / n:.1f}%")
    print(f"class accuracy (of all):              {cls_ok}/{n} = {100 * cls_ok / n:.1f}%")
    print(f"localisation hit-rate (IoU>=0.5):     {loc_ok}/{n} = {100 * loc_ok / n:.1f}%")
    print(f"latency ms: p50 {statistics.median(lat):.1f}  p95 {sorted(lat)[int(0.95 * len(lat)) - 1]:.1f}  "
          f"=> {1000 / statistics.mean(lat):.1f} img/s on this machine")
    print(f"\n{'class':<17}{'n':>5}{'recall%':>9}{'class%':>8}{'loc%':>7}")
    for c, v in sorted(per.items()):
        print(f"{c:<17}{v['n']:>5}{100 * v['detected'] / v['n']:>9.1f}{100 * v['class_ok'] / v['n']:>8.1f}"
              f"{100 * v['loc_ok'] / v['n']:>7.1f}")

    if a.clean_dir:
        clean = [p for p in Path(a.clean_dir).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")]
        ff = sum(be.infer(p.read_bytes()).result["decision"] == "FAIL" for p in clean)
        print(f"\nfalse-FAIL rate on {len(clean)} defect-free images: {ff}/{len(clean)} = {100 * ff / max(1, len(clean)):.1f}%")


if __name__ == "__main__":
    main()
