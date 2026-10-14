import { sha256 } from "@noble/hashes/sha2";
import { bytesToHex, hexToBytes } from "@noble/hashes/utils";

export type ProofStep = { hash: string; side: "L" | "R" };

function concat(...parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

export function leafHash(eventHashHex: string): string {
  return bytesToHex(sha256(concat(Uint8Array.of(0), hexToBytes(eventHashHex))));
}

export function nodeHash(leftHex: string, rightHex: string): string {
  return bytesToHex(sha256(concat(Uint8Array.of(1), hexToBytes(leftHex), hexToBytes(rightHex))));
}

export interface MerkleTree {
  root: string;
  leaves: string[];
  proofs: ProofStep[][];
}

export function buildTree(eventHashes: string[]): MerkleTree {
  if (eventHashes.length === 0) throw new Error("cannot build a Merkle tree with no leaves");
  const leaves = eventHashes.map(leafHash);
  const proofs: ProofStep[][] = leaves.map(() => []);
  const positions = leaves.map((_, i) => i);
  let level = leaves;
  while (level.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < level.length; i += 2) {
      next.push(i + 1 < level.length ? nodeHash(level[i], level[i + 1]) : level[i]);
    }
    positions.forEach((pos, leafI) => {
      if (pos % 2 === 0) {
        if (pos + 1 < level.length) proofs[leafI].push({ hash: level[pos + 1], side: "R" });
      } else {
        proofs[leafI].push({ hash: level[pos - 1], side: "L" });
      }
      positions[leafI] = Math.floor(pos / 2);
    });
    level = next;
  }
  return { root: level[0], leaves, proofs };
}

export function rootFromProof(leafHex: string, proof: ProofStep[]): string {
  let h = leafHex;
  for (const step of proof) {
    if (step.side === "L") h = nodeHash(step.hash, h);
    else if (step.side === "R") h = nodeHash(h, step.hash);
    else throw new Error(`bad proof side ${String((step as ProofStep).side)}`);
  }
  return h;
}

export function verifyProof(leafHex: string, proof: ProofStep[], rootHex: string): boolean {
  try {
    return rootFromProof(leafHex, proof) === rootHex;
  } catch {
    return false;
  }
}
