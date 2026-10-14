from __future__ import annotations

import asyncio
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy import Connection, text

from ..auth.deps import ALL_ROLES, CurrentUser
from ..core.config import get_settings
from ..core.errors import ApiError, not_found
from ..db.engine import get_conn
from ..services.feed import hub
from ..services.storage import get_storage
from .queries import LIST_SQL, detail, list_row, resolve_inspection_id, timeline

router = APIRouter(tags=["inspections"])


@router.get("/inspections")
def list_inspections(
    line: str | None = None,
    batch: str | None = None,
    decision: str | None = None,
    risk: str | None = None,
    status: str | None = None,
    device: str | None = None,
    q: str | None = Query(default=None, description="search code / serial / record hash prefix"),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    _: CurrentUser = Depends(ALL_ROLES),
    conn: Connection = Depends(get_conn),
):
    where, params = [], {}
    for col, val, key in [("l.code", line, "line"), ("b.batch_code", batch, "batch"), ("d.device_code", device, "device"),
                          ("i.decision::text", decision, "decision"), ("i.risk_level::text", risk, "risk"),
                          ("s.status", status, "status")]:
        if val:
            where.append(f"{col} = :{key}")
            params[key] = val
    if q:
        where.append("(i.inspection_code ILIKE :q OR i.unit_serial ILIKE :q OR i.record_hash LIKE :qh)")
        params["q"], params["qh"] = f"%{q}%", f"{q.lower()}%"
    if from_:
        where.append("i.inspected_at >= :from")
        params["from"] = from_
    if to:
        where.append("i.inspected_at <= :to")
        params["to"] = to
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(text(
        "SELECT count(*) FROM inspections i JOIN inspection_status s ON s.inspection_id=i.id "
        "JOIN batches b ON b.id=i.batch_id JOIN production_lines l ON l.id=i.line_id JOIN devices d ON d.id=i.device_id"
        + clause), params).scalar_one()
    rows = conn.execute(text(LIST_SQL + clause + " ORDER BY i.inspected_at DESC, i.created_at DESC LIMIT :lim OFFSET :off"),
                        {**params, "lim": limit, "off": offset}).mappings().all()
    return {"total": total, "items": [list_row(r) for r in rows]}


@router.get("/inspections/{id_or_code}")
def get_inspection(id_or_code: str, _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    return detail(conn, resolve_inspection_id(conn, id_or_code))


@router.get("/inspections/{id_or_code}/timeline")
def get_timeline(id_or_code: str, _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    return timeline(conn, resolve_inspection_id(conn, id_or_code))


@router.get("/inspections/{id_or_code}/evidence")
def get_evidence(id_or_code: str, _: CurrentUser = Depends(ALL_ROLES), conn: Connection = Depends(get_conn)):
    return detail(conn, resolve_inspection_id(conn, id_or_code))["evidence"]


@router.get("/evidence/{evidence_id}/content", include_in_schema=True)
def evidence_content(evidence_id: str, token: str, conn: Connection = Depends(get_conn)):
    """Serve evidence bytes with a short-lived signed token (usable in <img src>)."""
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ApiError(401, "UNAUTHORIZED", "invalid or expired evidence token") from e
    if claims.get("type") != "evidence" or claims.get("sub") != evidence_id:
        raise ApiError(401, "UNAUTHORIZED", "token not valid for this evidence")
    row = conn.execute(text("SELECT storage_uri, mime_type FROM evidence WHERE id::text=:i"),
                       {"i": evidence_id}).first()
    if not row:
        raise not_found("evidence")
    return Response(get_storage().get(row[0]), media_type=row[1], headers={"Cache-Control": "private, max-age=300"})


@router.websocket("/ws/feed")
async def ws_feed(ws: WebSocket, token: str = Query(...)):
    from ..core.security import decode_token

    try:
        decode_token(token)
    except jwt.PyJWTError:
        await ws.close(code=4401)
        return
    await ws.accept()
    q = hub.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=25)
                await ws.send_text(msg)
            except TimeoutError:
                await ws.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)
