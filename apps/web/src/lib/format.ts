export function short(h?: string | null, n = 10): string {
  if (!h) return "—";
  return h.length > n * 2 ? `${h.slice(0, n)}…${h.slice(-4)}` : h;
}

export function dt(s?: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

export function ago(s?: string | null): string {
  if (!s) return "—";
  const sec = Math.round((Date.now() - new Date(s).getTime()) / 1000);
  if (sec < 60) return `${Math.max(sec, 0)}s ago`;
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}

export function pct(v?: string | number | null, digits = 1): string {
  if (v === null || v === undefined || v === "") return "—";
  return `${(Number(v) * 100).toFixed(digits)}%`;
}

export function inr(v?: string | number | null, digits = 4): string {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toFixed(digits)}`;
}

export const STATUS_LABEL: Record<string, string> = {
  AUTO_ACCEPTED: "Auto-accepted",
  PENDING_REVIEW: "Pending review",
  PENDING_APPROVAL: "Pending approval",
  RELEASED: "Released",
  REJECTED: "Rejected",
  DISPUTED: "Disputed",
};
