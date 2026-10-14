from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from ..auth.deps import ALL_ROLES, CurrentUser, require_roles
from ..core.errors import not_found
from ..core.time import iso
from ..db.engine import get_conn, get_engine
from ..services.storage import get_storage
from .service import REPORT_TYPES, generate

router = APIRouter(tags=["reports"])


class ReportIn(BaseModel):
    report_type: str
    params: dict = Field(default_factory=dict)


@router.get("/reports/types")
def report_types(_: CurrentUser = Depends(ALL_ROLES)):
    return [{"type": k, "title": v} for k, v in REPORT_TYPES.items()]


@router.post("/reports", status_code=201)
def create_report(body: ReportIn, user: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "AUDITOR", "ADMIN"))):
    with get_engine().begin() as conn:
        return generate(conn, body.report_type, body.params, user.id, user.employee_code)


@router.get("/reports")
def list_reports(_: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    rows = conn.execute(text(
        "SELECT r.id::text, r.report_type, r.params, r.file_sha256, r.verification_code, r.summary->'summary' AS summary, "
        "r.created_at, u.employee_code AS generated_by FROM reports r JOIN users u ON u.id=r.generated_by "
        "ORDER BY r.created_at DESC LIMIT 100")).mappings().all()
    return [{**dict(r), "created_at": iso(r["created_at"]), "title": REPORT_TYPES.get(r["report_type"])} for r in rows]


@router.get("/reports/{report_id}/download")
def download(report_id: str, _: CurrentUser = Depends(require_roles("QUALITY_MANAGER", "AUDITOR", "ADMIN")),
             conn: Connection = Depends(get_conn)):
    row = conn.execute(text("SELECT file_uri, verification_code, report_type FROM reports WHERE id::text=:i"),
                       {"i": report_id}).first()
    if not row:
        raise not_found("report")
    return Response(get_storage().get(row[0]), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="ledgeit-{row[2].lower()}-{row[1]}.pdf"'})
