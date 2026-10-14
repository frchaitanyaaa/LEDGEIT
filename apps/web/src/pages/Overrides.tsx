import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApprovalActions } from "../components/Actions";
import { Badge, Card, DecisionBadge, ErrorBox, PageHeader, Table } from "../components/ui";
import { api } from "../lib/api";
import { dt } from "../lib/format";

export default function Overrides() {
  const [tab, setTab] = useState<"PENDING" | "DECIDED">("PENDING");
  const q = useQuery({ queryKey: ["overrides", tab], queryFn: () => api<any[]>(`/overrides?status=${tab}`), refetchInterval: 4000 });
  return (
    <>
      <PageHeader title="Override center" subtitle="Every human override carries who, why and which evidence was reviewed — signed and anchored."
        actions={(["PENDING", "DECIDED"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={tab === t ? "btn-primary" : "btn-secondary"}>{t === "PENDING" ? "Awaiting approval" : "Decided"}</button>
        ))} />
      <ErrorBox error={q.error} />
      {tab === "PENDING" ? (
        <div className="space-y-3">
          {q.data?.length === 0 && <Card><p className="text-sm text-slate-500">No overrides waiting for approval.</p></Card>}
          {q.data?.map((o) => (
            <Card key={o.id} title={<Link to={`/inspections/${o.inspection_id}`} className="font-mono text-brand-600">{o.inspection_code}</Link>}
              actions={<span className="text-xs text-slate-500">{dt(o.created_at)}</span>}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1 text-sm">
                  <div className="flex items-center gap-2">AI <DecisionBadge d={o.original_decision} /> <span className="text-xs">conf {o.original_confidence}</span> → override <DecisionBadge d={o.new_decision} /></div>
                  <div><Badge>{o.reason_code}</Badge> “{o.reason_text}”</div>
                  <div className="text-xs text-slate-500">by {o.operator_name} ({o.operator}) · {o.line} · {o.model}</div>
                </div>
                <ApprovalActions ins={{ id: o.inspection_id }} override={o} />
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <Table head={["Inspection", "AI → override", "Reason", "Operator", "Outcome", "Approver", "Decided"]} empty={q.data?.length === 0}>
            {q.data?.map((o) => (
              <tr key={o.id}>
                <td className="td"><Link className="font-mono text-xs text-brand-600" to={`/inspections/${o.inspection_id}`}>{o.inspection_code}</Link></td>
                <td className="td"><DecisionBadge d={o.original_decision} /> → <DecisionBadge d={o.new_decision} /></td>
                <td className="td text-xs"><Badge>{o.reason_code}</Badge> {o.reason_text}</td>
                <td className="td text-xs">{o.operator}</td>
                <td className="td"><Badge tone={o.approved ? "green" : "red"}>{o.approved ? "approved" : "rejected"}</Badge></td>
                <td className="td text-xs">{o.approver}</td>
                <td className="td text-xs text-slate-500">{dt(o.decided_at)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </>
  );
}
