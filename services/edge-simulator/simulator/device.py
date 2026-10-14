"""An edge AI camera: runs inference, seals the record, signs it with its device key, posts it."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import imagehash
from PIL import Image

from ledgeit_proof import build_inspection_record, fmt_ts, hash_json, sign_hex_digest

InferFn = Callable[[bytes, str, str | None], dict]


def http_infer(ai: httpx.Client) -> InferFn:
    def _infer(data: bytes, mime: str, version: str | None) -> dict:
        params = {"version": version} if version else None
        r = ai.post("/infer", files={"image": ("frame", data, mime)}, params=params)
        r.raise_for_status()
        return r.json()

    return _infer


def load_key(keys_dir: Path, device_code: str) -> dict:
    f = keys_dir / f"{device_code}.json"
    if not f.exists():
        raise SystemExit(f"device key {f} not found — run `make seed` first (it generates device keys)")
    return json.loads(f.read_text())


@dataclass
class EdgeDevice:
    code: str
    seed_b64: str
    api: httpx.Client
    infer: InferFn
    line: str = ""
    last_record_hash: str = "0" * 64
    counter: int = 0
    sent: list[dict] = field(default_factory=list)

    def sync_head(self) -> None:
        r = self.api.get(f"/api/v1/devices/{self.code}/head")
        r.raise_for_status()
        h = r.json()
        self.line, self.last_record_hash, self.counter = h["line"], h["last_record_hash"], h["count"]

    def _code(self, now: datetime) -> str:
        short = self.code.replace("CAM-", "").replace("-", "")
        return f"INS-{now:%Y%m%d}-{short}-{self.counter + 1:06d}"

    def inspect(self, image: bytes, *, mime: str = "image/jpeg", unit_serial: str, batch_code: str,
                model_version: str | None = None, product_sku: str | None = None,
                tamper_after_sign: Callable[[dict], None] | None = None) -> httpx.Response:
        ai = self.infer(image, mime, model_version)
        heatmap = base64.b64decode(ai["heatmap_png_b64"])
        now = datetime.now(timezone.utc)
        record = build_inspection_record(
            inspection_id=str(uuid.uuid4()),
            inspection_code=self._code(now),
            unit_serial=unit_serial,
            batch_code=batch_code,
            line=self.line,
            device=self.code,
            inspected_at=fmt_ts(now),
            evidence_sha256=hashlib.sha256(image).hexdigest(),
            phash=str(imagehash.phash(Image.open(io.BytesIO(image)))),
            mime=mime,
            size_bytes=len(image),
            model=ai["model"],
            result=ai,
            explanation_method=ai["explanation"]["method"],
            heatmap_sha256=hashlib.sha256(heatmap).hexdigest(),
            summary=ai["explanation"]["summary"],
            prev_record_hash=self.last_record_hash,
        )
        record_hash = hash_json(record)
        signature = sign_hex_digest(record_hash, self.seed_b64)
        if tamper_after_sign:
            tamper_after_sign(record)  # used by tests/attacks: signature no longer matches
        data = {"record": json.dumps(record), "device_signature": signature}
        if product_sku:
            data["product_sku"] = product_sku
        files = {"image": ("evidence", image, mime), "heatmap": ("heatmap.png", heatmap, "image/png")}
        r = self.api.post("/api/v1/inspections", data=data, files=files)
        if r.status_code == 201:
            self.last_record_hash = record_hash
            self.counter += 1
            self.sent.append({"record": record, "response": r.json()})
        elif r.status_code == 409 and r.json().get("error", {}).get("code") == "PREV_RECORD_MISMATCH":
            self.sync_head()
        return r
