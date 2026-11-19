import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { KeyRound, LogOut, Moon, Sun } from "lucide-react";
import { lazy, Suspense } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Sheet } from "../components/Sheet";
import { Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ago, pct } from "../lib/format";
import { useTheme } from "../lib/theme";
import { PANELS, useWorkspace } from "../lib/workspace";
import InspectionDetail from "./InspectionDetail";
import LiveFeed from "./LiveFeed";

const Economics = lazy(() => import("./Economics"));
const Executive = lazy(() => import("./Executive"));
const Explorer = lazy(() => import("./Explorer"));
const Inspections = lazy(() => import("./Inspections"));
const Integrations = lazy(() => import("./Integrations"));
const Models = lazy(() => import("./Models"));
const Overrides = lazy(() => import("./Overrides"));
const Reports = lazy(() => import("./Reports"));
const Risk = lazy(() => import("./Risk"));
const VerificationCenter = lazy(() => import("./VerificationCenter"));

const PANEL_VIEW: Record<string, React.ComponentType> = {
  inspections: Inspections, overrides: Overrides, verification: VerificationCenter, explorer: Explorer, risk: Risk,
  models: Models, reports: Reports, economics: Economics, integrations: Integrations, analytics: Executive,
};

function Kpi({ label, value, tone, onClick }: { label: string; value: React.ReactNode; tone?: "red" | "green" | "amber"; onClick?: () => void }) {
  return (
    <button onClick={onClick} disabled={!onClick}
      className="min-w-[7.5rem] shrink-0 rounded-xl bg-brand-50 px-3.5 py-2 text-left transition enabled:hover:bg-brand-100 disabled:cursor-default">
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={clsx("text-xl font-semibold leading-tight",
        tone === "red" ? "text-rose-600" : tone === "green" ? "text-emerald-600" : tone === "amber" ? "text-amber-600" : "text-slate-900")}>{value}</div>
    </button>
  );
}

function TopBar() {
  const { user, key, logout } = useAuth();
  const { openPanel } = useWorkspace();
  const { theme, toggle } = useTheme();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<any>("/dashboard/summary"), refetchInterval: 5000 });
  const k = q.data?.kpis;
  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-3 py-2.5 md:px-5">
      <div className="flex shrink-0 items-center gap-2">
        <img src="/favicon.svg" className="h-7 w-7" alt="" />
        <span className="hidden text-sm font-bold tracking-wide text-brand-700 sm:block">LEDGEIT</span>
      </div>
      <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto" aria-label="Key figures">
        {k ? (
          <>
            <Kpi label="Inspections" value={k.inspections} />
            <Kpi label="AI fail rate" value={pct(k.fail_rate)} />
            <Kpi label="Pending review" value={k.pending_review} tone={k.pending_review ? "amber" : undefined} onClick={() => openPanel("overrides")} />
            <Kpi label="Anchored" value={pct(k.anchored_rate)} tone="green" onClick={() => openPanel("explorer")} />
            <Kpi label="Verify failures" value={k.verification_failed} tone={k.verification_failed ? "red" : "green"} onClick={() => openPanel("verification")} />
          </>
        ) : <span className="px-2 text-xs text-slate-500">{q.error ? "Dashboard unavailable" : "Loading…"}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3 text-xs">
        <div className="hidden text-right md:block">
          <div className="font-medium text-slate-900">{user?.full_name}</div>
          <div className="text-slate-500">{user?.role.replace("_", " ").toLowerCase()}</div>
        </div>
        <span title={key ? key.publicKeyB64 : "no signing key in this browser"} className="hidden sm:block">
          <KeyRound size={15} className={key ? "text-emerald-600" : "text-amber-600"} />
        </span>
        <button onClick={toggle} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} title={theme === "dark" ? "Light mode" : "Dark mode"}
          className="rounded-full p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700">{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</button>
        <button onClick={logout} aria-label="Sign out" title="Sign out" className="rounded-full p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700"><LogOut size={16} /></button>
      </div>
    </header>
  );
}

/** Right-hand glance column: activity, open alerts and anchoring status. Everything deeper is one tap away. */
function Overview() {
  const { openPanel } = useWorkspace();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<any>("/dashboard/summary"), refetchInterval: 5000 });
  if (!q.data) return <div className="p-4 text-slate-500">{q.error ? "Dashboard unavailable." : <Spinner />}</div>;
  const d = q.data;
  const hourly = d.hourly.slice(-12).map((h: any) => ({ ...h, hour: h.hour.slice(11, 13) }));
  const critical = ["TAMPER_DETECTED", "DUPLICATE_EVIDENCE", "MISSING_ANCHOR", "SIGNATURE_INVALID", "MODEL_MISMATCH"];
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 text-sm">
      <section className="card p-3">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Last 12 hours</h3>
        <div className="h-28">
          <ResponsiveContainer>
            <BarChart data={hourly}>
              <XAxis dataKey="hour" fontSize={10} tick={{ fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#2f7cf614" }} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="pass" stackId="a" fill="#10b981" name="PASS" />
              <Bar dataKey="fail" stackId="a" fill="#e11d48" name="FAIL" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="card p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Open alerts</h3>
          <button onClick={() => openPanel("risk")} className="text-xs text-brand-600 hover:underline">View all</button>
        </div>
        {d.alert_types.length === 0 ? <p className="text-slate-500">No open alerts.</p> : (
          <ul className="space-y-1">
            {d.alert_types.slice(0, 5).map((a: any) => (
              <li key={a.type} className="flex items-center justify-between text-slate-700">
                <span>{a.type.replaceAll("_", " ").toLowerCase()}</span>
                <span className={clsx("rounded-md px-2 py-0.5 text-xs font-medium", critical.includes(a.type) ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800")}>{a.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="card p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Blockchain anchoring</h3>
          <button onClick={() => openPanel("explorer")} className="text-xs text-brand-600 hover:underline">Explorer</button>
        </div>
        <dl className="grid grid-cols-3 gap-2 text-center">
          <div><dd className="text-lg font-semibold text-emerald-600">{d.anchoring.confirmed}</dd><dt className="text-[10px] uppercase text-slate-500">confirmed</dt></div>
          <div><dd className="text-lg font-semibold text-amber-600">{d.anchoring.pending}</dd><dt className="text-[10px] uppercase text-slate-500">pending</dt></div>
          <div><dd className="text-lg font-semibold text-slate-900">{d.anchoring.queued_events}</dd><dt className="text-[10px] uppercase text-slate-500">queued</dt></div>
        </dl>
        <p className="mt-2 text-xs text-slate-500">Last confirmed {ago(d.anchoring.last_confirmed)}</p>
      </section>
      <section className="card p-3">
        <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Lines</h3>
        <ul className="space-y-1 text-slate-700">
          {d.by_line.map((l: any) => (
            <li key={l.line} className="flex justify-between"><span>{l.line}</span><span className="text-slate-500">{l.inspections} insp · {l.fail} fail</span></li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Dock() {
  const { user } = useAuth();
  const { panel, openPanel, closeAll } = useWorkspace();
  const items = PANELS.filter((p) => user && p.roles.includes(user.role));
  return (
    <nav aria-label="Tools" className="shrink-0 border-t border-slate-200 bg-white px-2 py-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))]">
      <ul className="mx-auto flex max-w-5xl justify-start gap-1 overflow-x-auto md:justify-center">
        {items.map(({ id, label, icon: Icon }) => {
          const active = panel?.id === id;
          return (
            <li key={id} className="shrink-0">
              <button onClick={() => (active ? closeAll() : openPanel(id))} aria-current={active ? "page" : undefined}
                className={clsx("flex w-[4.5rem] flex-col items-center gap-0.5 rounded-xl px-2 py-1.5 text-[11px] transition",
                  active ? "bg-brand-600 text-white" : "text-slate-500 hover:bg-brand-50 hover:text-brand-700")}>
                <Icon size={19} />{label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default function Workspace() {
  const { panel, inspection, closeTop } = useWorkspace();
  const View = panel ? PANEL_VIEW[panel.id] : null;
  return (
    <div className="app-bg flex h-dvh flex-col overflow-hidden text-slate-800">
      <TopBar />
      <main className="grid min-h-0 flex-1 lg:grid-cols-[1fr,22rem]">
        <div className="min-h-0 border-slate-200 lg:border-r"><LiveFeed /></div>
        <aside className="hidden min-h-0 lg:block" aria-label="Overview"><Overview /></aside>
      </main>
      <Dock />
      {panel && View && (
        <Sheet title={panel.label} onClose={inspection ? () => undefined : closeTop} wide>
          <Suspense fallback={<Spinner />}><View /></Suspense>
        </Sheet>
      )}
      {inspection && (
        <Sheet title="Inspection" level={2} onClose={closeTop}>
          <InspectionDetail id={inspection} />
        </Sheet>
      )}
    </div>
  );
}
