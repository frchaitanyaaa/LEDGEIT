// Browser-held Ed25519 signing keys (ADR-005). Private key never leaves IndexedDB.
import { generateKeypair, hashJson, signHexDigest, type KeyPair } from "@ledgeit/proof-core";
import { api } from "./api";
import type { User } from "./types";

const DB = "ledgeit-keys";
const STORE = "keys";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idb<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
    req.onsuccess = () => resolve(req.result as T);
    req.onerror = () => reject(req.error);
  });
}

export async function loadKey(employeeCode: string): Promise<KeyPair | undefined> {
  try {
    return await idb<KeyPair | undefined>("readonly", (s) => s.get(employeeCode));
  } catch {
    return undefined;
  }
}

export async function saveKey(employeeCode: string, kp: KeyPair): Promise<void> {
  await idb("readwrite", (s) => s.put(kp, employeeCode));
}

/** Make sure this browser holds a key for the user and that the server knows its public half. */
export async function ensureSigningKey(user: User): Promise<KeyPair> {
  let kp = await loadKey(user.employee_code);
  if (!kp) {
    kp = generateKeypair();
    await saveKey(user.employee_code, kp);
  }
  if (!user.public_keys.some((k) => k.public_key === kp!.publicKeyB64)) {
    await api("/auth/keys", { method: "POST", json: { public_key: kp.publicKeyB64, label: navigator.userAgent.slice(0, 60) } });
  }
  return kp;
}

export interface Signed<T> {
  payload: T;
  signature: string;
  digest: string;
}

export function sign<T extends object>(payload: T, kp: KeyPair): Signed<T> {
  const digest = hashJson(payload);
  return { payload, signature: signHexDigest(digest, kp.seedB64), digest };
}

export function signer(user: User, kp: KeyPair) {
  return { employee_code: user.employee_code, public_key: kp.publicKeyB64 };
}

export function nowTs(): string {
  return new Date().toISOString();
}
