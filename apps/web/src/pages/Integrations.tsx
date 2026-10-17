import { useQuery } from "@tanstack/react-query";
import { Badge, Card, ErrorBox, Hash, PageHeader, Table } from "../components/ui";
import { api } from "../lib/api";
import { ago } from "../lib/format";

const PLANNED = [
  ["MES (Manufacturing Execution System)", "Batch + work-order sync"],
  ["ERP (SAP / Oracle)", "Product master data, regulated SKUs"],
  ["SCADA / PLC", "Line stop on CRITICAL defects"],
  ["Existing AI cameras (Cognex, Keyence)", "Signed record export via edge agent"],
];

export default function Integrations() {
  const devices = useQuery({ queryKey: ["devices"], queryFn: () => api<any[]>("/devices"), refetchInterval: 5000 });
  const lines = useQuery({ queryKey: ["lines"], queryFn: () => api<any[]>("/lines") });
  return (
    <>
      <PageHeader title="System integrations" subtitle="LEDGEIT is a verification layer on top of existing inspection systems." />
      <ErrorBox error={devices.error || lines.error} onRetry={() => { devices.refetch(); lines.refetch(); }} />
      <Card title="Edge devices" className="mt-4">
        <Table head={["Device", "Line", "Type", "Public key (Ed25519)", "Inspections", "Last seen", "Status"]}
          loading={devices.isLoading} empty={devices.data?.length === 0} emptyText="No edge devices registered. Run the seed to create the demo devices.">
          {devices.data?.map((d) => (
            <tr key={d.id}><td className="td font-mono text-xs">{d.device_code}</td><td className="td">{d.line}</td><td className="td text-xs">{d.device_type}</td>
              <td className="td"><Hash value={d.public_key} n={6} /></td><td className="td">{d.inspections}</td><td className="td text-xs">{d.last_seen ? ago(d.last_seen) : "never"}</td>
              <td className="td"><Badge tone={d.is_active ? "green" : "slate"}>{d.is_active ? "active" : "inactive"}</Badge></td></tr>
          ))}
        </Table>
      </Card>
      <Card title="Production line hash chains" className="mt-4">
        <Table head={["Line", "Plant", "Events", "Head hash", "Genesis"]}
          loading={lines.isLoading} empty={lines.data?.length === 0} emptyText="No production lines configured yet.">
          {lines.data?.map((l) => (
            <tr key={l.id}><td className="td font-medium">{l.code}</td><td className="td text-xs">{l.plant}</td><td className="td">{l.last_seq}</td>
              <td className="td"><Hash value={l.last_event_hash} n={6} /></td><td className="td"><Hash value={l.genesis_hash} n={6} /></td></tr>
          ))}
        </Table>
      </Card>
      <Card title="Roadmap" className="mt-4">
        <ul className="space-y-2 text-sm">
          {PLANNED.map(([n, d]) => <li key={n} className="flex items-center gap-2"><Badge>planned</Badge><b>{n}</b><span className="text-slate-500">— {d}</span></li>)}
        </ul>
      </Card>
    </>
  );
}
