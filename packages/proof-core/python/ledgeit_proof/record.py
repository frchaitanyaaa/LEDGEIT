"""Builders for the signed payload formats in SPEC §5–6 (helpers, not part of the hash spec)."""

from __future__ import annotations

from typing import Any

INSPECTION_SCHEMA = "ledgeit.inspection.v1"
OVERRIDE_SCHEMA = "ledgeit.override.v1"
REVIEW_SCHEMA = "ledgeit.review.v1"
APPROVAL_SCHEMA = "ledgeit.approval.v1"
DISPUTE_SCHEMA = "ledgeit.dispute.v1"

RECORD_KEYS = {"schema", "inspection_id", "inspection_code", "unit_serial", "batch_code", "line", "device",
               "inspected_at", "evidence", "model", "result", "explanation", "prev_record_hash"}


def build_inspection_record(
    *,
    inspection_id: str,
    inspection_code: str,
    unit_serial: str,
    batch_code: str,
    line: str,
    device: str,
    inspected_at: str,
    evidence_sha256: str,
    phash: str | None,
    mime: str,
    size_bytes: int,
    model: dict[str, str],
    result: dict[str, Any],
    explanation_method: str,
    heatmap_sha256: str | None,
    summary: str,
    prev_record_hash: str,
) -> dict[str, Any]:
    return {
        "schema": INSPECTION_SCHEMA,
        "inspection_id": inspection_id,
        "inspection_code": inspection_code,
        "unit_serial": unit_serial,
        "batch_code": batch_code,
        "line": line,
        "device": device,
        "inspected_at": inspected_at,
        "evidence": {"sha256": evidence_sha256, "phash": phash, "mime": mime, "bytes": size_bytes},
        "model": {"name": model["name"], "version": model["version"], "weights_sha256": model["weights_sha256"]},
        "result": {
            "decision": result["decision"],
            "defect_class": result.get("defect_class"),
            "severity": result["severity"],
            "confidence": result["confidence"],
            "boxes": result.get("boxes", []),
        },
        "explanation": {"method": explanation_method, "heatmap_sha256": heatmap_sha256, "summary": summary},
        "prev_record_hash": prev_record_hash,
    }
