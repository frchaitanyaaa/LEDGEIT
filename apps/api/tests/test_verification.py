import pytest
from sqlalchemy import text

import tamper_lab

from .test_human import approval_payload, override_payload
from .test_ingest import bad_frame, good_frame


@pytest.fixture
def chain():
    from ledgeit_api.chain.client import MemoryChain, set_chain

    c = MemoryChain()
    set_chain(c)
    yield c
    set_chain(None)


@pytest.fixture
def anchored(make_device, frame, engine, chain, keys_dir, monkeypatch):
    """Two FAIL inspections + one PASS, all anchored. Returns (device, [responses])."""
    from ledgeit_api.anchoring.worker import tick

    monkeypatch.setattr(tamper_lab, "ROOT", keys_dir.parents[0] / "_root")
    dev = make_device()
    out = [dev.inspect(bad_frame(frame), unit_serial="U1", batch_code="BATCH-A-001").json(),
           dev.inspect(bad_frame(frame, 20), unit_serial="U2", batch_code="BATCH-A-001").json(),
           dev.inspect(good_frame(frame), unit_serial="U3", batch_code="BATCH-A-001").json()]
    tick(engine, chain, force=True)
    return dev, out


def verify(client, auth, iid):
    r = client.post(f"/api/v1/inspections/{iid}/verify", headers=auth("auditor"))
    assert r.status_code == 200, r.text
    b = r.json()
    return b["result"], {k: v["status"] for k, v in b["checks"].items()}, b


def test_pending_then_verified(client, auth, make_device, frame, engine, chain):
    from ledgeit_api.anchoring.worker import tick

    dev = make_device()
    iid = dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001").json()["inspection_id"]
    res, checks, _ = verify(client, auth, iid)
    assert res == "PENDING_ANCHOR" and checks["anchor"] == "PENDING"
    assert all(checks[k] == "PASS" for k in ("evidence", "model", "signature", "chain"))
    tick(engine, chain, force=True)
    res, checks, body = verify(client, auth, iid)
    assert res == "VERIFIED", body
    with engine.begin() as c:
        assert c.execute(text("SELECT last_verification::text FROM inspection_status WHERE inspection_id=:i"),
                         {"i": iid}).scalar() == "VERIFIED"


def test_verified_with_signed_override(client, auth, anchored, signer, engine, chain):
    from ledgeit_api.anchoring.worker import tick

    _, out = anchored
    iid = out[0]["inspection_id"]
    ins = client.get(f"/api/v1/inspections/{iid}", headers=auth("qe")).json()
    qe, qm = signer("qe"), signer("qm")
    ov = client.post(f"/api/v1/inspections/{iid}/override", headers=qe.headers,
                     json=qe.sign(override_payload(ins, qe))).json()
    client.post(f"/api/v1/overrides/{ov['override_id']}/approve", headers=qm.headers,
                json=qm.sign(approval_payload(ins, qm, ov)))
    tick(engine, chain)  # HIGH -> immediate
    res, checks, body = verify(client, auth, iid)
    assert res == "VERIFIED", body
    assert body["checks"]["signature"]["facts"]["human_signatures"] == 2


def test_attack_edit_decision(client, auth, anchored, engine):
    _, out = anchored
    tamper_lab.edit_decision(engine, out[0]["inspection_code"])
    res, checks, body = verify(client, auth, out[0]["inspection_id"])
    assert res == "FAILED"
    assert checks["signature"] == "FAIL" and checks["chain"] == "FAIL"
    assert checks["evidence"] == "PASS" and checks["model"] == "PASS"
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM alerts WHERE alert_type='TAMPER_DETECTED'")).scalar() == 1
    # other inspections are untouched
    assert verify(client, auth, out[1]["inspection_id"])[0] == "VERIFIED"


def test_attack_swap_image(client, auth, anchored, engine):
    _, out = anchored
    tamper_lab.swap_image(engine, out[0]["inspection_code"])
    res, checks, _ = verify(client, auth, out[0]["inspection_id"])
    assert res == "FAILED" and checks["evidence"] == "FAIL"
    assert [k for k, v in checks.items() if v == "FAIL"] == ["evidence"]


def test_attack_delete_newest_event(client, auth, anchored, engine):
    _, out = anchored
    tamper_lab.delete_event(engine, out[2]["inspection_code"])  # newest event on the line (head)
    res, checks, body = verify(client, auth, out[2]["inspection_id"])
    assert res == "FAILED" and checks["chain"] == "FAIL", body


def test_attack_delete_middle_event(client, auth, anchored, engine):
    _, out = anchored
    tamper_lab.delete_event(engine, out[0]["inspection_code"], "EVIDENCE_HASHED")
    res, checks, body = verify(client, auth, out[0]["inspection_id"])
    assert res == "FAILED" and checks["chain"] == "FAIL"
    assert any("SEQ_GAP" in p for p in body["checks"]["chain"]["problems"])


def test_attack_smart_insider_only_chain_catches_it(client, auth, anchored, engine, keys_dir):
    import json

    _, out = anchored
    seed = json.loads((keys_dir / "CAM-A-01.json").read_text())["seed_b64"]
    r = tamper_lab.smart_insider(engine, out[0]["inspection_code"], device_seed_b64=seed)
    assert r["events_rewritten"] >= 9 and r["batches_rebuilt"] >= 1
    res, checks, body = verify(client, auth, out[0]["inspection_id"])
    assert res == "FAILED", body
    assert checks == {"evidence": "PASS", "model": "PASS", "signature": "PASS", "chain": "PASS", "anchor": "FAIL"}, body
    det = client.get(f"/api/v1/inspections/{out[0]['inspection_id']}", headers=auth("qe")).json()
    assert det["decision"] == "PASS"  # the DB now *looks* clean


def test_unapproved_model_fails_model_check(client, auth, make_device, frame):
    dev = make_device()
    iid = dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001",
                      model_version="1.1.0").json()["inspection_id"]
    res, checks, _ = verify(client, auth, iid)
    assert res == "FAILED" and checks["model"] == "FAIL"


def test_public_verify(client, anchored):
    _, out = anchored
    code = out[2]["inspection_code"]
    r = client.get(f"/api/v1/public/verify/{code}")
    assert r.status_code == 200
    b = r.json()
    assert b["result"] == "VERIFIED" and b["inspection"]["inspection_code"] == code
    assert "url" not in str(b["record"]) and all("storage_uri" not in str(e) for e in b["proof"]["events"])
    assert len(b["proof"]["events"]) == 3 and all(e["anchor"]["merkle_root"] for e in b["proof"]["events"])
    assert client.get("/api/v1/public/verify/NOPE").status_code == 404


def test_batch_verify_summary(client, auth, anchored, engine):
    _, out = anchored
    tamper_lab.swap_image(engine, out[1]["inspection_code"])
    r = client.post("/api/v1/verify/batch?line=LINE-A", headers=auth("auditor")).json()
    assert r["summary"] == {"VERIFIED": 2, "PENDING_ANCHOR": 0, "FAILED": 1}
