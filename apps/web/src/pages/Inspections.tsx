import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AnchorBadge, Card, DecisionBadge, ErrorBox, Hash, PageHeader, RiskBadge, StatusBadge, Table, VerifyBadge } from "../components/ui";
import { api } from "../lib/api";
import { STATUS_LABEL, dt } from "../lib/format";
import type { InspectionRow } from "../lib/types";

const FILTERS = {
  decision: ["", "PASS", "FAIL"],
  risk: ["", "LOW", "MEDIUM", "HIGH"],
  status: ["", "AUTO_ACCEPTED", "PENDING_REVIEW", "PENDING_APPROVAL", "RELEASED", "REJECTED", "DISPUTED"],
  line: ["", "LINE-A", "LINE-B"],
} as const;
const FILTER_ALL: Record<keyof typeof FILTERS, string> = {
  decision: "All decisions", risk: "All risk levels", status: "All statuses", line: "All lines",
};

export default function Inspections() {
  const [f, setF] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const params = new URLSearchParams({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), ...(q ? { q } : {}),
                                       limit: "50", offset: String(page * 50) });
  const r = useQuery({ queryKey: ["inspections", params.toString()], queryFn: () => api<{ total: number; items: InspectionRow[] }>(`/inspections?${params}`),
                       placeholderData: keepPreviousData, refetchInterval: 5000 });
  const filtered = Boolean(q) || Object.values(f).some(Boolean);
  return (
    <>
      <PageHeader title="Inspections" subtitle={r.data ? `${r.data.total} sealed records` : undefined} />
      <Card>
        <div className="mb-3 flex flex-wrap gap-2">
          <input className="input w-64" placeholder="Search code, unit serial, record hash…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          {Object.entries(FILTERS).map(([k, opts]) => (
            <select key={k} className="input w-auto" value={f[k] ?? ""} onChange={(e) => { setF({ ...f, [k]: e.target.value }); setPage(0); }}>
              {opts.map((o) => <option key={o} value={o}>{o ? (k === "status" ? STATUS_LABEL[o] ?? o : o) : FILTER_ALL[k as keyof typeof FILTERS]}</option>)}
            </select>
          ))}
        </div>
        <ErrorBox error={r.error} onRetry={() => r.refetch()} />
        <Table head={["Inspection", "Unit", "AI", "Defect", "Conf.", "Risk", "Status", "Anchor", "Verified", "Record hash", "Inspected"]}
          loading={r.isLoading} empty={r.data?.items.length === 0}
          emptyText={filtered ? "No inspections match these filters." : "No inspections yet. Start the edge simulator to stream sealed records."}>
          {r.data?.items.map((i) => (
            <tr key={i.id} className="hover:bg-slate-50">
              <td className="td"><Link className="font-mono text-xs text-brand-600 hover:underline" to={`/inspections/${i.id}`}>{i.inspection_code}</Link></td>
              <td className="td text-xs">{i.unit_serial}</td>
              <td className="td"><DecisionBadge d={i.decision} /></td>
              <td className="td text-xs">{i.defect_class ?? "—"} <span className="text-slate-400">{i.severity !== "NONE" ? i.severity.toLowerCase() : ""}</span></td>
              <td className="td text-xs">{i.confidence}</td>
              <td className="td"><RiskBadge r={i.risk_level} /></td>
              <td className="td"><StatusBadge s={i.status} /></td>
              <td className="td"><AnchorBadge s={i.anchor_status} /></td>
              <td className="td"><VerifyBadge v={i.last_verification} /></td>
              <td className="td"><Hash value={i.record_hash} n={5} /></td>
              <td className="td whitespace-nowrap text-xs text-slate-500">{dt(i.inspected_at)}</td>
            </tr>
          ))}
        </Table>
        {r.data && r.data.total > 50 && (
          <div className="mt-3 flex items-center gap-2 text-sm">
            <button className="btn-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
            <span>Page {page + 1} of {Math.ceil(r.data.total / 50)}</span>
            <button className="btn-secondary" disabled={(page + 1) * 50 >= r.data.total} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </Card>
    </>
  );
}
