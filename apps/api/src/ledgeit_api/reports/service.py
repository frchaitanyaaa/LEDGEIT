"""Compliance reports (PDF + QR) — CHAITANYA.md stage 6 "Report".

A report freezes a set of inspections with their record hashes and the verification result at
generation time. The PDF's SHA-256 and a random verification code are stored; the QR code opens the
public verify page, which re-verifies every listed inspection *now* and lets anyone hash the PDF they hold.
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone
from typing import Any

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import Connection, text

from ledgeit_proof import hash_json, sha256_hex

from ..chain.client import get_chain
from ..core.config import get_settings
from ..core.errors import ApiError
from ..core.time import iso
from ..db.json import jdump
from ..services.storage import get_storage
from ..verification.engine import verify_inspection

REPORT_TYPES = {
    "BATCH": "Batch Inspection Report",
    "DEFECT": "Defect Report",
    "OVERRIDE": "Human Override Report",
    "MODEL_HISTORY": "AI Model History Report",
    "TAMPER": "Tamper & Alert Report",
    "CHAIN_VERIFICATION": "Chain Verification Report",
}
MAX_ROWS = 300


def _select(conn: Connection, rtype: str, params: dict) -> list[str]:
    where, p = [], {}
    if params.get("batch_code"):
        where.append("b.batch_code=:batch")
        p["batch"] = params["batch_code"]
    if params.get("line"):
        where.append("l.code=:line")
        p["line"] = params["line"]
    if params.get("from"):
        where.append("i.inspected_at >= CAST(:f AS timestamptz)")
        p["f"] = params["from"]
    if params.get("to"):
        where.append("i.inspected_at <= CAST(:t AS timestamptz)")
        p["t"] = params["to"]
    if params.get("model"):
        where.append("(m.name || '@' || m.version) = :model")
        p["model"] = params["model"]
    if rtype == "BATCH" and not params.get("batch_code"):
        raise ApiError(422, "BAD_PARAMS", "BATCH report needs params.batch_code")
    if rtype == "DEFECT":
        where.append("i.decision='FAIL'")
    if rtype == "OVERRIDE":
        where.append("EXISTS (SELECT 1 FROM overrides o WHERE o.inspection_id=i.id)")
    if rtype == "TAMPER":
        where.append("(EXISTS (SELECT 1 FROM alerts a WHERE a.inspection_id=i.id AND a.severity='HIGH') "
                     "OR s.last_verification='FAILED')")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return [r[0] for r in conn.execute(text(
        "SELECT i.id::text FROM inspections i JOIN batches b ON b.id=i.batch_id JOIN production_lines l "
        "ON l.id=i.line_id JOIN ai_models m ON m.id=i.model_id JOIN inspection_status s ON s.inspection_id=i.id"
        + clause + " ORDER BY i.inspected_at LIMIT :n"), {**p, "n": MAX_ROWS})]


def _rows(conn: Connection, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    rows = conn.execute(text("""
        SELECT i.id::text AS id, i.inspection_code, i.unit_serial, b.batch_code, l.code AS line,
               i.decision::text AS ai_decision, s.final_decision::text AS final_decision, s.status,
               i.defect_class, i.severity::text AS severity, i.confidence::text AS confidence,
               i.risk_level::text AS risk, m.name || '@' || m.version AS model, i.record_hash, i.inspected_at,
               (SELECT count(*) FROM overrides o WHERE o.inspection_id=i.id) AS overrides
        FROM inspections i JOIN batches b ON b.id=i.batch_id JOIN production_lines l ON l.id=i.line_id
        JOIN ai_models m ON m.id=i.model_id JOIN inspection_status s ON s.inspection_id=i.id
        WHERE i.id = ANY(CAST(:ids AS uuid[])) ORDER BY i.inspected_at
    """), {"ids": ids}).mappings().all()
    return [dict(r) for r in rows]


def _qr_png(url: str) -> bytes:
    img = qrcode.make(url, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pdf(title: str, meta: list[tuple[str, str]], summary: dict, rows: list[dict], verify_url: str,
         code: str, extra_tables: list[tuple[str, list[list[str]]]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=title, author="LEDGEIT")
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=7.5, leading=9)
    mono = ParagraphStyle("mono", parent=small, fontName="Courier", fontSize=6.5)
    story: list[Any] = []
    qr = Image(io.BytesIO(_qr_png(verify_url)), width=32 * mm, height=32 * mm)
    head = Table([[Paragraph(f"<b>LEDGEIT</b> — {title}", ss["Title"]), qr]], colWidths=[140 * mm, 36 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [head, Paragraph(f"Verification code <b>{code}</b> · scan the QR or open {verify_url}", small),
              Spacer(1, 4 * mm)]
    mt = Table([[Paragraph(f"<b>{k}</b>", small), Paragraph(v, small)] for k, v in meta], colWidths=[40 * mm, 136 * mm])
    mt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story += [mt, Spacer(1, 4 * mm)]
    st = Table([[Paragraph(f"<b>{k}</b>", small) for k in summary], [Paragraph(str(v), small) for v in summary.values()]])
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]))
    story += [st, Spacer(1, 5 * mm)]
    for name, table in extra_tables:
        if len(table) > 1:
            story.append(Paragraph(f"<b>{name}</b>", ss["Heading4"]))
            t = Table([[Paragraph(str(c), small) for c in r] for r in table], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]))
            story += [t, Spacer(1, 4 * mm)]
    header = ["Inspection", "Unit", "AI", "Final", "Class / severity", "Conf.", "Risk", "Model", "Verified",
              "Record hash"]
    data = [header] + [[
        r["inspection_code"], r["unit_serial"], r["ai_decision"], r["final_decision"] or r["status"],
        f"{r['defect_class'] or '-'} / {r['severity']}", r["confidence"], r["risk"], r["model"],
        r.get("verification", "-"), Paragraph(r["record_hash"][:32] + "…", mono)] for r in rows]
    story.append(Paragraph("<b>Inspections</b>", ss["Heading4"]))
    t = Table([[c if isinstance(c, Paragraph) else Paragraph(str(c), small) for c in row] for row in data],
              repeatRows=1, colWidths=[30 * mm, 20 * mm, 9 * mm, 15 * mm, 25 * mm, 11 * mm, 13 * mm, 22 * mm,
                                       16 * mm, 21 * mm])
    style = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]
    for i, r in enumerate(rows, start=1):
        if r.get("verification") == "FAILED":
            style.append(("BACKGROUND", (8, i), (8, i), colors.HexColor("#fde2e1")))
        elif r.get("verification") == "VERIFIED":
            style.append(("BACKGROUND", (8, i), (8, i), colors.HexColor("#e3f6e8")))
    t.setStyle(TableStyle(style))
    story.append(t)
    story += [Spacer(1, 5 * mm), Paragraph(
        "Each record hash is SHA-256 over the RFC 8785 canonical inspection record, signed by the edge device "
        "and chained per production line; Merkle roots are anchored on the configured blockchain. "
        "Anyone can re-verify these records from the public verification page.", small)]
    doc.build(story)
    return buf.getvalue()


def generate(conn: Connection, rtype: str, params: dict, user_id: str, user_code: str) -> dict:
    if rtype not in REPORT_TYPES:
        raise ApiError(422, "BAD_REPORT_TYPE", f"report_type must be one of {sorted(REPORT_TYPES)}")
    ids = _select(conn, rtype, params)
    storage, chain = get_storage(), get_chain()
    rows = _rows(conn, ids)
    for r in rows:
        v = verify_inspection(conn, r["id"], storage=storage, chain=chain, requested_by=user_id)
        r["verification"] = v["result"]
    counts = {k: sum(1 for r in rows if r["verification"] == k) for k in ("VERIFIED", "PENDING_ANCHOR", "FAILED")}
    summary = {
        "Inspections": len(rows),
        "AI FAIL": sum(1 for r in rows if r["ai_decision"] == "FAIL"),
        "Overridden": sum(1 for r in rows if r["overrides"]),
        "Verified": counts["VERIFIED"],
        "Pending anchor": counts["PENDING_ANCHOR"],
        "Failed": counts["FAILED"],
    }
    extra: list[tuple[str, list[list[str]]]] = []
    if rtype in ("OVERRIDE", "BATCH"):
        ov = conn.execute(text(
            "SELECT i.inspection_code, o.original_decision::text, o.new_decision::text, o.reason_code, u.employee_code, "
            "COALESCE(au.employee_code, '-'), CASE WHEN a.approved IS NULL THEN 'pending' WHEN a.approved THEN 'approved' "
            "ELSE 'rejected' END FROM overrides o JOIN inspections i ON i.id=o.inspection_id JOIN users u ON "
            "u.id=o.operator_id LEFT JOIN override_approvals a ON a.override_id=o.id LEFT JOIN users au ON "
            "au.id=a.approver_id WHERE o.inspection_id = ANY(CAST(:ids AS uuid[])) ORDER BY o.created_at"),
            {"ids": ids}).all()
        extra.append(("Human overrides (signed)", [["Inspection", "AI", "Override", "Reason", "Operator", "Approver",
                                                    "Outcome"]] + [list(r) for r in ov]))
    if rtype == "MODEL_HISTORY":
        ms = conn.execute(text(
            "SELECT name || '@' || version, status::text, left(weights_sha256, 16) || '…', framework, dataset_version, "
            "COALESCE(to_char(approved_at, 'YYYY-MM-DD HH24:MI'), '-'), (SELECT count(*) FROM inspections i WHERE "
            "i.model_id=m.id) FROM ai_models m ORDER BY name, version")).all()
        extra.append(("Model registry", [["Model", "Status", "Weights SHA-256", "Framework", "Dataset", "Approved",
                                          "Inspections"]] + [list(r) for r in ms]))
    if rtype == "TAMPER":
        al = conn.execute(text(
            "SELECT a.alert_type::text, a.severity::text, a.status::text, COALESCE(i.inspection_code, '-'), "
            "to_char(a.created_at, 'YYYY-MM-DD HH24:MI') FROM alerts a LEFT JOIN inspections i ON i.id=a.inspection_id "
            "WHERE a.severity='HIGH' ORDER BY a.created_at DESC LIMIT 100")).all()
        extra.append(("High-severity alerts", [["Alert", "Severity", "Status", "Inspection", "Raised"]]
                      + [list(r) for r in al]))
    code = secrets.token_hex(5).upper()
    s = get_settings()
    verify_url = f"{s.public_base_url.rstrip('/')}/verify/{code}"
    now = datetime.now(timezone.utc)
    meta = [("Report type", REPORT_TYPES[rtype]), ("Parameters", jdump(params) if params else "—"),
            ("Generated", f"{iso(now)} by {user_code}"),
            ("Chain", f"{chain.network} (chain id {chain.chain_id}) contract {chain.contract_address}" if chain
             else "not configured")]
    pdf = _pdf(REPORT_TYPES[rtype], meta, summary, rows, verify_url, code, extra)
    file_sha = sha256_hex(pdf)
    frozen = {"report_type": rtype, "params": params, "generated_at": iso(now), "verification_code": code,
              "inspections": [{"inspection_code": r["inspection_code"], "record_hash": r["record_hash"],
                               "verification": r["verification"]} for r in rows],
              "summary": summary}
    uri = storage.put(f"reports/{now:%Y/%m/%d}/{file_sha}.pdf", pdf, "application/pdf")
    rid = conn.execute(text(
        "INSERT INTO reports(report_type, params, file_uri, file_sha256, verification_code, summary, generated_by) "
        "VALUES (:t, CAST(:p AS jsonb), :u, :h, :c, CAST(:s AS jsonb), :g) RETURNING id::text"
    ), {"t": rtype, "p": jdump(params), "u": uri, "h": file_sha, "c": code,
        "s": jdump({**frozen, "content_hash": hash_json(frozen)}), "g": user_id}).scalar_one()
    return {"id": rid, "report_type": rtype, "verification_code": code, "file_sha256": file_sha,
            "verify_url": verify_url, "summary": summary, "inspections": len(rows)}


def public_report_verification(conn: Connection, code: str) -> dict:
    rep = conn.execute(text(
        "SELECT r.report_type, r.params, r.file_sha256, r.summary, r.created_at, u.employee_code FROM reports r "
        "JOIN users u ON u.id=r.generated_by WHERE r.verification_code=:c"), {"c": code}).mappings().one()
    frozen = rep["summary"]
    content_ok = hash_json({k: v for k, v in frozen.items() if k != "content_hash"}) == frozen.get("content_hash")
    storage, chain = get_storage(), get_chain()
    items = []
    for it in frozen.get("inspections", []):
        iid = conn.execute(text("SELECT id::text FROM inspections WHERE inspection_code=:c"),
                           {"c": it["inspection_code"]}).scalar()
        now_result = "MISSING"
        if iid:
            now_result = verify_inspection(conn, iid, storage=storage, chain=chain, requested_by=None)["result"]
        items.append({**it, "verification_now": now_result})
    failed = sum(1 for i in items if i["verification_now"] in ("FAILED", "MISSING"))
    pending = sum(1 for i in items if i["verification_now"] == "PENDING_ANCHOR")
    result = "FAILED" if failed or not content_ok else "PENDING_ANCHOR" if pending else "VERIFIED"
    return {
        "kind": "report", "result": result,
        "message": {"VERIFIED": "Every record in this report still verifies",
                    "FAILED": "Verification Failed — at least one record no longer matches",
                    "PENDING_ANCHOR": "Records intact; some are waiting for their on-chain anchor"}[result],
        "report": {"type": rep["report_type"], "title": REPORT_TYPES.get(rep["report_type"]), "params": rep["params"],
                   "generated_at": iso(rep["created_at"]), "generated_by": rep["employee_code"],
                   "file_sha256": rep["file_sha256"], "verification_code": code, "summary": frozen.get("summary"),
                   "content_intact": content_ok},
        "inspections": items,
    }
