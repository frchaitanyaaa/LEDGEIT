import base64
import json
from pathlib import Path

import pytest

from ledgeit_proof import (
    build_tree,
    canonicalize,
    genesis_hash,
    hash_json,
    keypair_from_seed,
    leaf_hash,
    verify_chain,
    verify_hex_digest,
    verify_proof,
)

VEC = Path(__file__).resolve().parents[2] / "test-vectors"


def load(name):
    return json.loads((VEC / name).read_text(encoding="utf-8"))


def test_canonical_vectors():
    v = load("canonical.json")
    for case in v["cases"]:
        assert canonicalize(case["input"]).decode("utf-8") == case["canonical"]
        assert hash_json(case["input"]) == case["sha256"]
    for bad in v["must_reject"]:
        with pytest.raises(ValueError):
            canonicalize(json.loads(bad["input_json"]))


def test_chain_vectors():
    v = load("chain.json")
    assert genesis_hash(v["line"]) == v["genesis"]
    assert verify_chain(v["line"], v["events"]) == []


def test_merkle_vectors():
    v = load("merkle.json")
    assert leaf_hash(v["leaf_example"]["event_hash"]) == v["leaf_example"]["leaf"]
    for case in v["cases"]:
        t = build_tree(case["event_hashes"])
        assert t.root == case["root"]
        assert t.leaves == case["leaves"]
        assert t.proofs == case["proofs"]
        for leaf, proof in zip(t.leaves, t.proofs):
            assert verify_proof(leaf, proof, t.root)


def test_signature_vectors():
    v = load("signatures.json")
    for case in v["cases"]:
        kp = keypair_from_seed(base64.b64decode(case["seed_b64"]))
        assert kp.public_key_b64 == case["public_key_b64"]
        assert kp.sign(case["message_hex"]) == case["signature_b64"]
        assert verify_hex_digest(case["message_hex"], case["signature_b64"], case["public_key_b64"])
    for bad in v["invalid"]:
        assert not verify_hex_digest(bad["message_hex"], bad["signature_b64"], bad["public_key_b64"])


def test_record_vector():
    v = load("record.json")
    assert canonicalize(v["record"]).decode("utf-8") == v["canonical"]
    assert hash_json(v["record"]) == v["record_hash"]
    assert verify_hex_digest(v["record_hash"], v["device_signature_b64"], v["device_public_key_b64"])
    assert not verify_hex_digest(v["tampered_record_hash"], v["device_signature_b64"], v["device_public_key_b64"])
