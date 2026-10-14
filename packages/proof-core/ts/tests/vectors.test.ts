import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  b64decode,
  buildTree,
  canonicalString,
  fmtDecimal,
  genesisHash,
  hashJson,
  keypairFromSeed,
  leafHash,
  signHexDigest,
  verifyChain,
  verifyHexDigest,
  verifyProof,
} from "../src";

const VEC = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "test-vectors");
const load = (n: string) => JSON.parse(readFileSync(join(VEC, n), "utf-8"));

describe("shared test vectors", () => {
  it("canonical.json", () => {
    const v = load("canonical.json");
    for (const c of v.cases) {
      expect(canonicalString(c.input)).toBe(c.canonical);
      expect(hashJson(c.input)).toBe(c.sha256);
    }
    for (const bad of v.must_reject) expect(() => canonicalString(JSON.parse(bad.input_json))).toThrow();
  });

  it("chain.json", () => {
    const v = load("chain.json");
    expect(genesisHash(v.line)).toBe(v.genesis);
    expect(verifyChain(v.line, v.events)).toEqual([]);
    const deleted = [...v.events.slice(0, 2), ...v.events.slice(3)];
    expect(verifyChain(v.line, deleted).map((i) => i.code)).toContain("SEQ_GAP");
  });

  it("merkle.json", () => {
    const v = load("merkle.json");
    expect(leafHash(v.leaf_example.event_hash)).toBe(v.leaf_example.leaf);
    for (const c of v.cases) {
      const t = buildTree(c.event_hashes);
      expect(t.root).toBe(c.root);
      expect(t.leaves).toEqual(c.leaves);
      expect(t.proofs).toEqual(c.proofs);
      t.leaves.forEach((l, i) => expect(verifyProof(l, t.proofs[i], t.root)).toBe(true));
    }
  });

  it("signatures.json", () => {
    const v = load("signatures.json");
    for (const c of v.cases) {
      const kp = keypairFromSeed(b64decode(c.seed_b64));
      expect(kp.publicKeyB64).toBe(c.public_key_b64);
      expect(signHexDigest(c.message_hex, c.seed_b64)).toBe(c.signature_b64);
      expect(verifyHexDigest(c.message_hex, c.signature_b64, c.public_key_b64)).toBe(true);
    }
    for (const bad of v.invalid) {
      expect(verifyHexDigest(bad.message_hex, bad.signature_b64, bad.public_key_b64)).toBe(false);
    }
  });

  it("record.json", () => {
    const v = load("record.json");
    expect(canonicalString(v.record)).toBe(v.canonical);
    expect(hashJson(v.record)).toBe(v.record_hash);
    expect(verifyHexDigest(v.record_hash, v.device_signature_b64, v.device_public_key_b64)).toBe(true);
    expect(verifyHexDigest(v.tampered_record_hash, v.device_signature_b64, v.device_public_key_b64)).toBe(false);
  });
});

describe("helpers", () => {
  it("fmtDecimal matches Python banker's rounding", () => {
    expect(fmtDecimal(0.96395)).toBe("0.9640");
    expect(fmtDecimal("0.62")).toBe("0.6200");
    expect(fmtDecimal("0.12345")).toBe("0.1234");
    expect(fmtDecimal("0.12355")).toBe("0.1236");
    expect(fmtDecimal("0.123451")).toBe("0.1235");
    expect(fmtDecimal(1)).toBe("1.0000");
  });
});
