import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, CircleDashed, ExternalLink, XCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { sha256Hex } from "@ledgeit/proof-core";
import { ResultBanner, VerifyChecklist } from "../components/VerifyChecklist";
import { Badge, Card, DecisionBadge, ErrorBox, Hash, Spinner, Table } from "../components/ui";
import { verifyInBrowser, type Step } from "../lib/chainVerify";
import { dt } from "../lib/format";

async function fetchPublic(code: string) {
  const r = await fetch(`/api/v1/public/verify/${encodeURIComponent(code)}`);
  if (!r.ok) throw new Error(r.status === 404 ? "No inspection or report with this code." : `Verification service error (${r.status})`);
  return r.json();
}

function Steps({ steps }: { steps: Step[] }) {
  return (
    <ul className="space-y-1 text-xs">
      {steps.map((s, i) => (
        <li key={i} className="flex items-start gap-2">
          {s.ok === true ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" /> : s.ok === false ? <XCircle size={14} className="mt-0.5 shrink-0 text-rose-600" /> : <CircleDashed size={14} className="mt-0.5 shrink-0 text-amber-500" />}
          <span className={clsx(s.ok === false && "font-semibold text-rose-700")}>{s.label}</span>
          {s.detail && <span className="ml-auto truncate pl-2 font-mono text-[10px] text-slate-400">{s.detail.length > 40 ? s.detail.slice(0, 16) + "…" : s.detail}</span>}
        </li>
      ))}
    </ul>
  );
}

function InspectionView({ d }: { d: any }) {
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [busy, setBusy] = useState(false);
  const i = d.inspection;
  return (
    <div className="space-y-4">
      <ResultBanner result={d.result} message={d.message} />
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Record">
          <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-sm">
            <dt className="text-slate-500">Inspection</dt><dd className="font-mono">{i.inspection_code}</dd>
            <dt className="text-slate-500">Unit / batch</dt><dd>{i.unit_serial} · {i.batch_code}</dd>
            <dt className="text-slate-500">Product</dt><dd>{i.product}</dd>
            <dt className="text-slate-500">AI decision</dt><dd className="flex items-center gap-2"><DecisionBadge d={i.ai_decision} /> {i.defect_class ?? ""} <span className="text-xs text-slate-500">conf {i.confidence}</span></dd>
            <dt className="text-slate-500">Final decision</dt><dd><DecisionBadge d={i.final_decision} /> <span className="text-xs text-slate-500">{i.status}</span></dd>
            <dt className="text-slate-500">Model</dt><dd className="font-mono text-xs">{i.model_name}@{i.model_version}</dd>
            <dt className="text-slate-500">Inspected</dt><dd>{dt(i.inspected_at)}</dd>
            <dt className="text-slate-500">Record hash</dt><dd><Hash value={i.record_hash} /></dd>
          </dl>
          <p className="mt-3 text-xs text-slate-500">Evidence images are confidential and never shown here; only their hashes are.</p>
        </Card>
        <Card title="Server-side checks"><VerifyChecklist checks={d.checks} /></Card>
      </div>
      <Card title="Don’t trust us — verify in your browser"
        actions={d.proof.chain?.explorer && d.proof.events.find((e: any) => e.anchor?.tx_hash) &&
          <a className="inline-flex items-center gap-1 text-xs text-brand-600" target="_blank" rel="noreferrer"
             href={`${d.proof.chain.explorer}/tx/${d.proof.events.find((e: any) => e.anchor?.tx_hash).anchor.tx_hash}`}>Polygonscan <ExternalLink size={12} /></a>}>
        <p className="mb-3 text-sm text-slate-600">
          Your browser recomputes every event hash with the open LEDGEIT spec (RFC 8785 + SHA-256), walks each Merkle proof,
          and asks <b>{d.proof.chain?.network ?? "the blockchain"}</b> directly whether the root exists — no LEDGEIT server involved.
        </p>
        <button className="btn-primary" disabled={busy} onClick={async () => {
          setBusy(true);
          try { setSteps(await verifyInBrowser(d.proof.line, d.record, d.proof.events, d.proof.chain)); } finally { setBusy(false); }
        }}>{busy ? "Checking…" : "Run independent check"}</button>
        {steps && <div className="mt-3"><Steps steps={steps} />
          <div className="mt-2 text-sm font-semibold">{steps.some((s) => s.ok === false) ? "❌ Independent check failed" : steps.some((s) => s.ok === null) ? "⏳ Integrity confirmed; some anchors pending or chain not reachable" : "✅ Independently verified"}</div></div>}
        {d.proof.chain && <p className="mt-3 text-xs text-slate-500">Contract <Hash value={d.proof.chain.contract_address} n={6} /> on chain id {d.proof.chain.chain_id} via {d.proof.chain.rpc_url}</p>}
      </Card>
    </div>
  );
}

function ReportView({ d }: { d: any }) {
  const [fileHash, setFileHash] = useState<string | null>(null);
  const r = d.report;
  return (
    <div className="space-y-4">
      <ResultBanner result={d.result} message={d.message} />
      <Card title={r.title}>
        <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="text-slate-500">Code</dt><dd className="font-mono">{r.verification_code}</dd>
          <dt className="text-slate-500">Generated</dt><dd>{dt(r.generated_at)} by {r.generated_by}</dd>
          <dt className="text-slate-500">PDF SHA-256</dt><dd><Hash value={r.file_sha256} n={12} /></dd>
          <dt className="text-slate-500">Frozen content</dt><dd>{r.content_intact ? <Badge tone="green">intact</Badge> : <Badge tone="red">modified</Badge>}</dd>
        </dl>
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-3 text-sm">
          <label className="label">Check the PDF you received</label>
          <input type="file" accept="application/pdf" onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) setFileHash(sha256Hex(new Uint8Array(await f.arrayBuffer())));
          }} />
          {fileHash && <div className={clsx("mt-2 font-medium", fileHash === r.file_sha256 ? "text-emerald-700" : "text-rose-700")}>
            {fileHash === r.file_sha256 ? "✅ This is the original PDF (hash computed in your browser)" : "❌ This file differs from the issued report"}</div>}
        </div>
      </Card>
      <Card title="Records in this report — re-verified now">
        <Table head={["Inspection", "Record hash", "At issue", "Now"]}>
          {d.inspections.map((i: any) => (
            <tr key={i.inspection_code}>
              <td className="td"><a className="font-mono text-xs text-brand-600" href={`/verify/${i.inspection_code}`}>{i.inspection_code}</a></td>
              <td className="td"><Hash value={i.record_hash} n={6} /></td>
              <td className="td"><Badge tone={i.verification === "VERIFIED" ? "green" : i.verification === "FAILED" ? "red" : "amber"}>{i.verification}</Badge></td>
              <td className="td"><Badge tone={i.verification_now === "VERIFIED" ? "green" : i.verification_now === "PENDING_ANCHOR" ? "amber" : "red"}>{i.verification_now}</Badge></td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

export default function PublicVerify() {
  const { code } = useParams();
  const nav = useNavigate();
  const [input, setInput] = useState(code ?? "");
  const q = useQuery({ queryKey: ["public", code], queryFn: () => fetchPublic(code!), enabled: !!code, retry: false });
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-ink-950 text-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <img src="/favicon.svg" className="h-8 w-8" alt="" />
          <div><div className="font-bold tracking-wide">LEDGEIT public verification</div>
            <div className="text-xs text-slate-400">Check an AI inspection record or compliance report — no login needed</div></div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <form className="mb-5 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (input.trim()) nav(`/verify/${input.trim()}`); }}>
          <input className="input" placeholder="Report code (from the QR) or inspection code INS-…" value={input} onChange={(e) => setInput(e.target.value)} />
          <button className="btn-primary">Verify</button>
        </form>
        {q.isLoading && <Spinner label="Re-verifying against the blockchain…" />}
        <ErrorBox error={q.error} />
        {q.data?.kind === "inspection" && <InspectionView d={q.data} />}
        {q.data?.kind === "report" && <ReportView d={q.data} />}
      </main>
    </div>
  );
}
