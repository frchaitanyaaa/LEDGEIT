import clsx from "clsx";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useAuth } from "../lib/auth";
import { PANELS } from "../lib/workspace";

interface Step { target: string | null; title: string; body: string }

const PANEL_TEXT: Record<string, string> = {
  inspections: "Every sealed inspection record. Search and filter by decision, risk, status or line, then open one for its full detail.",
  overrides: "Review AI decisions and approve or reject human overrides. Every change is recorded, never edited in place.",
  verification: "Re-compute an inspection's hashes and check them against the blockchain to prove nothing was altered.",
  explorer: "Browse anchored batches: transaction IDs, confirmation status and which inspections each batch covers.",
  risk: "Alerts such as duplicate evidence, possible replay and low confidence, so suspicious inspections get triaged.",
  models: "How the AI model performs: accuracy, false positives and false negatives.",
  reports: "Generate tamper-evident compliance reports with a verification code a regulator can check.",
  economics: "The business impact: defects caught, escapes avoided and review effort saved.",
  integrations: "Connect external systems such as ERP/MES, cameras and notifications.",
  analytics: "Trend charts for volume, fail rate and risk over time.",
};

/** The tutorial walks the screen top to bottom, then the tools a user's role can open. */
function useSteps(): Step[] {
  const { user } = useAuth();
  return useMemo(() => {
    const dock = PANELS.filter((p) => user && p.roles.includes(user.role))
      .map((p) => ({ target: `dock-${p.id}`, title: p.label, body: PANEL_TEXT[p.id] ?? "" }));
    return [
      { target: null, title: "Welcome to LEDGEIT", body: "A quick tour of the screen, from the top to the tools at the bottom. Use the arrow keys or the buttons; Esc closes it." },
      { target: "kpis", title: "Key figures", body: "Totals at a glance: inspections, AI fail rate, records waiting for review, anchored share and verification failures. Tap one to jump to it." },
      { target: "feed", title: "Live line", body: "Inspections appear here as they happen, with the AI decision, defect, risk and review status. Filter by pass, fail, high risk or alerts." },
      { target: "overview", title: "Overview", body: "Activity over the last 12 hours, open alerts, blockchain anchoring status and totals per production line." },
      ...dock,
      { target: "tutorial", title: "Tutorial switch", body: "Replay this tour any time, or switch the tutorial off so it never opens on its own." },
    ];
  }, [user]);
}

const PAD = 6;
const CARD_W = 340;
const find = (t: string | null) => (t ? document.querySelector<HTMLElement>(`[data-tour="${t}"]`) : null);

export function Tour({ onClose, onDisable }: { onClose: () => void; onDisable: () => void }) {
  const all = useSteps();
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Steps whose element is not on screen (e.g. the overview column on a phone) are dropped.
  const steps = useMemo(() => all.filter((s) => !s.target || !!find(s.target)?.getBoundingClientRect().width), [all]);
  const idx = Math.min(i, steps.length - 1);
  const step = steps[idx];
  const last = idx >= steps.length - 1;

  const measure = useCallback(() => {
    const el = find(step?.target ?? null);
    setRect(el ? el.getBoundingClientRect() : null);
  }, [step]);

  useLayoutEffect(() => {
    find(step?.target ?? null)?.scrollIntoView({ block: "nearest", inline: "center" });
    measure();
  }, [step, measure]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") (last ? onClose() : setI(idx + 1));
      else if (e.key === "ArrowLeft") setI(Math.max(0, idx - 1));
    };
    window.addEventListener("keydown", key);
    window.addEventListener("resize", measure);
    return () => { window.removeEventListener("keydown", key); window.removeEventListener("resize", measure); };
  }, [idx, last, measure, onClose]);

  if (!step) return null;
  const vw = window.innerWidth, vh = window.innerHeight;
  const w = Math.min(CARD_W, vw - 24);
  let style: React.CSSProperties;
  if (rect) {
    const below = rect.bottom + PAD + 10 + 200 < vh;
    const left = Math.min(Math.max(12, rect.left + rect.width / 2 - w / 2), vw - w - 12);
    style = { width: w, left, ...(below ? { top: rect.bottom + PAD + 10 } : { bottom: vh - rect.top + PAD + 10 }) };
  } else {
    style = { width: w, left: (vw - w) / 2, top: vh / 3 };
  }

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-label="Guided tutorial">
      {/* Click-catcher so the page underneath can't be used mid-tour. */}
      <div className="absolute inset-0" />
      {rect ? (
        <div className="pointer-events-none absolute rounded-xl ring-2 ring-brand-500 transition-all duration-200"
          style={{ top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2, boxShadow: "0 0 0 9999px rgba(15,23,42,0.6)" }} />
      ) : <div className="absolute inset-0 bg-slate-900/60" />}
      <div className="absolute rounded-2xl border border-slate-200 bg-white p-4 text-slate-800 shadow-2xl" style={style}>
        <button onClick={onClose} aria-label="Close tutorial" className="absolute right-2 top-2 rounded-full p-1.5 text-slate-400 hover:bg-brand-50 hover:text-brand-700"><X size={15} /></button>
        <p className="text-[11px] font-medium uppercase tracking-wider text-brand-600">Step {idx + 1} of {steps.length}</p>
        <h2 className="mt-0.5 pr-6 text-base font-semibold text-slate-900">{step.title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">{step.body}</p>
        <div className="mt-3 flex items-center gap-1" aria-hidden>
          {steps.map((_, n) => <span key={n} className={clsx("h-1 flex-1 rounded-full", n <= idx ? "bg-brand-500" : "bg-slate-200")} />)}
        </div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <button onClick={onDisable} className="text-xs text-slate-500 underline-offset-2 hover:underline">Don't show again</button>
          <div className="flex gap-2">
            <button onClick={() => setI(Math.max(0, idx - 1))} disabled={idx === 0}
              className="flex items-center gap-0.5 rounded-lg px-2.5 py-1.5 text-sm text-slate-600 enabled:hover:bg-brand-50 disabled:opacity-40"><ChevronLeft size={14} />Back</button>
            <button onClick={() => (last ? onClose() : setI(idx + 1))}
              className="flex items-center gap-0.5 rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
              {last ? "Done" : "Next"}{!last && <ChevronRight size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
