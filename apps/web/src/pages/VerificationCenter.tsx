import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge, Card, ErrorBox, PageHeader, Stat, Table, VerifyBadge } from "../components/ui";
import { api } from "../lib/api";
import { dt } from "../lib/format";

const CHECKS = ["evidence", "model", "signature", "chain", "anchor"];

export default function VerificationCenter() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [line, setLine] = useState("");
  const [code, setCode] = useState("");
  const history = useQuery({ queryKey: ["verifications"], queryFn: () => api<any[]>("/verifications?limit=100"), refetchInterval: 5000 });
  const run = useMutation({
    mutationFn: () => api<any>(`/verify/batch?limit=100${line ? `&line=${line}` : ""}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["verifications"] }),
  });
  return (
    <>
      <PageHeader title="Verification center" subtitle="Re-check records against their original fingerprints. One changed byte → mismatch."
        actions={<>
          <select className="input w-auto" value={line} onChange={(e) => setLine(e.target.value)}>
            <option value="">all lines</option><option>LINE-A</option><option>LINE-B</option>
          </select>
          <button className="btn-primary" onClick={() => run.mutate()} disabled={run.isPending}><ShieldCheck size={16} /> {run.isPending ? "Verifying…" : "Verify latest 100"}</button>
        </>} />
      <Card className="mb-4">
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (code.trim()) nav(`/inspections/${code.trim()}`); }}>
          <div className="flex-1"><label className="label">Verify one record</label>
            <input className="input" placeholder="Inspection code (INS-…) or id" value={code} onChange={(e) => setCode(e.target.value)} /></div>
          <button className="btn-secondary">Open</button>
        </form>
      </Card>
      <ErrorBox error={run.error} />
      {run.data && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <Stat label="Verified" value={run.data.summary.VERIFIED} tone="green" />
          <Stat label="Pending anchor" value={run.data.summary.PENDING_ANCHOR} tone="amber" />
          <Stat label="Failed" value={run.data.summary.FAILED} tone={run.data.summary.FAILED ? "red" : undefined} />
        </div>
      )}
      <Card title="Verification history">
        <Table head={["When", "Inspection", "Result", ...CHECKS.map((c, i) => `${i + 1}. ${c}`), "By"]} empty={history.data?.length === 0}>
          {history.data?.map((v) => (
            <tr key={v.id}>
              <td className="td whitespace-nowrap text-xs text-slate-500">{dt(v.verified_at)}</td>
              <td className="td"><Link className="font-mono text-xs text-brand-600" to={`/inspections/${v.inspection_id}`}>{v.inspection_code}</Link></td>
              <td className="td"><VerifyBadge v={v.result} /></td>
              {CHECKS.map((c) => (
                <td key={c} className="td"><Badge tone={v.checks[c] === "PASS" ? "green" : v.checks[c] === "FAIL" ? "red" : "amber"}>{v.checks[c]}</Badge></td>
              ))}
              <td className="td text-xs">{v.requested_by ?? "public"}</td>
            </tr>
          ))}
        </Table>
      </Card>
    </>
  );
}
