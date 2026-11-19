import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

/** Opens an inspection as a sheet over the current screen, keeping whichever panel is open underneath. */
export function InspectionLink({ id, children, className }: { id: string; children: ReactNode; className?: string }) {
  const { search } = useLocation();
  const p = new URLSearchParams(search);
  p.set("inspection", id);
  return <Link to={`/?${p.toString()}`} className={className}>{children}</Link>;
}
