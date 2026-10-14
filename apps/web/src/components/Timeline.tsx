import clsx from "clsx";
import { Bot, Cpu, Link2, User } from "lucide-react";
import { dt } from "../lib/format";
import type { TimelineEvent } from "../lib/types";
import { AnchorBadge, Badge, Hash } from "./ui";

const ICON = { DEVICE: Cpu, USER: User, SYSTEM: Bot } as const;
const TONE: Record<string, string> = {
  OVERRIDDEN: "bg-amber-500", APPROVED: "bg-emerald-500", REJECTED: "bg-rose-500", RELEASED: "bg-emerald-500",
  REVIEWED: "bg-brand-500", DISPUTE_RAISED: "bg-violet-500", DISPUTE_RESOLVED: "bg-violet-500",
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-6">
      {events.map((e) => {
        const Icon = ICON[e.actor_type as keyof typeof ICON] ?? Bot;
        const inner = e.payload?.payload;
        return (
          <li key={e.id} className="relative">
            <span className={clsx("absolute -left-[33px] flex h-5 w-5 items-center justify-center rounded-full ring-4 ring-white", TONE[e.event_type] ?? "bg-slate-400")}>
              <Icon size={11} className="text-white" />
            </span>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold text-slate-800">{e.event_type}</span>
              <Badge>seq {e.seq}</Badge>
              <span className="text-slate-500">{e.actor_type.toLowerCase()} {e.actor_id ?? ""}</span>
              <span className="text-xs text-slate-400">{dt(e.created_at)}</span>
              <span className="ml-auto"><AnchorBadge s={e.anchor?.status ?? (e.queued_risk ? `queued ${e.queued_risk}` : null)} /></span>
            </div>
            {inner && (
              <div className="mt-1 text-xs text-slate-600">
                {inner.new_decision && <>Override → <b>{inner.new_decision}</b> ({inner.reason_code}): “{inner.reason_text}”</>}
                {inner.accepted_decision && <>Accepted AI decision <b>{inner.accepted_decision}</b>{inner.comment ? ` — ${inner.comment}` : ""}</>}
                {inner.approved !== undefined && <>{inner.approved ? "Approved" : "Rejected"} the override{inner.comment ? ` — ${inner.comment}` : ""}</>}
                {inner.action && <>Dispute {inner.action.toLowerCase()}{inner.resolution ? ` → ${inner.resolution}` : ""}: “{inner.reason_text}”</>}
              </div>
            )}
            {e.payload?.final_decision && <div className="mt-1 text-xs text-slate-600">Final decision <b>{e.payload.final_decision}</b></div>}
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
              <span>hash</span><Hash value={e.event_hash} n={6} />
              <Link2 size={11} /> <span>prev</span><Hash value={e.prev_event_hash} n={6} />
              {e.signature && <><span>sig</span><Hash value={e.signature} n={6} /></>}
              {e.anchor?.tx_hash && <><span>tx</span><Hash value={e.anchor.tx_hash} n={6} /> <span>block {e.anchor.block_number}</span></>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
