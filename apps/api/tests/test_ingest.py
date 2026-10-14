import json

from sqlalchemy import text

from ledgeit_proof import genesis_hash, verify_chain


def good_frame(frame, start=0):
    for i in range(start, start + 200):
        img, truth = frame(i)
        if truth is None:
            return img
    raise AssertionError("no good frame")


def bad_frame(frame, start=0):
    for i in range(start, start + 200):
        img, truth = frame(i, defect_rate=1.0)
        if truth in ("scratches", "inclusion", "patches"):
            return img
    raise AssertionError("no defect frame")


def test_ingest_good_frame_is_sealed_and_chained(client, make_device, frame, auth, engine):
    dev = make_device("CAM-A-01")
    r = dev.inspect(good_frame(frame), unit_serial="UNIT-A-1", batch_code="BATCH-A-001")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["risk_level"] == "LOW" and body["status"] == "AUTO_ACCEPTED"
    assert [e["event_type"] for e in body["events"]] == ["INSPECTED", "EVIDENCE_HASHED", "RECORD_CREATED"]
    assert [e["seq"] for e in body["events"]] == [1, 2, 3]

    h = auth("qe")
    det = client.get(f"/api/v1/inspections/{body['inspection_code']}", headers=h).json()
    assert det["record_hash"] == body["record_hash"] and det["decision"] == "PASS"
    assert det["record"]["device"] == "CAM-A-01"
    assert {e["kind"] for e in det["evidence"]} == {"IMAGE", "HEATMAP"}
    img = next(e for e in det["evidence"] if e["kind"] == "IMAGE")
    content = client.get(img["url"])
    assert content.status_code == 200 and content.content[:2] == b"\xff\xd8"
    assert client.get(img["url"].split("?")[0] + "?token=bad").status_code == 401

    tl = client.get(f"/api/v1/inspections/{body['inspection_id']}/timeline", headers=h).json()
    assert verify_chain("LINE-A", tl) == []
    assert tl[0]["prev_event_hash"] == genesis_hash("LINE-A")
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM anchor_queue WHERE risk_level='LOW'")).scalar() == 3


def test_defect_needs_review_and_device_chain_links(client, make_device, frame, auth):
    dev = make_device()
    r1 = dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001")
    r2 = dev.inspect(bad_frame(frame), unit_serial="U2", batch_code="BATCH-A-001")
    assert r2.status_code == 201, r2.text
    b2 = r2.json()
    assert b2["risk_level"] in ("MEDIUM", "HIGH") and b2["status"] == "PENDING_REVIEW"
    assert dev.sent[1]["record"]["prev_record_hash"] == r1.json()["record_hash"]
    lst = client.get("/api/v1/inspections?decision=FAIL", headers=auth("auditor")).json()
    assert lst["total"] == 1 and lst["items"][0]["inspection_code"] == b2["inspection_code"]
    head = client.get("/api/v1/devices/CAM-A-01/head").json()
    assert head["last_record_hash"] == b2["record_hash"] and head["count"] == 2


def test_regulated_product_is_high_risk(make_device, frame):
    dev = make_device("CAM-B-01")
    r = dev.inspect(good_frame(frame), unit_serial="B1", batch_code="BATCH-B-001")
    assert r.status_code == 201
    assert r.json()["risk_level"] == "HIGH" and "regulated product" in r.json()["risk_reasons"]


def test_ingest_is_idempotent(client, make_device, frame, ai_client):
    import base64

    from ledgeit_proof import hash_json, sign_hex_digest

    dev = make_device()
    img = good_frame(frame)
    first = dev.inspect(img, unit_serial="U1", batch_code="BATCH-A-001")
    assert first.status_code == 201
    rec = dev.sent[-1]["record"]
    heat = base64.b64decode(ai_client.post("/infer", files={"image": ("f", img, "image/jpeg")}).json()["heatmap_png_b64"])
    again = client.post("/api/v1/inspections",
                        data={"record": json.dumps(rec), "device_signature": sign_hex_digest(hash_json(rec), dev.seed_b64)},
                        files={"image": ("x", img, "image/jpeg"), "heatmap": ("h", heat, "image/png")})
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["record_hash"] == first.json()["record_hash"]


def test_rejections(client, make_device, frame, engine):
    dev = make_device()
    img = good_frame(frame)

    # record edited after signing -> signature invalid + alert
    r = dev.inspect(img, unit_serial="U1", batch_code="BATCH-A-001",
                    tamper_after_sign=lambda rec: rec["result"].__setitem__("confidence", "0.9999"))
    assert r.status_code == 401 and r.json()["error"]["code"] == "SIGNATURE_INVALID"

    # wrong prev_record_hash
    dev.last_record_hash = "f" * 64
    r = dev.inspect(img, unit_serial="U1", batch_code="BATCH-A-001")
    assert r.status_code == 409 and r.json()["error"]["code"] == "PREV_RECORD_MISMATCH"
    dev.sync_head()

    # unknown batch
    r = dev.inspect(img, unit_serial="U1", batch_code="NOPE")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_BATCH"
    # ...unless product_sku given
    r = dev.inspect(img, unit_serial="U1", batch_code="BATCH-A-NEW", product_sku="STEEL-HR-2MM")
    assert r.status_code == 201, r.text

    # unregistered model version
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role = replica"))
        c.execute(text("DELETE FROM ai_models WHERE version='1.1.0'"))
    r = dev.inspect(img, unit_serial="U2", batch_code="BATCH-A-001", model_version="1.1.0")
    assert r.status_code == 422 and r.json()["error"]["code"] == "MODEL_MISMATCH"
    with engine.begin() as c:
        types = {t for (t,) in c.execute(text("SELECT alert_type::text FROM alerts"))}
    assert {"SIGNATURE_INVALID", "MODEL_MISMATCH"} <= types


def test_unapproved_model_is_accepted_but_high_risk(make_device, frame):
    dev = make_device()
    r = dev.inspect(good_frame(frame), unit_serial="U1", batch_code="BATCH-A-001", model_version="1.1.0")
    assert r.status_code == 201
    b = r.json()
    assert b["risk_level"] == "HIGH" and "MODEL_MISMATCH" in b["alerts"]


def test_exact_and_near_replay(make_device, frame):
    import io

    from PIL import Image, ImageEnhance

    dev = make_device()
    img = good_frame(frame)
    assert dev.inspect(img, unit_serial="U1", batch_code="BATCH-A-001").status_code == 201
    r = dev.inspect(img, unit_serial="U2", batch_code="BATCH-A-001")
    assert r.status_code == 201
    assert "DUPLICATE_EVIDENCE" in r.json()["alerts"] and r.json()["risk_level"] == "HIGH"

    im = ImageEnhance.Brightness(Image.open(io.BytesIO(img))).enhance(1.08)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80)
    r = dev.inspect(buf.getvalue(), unit_serial="U3", batch_code="BATCH-A-001")
    assert r.status_code == 201
    assert "POSSIBLE_REPLAY" in r.json()["alerts"]

    # unrelated frames do not trigger near-replay
    other = good_frame(frame, start=50)
    r = dev.inspect(other, unit_serial="U4", batch_code="BATCH-A-001")
    assert "POSSIBLE_REPLAY" not in r.json()["alerts"] and "DUPLICATE_EVIDENCE" not in r.json()["alerts"]


def test_two_lines_have_independent_chains(client, make_device, frame, auth):
    a, b = make_device("CAM-A-01"), make_device("CAM-B-01")
    a.inspect(good_frame(frame), unit_serial="A1", batch_code="BATCH-A-001")
    b.inspect(good_frame(frame, 30), unit_serial="B1", batch_code="BATCH-B-001")
    a.inspect(good_frame(frame, 60), unit_serial="A2", batch_code="BATCH-A-001")
    lines = {ln["code"]: ln for ln in client.get("/api/v1/lines", headers=auth("qe")).json()}
    assert lines["LINE-A"]["last_seq"] == 6 and lines["LINE-B"]["last_seq"] == 3


def test_models_registry_flow(client, auth):
    models = client.get("/api/v1/models", headers=auth("qe")).json()
    by_v = {m["version"]: m for m in models if m["name"] == "ledgeit-defect-stub"}
    assert by_v["1.0.0"]["status"] == "APPROVED" and by_v["1.1.0"]["status"] == "DRAFT"
    assert client.post(f"/api/v1/models/{by_v['1.1.0']['id']}/approve", headers=auth("qe")).status_code == 403
    r = client.post(f"/api/v1/models/{by_v['1.1.0']['id']}/approve", headers=auth("qm"))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["approved_by"] == "QM-0007"
    body = {"name": "x", "version": "1.0.0", "weights_sha256": "a" * 64, "framework": "f", "dataset_version": "d"}
    assert client.post("/api/v1/models", headers=auth("admin"), json=body).status_code == 201
    assert client.post("/api/v1/models", headers=auth("admin"), json=body).status_code == 409
