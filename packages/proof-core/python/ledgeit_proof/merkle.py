"""Domain-separated Merkle tree with odd-node promotion (SPEC §4)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(event_hash_hex: str) -> str:
    return _h(b"\x00" + bytes.fromhex(event_hash_hex)).hex()


def node_hash(left_hex: str, right_hex: str) -> str:
    return _h(b"\x01" + bytes.fromhex(left_hex) + bytes.fromhex(right_hex)).hex()


@dataclass(frozen=True)
class MerkleTree:
    root: str
    leaves: list[str]
    proofs: list[list[dict[str, str]]]


def build_tree(event_hashes: Sequence[str]) -> MerkleTree:
    if not event_hashes:
        raise ValueError("cannot build a Merkle tree with no leaves")
    leaves = [leaf_hash(e) for e in event_hashes]
    proofs: list[list[dict[str, str]]] = [[] for _ in leaves]
    # positions[i] = index of leaf i's ancestor in the current level
    positions = list(range(len(leaves)))
    level = leaves
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(node_hash(level[i], level[i + 1]))
            else:
                nxt.append(level[i])  # promote unchanged
        for leaf_i, pos in enumerate(positions):
            if pos % 2 == 0:
                if pos + 1 < len(level):
                    proofs[leaf_i].append({"hash": level[pos + 1], "side": "R"})
            else:
                proofs[leaf_i].append({"hash": level[pos - 1], "side": "L"})
            positions[leaf_i] = pos // 2
        level = nxt
    return MerkleTree(root=level[0], leaves=leaves, proofs=proofs)


def root_from_proof(leaf_hex: str, proof: Sequence[dict[str, str]]) -> str:
    h = leaf_hex
    for step in proof:
        if step["side"] == "L":
            h = node_hash(step["hash"], h)
        elif step["side"] == "R":
            h = node_hash(h, step["hash"])
        else:
            raise ValueError(f"bad proof side {step['side']!r}")
    return h


def verify_proof(leaf_hex: str, proof: Sequence[dict[str, str]], root_hex: str) -> bool:
    try:
        return root_from_proof(leaf_hex, proof) == root_hex
    except (ValueError, KeyError):
        return False
