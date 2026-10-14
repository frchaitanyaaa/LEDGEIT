import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileSignature, PenLine } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { nowTs, sign, signer } from "../lib/keys";
import type { InspectionDetail } from "../lib/types";
import { ErrorBox, Hash } from "./ui";

const REASONS = ["FALSE_POSITIVE", "FALSE_NEGATIVE", "LIGHTING", "SENSOR_FAULT", "OTHER"];

function SignPreview({ payload }: { payload: object }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="text-xs text-slate-500">
      <button type="button" className="underline" onClick={() => setOpen(!open)}>
        {open ? "hide" : "show"} exactly what you are signing
      </button>
      {open && <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">{JSON.stringify(payload, null, 2)}</pre>}
    </div>
  );
}

function useSigned(path: string, invalidate: string[]) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { payload: object; signature: string }) => api(path, { method: "POST", json: body }),
    onSuccess: () => invalidate.forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });
}

export function ReviewActions({ ins }: { ins: InspectionDetail }) {
  const { user, key, can } = useAuth();
  const [mode, setMode] = useState<"none" | "override">("none");
  const [reason, setReason] = useState(ins.decision === "FAIL" ? "FALSE_POSITIVE" : "FALSE_NEGATIVE");
  const [text, setText] = useState("");
  const [reviewed, setReviewed] = useState<string[]>([]);
  const review = useSigned(`/inspections/${ins.id}/review`, ["inspection", "timeline", "inspections"]);
  const override = useSigned(`/inspections/${ins.id}/override`, ["inspection", "timeline", "inspections", "overrides"]);
  if (!user || !can("QUALITY_ENGINEER", "QUALITY_MANAGER")) return null;
  if (!["PENDING_REVIEW", "AUTO_ACCEPTED"].includes(ins.status)) return null;
  if (!key) return <ErrorBox error="This browser has no signing key (IndexedDB unavailable) — actions are disabled." />;
  const newDecision = ins.decision === "PASS" ? "FAIL" : "PASS";

  const reviewPayload = {
    schema: "ledgeit.review.v1", inspection_id: ins.id, record_hash: ins.record_hash,
    accepted_decision: ins.decision, comment: "AI decision confirmed on review", reviewer: signer(user, key), signed_at: nowTs(),
  };
  const overridePayload = {
    schema: "ledgeit.override.v1", inspection_id: ins.id, record_hash: ins.record_hash,
    original: { decision: ins.decision, confidence: ins.confidence }, new_decision: newDecision,
    reason_code: reason, reason_text: text.trim(), reviewed_evidence: reviewed, operator: signer(user, key), signed_at: nowTs(),
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {ins.status === "PENDING_REVIEW" && (
          <button className="btn-success" disabled={review.isPending}
            onClick={() => review.mutate(sign({ ...reviewPayload, signed_at: nowTs() }, key))}>
            <FileSignature size={15} /> Sign: accept AI {ins.decision}
          </button>
        )}
        <button className="btn-secondary" onClick={() => setMode(mode === "override" ? "none" : "override")}>
          <PenLine size={15} /> Override to {newDecision}
        </button>
      </div>
      {mode === "override" && (
        <form className="space-y-3 rounded-lg border border-amber-200 bg-amber-50/50 p-3"
          onSubmit={(e) => { e.preventDefault(); override.mutate(sign({ ...overridePayload, signed_at: nowTs() }, key)); }}>
          <div>
            <label className="label">Reason code</label>
            <select className="input" value={reason} onChange={(e) => setReason(e.target.value)}>
              {REASONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Why (sealed with your signature)</label>
            <textarea className="input" rows={2} value={text} onChange={(e) => setText(e.target.value)}
              placeholder="e.g. Reflection from lighting, not a crack; checked under alternate angle" />
          </div>
          <div>
            <label className="label">Evidence you reviewed</label>
            {ins.evidence.map((ev) => (
              <label key={ev.id} className="mr-4 inline-flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={reviewed.includes(ev.sha256)}
                  onChange={(e) => setReviewed(e.target.checked ? [...reviewed, ev.sha256] : reviewed.filter((x) => x !== ev.sha256))} />
                {ev.kind.toLowerCase()} <Hash value={ev.sha256} n={5} />
              </label>
            ))}
          </div>
          <SignPreview payload={overridePayload} />
          <button className="btn-primary" disabled={override.isPending || text.trim().length < 10 || reviewed.length === 0}>
            <FileSignature size={15} /> Sign &amp; submit override
          </button>
        </form>
      )}
      <ErrorBox error={review.error || override.error} />
    </div>
  );
}

export function ApprovalActions({ ins, override: ov }: { ins: { id: string }; override: { id: string; payload_hash: string; operator: string } }) {
  const { user, key, can } = useAuth();
  const [comment, setComment] = useState("");
  const m = useSigned(`/overrides/${ov.id}/approve`, ["inspection", "timeline", "overrides", "inspections"]);
  if (!user || !can("QUALITY_MANAGER")) return null;
  if (user.employee_code === ov.operator) return <p className="text-xs text-slate-500">You raised this override — another Quality Manager must approve it.</p>;
  if (!key) return <ErrorBox error="No signing key in this browser." />;
  const payload = (approved: boolean) => ({
    schema: "ledgeit.approval.v1", override_payload_hash: ov.payload_hash, inspection_id: ins.id, approved,
    comment: comment.trim() || null, approver: signer(user, key), signed_at: nowTs(),
  });
  return (
    <div className="space-y-2">
      <input className="input" placeholder="Comment (optional, signed)" value={comment} onChange={(e) => setComment(e.target.value)} />
      <div className="flex gap-2">
        <button className="btn-success" disabled={m.isPending} onClick={() => m.mutate(sign(payload(true), key))}>
          <FileSignature size={15} /> Sign approval
        </button>
        <button className="btn-danger" disabled={m.isPending} onClick={() => m.mutate(sign(payload(false), key))}>
          Sign rejection
        </button>
      </div>
      <ErrorBox error={m.error} />
    </div>
  );
}

export function DisputeActions({ ins }: { ins: InspectionDetail }) {
  const { user, key, can } = useAuth();
  const [text, setText] = useState("");
  const m = useSigned(`/inspections/${ins.id}/dispute`, ["inspection", "timeline", "inspections"]);
  if (!user || !key || !can("QUALITY_MANAGER", "AUDITOR")) return null;
  const canRaise = ["RELEASED", "REJECTED", "AUTO_ACCEPTED"].includes(ins.status);
  const canResolve = ins.status === "DISPUTED" && user.role === "QUALITY_MANAGER";
  if (!canRaise && !canResolve) return null;
  const payload = (action: string, resolution: string | null) => ({
    schema: "ledgeit.dispute.v1", inspection_id: ins.id, record_hash: ins.record_hash, action, resolution,
    reason_text: text.trim(), actor: signer(user, key), signed_at: nowTs(),
  });
  return (
    <div className="space-y-2">
      <textarea className="input" rows={2} value={text} onChange={(e) => setText(e.target.value)}
        placeholder={canRaise ? "Why is this decision disputed? (e.g. customer return)" : "Resolution reasoning"} />
      <div className="flex gap-2">
        {canRaise && <button className="btn-secondary" disabled={text.trim().length < 10 || m.isPending}
          onClick={() => m.mutate(sign(payload("RAISE", null), key))}>Sign: raise dispute</button>}
        {canResolve && <>
          <button className="btn-success" disabled={text.trim().length < 10 || m.isPending}
            onClick={() => m.mutate(sign(payload("RESOLVE", "RELEASED"), key))}>Resolve → release</button>
          <button className="btn-danger" disabled={text.trim().length < 10 || m.isPending}
            onClick={() => m.mutate(sign(payload("RESOLVE", "REJECTED"), key))}>Resolve → reject</button>
        </>}
      </div>
      <ErrorBox error={m.error} />
    </div>
  );
}
