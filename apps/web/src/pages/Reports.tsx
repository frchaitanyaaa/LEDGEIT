import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileCheck2 } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { Card, ErrorBox, Hash, PageHeader, Table } from "../components/ui";
import { api, download } from "../lib/api";
import { dt } from "../lib/format";

function Qr({ url }: { url: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => { QRCode.toDataURL(url, { margin: 1, width: 140 }).then(setSrc).catch(() => setSrc("")); }, [url]);
  return src ? <img src={src} alt={`QR code for ${url}`} className="h-28 w-28 rounded border" /> : null;
}

export default function Reports() {
  const qc = useQueryClient();
  const types = useQuery({ queryKey: ["report-types"], queryFn: () => api<{ type: string; title: string }[]>("/reports/types") });
  const batches = useQuery({ queryKey: ["batches"], queryFn: () => api<any[]>("/batches") });
  const list = useQuery({ queryKey: ["reports"], queryFn: () => api<any[]>("/reports") });
  const [rtype, setRtype] = useState("BATCH");
  const [batch, setBatch] = useState("");
  const [line, setLine] = useState("");
  const gen = useMutation({
    mutationFn: () => api<any>("/reports", { method: "POST", json: { report_type: rtype,
      params: { ...(rtype === "BATCH" ? { batch_code: batch || batches.data?.[0]?.batch_code } : {}), ...(line ? { line } : {}) } } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });
  const verifyUrl = (code: string) => `${location.origin}/verify/${code}`;
  return (
    <>
      <PageHeader title="Compliance reports" subtitle="Audit-ready PDFs. Each carries a QR code that re-verifies every listed record — for inspectors, regulators and customers." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Generate">
          <div className="space-y-3">
            <div><label className="label">Report type</label>
              <select className="input" value={rtype} onChange={(e) => setRtype(e.target.value)}>
                {types.data?.map((t) => <option key={t.type} value={t.type}>{t.title}</option>)}
              </select></div>
            {rtype === "BATCH" && <div><label className="label">Batch</label>
              <select className="input" value={batch} onChange={(e) => setBatch(e.target.value)}>
                {batches.data?.map((b) => <option key={b.batch_code} value={b.batch_code}>{b.batch_code} ({b.inspections})</option>)}
              </select></div>}
            <div><label className="label">Line (optional)</label>
              <select className="input" value={line} onChange={(e) => setLine(e.target.value)}>
                <option value="">All lines</option><option>LINE-A</option><option>LINE-B</option>
              </select></div>
            {rtype === "BATCH" && batches.data?.length === 0 && <p className="text-xs text-slate-500">No batches yet. Stream inspections first.</p>}
            <button className="btn-primary w-full" onClick={() => gen.mutate()}
              disabled={gen.isPending || types.isLoading || (rtype === "BATCH" && !batches.data?.length)}>
              <FileCheck2 size={16} /> {gen.isPending ? "Verifying records and rendering…" : "Generate report"}
            </button>
            <ErrorBox error={types.error || batches.error} onRetry={() => { types.refetch(); batches.refetch(); }} />
            <ErrorBox error={gen.error} />
            {gen.data && (
              <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3 text-sm">
                <Qr url={verifyUrl(gen.data.verification_code)} />
                <div>
                  <div className="font-semibold">{gen.data.verification_code}</div>
                  <div className="text-xs text-slate-500">{gen.data.inspections} records · {gen.data.summary.Verified} verified · {gen.data.summary.Failed} failed</div>
                  <a className="text-xs text-brand-600 underline" href={`/verify/${gen.data.verification_code}`} target="_blank" rel="noreferrer">Open public page</a>
                </div>
              </div>
            )}
          </div>
        </Card>
        <Card title="Generated reports" className="lg:col-span-2">
          <ErrorBox error={list.error} onRetry={() => list.refetch()} />
          <Table head={["Report", "Code", "Records", "Verified / failed", "PDF SHA-256", "Generated", ""]}
            loading={list.isLoading} empty={list.data?.length === 0} emptyText="No reports generated yet. Pick a type on the left and generate one.">
            {list.data?.map((r) => (
              <tr key={r.id}>
                <td className="td text-sm">{r.title}<div className="text-xs text-slate-500">{Object.values(r.params).join(" · ")}</div></td>
                <td className="td"><a className="font-mono text-xs text-brand-600" href={`/verify/${r.verification_code}`} target="_blank" rel="noreferrer">{r.verification_code}</a></td>
                <td className="td">{r.summary?.Inspections}</td>
                <td className="td text-xs">{r.summary?.Verified} / <span className={r.summary?.Failed ? "font-semibold text-rose-600" : ""}>{r.summary?.Failed}</span></td>
                <td className="td"><Hash value={r.file_sha256} n={5} /></td>
                <td className="td text-xs text-slate-500">{dt(r.created_at)} · {r.generated_by}</td>
                <td className="td"><button className="btn-secondary px-2 py-1 text-xs" onClick={() => download(`/reports/${r.id}/download`, `ledgeit-${r.verification_code}.pdf`)}><Download size={13} /> PDF</button></td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </>
  );
}
