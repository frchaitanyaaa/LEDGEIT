"""POST /inspections — edge-first ingest (ADR-004). The device has already run inference and signed the
record; the API re-validates everything it can, then seals the record into the line's hash chain."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, text

from ledgeit_proof import ZERO_HASH, hash_json, parse_ts, sha256_hex, verify_hex_digest
from ledgeit_proof.record import INSPECTION_SCHEMA, RECORD_KEYS

from ..core.errors import ApiError
from ..core.time import now_ms
from ..db.engine import get_engine
from ..db.json import jdump
from ..services import risk as risk_engine
from ..services.alerts import raise_alert
from ..services.events import append_event
from ..services.feed import hub
from ..services.replay import compute_phash, find_replays
from ..services.storage import get_storage, object_key

router = APIRouter(tags=["inspections"])

HEX64 = re.compile(r"^[0-9a-f]{64}$")
CONF = re.compile(r"^(0\.\d{4}|1\.0000)$")
MIMES = {"image/jpeg", "image/png", "image/bmp"}
MAX_IMAGE = 10 * 1024 * 1024


def _bad(code: str, msg: str, **details: Any) -> ApiError:
    return ApiError(422, code, msg, details or None)


def _validate_shape(rec: dict) -> None:
    if set(rec) != RECORD_KEYS:
        raise _bad("BAD_RECORD", "record keys do not match ledgeit.inspection.v1",
                   missing=sorted(RECORD_KEYS - set(rec)), extra=sorted(set(rec) - RECORD_KEYS))
    if rec["schema"] != INSPECTION_SCHEMA:
        raise _bad("BAD_RECORD", f"unsupported schema {rec['schema']!r}")
    r = rec["result"]
    if r.get("decision") not in ("PASS", "FAIL") or r.get("severity") not in ("NONE", "MINOR", "MAJOR", "CRITICAL"):
        raise _bad("BAD_RECORD", "invalid decision or severity")
    if not isinstance(r.get("confidence"), str) or not CONF.match(r["confidence"]):
        raise _bad("BAD_RECORD", "confidence must be a decimal string with 4 places")
    for b in r.get("boxes", []):
        if not all(isinstance(b.get(k), int) for k in ("x1", "y1", "x2", "y2")) or not CONF.match(str(b.get("conf"))):
            raise _bad("BAD_RECORD", "boxes need integer coordinates and 4-place conf strings")
    if not HEX64.match(rec["evidence"].get("sha256", "")) or not HEX64.match(rec["prev_record_hash"]):
        raise _bad("BAD_RECORD", "hashes must be 64 lowercase hex chars")
    if not HEX64.match(rec["model"].get("weights_sha256", "")):
        raise _bad("BAD_RECORD", "model.weights_sha256 must be 64 lowercase hex chars")


def _existing(conn: Connection, record_hash: str) -> dict | None:
    row = conn.execute(text(
        "SELECT i.id::text AS inspection_id, i.inspection_code, i.record_hash, i.risk_level::text AS risk_level, "
        "i.risk_reasons, s.status FROM inspections i JOIN inspection_status s ON s.inspection_id=i.id "
        "WHERE i.record_hash=:h"
    ), {"h": record_hash}).mappings().first()
    return dict(row) if row else None


@router.post("/inspections", status_code=201, summary="Ingest a device-signed inspection record")
async def ingest(
    record: str = Form(..., description="ledgeit.inspection.v1 JSON"),
    device_signature: str = Form(..., description="base64 Ed25519 signature over record_hash"),
    image: UploadFile = File(...),
    heatmap: UploadFile | None = File(default=None),
    product_sku: str | None = Form(default=None, description="create batch on first use with this product"),
):
    image_bytes = await image.read()
    heatmap_bytes = await heatmap.read() if heatmap is not None else None
    # Do the blocking DB/storage work in a worker thread.
    from starlette.concurrency import run_in_threadpool

    status, body = await run_in_threadpool(_ingest_sync, record, device_signature, image_bytes,
                                           image.content_type or "", heatmap_bytes, product_sku)
    return JSONResponse(status_code=status, content=body)


def _ingest_sync(record_json: str, signature: str, image_bytes: bytes, image_mime: str,
                 heatmap_bytes: bytes | None, product_sku: str | None) -> tuple[int, dict]:
    try:
        rec = json.loads(record_json)
    except json.JSONDecodeError as e:
        raise _bad("BAD_RECORD", f"record is not JSON: {e}") from e
    if not isinstance(rec, dict):
        raise _bad("BAD_RECORD", "record must be an object")
    _validate_shape(rec)
    try:
        record_hash = hash_json(rec)
    except ValueError as e:
        raise _bad("BAD_RECORD", str(e)) from e

    ev = rec["evidence"]
    mime = ev.get("mime")
    if mime not in MIMES:
        raise _bad("BAD_EVIDENCE", f"unsupported mime {mime}")
    if not image_bytes or len(image_bytes) > MAX_IMAGE:
        raise _bad("BAD_EVIDENCE", "image missing or too large")
    if sha256_hex(image_bytes) != ev["sha256"] or len(image_bytes) != ev.get("bytes"):
        raise _bad("EVIDENCE_HASH_MISMATCH", "uploaded image does not match record.evidence")
    try:
        phash = compute_phash(image_bytes)
    except Exception as e:
        raise _bad("BAD_EVIDENCE", f"image cannot be decoded: {e}") from e
    if ev.get("phash") is not None and ev["phash"] != phash:
        raise _bad("PHASH_MISMATCH", "record.evidence.phash does not match image", expected=phash)
    hm_hash = rec["explanation"].get("heatmap_sha256")
    if hm_hash is not None and (heatmap_bytes is None or sha256_hex(heatmap_bytes) != hm_hash):
        raise _bad("EVIDENCE_HASH_MISMATCH", "heatmap missing or does not match record.explanation")
    try:
        inspected_at = parse_ts(rec["inspected_at"])
    except (ValueError, TypeError) as e:
        raise _bad("BAD_RECORD", "inspected_at must be ISO-8601 UTC") from e
    now = now_ms()
    if inspected_at > now + timedelta(minutes=5):
        raise _bad("BAD_RECORD", "inspected_at is in the future")

    alerts_out: list[str] = []
    with get_engine().begin() as conn:
        dup = _existing(conn, record_hash)
        if dup:
            return 200, {**dup, "duplicate": True}

        dev = conn.execute(text(
            "SELECT d.id::text, d.public_key, d.is_active, l.id::text AS line_id, l.code AS line_code "
            "FROM devices d JOIN production_lines l ON l.id=d.line_id WHERE d.device_code=:c FOR UPDATE OF d"
        ), {"c": rec["device"]}).mappings().first()
        if not dev or not dev["is_active"]:
            raise ApiError(403, "UNKNOWN_DEVICE", f"device {rec['device']} is not registered or inactive")
        if dev["line_code"] != rec["line"]:
            raise _bad("LINE_MISMATCH", f"device {rec['device']} belongs to {dev['line_code']}, not {rec['line']}")
        if not verify_hex_digest(record_hash, signature, dev["public_key"]):
            with get_engine().begin() as c2:
                raise_alert(c2, "SIGNATURE_INVALID", "HIGH",
                            {"device": rec["device"], "record_hash": record_hash, "stage": "ingest"})
            raise ApiError(401, "SIGNATURE_INVALID", "device signature does not verify against registered key")

        prev = conn.execute(text(
            "SELECT record_hash FROM inspections WHERE device_id=:d ORDER BY created_at DESC, id DESC LIMIT 1"
        ), {"d": dev["id"]}).scalar() or ZERO_HASH
        if rec["prev_record_hash"] != prev:
            raise ApiError(409, "PREV_RECORD_MISMATCH", "prev_record_hash is not this device's last record",
                           {"expected": prev})

        m = rec["model"]
        model = conn.execute(text(
            "SELECT id::text, weights_sha256, status::text AS status, approved_at, retired_at FROM ai_models "
            "WHERE name=:n AND version=:v"
        ), {"n": m["name"], "v": m["version"]}).mappings().first()
        if not model or model["weights_sha256"] != m["weights_sha256"]:
            with get_engine().begin() as c2:
                raise_alert(c2, "MODEL_MISMATCH", "HIGH", {
                    "device": rec["device"], "model": m, "reason": "unknown model" if not model else "weights mismatch",
                })
            raise _bad("MODEL_MISMATCH", "model is not registered or weights_sha256 differs from the registry")
        model_ok = model["status"] == "APPROVED" and model["approved_at"] is not None \
            and model["approved_at"] <= inspected_at and (model["retired_at"] is None or model["retired_at"] > inspected_at)

        batch = conn.execute(text(
            "SELECT b.id::text, b.line_id::text, p.is_regulated FROM batches b JOIN products p ON p.id=b.product_id "
            "WHERE b.batch_code=:b"
        ), {"b": rec["batch_code"]}).mappings().first()
        if not batch and product_sku:
            prod = conn.execute(text("SELECT id::text, is_regulated FROM products WHERE sku=:s"),
                                {"s": product_sku}).mappings().first()
            if not prod:
                raise _bad("UNKNOWN_PRODUCT", f"product {product_sku} not found")
            bid = conn.execute(text(
                "INSERT INTO batches(batch_code, product_id, line_id, started_at) VALUES (:b, :p, :l, :t) "
                "RETURNING id::text"
            ), {"b": rec["batch_code"], "p": prod["id"], "l": dev["line_id"], "t": inspected_at}).scalar_one()
            batch = {"id": bid, "line_id": dev["line_id"], "is_regulated": prod["is_regulated"]}
        if not batch:
            raise _bad("UNKNOWN_BATCH", f"batch {rec['batch_code']} not found (send product_sku to create it)")
        if batch["line_id"] != dev["line_id"]:
            raise _bad("LINE_MISMATCH", "batch runs on a different line than the device")

        replays = find_replays(conn, ev["sha256"], phash, rec["unit_serial"], now)
        risk, reasons = risk_engine.classify(
            rec["result"], regulated=batch["is_regulated"],
            replay_alert=bool(replays["exact"] or replays["near"]), unapproved_model=not model_ok,
        )

        storage = get_storage()
        img_uri = storage.put(object_key("IMAGE", ev["sha256"], mime, inspected_at), image_bytes, mime)
        size = _dims(image_bytes)
        img_id = conn.execute(text(
            "INSERT INTO evidence(kind, sha256, phash, storage_uri, mime_type, size_bytes, width, height, device_id, "
            "captured_at) VALUES ('IMAGE', :h, :ph, :u, :m, :s, :w, :ht, :d, :t) RETURNING id::text"
        ), {"h": ev["sha256"], "ph": phash, "u": img_uri, "m": mime, "s": len(image_bytes), "w": size[0],
            "ht": size[1], "d": dev["id"], "t": inspected_at}).scalar_one()
        hm_id = None
        if heatmap_bytes is not None and hm_hash:
            hm_uri = storage.put(object_key("HEATMAP", hm_hash, "image/png", inspected_at), heatmap_bytes, "image/png")
            hsize = _dims(heatmap_bytes)
            hm_id = conn.execute(text(
                "INSERT INTO evidence(kind, sha256, phash, storage_uri, mime_type, size_bytes, width, height, "
                "device_id, captured_at) VALUES ('HEATMAP', :h, NULL, :u, 'image/png', :s, :w, :ht, :d, :t) "
                "RETURNING id::text"
            ), {"h": hm_hash, "u": hm_uri, "s": len(heatmap_bytes), "w": hsize[0], "ht": hsize[1], "d": dev["id"],
                "t": inspected_at}).scalar_one()

        r = rec["result"]
        iid = rec["inspection_id"]
        conn.execute(text(
            "INSERT INTO inspections(id, inspection_code, unit_serial, batch_id, line_id, device_id, model_id, "
            "evidence_id, heatmap_evidence_id, decision, defect_class, severity, confidence, explanation, risk_level, "
            "risk_reasons, canonical_record, record_hash, device_signature, inspected_at) VALUES (:id, :code, :u, "
            ":b, :l, :d, :m, :e, :he, CAST(:dec AS decision_t), :cls, CAST(:sev AS severity_t), :conf, "
            "CAST(:expl AS jsonb), CAST(:risk AS risk_t), :reasons, CAST(:rec AS jsonb), :rh, :sig, :t)"
        ), {"id": iid, "code": rec["inspection_code"], "u": rec["unit_serial"], "b": batch["id"], "l": dev["line_id"],
            "d": dev["id"], "m": model["id"], "e": img_id, "he": hm_id, "dec": r["decision"],
            "cls": r.get("defect_class"), "sev": r["severity"], "conf": r["confidence"],
            "expl": jdump({**rec["explanation"], "boxes": r.get("boxes", [])}), "risk": risk, "reasons": reasons,
            "rec": jdump(rec), "rh": record_hash, "sig": signature, "t": inspected_at})
        auto = risk == "LOW" and r["decision"] == "PASS"
        conn.execute(text(
            "INSERT INTO inspection_status(inspection_id, status, final_decision) VALUES (:i, :s, CAST(:d AS decision_t))"
        ), {"i": iid, "s": "AUTO_ACCEPTED" if auto else "PENDING_REVIEW", "d": "PASS" if auto else None})

        common = {"inspection_id": iid, "line_id": dev["line_id"], "line_code": dev["line_code"],
                  "actor_type": "DEVICE", "actor_id": rec["device"], "risk": risk}
        events = [
            append_event(conn, event_type="INSPECTED", payload={
                "inspection_id": iid, "unit_serial": rec["unit_serial"], "decision": r["decision"],
                "confidence": r["confidence"]}, **common),
            append_event(conn, event_type="EVIDENCE_HASHED", payload={
                "inspection_id": iid, "evidence_sha256": ev["sha256"], "heatmap_sha256": hm_hash}, **common),
            append_event(conn, event_type="RECORD_CREATED", payload={
                "inspection_id": iid, "record_hash": record_hash, "device_signature": signature},
                signature=signature, **common),
        ]

        if replays["exact"]:
            alerts_out.append("DUPLICATE_EVIDENCE")
            raise_alert(conn, "DUPLICATE_EVIDENCE", "HIGH", {"evidence_sha256": ev["sha256"], "matches": replays["exact"],
                                                             "unit_serial": rec["unit_serial"]}, iid)
        elif replays["near"]:
            alerts_out.append("POSSIBLE_REPLAY")
            raise_alert(conn, "POSSIBLE_REPLAY", "MEDIUM", {"phash": phash, "matches": replays["near"],
                                                            "unit_serial": rec["unit_serial"]}, iid)
        if not model_ok:
            alerts_out.append("MODEL_MISMATCH")
            raise_alert(conn, "MODEL_MISMATCH", "HIGH", {"model": m, "status": model["status"],
                                                         "reason": "model not APPROVED at inspected_at"}, iid)
        from decimal import Decimal

        from ..core.yamlconf import risk_config
        low = Decimal(risk_config()["alerts"]["low_confidence_below"])
        if Decimal(r["confidence"]) < low:
            alerts_out.append("LOW_CONFIDENCE")
            raise_alert(conn, "LOW_CONFIDENCE", "MEDIUM", {"confidence": r["confidence"], "threshold": str(low)}, iid)

        status = "AUTO_ACCEPTED" if auto else "PENDING_REVIEW"

    out = {
        "inspection_id": iid, "inspection_code": rec["inspection_code"], "record_hash": record_hash,
        "risk_level": risk, "risk_reasons": reasons, "status": status, "alerts": alerts_out,
        "events": [{"seq": e["seq"], "event_type": e["event_type"], "event_hash": e["event_hash"]} for e in events],
    }
    hub.publish("inspection", {
        **out, "unit_serial": rec["unit_serial"], "line": rec["line"], "device": rec["device"],
        "decision": r["decision"], "defect_class": r.get("defect_class"), "severity": r["severity"],
        "confidence": r["confidence"], "model": m, "inspected_at": rec["inspected_at"],
    })
    return 201, out


def _dims(data: bytes) -> tuple[int | None, int | None]:
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as im:
            return im.size
    except Exception:
        return None, None
