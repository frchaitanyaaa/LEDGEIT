import { useQuery } from "@tanstack/react-query";
import { Pause, Play, Radio, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useWorkspace } from "../lib/workspace";
import { DecisionBadge, ErrorBox, RiskBadge, Spinner, StatusBadge } from "../components/ui";
import { api, getTokens } from "../lib/api";
import { ago } from "../lib/format";
import type { InspectionRow } from "../lib/types";

interface FeedItem {
  inspection_id: string; inspection_code: string; unit_serial: string; line: string; device: string; decision: string;
  defect_class: string | null; severity: string; confidence: string; risk_level: string; status: string; alerts: string[];
  record_hash: string; inspected_at: string; model: { name: string; version: string };
}

function fromRow(r: InspectionRow): FeedItem {
  return { inspection_id: r.id, inspection_code: r.inspection_code, unit_serial: r.unit_serial, line: r.line, device: r.device,
    decision: r.decision, defect_class: r.defect_class, severity: r.severity, confidence: r.confidence, risk_level: r.risk_level,
    status: r.status, alerts: [], record_hash: r.record_hash, inspected_at: r.inspected_at,
    model: { name: r.model_name, version: r.model_version } };
}

const MAX_ROWS = 40; // rows rendered; keeps the page readable however long the stream runs

export default function LiveFeed() {
  const { openInspection } = useWorkspace();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [conn, setConn] = useState<"connecting" | "live" | "reconnecting">("connecting");
  const [anchorEvents, setAnchorEvents] = useState(0);
  const [paused, setPaused] = useState(false);
  const [decision, setDecision] = useState("");
  const [risk, setRisk] = useState("");
  const [alertsOnly, setAlertsOnly] = useState(false);
  const seeded = useRef(false);
  const pausedRef = useRef(false);
  pausedRef.current = paused;
  const initial = useQuery({ queryKey: ["inspections", "feed-seed"], queryFn: () => api<{ items: InspectionRow[] }>("/inspections?limit=60") });

  useEffect(() => {
    if (initial.data && !seeded.current) {
      seeded.current = true;
      setItems((cur) => [...cur, ...initial.data.items.map(fromRow)].slice(0, 200));
    }
  }, [initial.data]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let stop = false;
    let retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      const t = getTokens();
      if (!t) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/feed?token=${encodeURIComponent(t.access_token)}`);
      ws.onopen = () => setConn("live");
      ws.onclose = () => { if (!stop) { setConn("reconnecting"); retry = setTimeout(connect, 2000); } };
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === "inspection" && !pausedRef.current)
          setItems((cur) => [msg.data as FeedItem, ...cur.filter((c) => c.inspection_id !== msg.data.inspection_id)].slice(0, 200));
        if (msg.type === "anchor") setAnchorEvents((n) => n + 1);
      };
    };
    connect();
    return () => { stop = true; clearTimeout(retry); ws?.close(); };
  }, []);

  const shown = items
    .filter((i) => (!decision || i.decision === decision) && (!risk || i.risk_level === risk) && (!alertsOnly || i.alerts?.length))
    .slice(0, MAX_ROWS);
  const filtered = decision || risk || alertsOnly;

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label="Live inspections">
      <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-2.5">
        <h2 className="mr-1 text-sm font-semibold text-slate-900">Live line</h2>
        <span className={"inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium " +
          (paused ? "bg-slate-100 text-slate-700" : conn === "live" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800")}>
          <Radio size={12} className={!paused && conn === "live" ? "animate-pulse" : ""} />
          {paused ? "Paused" : conn === "live" ? "Live" : conn === "connecting" ? "Connecting…" : "Reconnecting…"}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-1.5 text-xs">
          {([["", "All"], ["FAIL", "FAIL"], ["PASS", "PASS"]] as const).map(([v, l]) => (
            <button key={l} onClick={() => setDecision(v)} aria-pressed={decision === v}
              className={"rounded-full px-2.5 py-1 transition " + (decision === v ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>{l}</button>
          ))}
          <button onClick={() => setRisk(risk ? "" : "HIGH")} aria-pressed={!!risk}
            className={"rounded-full px-2.5 py-1 transition " + (risk ? "bg-rose-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>High risk</button>
          <button onClick={() => setAlertsOnly((a) => !a)} aria-pressed={alertsOnly}
            className={"rounded-full px-2.5 py-1 transition " + (alertsOnly ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>Alerts</button>
          <button onClick={() => setPaused((p) => !p)} aria-label={paused ? "Resume" : "Pause"}
            className="rounded-full bg-slate-100 p-1.5 text-slate-600 hover:bg-slate-200">{paused ? <Play size={14} /> : <Pause size={14} />}</button>
        </div>
      </header>
      {initial.error ? <div className="p-3"><ErrorBox error={initial.error} onRetry={() => initial.refetch()} /></div> : null}
      <div className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto">
        {shown.map((it) => (
          <button key={it.inspection_id} onClick={() => openInspection(it.inspection_id)}
            className="grid w-full grid-cols-[3rem,1fr] items-center gap-x-3 gap-y-1 sm:grid-cols-[3.5rem,1fr,auto] px-4 py-2.5 text-left transition hover:bg-brand-50 focus:bg-brand-50 focus:outline-none">
            <span className="text-xs text-slate-500">{ago(it.inspected_at)}</span>
            <span className="min-w-0">
              <span className="flex items-center gap-2 text-sm text-slate-900">
                <DecisionBadge d={it.decision} />
                <span className="truncate font-medium">{it.defect_class ?? "No defect"}</span>
                {it.decision === "FAIL" && <span className="text-xs text-slate-500">{it.severity.toLowerCase()}</span>}
                <span className="text-xs text-slate-500">· {it.confidence}</span>
              </span>
              <span className="block truncate font-mono text-xs text-slate-500">{it.inspection_code} · {it.device}</span>
            </span>
            <span className="col-start-2 flex flex-wrap items-center gap-1.5 sm:col-start-3 sm:justify-end">
              {it.alerts?.length > 0 && (
                <span title={it.alerts.join(", ")} className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                  <TriangleAlert size={12} /> {it.alerts.length}
                </span>
              )}
              {it.risk_level !== "LOW" && <RiskBadge r={it.risk_level} />}
              <StatusBadge s={it.status} />
            </span>
          </button>
        ))}
        {shown.length === 0 && initial.isLoading && <div className="p-4 text-slate-500"><Spinner label="Loading recent inspections…" /></div>}
        {shown.length === 0 && !initial.isLoading && !initial.error && (
          <p className="p-4 text-sm text-slate-500">
            {filtered && items.length > 0 ? "No inspections match these filters." : "Waiting for inspections — the simulated cameras stream here every couple of seconds."}
          </p>
        )}
      </div>
      <footer className="border-t border-slate-200 px-4 py-1.5 text-xs text-slate-500">
        Latest {shown.length}{items.length > shown.length ? ` of ${items.length}` : ""}
        {anchorEvents > 0 && ` · ${anchorEvents} anchoring update${anchorEvents === 1 ? "" : "s"}`}
        {filtered && <button className="ml-3 text-brand-600 hover:underline" onClick={() => { setDecision(""); setRisk(""); setAlertsOnly(false); }}>Clear filters</button>}
      </footer>
    </section>
  );
}
