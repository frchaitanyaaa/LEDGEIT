import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ErrorBox, PageHeader, RiskBadge, Spinner, Stat, Table } from "../components/ui";
import { api } from "../lib/api";
import { inr } from "../lib/format";

export default function Economics() {
  const q = useQuery({ queryKey: ["economics"], queryFn: () => api<any>("/economics"), refetchInterval: 10000 });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const e = q.data;
  const cmp = [
    { name: "LEDGEIT (risk-adaptive batching)", inr: Number(e.batching.actual_inr) },
    { name: "1 tx per inspection", inr: Number(e.batching.without_batching_one_tx_per_inspection_inr) },
    { name: "1 tx per event", inr: Number(e.batching.without_batching_one_tx_per_event_inr) },
  ];
  return (
    <>
      <PageHeader title="Economics" subtitle={`Measured from real transaction receipts · 1 ${e.native_symbol} = ₹${e.native_to_inr} (config/economics.yaml)`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Cost per inspection" value={inr(e.cost_per_inspection_inr, 5)} hint={`${e.coverage.inspections_anchored} inspections anchored`} tone="green" />
        <Stat label="Total chain fees" value={inr(e.chain.fee_inr)} hint={`${e.chain.transactions} txs · ${Number(e.chain.fee_native).toPrecision(4)} ${e.native_symbol}`} />
        <Stat label="Batching savings" value={e.batching.savings_percent ? `${e.batching.savings_percent}%` : "—"} hint="vs one transaction per event" tone="green" />
        <Stat label="Events per tx" value={e.coverage.events_per_tx ?? "—"} hint={`avg ${e.chain.avg_gas_per_tx} gas per anchor`} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="What anchoring would cost without batching">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={cmp} margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" fontSize={10} interval={0} />
                <YAxis fontSize={11} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v: number) => `₹${v.toFixed(4)}`} />
                <Bar dataKey="inr">{cmp.map((_, i) => <Cell key={i} fill={i === 0 ? "#10b981" : "#94a3b8"} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="By risk level">
          <Table head={["Risk", "Batches", "Events", "Avg batch", "Fees"]} empty={e.by_risk.length === 0} emptyText="No batches anchored yet, so there are no fees to show.">
            {e.by_risk.map((r: any) => (
              <tr key={r.risk}><td className="td"><RiskBadge r={r.risk} /></td><td className="td">{r.batches}</td><td className="td">{r.leaves}</td>
                <td className="td">{r.avg_batch}</td><td className="td">{inr(r.fee_inr)}</td></tr>
            ))}
          </Table>
          <p className="mt-3 text-xs text-slate-500">HIGH-risk events are anchored immediately; LOW-risk ones wait for large batches. The trade-off is set in <code>config/risk.yaml</code>.</p>
        </Card>
      </div>
      <Card title="Other running costs (estimates)" className="mt-4">
        <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
          <div><dt className="text-slate-500">Evidence storage</dt><dd>{e.other_costs.evidence_storage_gb} GB → {inr(e.other_costs.storage_inr_per_month)}/month</dd></div>
          <div><dt className="text-slate-500">Inference compute</dt><dd>{inr(e.other_costs.compute_inr)}</dd></div>
          <div><dt className="text-slate-500">Gas used (total)</dt><dd>{e.chain.gas_used.toLocaleString()}</dd></div>
        </dl>
      </Card>
    </>
  );
}
