import clsx from "clsx";
import { CheckCircle2, Clock, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import type { CheckOut, VerifyResult } from "../lib/types";

const ORDER = ["evidence", "model", "signature", "chain", "anchor"];

export function ResultBanner({ result, message }: { result: VerifyResult; message: string }) {
  const ok = result === "VERIFIED";
  const fail = result === "FAILED";
  return (
    <div className={clsx("flex items-center gap-3 rounded-xl border p-4",
      ok && "border-emerald-200 bg-emerald-50 text-emerald-800",
      fail && "border-rose-200 bg-rose-50 text-rose-800",
      !ok && !fail && "border-amber-200 bg-amber-50 text-amber-800")}
    >
      {ok ? <ShieldCheck size={28} /> : fail ? <ShieldAlert size={28} /> : <Clock size={28} />}
      <div>
        <div className="text-lg font-semibold">{result.replace("_", " ")}</div>
        <div className="text-sm">{message}</div>
      </div>
    </div>
  );
}

export function VerifyChecklist({ checks, compact }: { checks: Record<string, CheckOut | { status: string; title: string; problems: string[] }>; compact?: boolean }) {
  return (
    <ol className="space-y-2">
      {ORDER.filter((k) => checks[k]).map((k, i) => {
        const c = checks[k];
        const Icon = c.status === "PASS" ? CheckCircle2 : c.status === "FAIL" ? XCircle : Clock;
        return (
          <li key={k} className={clsx("rounded-lg border px-3 py-2",
            c.status === "PASS" && "border-emerald-200 bg-emerald-50/50",
            c.status === "FAIL" && "border-rose-200 bg-rose-50",
            c.status === "PENDING" && "border-amber-200 bg-amber-50/60")}
          >
            <div className="flex items-center gap-2 text-sm font-medium">
              <Icon size={16} className={clsx(c.status === "PASS" && "text-emerald-600", c.status === "FAIL" && "text-rose-600", c.status === "PENDING" && "text-amber-600")} />
              <span className="text-slate-500">{i + 1}.</span> {c.title}
              <span className="ml-auto text-xs font-semibold">{c.status}</span>
            </div>
            {!compact && c.problems.length > 0 && (
              <ul className="mt-1 list-disc space-y-0.5 pl-9 text-xs text-slate-700">
                {c.problems.slice(0, 6).map((p, j) => <li key={j}>{p}</li>)}
                {c.problems.length > 6 && <li>… {c.problems.length - 6} more</li>}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}
