"""Convert NEU-DET (Pascal VOC XML) into a YOLO dataset.

Expected input (as distributed on Kaggle / the NEU site):
  <src>/ANNOTATIONS/*.xml   and   <src>/IMAGES/*.jpg
  (also handles <src>/{train,validation}/{annotations,images}/... layouts)

Output: datasets/neu-det-yolo/{images,labels}/{train,val} + data.yaml

Usage: python training/prepare_neu_det.py --src datasets/NEU-DET --out datasets/neu-det-yolo --val 0.2
"""

from __future__ import annotations

import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

CLASSES = ["crazing", "inclusion", "patches", "pitted_surface", "rolled-in_scale", "scratches"]


def find_pairs(src: Path) -> list[tuple[Path, Path]]:
    images = {p.stem: p for p in src.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".bmp", ".png")}
    pairs = []
    for x in src.rglob("*.xml"):
        if x.stem in images:
            pairs.append((images[x.stem], x))
    return sorted(pairs)


def convert(xml: Path) -> list[str]:
    root = ET.parse(xml).getroot()
    w = float(root.findtext("size/width") or 200)
    h = float(root.findtext("size/height") or 200)
    lines = []
    for obj in root.iter("object"):
        name = obj.findtext("name").strip().lower().replace("rolled-in_scale", "rolled-in_scale")
        if name not in CLASSES:
            continue
        bb = obj.find("bndbox")
        x1, y1, x2, y2 = (float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        cx, cy, bw, bh = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h
        lines.append(f"{CLASSES.index(name)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="datasets/NEU-DET")
    ap.add_argument("--out", default="datasets/neu-det-yolo")
    ap.add_argument("--val", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    pairs = find_pairs(src)
    if not pairs:
        raise SystemExit(f"no image/xml pairs found under {src}")
    random.Random(a.seed).shuffle(pairs)
    n_val = int(len(pairs) * a.val)
    for split, items in (("val", pairs[:n_val]), ("train", pairs[n_val:])):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        for img, xml in items:
            shutil.copy2(img, out / "images" / split / img.name)
            (out / "labels" / split / f"{img.stem}.txt").write_text("\n".join(convert(xml)) + "\n")
    (out / "data.yaml").write_text(
        f"path: {out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES))
    )
    print(f"{len(pairs) - n_val} train / {n_val} val -> {out}/data.yaml")


if __name__ == "__main__":
    main()
