import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { ApprovalActions, DisputeActions, ReviewActions } from "../components/Actions";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { Timeline } from "../components/Timeline";
import { ResultBanner, VerifyChecklist } from "../components/VerifyChecklist";
import { AnchorBadge, Badge, Card, DecisionBadge, ErrorBox, Hash, PageHeader, RiskBadge, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { dt } from "../lib/format";
import type { InspectionDetail as Detail, TimelineEvent, VerifyOut } from "../lib/types";

export default function InspectionDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const ins = useQuery({ queryKey: ["inspection", id], queryFn: () => api<Detail>(`/inspections/${id}`), refetchInterval: 4000 });
  const tl = useQuery({ queryKey: ["timeline", id], queryFn: () => api<TimelineEvent[]>(`/inspections/${id}/timeline`), refetchInterval: 4000 });
  const verify = useMutation({
    mutationFn: () => api<VerifyOut>(`/inspections/${id}/verify`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inspection", id] }),
  });
  if (ins.isLoading) return <Spinner />;
  if (ins.error || !ins.data) return <ErrorBox error={ins.error} />;
  const d = ins.data;
  const v = verify.data ?? (d.latest_verification ? { result: d.latest_verification.result, checks: d.latest_verification.checks,
    message: `Last verified ${dt(d.latest_verification.verified_at)}` } : null);
  const pending = d.overrides.find((o) => o.approved === null || o.approved === undefined);
  return (
    <>
      <PageHeader
        title={d.inspection_code}
        subtitle={<>Unit <b>{d.unit_serial}</b> · {d.batch_code} · {d.line} · {d.device} · {dt(d.inspected_at)}</>}
        actions={<button className="btn-primary" onClick={() => verify.mutate()} disabled={verify.isPending}>
          <ShieldCheck size={16} /> {verify.isPending ? "Verifying…" : "Verify now"}
        </button>}
      />
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Evidence"><EvidenceViewer ins={d} /></Card>
          <Card title="Sealed record">
            <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-sm">
              <dt className="text-slate-500">AI decision</dt><dd className="flex items-center gap-2"><DecisionBadge d={d.decision} /> {d.defect_class ?? ""} <span className="text-xs text-slate-500">{d.severity} · conf {d.confidence}</span></dd>
              <dt className="text-slate-500">Final</dt><dd className="flex items-center gap-2"><StatusBadge s={d.status} /> {d.final_decision && <DecisionBadge d={d.final_decision} />}</dd>
              <dt className="text-slate-500">Risk</dt><dd className="flex flex-wrap items-center gap-1.5"><RiskBadge r={d.risk_level} /> <span className="text-xs text-slate-500">{d.risk_reasons.join(" · ")}</span></dd>
              <dt className="text-slate-500">Model</dt><dd><span className="font-mono text-xs">{d.model.name}@{d.model.version}</span> <Badge tone={d.model.status === "APPROVED" ? "green" : "amber"}>{d.model.status}</Badge></dd>
              <dt className="text-slate-500">Weights</dt><dd><Hash value={d.model.weights_sha256} /></dd>
              <dt className="text-slate-500">Product</dt><dd>{d.product.name} {d.product.is_regulated && <Badge tone="violet">regulated</Badge>}</dd>
              <dt className="text-slate-500">Record hash</dt><dd><Hash value={d.record_hash} /></dd>
              <dt className="text-slate-500">Device sig.</dt><dd><Hash value={d.device_signature} /></dd>
              <dt className="text-slate-500">Prev record</dt><dd><Hash value={d.record.prev_record_hash} /></dd>
              <dt className="text-slate-500">Anchor</dt><dd><AnchorBadge s={d.anchor_status} /></dd>
            </dl>
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-slate-500">canonical JSON (ledgeit.inspection.v1)</summary>
              <pre className="mt-1 max-h-72 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">{JSON.stringify(d.record, null, 2)}</pre>
            </details>
          </Card>
        </div>
        <div className="space-y-4 lg:col-span-3">
          <Card title="Verification">
            <ErrorBox error={verify.error} />
            {v ? <div className="space-y-3"><ResultBanner result={v.result} message={v.message} /><VerifyChecklist checks={v.checks} /></div>
               : <p className="text-sm text-slate-500">Not verified yet. Click “Verify now” to run the 5 independent checks.</p>}
          </Card>
          {(["PENDING_REVIEW", "AUTO_ACCEPTED"].includes(d.status) || pending || ["RELEASED", "REJECTED", "AUTO_ACCEPTED", "DISPUTED"].includes(d.status)) && (
            <Card title="Human decision (signed in your browser)">
              <div className="space-y-4">
                <ReviewActions ins={d} />
                {pending && d.status === "PENDING_APPROVAL" && (
                  <div>
                    <p className="mb-2 text-sm">Override by <b>{pending.operator}</b>: {pending.original_decision} → <b>{pending.new_decision}</b> ({pending.reason_code}) — “{pending.reason_text}”</p>
                    <ApprovalActions ins={d} override={pending} />
                  </div>
                )}
                <DisputeActions ins={d} />
              </div>
            </Card>
          )}
          {d.alerts.length > 0 && (
            <Card title="Alerts">
              <ul className="space-y-1.5 text-sm">
                {d.alerts.map((a) => <li key={a.id} className="flex items-center gap-2"><Badge tone={a.severity === "HIGH" ? "red" : "amber"}>{a.alert_type}</Badge><span className="text-xs text-slate-500">{a.status} · {dt(a.created_at)}</span></li>)}
              </ul>
            </Card>
          )}
          <Card title="Event timeline (hash-chained)" actions={<Link to={`/verify/${d.inspection_code}`} className="text-xs text-brand-600">public verify page ↗</Link>}>
            {tl.data ? <Timeline events={tl.data} /> : <Spinner />}
          </Card>
        </div>
      </div>
    </>
  );
}
