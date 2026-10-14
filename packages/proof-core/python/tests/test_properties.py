import copy
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from ledgeit_proof import (
    build_tree,
    compute_event_hash,
    fmt_decimal,
    fmt_ts,
    generate_keypair,
    genesis_hash,
    hash_json,
    verify_chain,
    verify_hex_digest,
    verify_proof,
)


def h(i: int) -> str:
    return hashlib.sha256(str(i).encode()).hexdigest()


def make_chain(line="LINE-T", n=6):
    prev = genesis_hash(line)
    out = []
    for seq in range(1, n + 1):
        payload = {"i": seq}
        ev = dict(seq=seq, event_type="INSPECTED", actor_type="DEVICE", actor_id="CAM-1",
                  payload=payload, payload_hash=hash_json(payload), prev_event_hash=prev,
                  created_at=f"2026-01-01T00:00:0{seq}.000Z")
        ev["event_hash"] = compute_event_hash(line=line, **{k: ev[k] for k in (
            "seq", "event_type", "actor_type", "actor_id", "payload_hash", "prev_event_hash", "created_at")})
        out.append(ev)
        prev = ev["event_hash"]
    return out


def test_formatting():
    assert fmt_decimal(0.96395) == "0.9640"
    assert fmt_decimal("0.62") == "0.6200"
    assert fmt_ts(datetime(2026, 10, 20, 10, 31, 2, 120999, tzinfo=timezone.utc)) == "2026-10-20T10:31:02.120Z"
    ist = timezone(timedelta(hours=5, minutes=30))
    assert fmt_ts(datetime(2026, 10, 20, 16, 1, 2, tzinfo=ist)) == "2026-10-20T10:31:02.000Z"
    with pytest.raises(ValueError):
        fmt_ts(datetime(2026, 1, 1))


def test_merkle_every_size_every_leaf():
    for n in range(1, 40):
        hs = [h(i) for i in range(n)]
        t = build_tree(hs)
        for i, (leaf, proof) in enumerate(zip(t.leaves, t.proofs)):
            assert verify_proof(leaf, proof, t.root), (n, i)
            # a different leaf never verifies with this proof
            assert not verify_proof(t.leaves[(i + 1) % n], proof, t.root) or n == 1


def test_merkle_empty_rejected():
    with pytest.raises(ValueError):
        build_tree([])


def test_chain_detects_edit_delete_reorder():
    chain = make_chain()
    assert verify_chain("LINE-T", chain) == []

    edited = copy.deepcopy(chain)
    edited[2]["payload"]["i"] = 999
    codes = {i.code for i in verify_chain("LINE-T", edited)}
    assert "PAYLOAD_HASH_MISMATCH" in codes

    deleted = chain[:3] + chain[4:]
    codes = {i.code for i in verify_chain("LINE-T", deleted)}
    assert {"SEQ_GAP", "BROKEN_LINK"} <= codes

    reordered = [chain[0], chain[2], chain[1]] + chain[3:]
    assert verify_chain("LINE-T", reordered)

    # smart insider: edits payload AND recomputes payload_hash + event_hash of that one event
    smart = copy.deepcopy(chain)
    smart[2]["payload"] = {"i": 999}
    smart[2]["payload_hash"] = hash_json(smart[2]["payload"])
    smart[2]["event_hash"] = compute_event_hash(line="LINE-T", **{k: smart[2][k] for k in (
        "seq", "event_type", "actor_type", "actor_id", "payload_hash", "prev_event_hash", "created_at")})
    codes = {i.code for i in verify_chain("LINE-T", smart)}
    assert codes == {"BROKEN_LINK"}  # next event no longer links


def test_signatures_roundtrip_and_reject():
    kp = generate_keypair()
    d = h(1)
    sig = kp.sign(d)
    assert verify_hex_digest(d, sig, kp.public_key_b64)
    assert not verify_hex_digest(h(2), sig, kp.public_key_b64)
    assert not verify_hex_digest(d, sig, generate_keypair().public_key_b64)
    assert not verify_hex_digest(d, "not-base64!!", kp.public_key_b64)
    assert not verify_hex_digest(d, sig, "AAAA")
    with pytest.raises(ValueError):
        kp.sign("ABC")
