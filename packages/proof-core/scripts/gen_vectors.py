"""Generate packages/proof-core/test-vectors/*.json from the Python reference implementation.

Run:  python packages/proof-core/scripts/gen_vectors.py
Both the Python and TypeScript implementations must reproduce every value in these files.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from ledgeit_proof import (  # noqa: E402
    ZERO_HASH,
    build_tree,
    canonicalize,
    compute_event_hash,
    genesis_hash,
    hash_json,
    keypair_from_seed,
    leaf_hash,
    sha256_hex,
)

OUT = ROOT / "test-vectors"


def seed(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()


def write(name: str, data: object) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def canonical_vectors() -> None:
    inputs = [
        {"b": 2, "a": 1},
        {"z": {"y": [3, 2, 1], "x": None}, "a": [True, False]},
        {"confidence": "0.9640", "n": -42, "big": 9007199254740991},
        {"unicode": "défaut — ½ 鋼", "emoji": "🔩", "esc": "line\nbreak \"q\" \\ \t"},
        {"é": 1, "e": 2, "\U0001f600": 3, "０": 4},
        {"control": "\u0001\u001f", "empty": {}, "arr": []},
        [],
        "plain string",
        0,
    ]
    write(
        "canonical.json",
        {
            "description": "JCS canonical form (UTF-8) and SHA-256 of each input",
            "cases": [
                {"input": v, "canonical": canonicalize(v).decode("utf-8"), "sha256": hash_json(v)}
                for v in inputs
            ],
            "must_reject": [{"input_json": "{\"x\": 0.5}", "reason": "float"},
                            {"input_json": "{\"x\": 9007199254740992}", "reason": "unsafe integer"}],
        },
    )


def chain_vectors() -> list[str]:
    line = "LINE-A"
    events = []
    prev = genesis_hash(line)
    specs = [
        ("INSPECTED", "DEVICE", "CAM-A-01", {"inspection_id": "11111111-1111-4111-8111-111111111111", "decision": "FAIL"}),
        ("EVIDENCE_HASHED", "DEVICE", "CAM-A-01", {"evidence_sha256": sha256_hex(b"image-1")}),
        ("RECORD_CREATED", "DEVICE", "CAM-A-01", {"record_hash": sha256_hex(b"record-1")}),
        ("OVERRIDDEN", "USER", "QE-0042", {"reason_code": "FALSE_POSITIVE"}),
        ("RELEASED", "SYSTEM", None, {"final_decision": "PASS"}),
    ]
    for i, (et, at, aid, payload) in enumerate(specs, start=1):
        created_at = f"2026-10-20T10:31:0{i}.120Z"
        ph = hash_json(payload)
        eh = compute_event_hash(
            line=line, seq=i, event_type=et, actor_type=at, actor_id=aid,
            payload_hash=ph, prev_event_hash=prev, created_at=created_at,
        )
        events.append({
            "seq": i, "event_type": et, "actor_type": at, "actor_id": aid, "payload": payload,
            "payload_hash": ph, "prev_event_hash": prev, "event_hash": eh, "created_at": created_at,
        })
        prev = eh
    write("chain.json", {
        "description": "Per-line hash chain. genesis = SHA256('LEDGEIT-GENESIS-v1:' + line)",
        "line": line,
        "genesis": genesis_hash(line),
        "events": events,
    })
    return [e["event_hash"] for e in events]


def merkle_vectors(event_hashes: list[str]) -> None:
    base = event_hashes + [sha256_hex(f"extra-{i}".encode()) for i in range(8)]
    cases = []
    for n in [1, 2, 3, 4, 5, 6, 7, 8, 13]:
        hs = base[:n]
        t = build_tree(hs)
        cases.append({"event_hashes": hs, "leaves": t.leaves, "root": t.root, "proofs": t.proofs})
    write("merkle.json", {
        "description": "leaf = SHA256(0x00||h); node = SHA256(0x01||l||r); odd node promoted",
        "leaf_example": {"event_hash": base[0], "leaf": leaf_hash(base[0])},
        "cases": cases,
    })


def signature_vectors() -> None:
    cases = []
    for label in ["device:CAM-A-01", "user:QE-0042", "user:QM-0007"]:
        kp = keypair_from_seed(seed(label))
        msg = sha256_hex(label.encode())
        cases.append({"label": label, "seed_b64": kp.seed_b64, "public_key_b64": kp.public_key_b64,
                      "message_hex": msg, "signature_b64": kp.sign(msg)})
    other = keypair_from_seed(seed("other"))
    write("signatures.json", {
        "description": "Ed25519 over ASCII bytes of the hex digest. Keys/sigs standard base64.",
        "cases": cases,
        "invalid": [{"public_key_b64": other.public_key_b64, "message_hex": cases[0]["message_hex"],
                     "signature_b64": cases[0]["signature_b64"], "reason": "wrong key"}],
    })


def record_vectors() -> None:
    device = keypair_from_seed(seed("device:CAM-A-01"))
    record = {
        "schema": "ledgeit.inspection.v1",
        "inspection_id": "8f0e7c1a-5b2d-4d1e-9a77-3c2f1e0b9d44",
        "inspection_code": "INS-20261020-A01-000123",
        "unit_serial": "UNIT-A-000123",
        "batch_code": "BATCH-2026-10-20-A",
        "line": "LINE-A",
        "device": "CAM-A-01",
        "inspected_at": "2026-10-20T10:31:02.120Z",
        "evidence": {"sha256": sha256_hex(b"raw-image-bytes"), "phash": "c3d1e0f0a8b4c2d1",
                     "mime": "image/jpeg", "bytes": 48211},
        "model": {"name": "ledgeit-defect-yolo", "version": "1.2.0", "weights_sha256": sha256_hex(b"weights")},
        "result": {"decision": "FAIL", "defect_class": "scratches", "severity": "MAJOR", "confidence": "0.9640",
                   "boxes": [{"x1": 34, "y1": 80, "x2": 120, "y2": 140, "cls": "scratches", "conf": "0.9640"}]},
        "explanation": {"method": "EigenCAM", "heatmap_sha256": sha256_hex(b"heatmap"),
                        "summary": "Linear high-contrast streak in upper-left region"},
        "prev_record_hash": ZERO_HASH,
    }
    rh = hash_json(record)
    tampered = json.loads(json.dumps(record))
    tampered["result"]["decision"] = "PASS"
    write("record.json", {
        "description": "Inspection proof record; device signs record_hash",
        "record": record,
        "canonical": canonicalize(record).decode("utf-8"),
        "record_hash": rh,
        "device_public_key_b64": device.public_key_b64,
        "device_signature_b64": device.sign(rh),
        "tampered_record_hash": hash_json(tampered),
    })


if __name__ == "__main__":
    canonical_vectors()
    ehs = chain_vectors()
    merkle_vectors(ehs)
    signature_vectors()
    record_vectors()
    print(f"wrote vectors to {OUT}")
