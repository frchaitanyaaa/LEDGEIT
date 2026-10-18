import { useQuery } from "@tanstack/react-query";
import { Pause, Play, Radio, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, DecisionBadge, ErrorBox, PageHeader, RiskBadge, Spinner, StatusBadge } from "../components/ui";
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
    <>
      <PageHeader title="Live feed" subtitle="Inspections appear here the moment an edge device seals and signs them."
        actions={<>
          <button className="btn-secondary" onClick={() => setPaused((p) => !p)}>
            {paused ? <><Play size={14} /> Resume</> : <><Pause size={14} /> Pause</>}
          </button>
          <Badge tone={paused ? "slate" : conn === "live" ? "green" : "amber"}>
            <Radio size={12} /> {paused ? "Paused" : conn === "live" ? "Live" : conn === "connecting" ? "Connecting…" : "Reconnecting…"}
          </Badge>
        </>} />
      <ErrorBox error={initial.error} onRetry={() => initial.refetch()} />
      <Card className="mb-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select className="input w-auto" value={decision} onChange={(e) => setDecision(e.target.value)} aria-label="Decision">
            <option value="">All decisions</option><option value="FAIL">FAIL</option><option value="PASS">PASS</option>
          </select>
          <select className="input w-auto" value={risk} onChange={(e) => setRisk(e.target.value)} aria-label="Risk">
            <option value="">All risk levels</option><option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option>
          </select>
          <label className="flex items-center gap-1.5 text-slate-600">
            <input type="checkbox" checked={alertsOnly} onChange={(e) => setAlertsOnly(e.target.checked)} /> With alerts only
          </label>
          {filtered && <button className="text-xs text-brand-600 hover:underline" onClick={() => { setDecision(""); setRisk(""); setAlertsOnly(false); }}>Clear filters</button>}
          <span className="ml-auto text-xs text-slate-500">
            Showing latest {shown.length}{items.length > shown.length ? ` of ${items.length} received` : ""}
            {anchorEvents > 0 && ` · ${anchorEvents} anchoring update${anchorEvents === 1 ? "" : "s"}`}
          </span>
        </div>
      </Card>
      <Card className="overflow-hidden p-0">
        <div className="divide-y divide-slate-100">
          {shown.map((it) => (
            <Link key={it.inspection_id} to={`/inspections/${it.inspection_id}`}
              className="grid grid-cols-[4.5rem,1fr,auto] items-center gap-x-3 gap-y-0.5 px-4 py-2.5 transition hover:bg-slate-50 sm:grid-cols-[4.5rem,5rem,1fr,auto]">
              <span className="text-xs text-slate-400">{ago(it.inspected_at)}</span>
              <span className="hidden sm:block"><DecisionBadge d={it.decision} /></span>
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-sm">
                  <span className="sm:hidden"><DecisionBadge d={it.decision} /></span>
                  <span className="truncate font-medium">{it.defect_class ?? "No defect"}</span>
                  {it.decision === "FAIL" && <span className="text-xs text-slate-500">{it.severity.toLowerCase()}</span>}
                  <span className="text-xs text-slate-400">· {it.confidence}</span>
                </span>
                <span className="block truncate font-mono text-xs text-slate-400">{it.inspection_code} · {it.device}</span>
              </span>
              <span className="flex items-center justify-end gap-1.5">
                {it.alerts?.length > 0 && (
                  <span title={it.alerts.join(", ")} className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
                    <TriangleAlert size={12} /> {it.alerts.length}
                  </span>
                )}
                {it.risk_level !== "LOW" && <RiskBadge r={it.risk_level} />}
                <StatusBadge s={it.status} />
              </span>
            </Link>
          ))}
        </div>
        {shown.length === 0 && initial.isLoading && <div className="p-4"><Spinner label="Loading recent inspections…" /></div>}
        {shown.length === 0 && !initial.isLoading && !initial.error && (
          <p className="p-4 text-sm text-slate-500">
            {filtered && items.length > 0 ? "No inspections match these filters." : <>Waiting for inspections. Start the edge simulator to stream them here: <code>python -m simulator --count 50 --rate 2</code></>}
          </p>
        )}
      </Card>
    </>
  );
}
