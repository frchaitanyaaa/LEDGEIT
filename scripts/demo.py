"""End-to-end LEDGEIT demo against a running stack (`make demo`).

Plays the story from docs/team/CHAITANYA.md §17 and asserts each outcome, so it doubles as an
integration test of the real services (API + AI inspector + chain + DB):

  1. stream inspections from two edge devices          5. replay attack -> DUPLICATE_EVIDENCE
  2. anchor (flush the batching windows)                6. compliance reports + public verification
  3. QE signs an override, QM signs the approval        7. economics
  4. Tamper Lab: 4 DB/storage attacks -> verification fails exactly where expected

Needs: API on :8000, AI inspector on :8001, Postgres, a chain (CHAIN=local + hardhat node), `make seed` done.
Every run uses fresh batch codes, so it can be repeated.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "tamper-lab"))

import tamper_lab  # noqa: E402
from ledgeit_api.anchoring.worker import tick  # noqa: E402
from ledgeit_api.chain.client import get_chain  # noqa: E402
from ledgeit_api.db.engine import get_engine  # noqa: E402
from ledgeit_proof import fmt_ts, generate_keypair, hash_json, sign_hex_digest  # noqa: E402
from simulator.device import EdgeDevice, http_infer, load_key  # noqa: E402
from simulator.synth import generate  # noqa: E402

API = "http://localhost:8000"
AI = "http://localhost:8001"
B, G, R, Y, D, X = "\033[1m", "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
failures: list[str] = []


def step(n: int | str, title: str) -> None:
    print(f"\n{B}── {n}. {title} {'─' * max(0, 60 - len(title))}{X}")


def expect(cond: bool, msg: str) -> None:
    print(f"   {G + '✔' if cond else R + '✘'} {msg}{X}")
    if not cond:
        failures.append(msg)


class User:
    def __init__(self, api: httpx.Client, email: str):
        r = api.post("/api/v1/auth/login", json={"email": email, "password": "ledgeit123"})
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.code = r.json()["user"]["employee_code"]
        self.key = generate_keypair()
        api.post("/api/v1/auth/keys", headers=self.h, json={"public_key": self.key.public_key_b64, "label": "demo script"})

    def who(self) -> dict:
        return {"employee_code": self.code, "public_key": self.key.public_key_b64}

    def sign(self, p: dict) -> dict:
        return {"payload": p, "signature": sign_hex_digest(hash_json(p), self.key.seed_b64)}


def now() -> str:
    return fmt_ts(datetime.now(timezone.utc))


def verify(api: httpx.Client, h: dict, iid: str) -> tuple[str, dict]:
    b = api.post(f"/api/v1/inspections/{iid}/verify", headers=h).json()
    return b["result"], {k: v["status"] for k, v in b["checks"].items()}


def show(code: str, result: str, checks: dict) -> None:
    col = G if result == "VERIFIED" else R if result == "FAILED" else Y
    marks = " ".join(f"{k}:{(G if v == 'PASS' else R if v == 'FAIL' else Y)}{v}{X}" for k, v in checks.items())
    print(f"   {code}  {col}{B}{result}{X}  {marks}")


def anchor_now(timeout: float = 30.0) -> None:
    """Cut batches now (ignoring the batching windows) and wait for the anchor worker to confirm them.
    Falls back to submitting in-process if no worker is running."""
    from sqlalchemy import text

    from ledgeit_api.anchoring.worker import flush

    eng = get_engine()
    with eng.begin() as c:
        created = flush(c, datetime.now(timezone.utc), force=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        with eng.begin() as c:
            pending = c.execute(text("SELECT count(*) FROM anchor_batches WHERE status IN ('PENDING','SUBMITTED')")).scalar()
        if not pending:
            break
        if time.time() > deadline - timeout + 8:  # no worker progress after 8 s -> do it ourselves
            tick(eng, get_chain())
        time.sleep(0.5)
    print(f"   {D}flushed batching windows → {len(created)} new batch(es) anchored on-chain{X}")


def main() -> int:
    api = httpx.Client(base_url=API, timeout=60)
    ai = httpx.Client(base_url=AI, timeout=60)
    try:
        api.get("/api/v1/health").raise_for_status()
        ai.get("/health").raise_for_status()
    except httpx.HTTPError as e:
        print(f"{R}stack not reachable ({e}). Start it with `make dev-start` or `make up`.{X}")
        return 2
    chain = get_chain()
    print(f"{B}LEDGEIT demo{X} · chain: {chain.network if chain else 'none'} "
          f"{chain.contract_address if chain else ''}")
    stamp = datetime.now().strftime("%H%M%S")
    batch_a, batch_b = f"DEMO-A-{stamp}", f"DEMO-B-{stamp}"
    keys = ROOT / "services" / "edge-simulator" / "keys"
    devs = {}
    for code in ("CAM-A-01", "CAM-B-01"):
        d = EdgeDevice(code=code, seed_b64=load_key(keys, code)["seed_b64"], api=api, infer=http_infer(ai))
        d.sync_head()
        devs[code] = d
    qe, qm, auditor = User(api, "qe@ledgeit.dev"), User(api, "qm@ledgeit.dev"), User(api, "auditor@ledgeit.dev")

    # ------------------------------------------------------------------ 1
    step(1, "Live line: edge devices seal, sign and stream inspections")
    sent = {"A": [], "B": []}
    base = int(stamp) * 10
    for i in range(14):
        img = generate(base + i, defect_rate=0.45).jpeg
        r = devs["CAM-A-01"].inspect(img, unit_serial=f"U-A-{stamp}-{i}", batch_code=batch_a, product_sku="STEEL-HR-2MM")
        if r.status_code != 201:
            expect(False, f"ingest failed: {r.text[:120]}")
            continue
        b = r.json()
        sent["A"].append({**b, "frame": base + i, "decision": devs["CAM-A-01"].sent[-1]["record"]["result"]["decision"]})
    for i in range(3):
        img = generate(base + 500 + i, defect_rate=0.3).jpeg
        r = devs["CAM-B-01"].inspect(img, unit_serial=f"U-B-{stamp}-{i}", batch_code=batch_b, product_sku="STEEL-AUTO-PNL")
        sent["B"].append(r.json())
    fails = [s for s in sent["A"] if s["decision"] == "FAIL"]
    passes = [s for s in sent["A"] if s["decision"] == "PASS"]
    risks = {s["risk_level"] for s in sent["A"]}
    print(f"   line A: {len(passes)} PASS / {len(fails)} FAIL, risk levels {sorted(risks)}; line B (regulated): "
          f"{[s['risk_level'] for s in sent['B']]}")
    expect(len(fails) >= 4 and len(passes) >= 4, "enough PASS and FAIL records for the story")
    expect(all(s["risk_level"] == "HIGH" for s in sent["B"]), "regulated product is always HIGH risk")

    # ------------------------------------------------------------------ 2
    step(2, "Anchor: Merkle batches per risk level go on-chain")
    anchor_now()
    res, checks = verify(api, auditor.h, passes[0]["inspection_id"])
    show(passes[0]["inspection_code"], res, checks)
    expect(res == "VERIFIED", "a fresh record verifies end-to-end (all 5 checks)")

    # ------------------------------------------------------------------ 3
    step(3, "Respond: QE overrides FAIL→PASS (signed), QM approves (signed)")
    target = fails[0]
    ins = api.get(f"/api/v1/inspections/{target['inspection_id']}", headers=qe.h).json()
    p = {"schema": "ledgeit.override.v1", "inspection_id": ins["id"], "record_hash": ins["record_hash"],
         "original": {"decision": ins["decision"], "confidence": ins["confidence"]}, "new_decision": "PASS",
         "reason_code": "FALSE_POSITIVE", "reason_text": "Reflection from lighting, not a crack; checked under alternate angle",
         "reviewed_evidence": [e["sha256"] for e in ins["evidence"]], "operator": qe.who(), "signed_at": now()}
    ov = api.post(f"/api/v1/inspections/{ins['id']}/override", headers=qe.h, json=qe.sign(p))
    expect(ov.status_code == 200, f"override signed by {qe.code} accepted → {ov.json().get('status')}")
    a = {"schema": "ledgeit.approval.v1", "override_payload_hash": ov.json()["override_payload_hash"],
         "inspection_id": ins["id"], "approved": True, "comment": "Agree, lighting artefact", "approver": qm.who(),
         "signed_at": now()}
    ap = api.post(f"/api/v1/overrides/{ov.json()['override_id']}/approve", headers=qm.h, json=qm.sign(a))
    expect(ap.status_code == 200 and ap.json()["status"] == "RELEASED", f"approval signed by {qm.code} → RELEASED")
    wrong = api.post(f"/api/v1/inspections/{fails[1]['inspection_id']}/override", headers=qm.h,
                      json=qm.sign({**p, "inspection_id": fails[1]["inspection_id"], "operator": qm.who(),
                                    "record_hash": "0" * 64}))
    expect(wrong.status_code == 422, "an override that references the wrong record is refused")
    anchor_now()
    res, checks = verify(api, auditor.h, ins["id"])
    show(ins["inspection_code"], res, checks)
    expect(res == "VERIFIED", "overridden record verifies, including both human signatures")

    # ------------------------------------------------------------------ 4
    step(4, "Attack: a malicious DBA tampers with the database and storage")
    eng = tamper_lab._engine()
    attacks = [
        ("T1 flip FAIL→PASS in DB", fails[1], lambda c: tamper_lab.edit_decision(eng, c), {"signature", "chain"}),
        ("T2 swap evidence image", fails[2], lambda c: tamper_lab.swap_image(eng, c), {"evidence"}),
        ("T3 delete newest event", passes[-1], lambda c: tamper_lab.delete_event(eng, c), {"chain"}),
    ]
    for label, rec, attack, must_fail in attacks:
        before, _ = verify(api, auditor.h, rec["inspection_id"])
        attack(rec["inspection_code"])
        res, checks = verify(api, auditor.h, rec["inspection_id"])
        print(f"   {B}{label}{X} (before: {before})")
        show(rec["inspection_code"], res, checks)
        failed = {k for k, v in checks.items() if v == "FAIL"}
        expect(res == "FAILED" and must_fail <= failed, f"caught by {sorted(failed)}")

    step(5, "Attack: smart insider re-signs and recomputes EVERY hash, proof and root")
    victim = sent["B"][0]
    out = tamper_lab.smart_insider(eng, victim["inspection_code"],
                                   device_seed_b64=load_key(keys, "CAM-B-01")["seed_b64"])
    print(f"   rewrote {out['events_rewritten']} events and {out['batches_rebuilt']} Merkle batches — the DB is "
          f"self-consistent")
    res, checks = verify(api, auditor.h, victim["inspection_id"])
    show(victim["inspection_code"], res, checks)
    expect(res == "FAILED" and checks["anchor"] == "FAIL" and
           all(checks[k] == "PASS" for k in ("evidence", "model", "signature", "chain")),
           "only check 5 fails: the DB can be rewritten; the chain cannot")

    # ------------------------------------------------------------------ 6
    step(6, "Replay: an old good image is re-sent for a new unit")
    r = devs["CAM-A-01"].inspect(generate(passes[0]["frame"], defect_rate=0.45).jpeg, unit_serial=f"U-A-{stamp}-R",
                                 batch_code=batch_a)
    b = r.json()
    print(f"   {b['inspection_code']} risk={b['risk_level']} alerts={b['alerts']}")
    expect("DUPLICATE_EVIDENCE" in b["alerts"] and b["risk_level"] == "HIGH", "DUPLICATE_EVIDENCE alert, forced HIGH")
    anchor_now()

    # ------------------------------------------------------------------ 7
    step(7, "Report: audit-ready PDFs with QR codes")
    for batch in (batch_b, batch_a):
        rep = api.post("/api/v1/reports", headers=qm.h, json={"report_type": "BATCH", "params": {"batch_code": batch}}).json()
        pub = api.get(f"/api/v1/public/verify/{rep['verification_code']}").json()
        print(f"   {batch}: {rep['inspections']} records, code {B}{rep['verification_code']}{X} → {rep['verify_url']}  "
              f"public result {pub['result']}")
    expect(pub["result"] == "FAILED", "report over the tampered batch shows FAILED to anyone scanning the QR")

    step(8, "Economics: real fees from transaction receipts")
    e = api.get("/api/v1/economics", headers=qm.h).json()
    print(f"   {e['chain']['transactions']} txs · {e['coverage']['events_anchored']} events · "
          f"cost/inspection ₹{e['cost_per_inspection_inr']} · batching saves {e['batching']['savings_percent']}% "
          f"vs one tx per event")

    print(f"\n{B}Open the dashboard:{X} http://localhost:5173  (qe@ / qm@ / auditor@ledgeit.dev, password ledgeit123)")
    print(f"{B}Public verify:{X} http://localhost:5173/verify/{victim['inspection_code']}")
    if failures:
        print(f"\n{R}{B}{len(failures)} expectation(s) failed:{X}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\n{G}{B}Demo complete — every expectation held.{X}")
    return 0


if __name__ == "__main__":
    t0 = time.time()
    code = main()
    print(f"{D}({time.time() - t0:.1f}s){X}")
    raise SystemExit(code)
