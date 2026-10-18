import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Card, ErrorBox, Hash, PageHeader, Table } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dt, pct } from "../lib/format";

export default function Models() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["models"], queryFn: () => api<any[]>("/models"), refetchInterval: 10000 });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "retire" }) => api(`/models/${id}/${action}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models"] }),
  });
  return (
    <>
      <PageHeader title="AI model registry" subtitle="Each version is identified by the SHA-256 of its weights. A record decided by an unapproved model fails verification check 2." />
      <ErrorBox error={q.error || act.error} onRetry={q.error ? () => q.refetch() : undefined} />
      <Card>
        <Table head={["Model", "Status", "Weights SHA-256", "Framework / dataset", "Metrics", "Inspections", "Override rate", "FP / FN rate", "Approved", ""]}
          loading={q.isLoading} empty={q.data?.length === 0} emptyText="No models registered yet. Run the seed or register one with POST /api/v1/models.">
          {q.data?.map((m) => (
            <tr key={m.id}>
              <td className="td font-mono text-xs">{m.name}<br /><b>{m.version}</b></td>
              <td className="td"><Badge tone={m.status === "APPROVED" ? "green" : m.status === "RETIRED" ? "slate" : "amber"}>{m.status}</Badge></td>
              <td className="td"><Hash value={m.weights_sha256} n={6} /></td>
              <td className="td text-xs">{m.framework}<br /><span className="text-slate-500">{m.dataset_version}</span></td>
              <td className="td text-xs">{Object.entries(m.metrics).filter(([k]) => k !== "per_class_mAP50").map(([k, v]) => <div key={k}>{k}: {String(v)}</div>)}</td>
              <td className="td">{m.inspections} <span className="text-xs text-slate-500">({m.ai_fail} FAIL)</span></td>
              <td className="td">{pct(m.override_rate)}</td>
              <td className="td text-xs" title="FP: AI said FAIL, human overrode to PASS. FN: AI said PASS, human overrode to FAIL.">{pct(m.fp_rate)} / {pct(m.fn_rate)}<br /><span className="text-slate-500">{m.false_positives} FP · {m.false_negatives} FN</span></td>
              <td className="td text-xs">{m.approved_by ? <>{m.approved_by}<br />{dt(m.approved_at)}</> : "â€”"}</td>
              <td className="td">
                {can("QUALITY_MANAGER", "ADMIN") && m.status !== "APPROVED" && <button className="btn-success px-2 py-1 text-xs" disabled={act.isPending} onClick={() => act.mutate({ id: m.id, action: "approve" })}>Approve</button>}
                {can("QUALITY_MANAGER", "ADMIN") && m.status === "APPROVED" && <button className="btn-secondary px-2 py-1 text-xs" disabled={act.isPending} onClick={() => act.mutate({ id: m.id, action: "retire" })}>Retire</button>}
              </td>
            </tr>
          ))}
        </Table>
        <p className="mt-3 text-xs text-slate-500">Register new versions with <code>POST /api/v1/models</code> (Admin) or <code>make seed</code> after training; identity (name, version, weights hash) is immutable in the database.</p>
      </Card>
    </>
  );
}
