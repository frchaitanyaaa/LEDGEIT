import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorBox, PageHeader, Stat, Table } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dt } from "../lib/format";

const SECURITY = ["TAMPER_DETECTED", "DUPLICATE_EVIDENCE", "POSSIBLE_REPLAY", "SIGNATURE_INVALID", "MODEL_MISMATCH", "MISSING_ANCHOR", "DELETION_ATTEMPT", "HASH_MISMATCH"];

function detailText(d: any): string {
  if (!d) return "";
  if (d.failed_checks) return `failed: ${d.failed_checks.join(", ")}`;
  if (d.matches) return `matches ${d.matches.map((m: any) => m.inspection_code + (m.distance !== undefined ? ` (d=${m.distance})` : "")).join(", ")}`;
  if (d.reason) return d.reason;
  if (d.rate) return `override rate ${d.rate} on ${d.model}`;
  return Object.entries(d).slice(0, 3).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ");
}

export default function Risk() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState("OPEN");
  const q = useQuery({ queryKey: ["alerts", status], queryFn: () => api<any>(`/alerts?limit=200${status ? `&status=${status}` : ""}`), refetchInterval: 4000 });
  const patch = useMutation({
    mutationFn: ({ id, s }: { id: string; s: string }) => api(`/alerts/${id}`, { method: "PATCH", json: { status: s } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
  const items: any[] = q.data?.items ?? [];
  const sec = items.filter((a) => SECURITY.includes(a.alert_type)).length;
  return (
    <>
      <PageHeader title="Risk & tampering" subtitle="Replay, tamper, model and anchoring alerts raised by ingest, verification and the worker."
        actions={<select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="OPEN">Open</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="RESOLVED">Resolved</option><option value="">All alerts</option>
        </select>} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Alerts (filtered)" value={items.length} />
        <Stat label="Security alerts" value={sec} tone={sec ? "red" : "green"} />
        <Stat label="HIGH severity" value={items.filter((a) => a.severity === "HIGH").length} tone="red" />
        <Stat label="MEDIUM severity" value={items.filter((a) => a.severity === "MEDIUM").length} tone="amber" />
      </div>
      <ErrorBox error={q.error || patch.error} onRetry={q.error ? () => q.refetch() : undefined} />
      <Card>
        <Table head={["Raised", "Alert", "Severity", "Inspection", "Details", "Status", ""]} loading={q.isLoading} empty={items.length === 0}
          emptyText={status === "OPEN" ? "No open alerts. Nothing needs attention right now." : "No alerts with this status."}>
          {items.map((a) => (
            <tr key={a.id}>
              <td className="td whitespace-nowrap text-xs text-slate-500">{dt(a.created_at)}</td>
              <td className="td"><Badge tone={SECURITY.includes(a.alert_type) ? "red" : "amber"}>{a.alert_type}</Badge></td>
              <td className="td"><Badge tone={a.severity === "HIGH" ? "red" : a.severity === "MEDIUM" ? "amber" : "slate"}>{a.severity}</Badge></td>
              <td className="td">{a.inspection_id ? <Link className="font-mono text-xs text-brand-600" to={`/inspections/${a.inspection_id}`}>{a.inspection_code}</Link> : "—"}</td>
              <td className="td max-w-md text-xs text-slate-600">{detailText(a.details)}</td>
              <td className="td text-xs">{a.status.charAt(0) + a.status.slice(1).toLowerCase()}{a.resolved_by ? ` by ${a.resolved_by}` : ""}</td>
              <td className="td whitespace-nowrap">
                {can("QUALITY_ENGINEER", "QUALITY_MANAGER", "ADMIN") && a.status === "OPEN" && <button className="btn-secondary px-2 py-1 text-xs" disabled={patch.isPending} onClick={() => patch.mutate({ id: a.id, s: "ACKNOWLEDGED" })}>Acknowledge</button>}
                {can("QUALITY_ENGINEER", "QUALITY_MANAGER", "ADMIN") && a.status !== "RESOLVED" && <button className="btn-secondary ml-1 px-2 py-1 text-xs" disabled={patch.isPending} onClick={() => patch.mutate({ id: a.id, s: "RESOLVED" })}>Resolve</button>}
              </td>
            </tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
