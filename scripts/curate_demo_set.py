"""Build a small, balanced demo image set from NEU-DET (output is git-ignored under datasets/).

  python scripts/curate_demo_set.py --src <NEU-DET dir> --out datasets/demo --per-class 8

Creates  <out>/stream/            per-class images to stream:  python -m simulator --source dir:<out>/stream
         <out>/replay/exact.jpg   a stream image, byte-identical        -> DUPLICATE_EVIDENCE (HIGH)
         <out>/replay/near.jpg    same image, brightened + recompressed -> POSSIBLE_REPLAY   (MEDIUM)
Pairs of images that are already byte-identical or within pHash distance 8 in the source are skipped, so the demo
never raises a replay alert by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import random
import shutil
from pathlib import Path

import imagehash
from PIL import Image, ImageEnhance

CLASSES = ["crazing", "inclusion", "patches", "pitted_surface", "rolled-in_scale", "scratches"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="datasets/demo")
    ap.add_argument("--per-class", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "stream").mkdir(parents=True)
    (out / "replay").mkdir()

    files = sorted(p for p in Path(a.src).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
    chosen: list[tuple[Path, imagehash.ImageHash]] = []
    seen_sha: set[str] = set()
    for cls in CLASSES:
        pool = [p for p in files if p.stem.startswith(cls)]
        rnd.shuffle(pool)
        n = 0
        for p in pool:
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            h = imagehash.phash(Image.open(p))
            if sha in seen_sha or any(h - c[1] <= 8 for c in chosen):
                continue
            seen_sha.add(sha)
            chosen.append((p, h))
            shutil.copy2(p, out / "stream" / p.name)
            n += 1
            if n == a.per_class:
                break
    src_img = chosen[0][0]
    shutil.copy2(src_img, out / "replay" / "exact.jpg")
    buf = io.BytesIO()
    ImageEnhance.Brightness(Image.open(src_img).convert("L")).enhance(1.08).save(buf, "JPEG", quality=80)
    (out / "replay" / "near.jpg").write_bytes(buf.getvalue())
    d = imagehash.phash(Image.open(src_img)) - imagehash.phash(Image.open(out / "replay" / "near.jpg"))
    print(f"{len(chosen)} images in {out / 'stream'} ({a.per_class}/class); replay source {src_img.name}; "
          f"near-copy pHash distance {d} (threshold in risk.yaml: replay.phash_max_distance)")


if __name__ == "__main__":
    main()
