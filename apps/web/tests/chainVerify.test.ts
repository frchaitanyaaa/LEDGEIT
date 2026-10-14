import { buildTree, computeEventHash, genesisHash, hashJson } from "@ledgeit/proof-core";
import { describe, expect, it } from "vitest";
import { verifyInBrowser, type PublicEvent } from "../src/lib/chainVerify";

function fixture() {
  const line = "LINE-T";
  const record = { schema: "ledgeit.inspection.v1", inspection_id: "x", result: { decision: "FAIL", confidence: "0.9000" } };
  const payloads = [
    { inspection_id: "x", decision: "FAIL" },
    { inspection_id: "x", evidence_sha256: "a".repeat(64) },
    { inspection_id: "x", record_hash: hashJson(record), device_signature: "sig" },
  ];
  const types = ["INSPECTED", "EVIDENCE_HASHED", "RECORD_CREATED"];
  let prev = genesisHash(line);
  const events: PublicEvent[] = payloads.map((payload, i) => {
    const e = { seq: i + 1, event_type: types[i], actor_type: "DEVICE", actor_id: "CAM", payload, payload_hash: hashJson(payload),
                prev_event_hash: prev, created_at: `2026-10-20T10:00:0${i}.000Z` };
    const event_hash = computeEventHash(line, e);
    prev = event_hash;
    return { ...e, event_hash, anchor: null };
  });
  const tree = buildTree(events.map((e) => e.event_hash));
  events.forEach((e, i) => (e.anchor = { leaf_hash: tree.leaves[i], merkle_proof: tree.proofs[i], merkle_root: tree.root, batch_id: 1,
                                         tx_hash: null, block_number: null }));
  return { line, record, events };
}

describe("in-browser verification", () => {
  it("passes for an untouched record (no chain configured)", async () => {
    const { line, record, events } = fixture();
    const steps = await verifyInBrowser(line, record, events, null);
    expect(steps.every((s) => s.ok !== false)).toBe(true);
    expect(steps.filter((s) => s.label.includes("links to"))).toHaveLength(2);
  });

  it("flags an edited payload and a tampered record", async () => {
    const { line, record, events } = fixture();
    events[0].payload = { ...events[0].payload, decision: "PASS" };
    const steps = await verifyInBrowser(line, { ...record, result: { ...record.result, decision: "PASS" } }, events, null);
    expect(steps.find((s) => s.label.startsWith("Record hash"))!.ok).toBe(false);
    expect(steps.find((s) => s.label.startsWith("#1 INSPECTED"))!.ok).toBe(false);
  });

  it("asks the chain and reports a missing root", async () => {
    const { line, record, events } = fixture();
    const calls: any[] = [];
    globalThis.fetch = (async (_u: string, init: any) => {
      calls.push(JSON.parse(init.body));
      return { json: async () => ({ result: "0x" + "0".repeat(256) }) };
    }) as any;
    const steps = await verifyInBrowser(line, record, events,
      { network: "test", chain_id: 1, contract_address: "0x" + "1".repeat(40), rpc_url: "http://rpc", explorer: null });
    expect(calls[0].method).toBe("eth_call");
    expect(calls[0].params[0].data.startsWith("0x")).toBe(true);
    expect(calls).toHaveLength(1); // one root -> one RPC call
    expect(steps.filter((s) => s.label.includes("root exists")).every((s) => s.ok === false)).toBe(true);
  });
});
