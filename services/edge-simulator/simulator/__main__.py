"""LEDGEIT edge simulator.

Examples:
  python -m simulator --count 50 --rate 2                    # stream 50 synthetic frames at 2/s
  python -m simulator --device CAM-B-01 --batch BATCH-B-001  # regulated product line
  python -m simulator --source dir:datasets/neu-det/images   # stream real NEU-DET images
  python -m simulator --replay 3                             # re-send synthetic frame #3 as a new unit (attack)
  python -m simulator --near-replay 3                        # brightened + recompressed copy of frame #3
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageEnhance

from .device import EdgeDevice, http_infer, load_key
from .synth import generate

ROOT = Path(__file__).resolve().parents[3]


def frames(source: str, start: int, defect_rate: float, seed: int):
    if source == "synth":
        i = start
        while True:
            s = generate(i, seed=seed, defect_rate=defect_rate)
            yield i, s.jpeg, "image/jpeg", s.truth
            i += 1
    elif source.startswith("dir:"):
        files = sorted(p for p in Path(source[4:]).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
        if not files:
            raise SystemExit(f"no images in {source[4:]}")
        rnd = random.Random(seed)
        i = start
        while True:
            p = rnd.choice(files)
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "bmp": "image/bmp"}[p.suffix[1:].lower()]
            yield i, p.read_bytes(), mime, p.parent.name
            i += 1
    else:
        raise SystemExit("--source must be 'synth' or 'dir:<path>'")


def near_copy(jpeg: bytes) -> bytes:
    img = ImageEnhance.Brightness(Image.open(io.BytesIO(jpeg))).enhance(1.08)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="simulator", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--ai", default=os.environ.get("AI_INSPECTOR_URL", "http://localhost:8001"))
    ap.add_argument("--device", default="CAM-A-01")
    ap.add_argument("--batch", default=None, help="default: BATCH-A-001 for line A, BATCH-B-001 for line B")
    ap.add_argument("--product-sku", default=None, help="create --batch on first use with this product")
    ap.add_argument("--keys-dir", default=str(ROOT / "services" / "edge-simulator" / "keys"))
    ap.add_argument("--source", default="synth")
    ap.add_argument("--count", type=int, default=20, help="0 = run forever")
    ap.add_argument("--rate", type=float, default=1.0, help="frames per second")
    ap.add_argument("--start", type=int, default=None, help="first synthetic frame index (default: device count)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--defect-rate", type=float, default=0.35)
    ap.add_argument("--model-version", default=None)
    ap.add_argument("--burst", action="store_true", help="ignore --rate and send as fast as possible")
    ap.add_argument("--replay", type=int, metavar="FRAME", help="re-send synthetic frame FRAME as a new unit")
    ap.add_argument("--near-replay", type=int, metavar="FRAME", help="send a brightened/recompressed copy of FRAME")
    a = ap.parse_args(argv)

    key = load_key(Path(a.keys_dir), a.device)
    api = httpx.Client(base_url=a.api, timeout=30)
    ai = httpx.Client(base_url=a.ai, timeout=60)
    dev = EdgeDevice(code=a.device, seed_b64=key["seed_b64"], api=api, infer=http_infer(ai))
    dev.sync_head()
    batch = a.batch or ("BATCH-B-001" if dev.line == "LINE-B" else "BATCH-A-001")
    print(f"[{a.device}] line={dev.line} batch={batch} head={dev.last_record_hash[:12]}… count={dev.counter}")

    def send(img: bytes, mime: str, label: str) -> None:
        serial = f"UNIT-{dev.line[-1]}-{dev.counter + 1:06d}"
        r = dev.inspect(img, mime=mime, unit_serial=serial, batch_code=batch, model_version=a.model_version,
                        product_sku=a.product_sku)
        if r.status_code in (200, 201):
            b = r.json()
            last = dev.sent[-1]["record"]["result"] if dev.sent else {}
            print(f"  {b['inspection_code']}  {last.get('decision', '?'):4} {last.get('defect_class') or '-':16} "
                  f"conf={last.get('confidence', '?')}  risk={b['risk_level']:<6} {b['status']:<15} "
                  f"{'ALERTS=' + ','.join(b.get('alerts', [])) if b.get('alerts') else ''} [{label}]")
        else:
            print(f"  ERROR {r.status_code}: {r.text}", file=sys.stderr)

    if a.replay is not None or a.near_replay is not None:
        idx = a.replay if a.replay is not None else a.near_replay
        jpeg = generate(idx, seed=a.seed, defect_rate=a.defect_rate).jpeg
        if a.near_replay is not None:
            jpeg = near_copy(jpeg)
        send(jpeg, "image/jpeg", ("near-replay" if a.near_replay is not None else "replay") + f" of frame {idx}")
        return 0

    start = a.start if a.start is not None else dev.counter + 1000 * (1 if dev.line == "LINE-B" else 0)
    for n, (i, img, mime, truth) in enumerate(frames(a.source, start, a.defect_rate, a.seed), start=1):
        t0 = time.monotonic()
        send(img, mime, f"frame {i}, truth={truth or 'good'}")
        if a.count and n >= a.count:
            break
        if not a.burst and a.rate > 0:
            time.sleep(max(0.0, 1.0 / a.rate - (time.monotonic() - t0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
