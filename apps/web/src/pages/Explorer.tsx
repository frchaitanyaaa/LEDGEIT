import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorBox, Hash, PageHeader, RiskBadge, Stat, Table } from "../components/ui";
import { api } from "../lib/api";
import { ago, dt, inr } from "../lib/format";

export default function Explorer() {
  const [sel, setSel] = useState<number | null>(null);
  const info = useQuery({ queryKey: ["chain-info"], queryFn: () => api<any>("/chain/info"), refetchInterval: 10000 });
  const list = useQuery({ queryKey: ["anchors"], queryFn: () => api<any>("/anchors?limit=100"), refetchInterval: 3000 });
  const batch = useQuery({ queryKey: ["anchor", sel], queryFn: () => api<any>(`/anchors/${sel}`), enabled: sel !== null });
  const c = info.data;
  return (
    <>
      <PageHeader title="Blockchain explorer" subtitle="Merkle roots of inspection events anchored to LedgeitAnchor. Routine events wait in a batch; critical ones go immediately." />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Network" value={<span className="text-base">{c?.network ?? c?.chain ?? "—"}</span>} hint={c ? `chain id ${c.chain_id ?? "—"}` : ""} />
        <Stat label="Contract" value={<Hash value={c?.contract_address} n={6} />} hint={c?.reachable ? "reachable" : "node unreachable"} />
        <Stat label="Roots on-chain" value={c?.onchain_anchor_count ?? "—"} />
        <Stat label="Queued events" value={Object.values(list.data?.queued ?? {}).reduce((a: number, b: any) => a + b, 0) as number}
          hint={Object.entries(list.data?.queued ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "nothing waiting"} />
      </div>
      <ErrorBox error={list.error} />
      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card title="Anchor batches" className="lg:col-span-3">
          <Table head={["Batch", "Risk", "Leaves", "Insp.", "Status", "Merkle root", "Block", "Fee", "When"]} empty={list.data?.items.length === 0}>
            {list.data?.items.map((b: any) => (
              <tr key={b.id} onClick={() => setSel(b.id)} className={`cursor-pointer hover:bg-slate-50 ${sel === b.id ? "bg-brand-50" : ""}`}>
                <td className="td font-mono">#{b.id}</td>
                <td className="td"><RiskBadge r={b.risk_level} /></td>
                <td className="td">{b.leaf_count}</td>
                <td className="td">{b.inspections}</td>
                <td className="td"><Badge tone={b.status === "CONFIRMED" ? "blue" : b.status === "FAILED" ? "red" : "amber"}>{b.status}</Badge></td>
                <td className="td"><Hash value={b.merkle_root} n={5} /></td>
                <td className="td text-xs">{b.block_number ?? "—"}</td>
                <td className="td text-xs">{inr(b.fee_inr)}</td>
                <td className="td text-xs text-slate-500">{ago(b.confirmed_at ?? b.created_at)}</td>
              </tr>
            ))}
          </Table>
        </Card>
        <Card title={sel ? `Batch #${sel}` : "Select a batch"} className="lg:col-span-2">
          {!batch.data ? <p className="text-sm text-slate-500">Click a batch to see its leaves and transaction.</p> : (
            <div className="space-y-3 text-sm">
              <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1">
                <dt className="text-slate-500">Root</dt><dd><Hash value={batch.data.merkle_root} /></dd>
                <dt className="text-slate-500">Tx</dt><dd className="flex items-center gap-1.5"><Hash value={batch.data.tx_hash} />
                  {batch.data.explorer_url && <a href={batch.data.explorer_url} target="_blank" rel="noreferrer" className="text-brand-600"><ExternalLink size={14} /></a>}</dd>
                <dt className="text-slate-500">Block</dt><dd>{batch.data.block_number ?? "—"} · {dt(batch.data.block_timestamp)}</dd>
                <dt className="text-slate-500">Gas</dt><dd>{batch.data.gas_used ?? "—"} · {batch.data.fee_native ?? "—"} native · {inr(batch.data.fee_inr)}</dd>
                {batch.data.last_error && <><dt className="text-slate-500">Error</dt><dd className="text-rose-600">{batch.data.last_error} (attempts {batch.data.attempts})</dd></>}
              </dl>
              <Table head={["Leaf", "Inspection", "Event", "Leaf hash"]}>
                {batch.data.items.map((i: any) => (
                  <tr key={i.event_id}>
                    <td className="td text-xs">{i.leaf_index}</td>
                    <td className="td"><Link className="font-mono text-xs text-brand-600" to={`/inspections/${i.inspection_id}`}>{i.inspection_code}</Link></td>
                    <td className="td text-xs">{i.line} #{i.seq} {i.event_type}</td>
                    <td className="td"><Hash value={i.leaf_hash} n={4} /></td>
                  </tr>
                ))}
              </Table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
