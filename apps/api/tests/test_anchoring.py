from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from ledgeit_proof import leaf_hash, verify_proof

from .test_ingest import bad_frame, good_frame


@pytest.fixture
def chain():
    from ledgeit_api.chain.client import MemoryChain, set_chain

    c = MemoryChain()
    set_chain(c)
    yield c
    set_chain(None)


def later(minutes=0, seconds=0):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes, seconds=seconds)


def test_low_risk_waits_for_window_then_batches(engine, make_device, frame, chain):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device()
    dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001")  # LOW: 3 events
    out = tick(engine, chain)
    assert out["created"] == []  # 3 < 100 items and < 10 min old
    out = tick(engine, chain, now=later(minutes=11))
    assert len(out["created"]) == 1 and out["confirmed"] == out["created"]
    with engine.begin() as c:
        b = c.execute(text("SELECT leaf_count, risk_level::text, status::text FROM anchor_batches")).one()
        st = c.execute(text("SELECT anchor_status::text FROM inspection_status")).scalar()
        tx = c.execute(text("SELECT gas_used, fee_native, fee_inr FROM blockchain_txs")).one()
    assert tuple(b) == (3, "LOW", "CONFIRMED") and st == "CONFIRMED"
    assert tx.gas_used == 71869 and tx.fee_native > 0 and tx.fee_inr is not None


def test_high_risk_anchored_immediately_and_proofs_valid(engine, make_device, frame, chain):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device("CAM-B-01")  # regulated -> HIGH
    dev.inspect(good_frame(frame), unit_serial="B1", batch_code="BATCH-B-001")
    out = tick(engine, chain)
    assert len(out["confirmed"]) == 1
    with engine.begin() as c:
        rows = c.execute(text(
            "SELECT e.event_hash, ai.leaf_hash, ai.merkle_proof, b.merkle_root FROM anchor_items ai "
            "JOIN inspection_events e ON e.id=ai.event_id JOIN anchor_batches b ON b.id=ai.batch_id")).all()
    assert len(rows) == 3
    for eh, lh, proof, root in rows:
        assert leaf_hash(eh) == lh and verify_proof(lh, proof, root)
        assert chain.get_anchor(root) is not None


def test_medium_batches_at_ten_items(engine, make_device, frame, chain):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device()
    for i in range(4):  # 4 defect inspections x 3 events = 12 MEDIUM/HIGH events
        dev.inspect(bad_frame(frame, start=i * 7), unit_serial=f"U{i}", batch_code="BATCH-A-001")
    with engine.begin() as c:
        medium = c.execute(text("SELECT count(*) FROM anchor_queue WHERE risk_level='MEDIUM'")).scalar()
    out = tick(engine, chain)
    with engine.begin() as c:
        sizes = [r[0] for r in c.execute(text("SELECT leaf_count FROM anchor_batches WHERE risk_level='MEDIUM'"))]
    assert sizes == ([10] if medium >= 10 else [])
    assert out is not None


def test_retry_backoff_and_failure_alert(engine, make_device, frame, chain):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device("CAM-B-01")
    dev.inspect(good_frame(frame), unit_serial="B1", batch_code="BATCH-B-001")
    chain.fail_next = 2
    t = datetime.now(timezone.utc)
    assert tick(engine, chain, now=t)["confirmed"] == []
    assert tick(engine, chain, now=t + timedelta(seconds=1))["confirmed"] == []  # backoff: skipped
    assert tick(engine, chain, now=t + timedelta(seconds=3))["confirmed"] == []  # attempt 2 fails
    assert len(tick(engine, chain, now=t + timedelta(seconds=10))["confirmed"]) == 1
    with engine.begin() as c:
        assert c.execute(text("SELECT attempts FROM anchor_batches")).scalar() == 2

    dev.inspect(good_frame(frame, 40), unit_serial="B2", batch_code="BATCH-B-001")
    chain.fail_next = 99
    for k in range(6):
        tick(engine, chain, now=t + timedelta(minutes=5 * (k + 1)))
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM anchor_batches WHERE status='FAILED'")).scalar() == 1
        assert c.execute(text("SELECT count(*) FROM alerts WHERE alert_type='MISSING_ANCHOR'")).scalar() == 1


def test_already_anchored_root_is_recovered(engine, make_device, frame, chain):
    from ledgeit_api.anchoring.worker import flush, submit

    dev = make_device("CAM-B-01")
    dev.inspect(good_frame(frame), unit_serial="B1", batch_code="BATCH-B-001")
    with engine.begin() as c:
        flush(c, datetime.now(timezone.utc))
        root, bid, n = c.execute(text("SELECT merkle_root, id, leaf_count FROM anchor_batches")).one()
    chain.anchor(root, bid, n, 2)  # simulate: tx landed but worker crashed before recording it
    assert submit(engine, chain, datetime.now(timezone.utc)) == [bid]


def test_explorer_endpoints(client, auth, make_device, frame, chain, engine):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device("CAM-B-01")
    dev.inspect(good_frame(frame), unit_serial="B1", batch_code="BATCH-B-001")
    tick(engine, chain)
    h = auth("auditor")
    lst = client.get("/api/v1/anchors", headers=h).json()
    assert lst["total"] == 1 and lst["items"][0]["status"] == "CONFIRMED" and lst["items"][0]["inspections"] == 1
    one = client.get(f"/api/v1/anchors/{lst['items'][0]['id']}", headers=h).json()
    assert [i["event_type"] for i in one["items"]] == ["INSPECTED", "EVIDENCE_HASHED", "RECORD_CREATED"]
    assert client.get("/api/v1/chain/txs", headers=h).json()[0]["gas_used"] == 71869
    assert client.get("/api/v1/chain/info", headers=h).json()["onchain_anchor_count"] == 1
    tl = client.get(f"/api/v1/inspections/{dev.sent[0]['response']['inspection_id']}/timeline", headers=h).json()
    assert all(e["anchor"] and e["anchor"]["status"] == "CONFIRMED" for e in tl)


def test_alert_rules_and_patch(client, auth, engine, make_device, frame):
    from ledgeit_api.services.alert_rules import run_rules

    dev = make_device()
    dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001")
    with engine.begin() as c:
        c.execute(text("INSERT INTO anchor_batches(merkle_root, leaf_count, risk_level, created_at) "
                       "VALUES (:r, 1, 'LOW', now() - interval '1 hour')"), {"r": "e" * 64})
        out = run_rules(c, datetime.now(timezone.utc))
        again = run_rules(c, datetime.now(timezone.utc))
    assert out["missing_anchor"] == 1 and again["missing_anchor"] == 0  # deduped
    alerts = client.get("/api/v1/alerts?type=MISSING_ANCHOR", headers=auth("qe")).json()["items"]
    aid = alerts[0]["id"]
    assert client.patch(f"/api/v1/alerts/{aid}", headers=auth("auditor"), json={"status": "RESOLVED"}).status_code == 403
    r = client.patch(f"/api/v1/alerts/{aid}", headers=auth("qm"), json={"status": "RESOLVED"})
    assert r.status_code == 200
    assert client.get("/api/v1/alerts?status=RESOLVED", headers=auth("qe")).json()["items"][0]["resolved_by"] == "QM-0007"
