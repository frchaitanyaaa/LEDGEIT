import clsx from "clsx";
import { AlertTriangle, Check, Copy, Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { STATUS_LABEL, short } from "../lib/format";

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={clsx("card", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}

const TONES = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  red: "bg-rose-50 text-rose-700 ring-rose-600/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/20",
  blue: "bg-brand-50 text-brand-700 ring-brand-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20",
  violet: "bg-violet-50 text-violet-700 ring-violet-600/20",
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ tone = "slate", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone], className)}>
      {children}
    </span>
  );
}

export function DecisionBadge({ d }: { d?: string | null }) {
  if (!d) return <Badge>—</Badge>;
  return <Badge tone={d === "PASS" ? "green" : "red"}>{d}</Badge>;
}

export function RiskBadge({ r }: { r: string }) {
  return <Badge tone={r === "HIGH" ? "red" : r === "MEDIUM" ? "amber" : "slate"}>{r}</Badge>;
}

export function StatusBadge({ s }: { s: string }) {
  const tone: Tone = s === "RELEASED" || s === "AUTO_ACCEPTED" ? "green" : s === "REJECTED" ? "red"
    : s === "DISPUTED" ? "violet" : s.startsWith("PENDING") ? "amber" : "slate";
  return <Badge tone={tone}>{STATUS_LABEL[s] ?? s}</Badge>;
}

export function VerifyBadge({ v }: { v?: string | null }) {
  if (!v) return <Badge>not verified</Badge>;
  return <Badge tone={v === "VERIFIED" ? "green" : v === "FAILED" ? "red" : "amber"}>{v.replace("_", " ")}</Badge>;
}

export function AnchorBadge({ s }: { s?: string | null }) {
  if (!s) return <Badge>—</Badge>;
  return <Badge tone={s === "CONFIRMED" ? "blue" : s === "FAILED" ? "red" : "amber"}>{s === "CONFIRMED" ? "on-chain" : s.toLowerCase()}</Badge>;
}

export function Hash({ value, n = 8, className }: { value?: string | null; n?: number; className?: string }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <button
      type="button"
      title={value}
      onClick={() => {
        navigator.clipboard?.writeText(value).catch(() => undefined);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className={clsx("inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700 hover:bg-slate-200", className)}
    >
      {short(value, n)}
      {copied ? <Check size={11} /> : <Copy size={11} className="opacity-50" />}
    </button>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "red" | "green" | "amber" }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={clsx("mt-1 text-2xl font-semibold", tone === "red" && "text-rose-600", tone === "green" && "text-emerald-600", tone === "amber" && "text-amber-600")}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
      <Loader2 className="animate-spin" size={16} /> {label}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">{children}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {msg}
    </div>
  );
}

export function Table({ head, children, empty }: { head: ReactNode[]; children: ReactNode; empty?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100">
        <thead className="bg-slate-50">
          <tr>{head.map((h, i) => <th key={i} className="th">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {empty && <div className="p-6 text-center text-sm text-slate-500">Nothing here yet.</div>}
    </div>
  );
}
