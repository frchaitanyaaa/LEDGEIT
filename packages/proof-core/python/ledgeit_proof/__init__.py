"""LEDGEIT proof-core. See packages/proof-core/SPEC.md — this package implements it exactly."""

from .canonical import canonicalize, fmt_decimal, fmt_ts, parse_ts
from .chain import (
    ChainIssue,
    compute_event_hash,
    event_header,
    genesis_hash,
    verify_chain,
)
from .hashing import hash_json, sha256_hex
from .merkle import MerkleTree, build_tree, leaf_hash, verify_proof
from .signing import (
    KeyPair,
    generate_keypair,
    keypair_from_seed,
    sign_hex_digest,
    verify_hex_digest,
)

ZERO_HASH = "0" * 64

__all__ = [
    "ZERO_HASH",
    "ChainIssue",
    "KeyPair",
    "MerkleTree",
    "build_tree",
    "canonicalize",
    "compute_event_hash",
    "event_header",
    "fmt_decimal",
    "fmt_ts",
    "generate_keypair",
    "genesis_hash",
    "hash_json",
    "keypair_from_seed",
    "leaf_hash",
    "parse_ts",
    "sha256_hex",
    "sign_hex_digest",
    "verify_chain",
    "verify_hex_digest",
    "verify_proof",
]
