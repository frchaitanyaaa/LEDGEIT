// Thin fetch wrapper: bearer token, one refresh retry, `{error:{code,message}}` errors.

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const TOKENS = "ledgeit.tokens";
type Tokens = { access_token: string; refresh_token: string };

export function getTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(TOKENS);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(t: Tokens | null) {
  try {
    if (t) localStorage.setItem(TOKENS, JSON.stringify(t));
    else localStorage.removeItem(TOKENS);
  } catch {
    /* storage unavailable: session-only */
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

async function refresh(): Promise<boolean> {
  const t = getTokens();
  if (!t) return false;
  const r = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh_token }),
  });
  if (!r.ok) return false;
  const body = await r.json();
  setTokens({ ...t, access_token: body.access_token });
  return true;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  const t = getTokens();
  if (t) headers.set("Authorization", `Bearer ${t.access_token}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const r = await fetch(`/api/v1${path}`, { ...init, headers, body });
  if (r.status === 401 && retry && t && !path.startsWith("/auth/login")) {
    if (await refresh()) return api<T>(path, init, false);
    setTokens(null);
    onUnauthorized?.();
  }
  if (!r.ok) {
    let code = "HTTP_ERROR";
    let message = r.statusText;
    let details: unknown;
    try {
      const e = (await r.json()).error;
      code = e.code;
      message = e.message;
      details = e.details;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(r.status, code, message, details);
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? r.json() : r.blob()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const blob = await api<Blob>(path);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
