import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorBox, PageHeader, Spinner, Stat, Table } from "../components/ui";
import { api } from "../lib/api";
import { ago, pct } from "../lib/format";

const RISK_COLORS: Record<string, string> = { LOW: "#94a3b8", MEDIUM: "#f59e0b", HIGH: "#e11d48" };

export default function Executive() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<any>("/dashboard/summary"), refetchInterval: 5000 });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const k = d.kpis;
  const hourly = d.hourly.map((h: any) => ({ ...h, hour: h.hour.slice(11) }));
  const risk = Object.entries(d.by_risk).map(([name, value]) => ({ name, value }));
  return (
    <>
      <PageHeader title="Executive dashboard" subtitle="Every AI decision sealed, chained and anchored — live." />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Inspections" value={k.inspections} hint={`${k.last_24h} in last 24 h`} />
        <Stat label="AI fail rate" value={pct(k.fail_rate)} hint={`${k.ai_fail} FAIL / ${k.ai_pass} PASS`} />
        <Stat label="Pending review" value={k.pending_review} tone={k.pending_review ? "amber" : undefined} hint={`${k.pending_approval} awaiting approval`} />
        <Stat label="Override rate" value={pct(k.override_rate)} hint={`${k.overrides} signed overrides`} />
        <Stat label="Anchored on-chain" value={pct(k.anchored_rate)} hint={`${d.anchoring.queued_events} events queued`} tone="green" />
        <Stat label="Verification failures" value={k.verification_failed} tone={k.verification_failed ? "red" : "green"} hint={`${k.verified} verified`} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Decisions per hour (24 h)" className="lg:col-span-2">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={hourly}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="hour" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Legend />
                <Bar dataKey="pass" stackId="a" fill="#10b981" name="PASS" />
                <Bar dataKey="fail" stackId="a" fill="#e11d48" name="FAIL" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Risk distribution">
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={risk} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                  {risk.map((r) => <Cell key={r.name} fill={RISK_COLORS[r.name]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Defect classes (AI FAIL)">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={d.by_class} layout="vertical" margin={{ left: 30 }}>
                <XAxis type="number" allowDecimals={false} fontSize={11} />
                <YAxis type="category" dataKey="defect_class" fontSize={11} width={100} />
                <Tooltip />
                <Bar dataKey="count" fill="#2f7cf6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Production lines">
          <Table head={["Line", "Inspections", "FAIL", "Chain length"]} empty={d.by_line.length === 0} emptyText="No production lines yet.">
            {d.by_line.map((l: any) => (
              <tr key={l.line}><td className="td whitespace-nowrap font-medium">{l.line}</td><td className="td">{l.inspections}</td>
                <td className="td">{l.fail}</td><td className="td">{l.chain_length} events</td></tr>
            ))}
          </Table>
          <div className="mt-3 text-xs text-slate-500">
            Anchoring: {d.anchoring.confirmed} batches confirmed · {d.anchoring.pending} pending · last {ago(d.anchoring.last_confirmed)}
          </div>
        </Card>
        <Card title="Open alerts" actions={<Link to="/risk" className="text-xs text-brand-600">View all</Link>}>
          {d.alert_types.length === 0 ? <p className="text-sm text-slate-500">No open alerts.</p> : (
            <ul className="space-y-1.5">
              {d.alert_types.map((a: any) => (
                <li key={a.type} className="flex items-center justify-between text-sm">
                  <span>{a.type.replaceAll("_", " ").toLowerCase()}</span><Badge tone={["TAMPER_DETECTED", "DUPLICATE_EVIDENCE", "MISSING_ANCHOR", "SIGNATURE_INVALID", "MODEL_MISMATCH"].includes(a.type) ? "red" : "amber"}>{a.count}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title="Models in use" className="mt-4">
        <Table head={["Model", "Status", "Inspections", "Overrides", "Avg confidence"]} empty={d.by_model.length === 0} emptyText="No inspections have used a model yet.">
          {d.by_model.map((m: any) => (
            <tr key={m.model}><td className="td font-mono text-xs">{m.model}</td><td className="td"><Badge tone={m.status === "APPROVED" ? "green" : "amber"}>{m.status}</Badge></td>
              <td className="td">{m.inspections}</td><td className="td">{m.overrides}</td><td className="td">{m.avg_confidence ?? "—"}</td></tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
