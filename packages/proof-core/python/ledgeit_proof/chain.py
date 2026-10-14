"""Per-line event hash chain (SPEC §3)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .hashing import hash_json, sha256_hex

GENESIS_PREFIX = "LEDGEIT-GENESIS-v1:"


def genesis_hash(line: str) -> str:
    return sha256_hex((GENESIS_PREFIX + line).encode("utf-8"))


def event_header(
    *,
    line: str,
    seq: int,
    event_type: str,
    actor_type: str,
    actor_id: str | None,
    payload_hash: str,
    prev_event_hash: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "line": line,
        "seq": seq,
        "event_type": event_type,
        "actor": {"type": actor_type, "id": actor_id},
        "payload_hash": payload_hash,
        "prev_event_hash": prev_event_hash,
        "created_at": created_at,
    }


def compute_event_hash(**kwargs: Any) -> str:
    return hash_json(event_header(**kwargs))


@dataclass(frozen=True)
class ChainIssue:
    seq: int
    code: str  # EVENT_HASH_MISMATCH | PAYLOAD_HASH_MISMATCH | BROKEN_LINK | SEQ_GAP | BAD_GENESIS
    detail: str


def verify_chain(
    line: str,
    events: Iterable[Mapping[str, Any]],
    *,
    expected_prev: str | None = None,
    expected_first_seq: int | None = None,
) -> list[ChainIssue]:
    """Verify a contiguous, seq-ordered segment of a line's chain.

    Each event mapping needs: seq, event_type, actor_type, actor_id, payload (or payload_hash),
    payload_hash, prev_event_hash, event_hash, created_at.
    If ``expected_prev`` is None and the segment starts at seq 1, the genesis hash is expected.
    """
    issues: list[ChainIssue] = []
    prev_hash = expected_prev
    prev_seq = None if expected_first_seq is None else expected_first_seq - 1
    for ev in events:
        seq = int(ev["seq"])
        if prev_seq is None:
            if seq == 1 and prev_hash is None:
                prev_hash = genesis_hash(line)
        elif seq != prev_seq + 1:
            issues.append(ChainIssue(seq, "SEQ_GAP", f"expected seq {prev_seq + 1}, found {seq}"))
        if "payload" in ev and ev["payload"] is not None:
            ph = hash_json(ev["payload"])
            if ph != ev["payload_hash"]:
                issues.append(ChainIssue(seq, "PAYLOAD_HASH_MISMATCH", "payload does not hash to payload_hash"))
        recomputed = compute_event_hash(
            line=line,
            seq=seq,
            event_type=ev["event_type"],
            actor_type=ev["actor_type"],
            actor_id=ev["actor_id"],
            payload_hash=ev["payload_hash"],
            prev_event_hash=ev["prev_event_hash"],
            created_at=ev["created_at"],
        )
        if recomputed != ev["event_hash"]:
            issues.append(ChainIssue(seq, "EVENT_HASH_MISMATCH", "event header does not hash to event_hash"))
        if prev_hash is not None and ev["prev_event_hash"] != prev_hash:
            code = "BAD_GENESIS" if seq == 1 else "BROKEN_LINK"
            issues.append(ChainIssue(seq, code, "prev_event_hash does not match previous event"))
        prev_hash = ev["event_hash"]
        prev_seq = seq
    return issues
