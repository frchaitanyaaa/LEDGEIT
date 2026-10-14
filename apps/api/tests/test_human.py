import pytest
from sqlalchemy import text

from .test_ingest import bad_frame, good_frame


@pytest.fixture
def failed_inspection(make_device, frame, client, auth):
    dev = make_device()
    r = dev.inspect(bad_frame(frame), unit_serial="U1", batch_code="BATCH-A-001")
    assert r.status_code == 201
    return client.get(f"/api/v1/inspections/{r.json()['inspection_id']}", headers=auth("qe")).json()


def override_payload(ins, s, new="PASS", **kw):
    ev = [e["sha256"] for e in ins["evidence"]]
    p = {"schema": "ledgeit.override.v1", "inspection_id": ins["id"], "record_hash": ins["record_hash"],
         "original": {"decision": ins["decision"], "confidence": ins["confidence"]}, "new_decision": new,
         "reason_code": "FALSE_POSITIVE", "reason_text": "Reflection from lighting, not a crack",
         "reviewed_evidence": ev, "operator": s.who(), "signed_at": s.now()}
    p.update(kw)
    return p


def approval_payload(ins, s, override, approved=True):
    return {"schema": "ledgeit.approval.v1", "override_payload_hash": override["override_payload_hash"],
            "inspection_id": ins["id"], "approved": approved, "comment": "ok", "approver": s.who(),
            "signed_at": s.now()}


def test_review_accepts_ai_decision(client, failed_inspection, signer, engine):
    ins, qe = failed_inspection, signer("qe")
    p = {"schema": "ledgeit.review.v1", "inspection_id": ins["id"], "record_hash": ins["record_hash"],
         "accepted_decision": "FAIL", "comment": "confirmed defect", "reviewer": qe.who(), "signed_at": qe.now()}
    r = client.post(f"/api/v1/inspections/{ins['id']}/review", headers=qe.headers, json=qe.sign(p))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"
    assert [e["event_type"] for e in r.json()["events"]] == ["REVIEWED", "REJECTED"]
    again = client.post(f"/api/v1/inspections/{ins['id']}/review", headers=qe.headers, json=qe.sign(p))
    assert again.status_code == 409
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM anchor_queue WHERE risk_level='HIGH'")).scalar() >= 2


def test_override_then_approval(client, failed_inspection, signer, auth):
    ins, qe, qm = failed_inspection, signer("qe"), signer("qm")
    r = client.post(f"/api/v1/inspections/{ins['id']}/override", headers=qe.headers,
                    json=qe.sign(override_payload(ins, qe)))
    assert r.status_code == 200, r.text
    ov = r.json()
    assert ov["status"] == "PENDING_APPROVAL"
    pending = client.get("/api/v1/overrides?status=PENDING", headers=auth("qm")).json()
    assert pending[0]["id"] == ov["override_id"] and pending[0]["operator"] == "QE-0042"

    r = client.post(f"/api/v1/overrides/{ov['override_id']}/approve", headers=qm.headers,
                    json=qm.sign(approval_payload(ins, qm, ov)))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RELEASED"
    det = client.get(f"/api/v1/inspections/{ins['id']}", headers=auth("auditor")).json()
    assert det["status"] == "RELEASED" and det["final_decision"] == "PASS"
    assert det["overrides"][0]["approved"] is True and det["overrides"][0]["approver"] == "QM-0007"
    tl = client.get(f"/api/v1/inspections/{ins['id']}/timeline", headers=auth("auditor")).json()
    assert [e["event_type"] for e in tl][-3:] == ["OVERRIDDEN", "APPROVED", "RELEASED"]


def test_rejected_override_keeps_ai_decision(client, failed_inspection, signer):
    ins, qe, qm = failed_inspection, signer("qe"), signer("qm")
    ov = client.post(f"/api/v1/inspections/{ins['id']}/override", headers=qe.headers,
                     json=qe.sign(override_payload(ins, qe))).json()
    r = client.post(f"/api/v1/overrides/{ov['override_id']}/approve", headers=qm.headers,
                    json=qm.sign(approval_payload(ins, qm, ov, approved=False)))
    assert r.json()["status"] == "REJECTED"


def test_override_validation(client, failed_inspection, signer):
    ins, qe = failed_inspection, signer("qe")
    url = f"/api/v1/inspections/{ins['id']}/override"
    bad_cases = [
        (override_payload(ins, qe, new="FAIL"), 422),                                  # same as AI
        (override_payload(ins, qe, reason_text="short"), 422),                         # no justification
        (override_payload(ins, qe, reviewed_evidence=["f" * 64]), 422),               # unknown evidence
        (override_payload(ins, qe, record_hash="0" * 64), 422),                        # wrong record
        (override_payload(ins, qe, signed_at="2020-01-01T00:00:00.000Z"), 422),       # stale
        (override_payload(ins, qe, operator={"employee_code": "QM-0007", "public_key": qe.key.public_key_b64}), 403),
    ]
    for p, code in bad_cases:
        r = client.post(url, headers=qe.headers, json=qe.sign(p))
        assert r.status_code == code, (p, r.text)
    # tampered after signing
    body = qe.sign(override_payload(ins, qe))
    body["payload"]["reason_text"] = "changed after signing!!"
    assert client.post(url, headers=qe.headers, json=body).status_code == 401
    # unregistered key
    from ledgeit_proof import generate_keypair, hash_json, sign_hex_digest

    k = generate_keypair()
    p = override_payload(ins, qe, operator={"employee_code": qe.code, "public_key": k.public_key_b64})
    r = client.post(url, headers=qe.headers, json={"payload": p, "signature": sign_hex_digest(hash_json(p), k.seed_b64)})
    assert r.status_code == 403 and r.json()["error"]["code"] == "KEY_NOT_REGISTERED"
    # wrong role
    op = signer("operator")
    assert client.post(url, headers=op.headers, json=op.sign(override_payload(ins, op))).status_code == 403


def test_separation_of_duties(client, failed_inspection, signer):
    ins, qm = failed_inspection, signer("qm")
    ov = client.post(f"/api/v1/inspections/{ins['id']}/override", headers=qm.headers,
                     json=qm.sign(override_payload(ins, qm))).json()
    r = client.post(f"/api/v1/overrides/{ov['override_id']}/approve", headers=qm.headers,
                    json=qm.sign(approval_payload(ins, qm, ov)))
    assert r.status_code == 403 and r.json()["error"]["code"] == "SEPARATION_OF_DUTIES"


def test_dispute_flow(client, make_device, frame, signer, auth):
    dev = make_device()
    r = dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001")
    iid = r.json()["inspection_id"]
    ins = client.get(f"/api/v1/inspections/{iid}", headers=auth("qe")).json()
    aud, qm = signer("auditor"), signer("qm")

    def payload(s, action, resolution=None):
        return {"schema": "ledgeit.dispute.v1", "inspection_id": iid, "record_hash": ins["record_hash"],
                "action": action, "resolution": resolution, "reason_text": "Customer reported surface crack",
                "actor": s.who(), "signed_at": s.now()}

    r = client.post(f"/api/v1/inspections/{iid}/dispute", headers=aud.headers, json=aud.sign(payload(aud, "RAISE")))
    assert r.status_code == 200 and r.json()["status"] == "DISPUTED"
    r = client.post(f"/api/v1/inspections/{iid}/dispute", headers=aud.headers,
                    json=aud.sign(payload(aud, "RESOLVE", "REJECTED")))
    assert r.status_code == 403
    r = client.post(f"/api/v1/inspections/{iid}/dispute", headers=qm.headers,
                    json=qm.sign(payload(qm, "RESOLVE", "REJECTED")))
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
