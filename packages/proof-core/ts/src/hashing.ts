import { sha256 } from "@noble/hashes/sha2";
import { bytesToHex, hexToBytes } from "@noble/hashes/utils";
import { canonicalize } from "./canonical";

export { bytesToHex, hexToBytes };

export function sha256Hex(data: Uint8Array | string): string {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  return bytesToHex(sha256(bytes));
}

export function hashJson(value: unknown): string {
  return sha256Hex(canonicalize(value));
}
