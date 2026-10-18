"""Tune `replay.phash_max_distance` (config/risk.yaml) on real NEU-DET images.

Replay detection raises POSSIBLE_REPLAY when two images with different unit serials have a pHash Hamming
distance <= the threshold. Too low misses re-compressed/cropped copies; too high flags genuinely different
surfaces (NEU-DET is 6 very similar textures). This sweeps the threshold and reports both error rates:

  * miss rate   - tampered copies (JPEG re-compress, brighten, small crop, noise) NOT flagged
  * false alarm - distinct real images flagged as a replay of each other

Usage: python training/tune_phash.py --src datasets/NEU-DET [--max-d 14]
Pick the largest threshold that still has ~0 false alarms, then edit risk.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import random
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageEnhance


def phash_img(img: Image.Image) -> imagehash.ImageHash:
    return imagehash.phash(img)


def variants(img: Image.Image, rng: random.Random) -> dict[str, Image.Image]:
    out = {}
    for q in (75, 40):
        buf = io.BytesIO()
        img.convert("L").save(buf, "JPEG", quality=q)
        out[f"jpeg_q{q}"] = Image.open(io.BytesIO(buf.getvalue()))
    out["brighten"] = ImageEnhance.Brightness(img).enhance(1.25)
    out["contrast"] = ImageEnhance.Contrast(img).enhance(1.2)
    w, h = img.size
    m = int(0.05 * w)
    out["crop5"] = img.crop((m, m, w - m, h - m)).resize((w, h))
    arr = np.asarray(img.convert("L"), dtype=np.float32) + np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, 6, (h, w))
    out["noise"] = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="datasets/NEU-DET")
    ap.add_argument("--max-d", type=int, default=14)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    files = sorted(p for p in Path(a.src).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".bmp", ".png"))
    if len(files) < 10:
        raise SystemExit(f"no images under {a.src}")
    hashes = [phash_img(Image.open(f)) for f in files]
    cls = [f.stem.rsplit("_", 1)[0] for f in files]

    # Exhaustive all-pairs distances (n=1800 -> 1.6M pairs, instant with numpy). Byte-identical files are
    # genuine duplicates in the dataset (an exact replay), not false alarms, so they are excluded.
    bits = np.array([h.hash.flatten() for h in hashes])
    dist = (bits[:, None, :] != bits[None, :, :]).sum(2)
    sha = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
    iu = np.triu_indices(len(files), k=1)
    keep = np.array([sha[i] != sha[j] for i, j in zip(*iu)])
    same = np.array([cls[i] == cls[j] for i, j in zip(*iu)])
    d_all = dist[iu][keep]
    d_same = dist[iu][keep & same]
    distinct = {"all": d_all.tolist(), "same_class": d_same.tolist()}

    copies: dict[str, list[int]] = {}
    for idx in rng.sample(range(len(files)), min(300, len(files))):
        img = Image.open(files[idx])
        for name, v in variants(img, rng).items():
            copies.setdefault(name, []).append(hashes[idx] - phash_img(v))
    all_copy = [d for v in copies.values() for d in v]

    print(f"{len(files)} images; {len(distinct['all'])} distinct pairs (exhaustive) ({len(distinct['same_class'])} same-class); "
          f"{len(all_copy)} tampered copies\n")
    print("copy distance by attack (mean / max): " + ", ".join(f"{k} {np.mean(v):.1f}/{max(v)}" for k, v in copies.items()))
    print(f"distinct-pair distance: min {min(distinct['all'])}, p1 {np.percentile(distinct['all'], 1):.0f}, "
          f"median {np.median(distinct['all']):.0f}\n")
    print(f"{'thr':>4} {'miss%':>7} {'false-alarm% (all)':>20} {'false-alarm% (same class)':>27}")
    best = None
    for t in range(0, a.max_d + 1):
        miss = 100 * np.mean([d > t for d in all_copy])
        fa = 100 * np.mean([d <= t for d in distinct["all"]])
        fas = 100 * np.mean([d <= t for d in distinct["same_class"]]) if distinct["same_class"] else 0.0
        print(f"{t:>4} {miss:>7.1f} {fa:>20.2f} {fas:>27.2f}")
        if fa == 0.0 and fas == 0.0:
            best = t  # largest threshold with zero false alarms
    print(f"\nLargest threshold with zero false alarms: {best}  (use it, or a little below for margin)")


if __name__ == "__main__":
    main()
