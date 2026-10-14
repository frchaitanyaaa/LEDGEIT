import * as ed from "@noble/ed25519";
import { sha512 } from "@noble/hashes/sha2";

// noble-ed25519 v2 needs a sync sha512 for the sync API.
ed.etc.sha512Sync = (...m: Uint8Array[]) => sha512(ed.etc.concatBytes(...m));

const HEX64 = /^[0-9a-f]{64}$/;

export function b64encode(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

export function b64decode(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export interface KeyPair {
  seedB64: string;
  publicKeyB64: string;
}

export function keypairFromSeed(seed: Uint8Array): KeyPair {
  if (seed.length !== 32) throw new Error("Ed25519 seed must be 32 bytes");
  return { seedB64: b64encode(seed), publicKeyB64: b64encode(ed.getPublicKey(seed)) };
}

export function generateKeypair(): KeyPair {
  return keypairFromSeed(ed.utils.randomPrivateKey());
}

export function signHexDigest(hexDigest: string, seedB64: string): string {
  if (!HEX64.test(hexDigest)) throw new Error("message must be a 64-char lowercase hex digest");
  return b64encode(ed.sign(new TextEncoder().encode(hexDigest), b64decode(seedB64)));
}

export function verifyHexDigest(hexDigest: string, signatureB64: string, publicKeyB64: string): boolean {
  try {
    return ed.verify(b64decode(signatureB64), new TextEncoder().encode(hexDigest), b64decode(publicKeyB64));
  } catch {
    return false;
  }
}
