import { Activity, AlertOctagon, BarChart3, Blocks, Boxes, Brain, FileCheck2, ListChecks, ShieldCheck, UserCheck, type LucideIcon } from "lucide-react";
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { Role } from "./types";

/**
 * The whole app lives on one screen ("/"). What used to be separate pages are now panels (sheets) that slide
 * over the live view; the open panel and inspection are kept in the URL (?panel=risk&inspection=<id>) so
 * links, refresh and the browser back button all keep working.
 */
const ALL: Role[] = ["OPERATOR", "QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN"];
const REVIEW: Role[] = ["QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN"];
const MGMT: Role[] = ["QUALITY_MANAGER", "AUDITOR", "ADMIN"];

export interface PanelDef { id: string; label: string; icon: LucideIcon; roles: Role[] }

export const PANELS: PanelDef[] = [
  { id: "inspections", label: "Inspections", icon: ListChecks, roles: ALL },
  { id: "overrides", label: "Overrides", icon: UserCheck, roles: REVIEW },
  { id: "verification", label: "Verify", icon: ShieldCheck, roles: ALL },
  { id: "explorer", label: "Chain", icon: Blocks, roles: ALL },
  { id: "risk", label: "Risk", icon: AlertOctagon, roles: REVIEW },
  { id: "models", label: "Models", icon: Brain, roles: ALL },
  { id: "reports", label: "Reports", icon: FileCheck2, roles: MGMT },
  { id: "economics", label: "Economics", icon: BarChart3, roles: MGMT },
  { id: "integrations", label: "Integrations", icon: Boxes, roles: ["ADMIN", "QUALITY_MANAGER"] },
  { id: "analytics", label: "Analytics", icon: Activity, roles: ALL },
];

export const panelById = (id: string | null) => PANELS.find((p) => p.id === id) ?? null;

export function useWorkspace() {
  const [params, setParams] = useSearchParams();
  const panel = panelById(params.get("panel"));
  const inspection = params.get("inspection");

  const update = useCallback((mut: (p: URLSearchParams) => void, replace = false) => {
    const next = new URLSearchParams(params);
    mut(next);
    setParams(next, { replace });
  }, [params, setParams]);

  return {
    panel,
    inspection,
    openPanel: (id: string) => update((p) => { p.set("panel", id); p.delete("inspection"); }),
    openInspection: (id: string) => update((p) => p.set("inspection", id)),
    /** Closes the top-most sheet: the inspection first, then the panel underneath it. */
    closeTop: () => update((p) => { if (p.get("inspection")) p.delete("inspection"); else p.delete("panel"); }),
    closeAll: () => update((p) => { p.delete("inspection"); p.delete("panel"); }),
  };
}
