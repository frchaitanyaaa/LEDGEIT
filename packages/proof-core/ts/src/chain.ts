import { hashJson, sha256Hex } from "./hashing";

export const GENESIS_PREFIX = "LEDGEIT-GENESIS-v1:";

export function genesisHash(line: string): string {
  return sha256Hex(GENESIS_PREFIX + line);
}

export interface ChainEvent {
  seq: number;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload?: unknown;
  payload_hash: string;
  prev_event_hash: string;
  event_hash: string;
  created_at: string;
}

export function computeEventHash(line: string, e: Omit<ChainEvent, "event_hash" | "payload">): string {
  return hashJson({
    line,
    seq: e.seq,
    event_type: e.event_type,
    actor: { type: e.actor_type, id: e.actor_id },
    payload_hash: e.payload_hash,
    prev_event_hash: e.prev_event_hash,
    created_at: e.created_at,
  });
}

export interface ChainIssue {
  seq: number;
  code: "EVENT_HASH_MISMATCH" | "PAYLOAD_HASH_MISMATCH" | "BROKEN_LINK" | "SEQ_GAP" | "BAD_GENESIS";
  detail: string;
}

export function verifyChain(
  line: string,
  events: ChainEvent[],
  opts: { expectedPrev?: string; expectedFirstSeq?: number } = {},
): ChainIssue[] {
  const issues: ChainIssue[] = [];
  let prevHash: string | undefined = opts.expectedPrev;
  let prevSeq: number | undefined = opts.expectedFirstSeq === undefined ? undefined : opts.expectedFirstSeq - 1;
  for (const ev of events) {
    if (prevSeq === undefined) {
      if (ev.seq === 1 && prevHash === undefined) prevHash = genesisHash(line);
    } else if (ev.seq !== prevSeq + 1) {
      issues.push({ seq: ev.seq, code: "SEQ_GAP", detail: `expected seq ${prevSeq + 1}, found ${ev.seq}` });
    }
    if (ev.payload !== undefined && ev.payload !== null && hashJson(ev.payload) !== ev.payload_hash) {
      issues.push({ seq: ev.seq, code: "PAYLOAD_HASH_MISMATCH", detail: "payload does not hash to payload_hash" });
    }
    if (computeEventHash(line, ev) !== ev.event_hash) {
      issues.push({ seq: ev.seq, code: "EVENT_HASH_MISMATCH", detail: "event header does not hash to event_hash" });
    }
    if (prevHash !== undefined && ev.prev_event_hash !== prevHash) {
      issues.push({
        seq: ev.seq,
        code: ev.seq === 1 ? "BAD_GENESIS" : "BROKEN_LINK",
        detail: "prev_event_hash does not match previous event",
      });
    }
    prevHash = ev.event_hash;
    prevSeq = ev.seq;
  }
  return issues;
}
