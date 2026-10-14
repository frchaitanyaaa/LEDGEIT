import { useQuery } from "@tanstack/react-query";
import { Radio } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, DecisionBadge, Hash, PageHeader, RiskBadge, StatusBadge } from "../components/ui";
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

export default function LiveFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [connected, setConnected] = useState(false);
  const [anchorEvents, setAnchorEvents] = useState(0);
  const seeded = useRef(false);
  const initial = useQuery({ queryKey: ["inspections", "feed-seed"], queryFn: () => api<{ items: InspectionRow[] }>("/inspections?limit=30") });

  useEffect(() => {
    if (initial.data && !seeded.current) {
      seeded.current = true;
      setItems((cur) => [...cur, ...initial.data.items.map(fromRow)].slice(0, 60));
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
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (!stop) retry = setTimeout(connect, 2000); };
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === "inspection") setItems((cur) => [msg.data as FeedItem, ...cur.filter((c) => c.inspection_id !== msg.data.inspection_id)].slice(0, 60));
        if (msg.type === "anchor") setAnchorEvents((n) => n + 1);
      };
    };
    connect();
    return () => { stop = true; clearTimeout(retry); ws?.close(); };
  }, []);

  return (
    <>
      <PageHeader title="Live feed" subtitle="Inspections arrive here the moment an edge device seals and signs them."
        actions={<Badge tone={connected ? "green" : "amber"}><Radio size={12} /> {connected ? "live" : "reconnecting…"}</Badge>} />
      {anchorEvents > 0 && <p className="mb-3 text-xs text-slate-500">{anchorEvents} anchoring updates received</p>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((it) => (
          <Link key={it.inspection_id} to={`/inspections/${it.inspection_id}`} className="card block p-3 transition hover:border-brand-500">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate-500">{it.inspection_code}</span>
              <span className="text-xs text-slate-400">{ago(it.inspected_at)}</span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <DecisionBadge d={it.decision} />
              <span className="text-sm font-medium">{it.defect_class ?? "no defect"}</span>
              <span className="text-xs text-slate-500">{it.severity.toLowerCase()} · conf {it.confidence}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <RiskBadge r={it.risk_level} /><StatusBadge s={it.status} />
              {it.alerts?.map((a) => <Badge key={a} tone="red">{a}</Badge>)}
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
              {it.line} · {it.device} · {it.model.name}@{it.model.version} <span className="ml-auto"><Hash value={it.record_hash} n={5} /></span>
            </div>
          </Link>
        ))}
      </div>
      {items.length === 0 && <Card><p className="text-sm text-slate-500">Waiting for inspections… start the edge simulator: <code>python -m simulator --count 0</code></p></Card>}
    </>
  );
}
