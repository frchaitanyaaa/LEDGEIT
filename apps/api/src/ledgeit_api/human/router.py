"""Signed human actions (CHAITANYA.md §6.3, SPEC §6): review, override, approval, dispute.

The browser builds the payload, signs SHA256(JCS(payload)) with the user's Ed25519 key, and posts
{payload, signature}. The server re-checks every field against the record, the user and the state machine,
then appends the payload to the line's hash chain as a USER event (anchored as HIGH risk).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, text

from ledgeit_proof import hash_json, parse_ts, verify_hex_digest
from ledgeit_proof.record import APPROVAL_SCHEMA, DISPUTE_SCHEMA, OVERRIDE_SCHEMA, REVIEW_SCHEMA

from ..auth.deps import ALL_ROLES, CurrentUser, require_roles
from ..core.config import get_settings
from ..core.errors import ApiError, not_found
from ..core.time import now_ms
from ..db.engine import get_engine
from ..db.json import jdump
from ..inspections.queries import resolve_inspection_id
from ..services.alerts import raise_alert
from ..services.events import append_event, set_status
from ..services.feed import hub
from ..services.risk import human_event_risk

router = APIRouter(tags=["human-review"])

REASON_CODES = {"FALSE_POSITIVE", "FALSE_NEGATIVE", "LIGHTING", "SENSOR_FAULT", "OTHER"}


class SignedIn(BaseModel):
    payload: dict[str, Any]
    signature: str


def _bad(code: str, msg: str) -> ApiError:
    return ApiError(422, code, msg)


def _load(conn: Connection, inspection_id: str) -> dict:
    row = conn.execute(text("""
        SELECT i.id::text AS id, i.inspection_code, i.record_hash, i.decision::text AS decision,
               i.confidence::text AS confidence, i.line_id::text AS line_id, l.code AS line_code,
               s.status, e1.sha256 AS evidence_sha256, e2.sha256 AS heatmap_sha256
        FROM inspections i JOIN production_lines l ON l.id=i.line_id
        JOIN inspection_status s ON s.inspection_id=i.id
        JOIN evidence e1 ON e1.id=i.evidence_id LEFT JOIN evidence e2 ON e2.id=i.heatmap_evidence_id
        WHERE i.id=:i FOR UPDATE OF s
    """), {"i": inspection_id}).mappings().first()
    if not row:
        raise not_found("inspection")
    return dict(row)


def _check_signer(conn: Connection, user: CurrentUser, signer: Any, payload: dict, signature: str,
                  insp: dict, key: str) -> None:
    if not isinstance(signer, dict) or signer.get("employee_code") != user.employee_code:
        raise ApiError(403, "SIGNER_MISMATCH", f"payload.{key}.employee_code must be the logged-in user")
    pk = signer.get("public_key")
    ok_key = conn.execute(text(
        "SELECT 1 FROM user_keys WHERE user_id=:u AND public_key=:k"
    ), {"u": user.id, "k": pk}).first()
    if not ok_key:
        raise ApiError(403, "KEY_NOT_REGISTERED", "signing key is not registered to this user (POST /auth/keys)")
    try:
        signed_at = parse_ts(payload["signed_at"])
    except (KeyError, ValueError, TypeError) as e:
        raise _bad("BAD_PAYLOAD", "signed_at must be ISO-8601 UTC") from e
    skew = timedelta(seconds=get_settings().signed_at_skew_seconds)
    if abs(signed_at - now_ms()) > skew:
        raise _bad("STALE_SIGNATURE", "signed_at is too far from server time")
    try:
        digest = hash_json(payload)
    except ValueError as e:
        raise _bad("BAD_PAYLOAD", str(e)) from e
    if not verify_hex_digest(digest, signature, pk):
        with get_engine().begin() as c2:
            raise_alert(c2, "SIGNATURE_INVALID", "HIGH", {"user": user.employee_code, "schema": payload.get("schema"),
                                                          "stage": "human-action"}, insp["id"])
        raise ApiError(401, "SIGNATURE_INVALID", "signature does not verify over SHA256(JCS(payload))")


def _common(payload: dict, insp: dict, schema: str) -> None:
    if payload.get("schema") != schema:
        raise _bad("BAD_PAYLOAD", f"payload.schema must be {schema}")
    if payload.get("inspection_id") != insp["id"]:
        raise _bad("BAD_PAYLOAD", "payload.inspection_id does not match")


def _event_payload(payload: dict, signature: str) -> dict:
    return {"inspection_id": payload["inspection_id"], "payload": payload, "payload_hash": hash_json(payload),
            "signature": signature}


def _finalize(conn: Connection, insp: dict, final: str, cause: dict) -> dict:
    ev = append_event(conn, inspection_id=insp["id"], line_id=insp["line_id"], line_code=insp["line_code"],
                      event_type="RELEASED" if final == "PASS" else "REJECTED", actor_type="SYSTEM", actor_id=None,
                      payload={"inspection_id": insp["id"], "final_decision": final,
                               "cause_event_hash": cause["event_hash"]}, risk=human_event_risk())
    set_status(conn, insp["id"], "RELEASED" if final == "PASS" else "REJECTED", final)
    return ev


def _user_event(conn, insp, user, event_type, payload, signature) -> dict:
    return append_event(conn, inspection_id=insp["id"], line_id=insp["line_id"], line_code=insp["line_code"],
                        event_type=event_type, actor_type="USER", actor_id=user.employee_code,
                        payload=_event_payload(payload, signature), signature=signature, risk=human_event_risk())


def _done(insp_id: str, kind: str, events: list[dict], status: str, extra: dict | None = None) -> dict:
    out = {"inspection_id": insp_id, "status": status,
           "events": [{"seq": e["seq"], "event_type": e["event_type"], "event_hash": e["event_hash"]} for e in events],
           **(extra or {})}
    hub.publish(kind, out)
    return out


@router.post("/inspections/{id_or_code}/review")
def review(id_or_code: str, body: SignedIn,
           user: CurrentUser = Depends(require_roles("QUALITY_ENGINEER", "QUALITY_MANAGER"))):
    p = body.payload
    with get_engine().begin() as conn:
        insp = _load(conn, resolve_inspection_id(conn, id_or_code))
        _common(p, insp, REVIEW_SCHEMA)
        if insp["status"] != "PENDING_REVIEW":
            raise ApiError(409, "BAD_STATE", f"cannot review an inspection in status {insp['status']}")
        if p.get("record_hash") != insp["record_hash"] or p.get("accepted_decision") != insp["decision"]:
            raise _bad("BAD_PAYLOAD", "record_hash / accepted_decision must match the AI record (use override otherwise)")
        _check_signer(conn, user, p.get("reviewer"), p, body.signature, insp, "reviewer")
        e1 = _user_event(conn, insp, user, "REVIEWED", p, body.signature)
        e2 = _finalize(conn, insp, insp["decision"], e1)
    return _done(insp["id"], "review", [e1, e2], "RELEASED" if insp["decision"] == "PASS" else "REJECTED")


@router.post("/inspections/{id_or_code}/override")
def override(id_or_code: str, body: SignedIn,
             user: CurrentUser = Depends(require_roles("QUALITY_ENGINEER", "QUALITY_MANAGER"))):
    p = body.payload
    with get_engine().begin() as conn:
        insp = _load(conn, resolve_inspection_id(conn, id_or_code))
        _common(p, insp, OVERRIDE_SCHEMA)
        if insp["status"] not in ("PENDING_REVIEW", "AUTO_ACCEPTED"):
            raise ApiError(409, "BAD_STATE", f"cannot override an inspection in status {insp['status']}")
        if p.get("record_hash") != insp["record_hash"]:
            raise _bad("BAD_PAYLOAD", "record_hash does not match")
        if p.get("original") != {"decision": insp["decision"], "confidence": insp["confidence"]}:
            raise _bad("BAD_PAYLOAD", "original must equal the AI decision and confidence")
        if p.get("new_decision") not in ("PASS", "FAIL") or p["new_decision"] == insp["decision"]:
            raise _bad("BAD_PAYLOAD", "new_decision must differ from the AI decision")
        if p.get("reason_code") not in REASON_CODES:
            raise _bad("BAD_PAYLOAD", f"reason_code must be one of {sorted(REASON_CODES)}")
        if len(str(p.get("reason_text", "")).strip()) < 10:
            raise _bad("BAD_PAYLOAD", "reason_text must explain the override (≥ 10 characters)")
        allowed = {insp["evidence_sha256"], insp["heatmap_sha256"]} - {None}
        reviewed = p.get("reviewed_evidence")
        if not isinstance(reviewed, list) or not reviewed or not set(reviewed) <= allowed:
            raise _bad("BAD_PAYLOAD", "reviewed_evidence must list the evidence hashes that were reviewed")
        _check_signer(conn, user, p.get("operator"), p, body.signature, insp, "operator")
        ev = _user_event(conn, insp, user, "OVERRIDDEN", p, body.signature)
        oid = conn.execute(text(
            "INSERT INTO overrides(inspection_id, original_decision, original_confidence, new_decision, reason_code, "
            "reason_text, reviewed_evidence, operator_id, payload, payload_hash, operator_public_key, "
            "operator_signature, event_id) VALUES (:i, CAST(:od AS decision_t), :oc, CAST(:nd AS decision_t), :rc, :rt, "
            ":re, :u, CAST(:p AS jsonb), :ph, :pk, :sig, :e) RETURNING id::text"
        ), {"i": insp["id"], "od": insp["decision"], "oc": insp["confidence"], "nd": p["new_decision"],
            "rc": p["reason_code"], "rt": p["reason_text"], "re": reviewed, "u": user.id, "p": jdump(p),
            "ph": hash_json(p), "pk": p["operator"]["public_key"], "sig": body.signature, "e": ev["id"]}).scalar_one()
        set_status(conn, insp["id"], "PENDING_APPROVAL")
    return _done(insp["id"], "override", [ev], "PENDING_APPROVAL",
                 {"override_id": oid, "override_payload_hash": hash_json(p)})


@router.post("/overrides/{override_id}/approve")
def approve(override_id: str, body: SignedIn, user: CurrentUser = Depends(require_roles("QUALITY_MANAGER"))):
    p = body.payload
    with get_engine().begin() as conn:
        o = conn.execute(text(
            "SELECT o.id::text, o.inspection_id::text, o.payload_hash, o.operator_id::text, o.new_decision::text, "
            "o.original_decision::text, (SELECT count(*) FROM override_approvals a WHERE a.override_id=o.id) AS n "
            "FROM overrides o WHERE o.id::text=:o"
        ), {"o": override_id}).mappings().first()
        if not o:
            raise not_found("override")
        insp = _load(conn, o["inspection_id"])
        _common(p, insp, APPROVAL_SCHEMA)
        if o["n"] or insp["status"] != "PENDING_APPROVAL":
            raise ApiError(409, "BAD_STATE", "override already decided")
        if o["operator_id"] == user.id:
            raise ApiError(403, "SEPARATION_OF_DUTIES", "the approver must be different from the operator")
        if p.get("override_payload_hash") != o["payload_hash"] or not isinstance(p.get("approved"), bool):
            raise _bad("BAD_PAYLOAD", "override_payload_hash must match and approved must be a boolean")
        _check_signer(conn, user, p.get("approver"), p, body.signature, insp, "approver")
        ev = _user_event(conn, insp, user, "APPROVED", p, body.signature)
        conn.execute(text(
            "INSERT INTO override_approvals(override_id, approver_id, approved, comment, payload, payload_hash, "
            "approver_public_key, signature, event_id) VALUES (:o, :u, :a, :c, CAST(:p AS jsonb), :ph, :pk, :s, :e)"
        ), {"o": o["id"], "u": user.id, "a": p["approved"], "c": p.get("comment"), "p": jdump(p),
            "ph": hash_json(p), "pk": p["approver"]["public_key"], "s": body.signature, "e": ev["id"]})
        final = o["new_decision"] if p["approved"] else o["original_decision"]
        e2 = _finalize(conn, insp, final, ev)
    return _done(insp["id"], "approval", [ev, e2], "RELEASED" if final == "PASS" else "REJECTED")


@router.post("/inspections/{id_or_code}/dispute")
def dispute(id_or_code: str, body: SignedIn,
            user: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "AUDITOR"))):
    p = body.payload
    with get_engine().begin() as conn:
        insp = _load(conn, resolve_inspection_id(conn, id_or_code))
        _common(p, insp, DISPUTE_SCHEMA)
        if p.get("record_hash") != insp["record_hash"]:
            raise _bad("BAD_PAYLOAD", "record_hash does not match")
        if len(str(p.get("reason_text", "")).strip()) < 10:
            raise _bad("BAD_PAYLOAD", "reason_text must be ≥ 10 characters")
        action = p.get("action")
        if action == "RAISE":
            if insp["status"] not in ("RELEASED", "REJECTED", "AUTO_ACCEPTED"):
                raise ApiError(409, "BAD_STATE", f"cannot dispute an inspection in status {insp['status']}")
            _check_signer(conn, user, p.get("actor"), p, body.signature, insp, "actor")
            ev = _user_event(conn, insp, user, "DISPUTE_RAISED", p, body.signature)
            set_status(conn, insp["id"], "DISPUTED")
            return _done(insp["id"], "dispute", [ev], "DISPUTED")
        if action == "RESOLVE":
            if user.role != "QUALITY_MANAGER":
                raise ApiError(403, "FORBIDDEN", "only a Quality Manager can resolve disputes")
            if insp["status"] != "DISPUTED" or p.get("resolution") not in ("RELEASED", "REJECTED"):
                raise ApiError(409, "BAD_STATE", "inspection is not disputed or resolution invalid")
            _check_signer(conn, user, p.get("actor"), p, body.signature, insp, "actor")
            ev = _user_event(conn, insp, user, "DISPUTE_RESOLVED", p, body.signature)
            e2 = _finalize(conn, insp, "PASS" if p["resolution"] == "RELEASED" else "FAIL", ev)
            return _done(insp["id"], "dispute", [ev, e2], p["resolution"])
        raise _bad("BAD_PAYLOAD", "action must be RAISE or RESOLVE")


@router.get("/overrides")
def list_overrides(status: str | None = None, _: CurrentUser = Depends(ALL_ROLES)):
    """status=PENDING (awaiting approval) | DECIDED | None (all)."""
    where = {"PENDING": " WHERE a.id IS NULL", "DECIDED": " WHERE a.id IS NOT NULL"}.get(status or "", "")
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT o.id::text, o.inspection_id::text, i.inspection_code, i.unit_serial, l.code AS line,
                   o.original_decision::text AS original_decision, o.original_confidence::text AS original_confidence,
                   o.new_decision::text AS new_decision, o.reason_code, o.reason_text, o.payload_hash,
                   u.employee_code AS operator, u.full_name AS operator_name, o.created_at,
                   a.approved, a.comment AS approval_comment, au.employee_code AS approver, a.created_at AS decided_at,
                   m.name || '@' || m.version AS model
            FROM overrides o JOIN inspections i ON i.id=o.inspection_id JOIN production_lines l ON l.id=i.line_id
            JOIN users u ON u.id=o.operator_id JOIN ai_models m ON m.id=i.model_id
            LEFT JOIN override_approvals a ON a.override_id=o.id LEFT JOIN users au ON au.id=a.approver_id
        """ + where + " ORDER BY o.created_at DESC LIMIT 200")).mappings().all()
    from ..core.time import iso

    return [{**dict(r), "created_at": iso(r["created_at"]), "decided_at": iso(r["decided_at"])} for r in rows]
