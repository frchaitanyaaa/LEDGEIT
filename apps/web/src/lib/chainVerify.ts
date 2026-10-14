// Independent, in-browser verification for the public page: recompute every hash from the data
// returned by the server, walk the Merkle proofs, and ask the blockchain directly (JSON-RPC eth_call).
import {
  computeEventHash,
  hashJson,
  leafHash,
  rootFromProof,
  type ProofStep,
} from "@ledgeit/proof-core";
import { keccak_256 } from "@noble/hashes/sha3";
import { bytesToHex } from "@noble/hashes/utils";

export interface PublicEvent {
  seq: number;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  payload: any;
  payload_hash: string;
  prev_event_hash: string;
  event_hash: string;
  created_at: string;
  anchor: null | { leaf_hash: string; merkle_proof: ProofStep[]; merkle_root: string; batch_id: number;
                   tx_hash: string | null; block_number: number | null };
}

export interface ChainRef { network: string; chain_id: number; contract_address: string; rpc_url: string | null;
                            explorer: string | null }

export interface Step { label: string; ok: boolean | null; detail?: string }

const SELECTOR = bytesToHex(keccak_256(new TextEncoder().encode("anchors(bytes32)"))).slice(0, 8);

export async function onchainTimestamp(chain: ChainRef, rootHex: string): Promise<number | null> {
  if (!chain.rpc_url) return null;
  const r = await fetch(chain.rpc_url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call",
                           params: [{ to: chain.contract_address, data: "0x" + SELECTOR + rootHex }, "latest"] }),
  });
  const body = await r.json();
  if (body.error) throw new Error(body.error.message);
  const hex: string = body.result.slice(2);
  return parseInt(hex.slice(0, 64), 16); // Anchor.timestamp (0 = not anchored)
}

export async function verifyInBrowser(line: string, record: any, events: PublicEvent[], chain: ChainRef | null): Promise<Step[]> {
  const steps: Step[] = [];
  const recordHash = hashJson(record);
  const created = events.find((e) => e.event_type === "RECORD_CREATED");
  steps.push({ label: "Record hash recomputed from the canonical record", ok: created?.payload?.record_hash === recordHash,
               detail: recordHash });
  const roots = new Map<string, number | null>();
  let prev: PublicEvent | null = null;
  for (const e of events) {
    const ph = hashJson(e.payload);
    const eh = computeEventHash(line, { ...e, payload_hash: ph });
    const linkOk = prev && prev.seq + 1 === e.seq ? e.prev_event_hash === prev.event_hash : null;
    steps.push({ label: `#${e.seq} ${e.event_type}: event hash recomputed`, ok: eh === e.event_hash && ph === e.payload_hash,
                 detail: eh });
    if (linkOk !== null) steps.push({ label: `#${e.seq} links to #${prev!.seq}`, ok: linkOk });
    if (!e.anchor) {
      steps.push({ label: `#${e.seq} anchor`, ok: null, detail: "waiting for the next anchoring window" });
    } else {
      const root = rootFromProof(leafHash(eh), e.anchor.merkle_proof);
      steps.push({ label: `#${e.seq} Merkle proof reaches batch ${e.anchor.batch_id} root`, ok: root === e.anchor.merkle_root,
                   detail: root });
      if (chain) {
        if (!roots.has(root)) {
          try {
            roots.set(root, await onchainTimestamp(chain, root));
          } catch {
            roots.set(root, null);
          }
        }
        const ts = roots.get(root);
        steps.push({
          label: `#${e.seq} root exists on ${chain.network}`,
          ok: ts === null || ts === undefined ? null : ts > 0,
          detail: ts ? `anchored ${new Date(ts * 1000).toISOString()}` : ts === 0 ? "root NOT found on-chain" : "RPC unreachable from this browser",
        });
      }
    }
    prev = e;
  }
  return steps;
}
