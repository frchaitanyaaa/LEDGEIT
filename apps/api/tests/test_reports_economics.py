import pytest

import tamper_lab

from .test_verification import anchored, chain  # noqa: F401  (fixtures)


def test_report_pdf_qr_and_public_verify(client, auth, anchored, engine):  # noqa: F811
    _, out = anchored
    h = auth("qm")
    assert client.post("/api/v1/reports", headers=auth("qe"), json={"report_type": "BATCH"}).status_code == 403
    assert client.post("/api/v1/reports", headers=h, json={"report_type": "BATCH"}).status_code == 422
    r = client.post("/api/v1/reports", headers=h, json={"report_type": "BATCH", "params": {"batch_code": "BATCH-A-001"}})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["inspections"] == 3 and rep["summary"]["Verified"] == 3
    pdf = client.get(f"/api/v1/reports/{rep['id']}/download", headers=h)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    import hashlib

    assert hashlib.sha256(pdf.content).hexdigest() == rep["file_sha256"]

    pub = client.get(f"/api/v1/public/verify/{rep['verification_code']}").json()
    assert pub["kind"] == "report" and pub["result"] == "VERIFIED" and pub["report"]["content_intact"]

    tamper_lab.edit_decision(engine, out[0]["inspection_code"])
    pub = client.get(f"/api/v1/public/verify/{rep['verification_code']}").json()
    assert pub["result"] == "FAILED"
    bad = [i for i in pub["inspections"] if i["verification_now"] == "FAILED"]
    assert [b["inspection_code"] for b in bad] == [out[0]["inspection_code"]]


@pytest.mark.parametrize("rtype", ["DEFECT", "OVERRIDE", "MODEL_HISTORY", "TAMPER", "CHAIN_VERIFICATION"])
def test_all_report_types(client, auth, anchored, rtype):  # noqa: F811
    r = client.post("/api/v1/reports", headers=auth("auditor"), json={"report_type": rtype, "params": {}})
    assert r.status_code == 201, r.text
    assert len(client.get("/api/v1/reports", headers=auth("qe")).json()) == 1


def test_economics_and_dashboard(client, auth, anchored):  # noqa: F811
    e = client.get("/api/v1/economics", headers=auth("qm")).json()
    assert e["chain"]["transactions"] >= 1 and e["coverage"]["inspections_anchored"] == 3
    assert e["coverage"]["events_anchored"] == 9
    assert float(e["batching"]["savings_percent"]) > 0
    assert e["cost_per_inspection_inr"] is not None
    assert client.get("/api/v1/economics", headers=auth("operator")).status_code == 403
    d = client.get("/api/v1/dashboard/summary", headers=auth("operator")).json()
    assert d["kpis"]["inspections"] == 3 and d["kpis"]["anchored"] == 3
    assert d["by_line"][0]["line"] == "LINE-A" and d["by_line"][0]["chain_length"] == 9
