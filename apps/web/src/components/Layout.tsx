import clsx from "clsx";
import {
  Activity, AlertOctagon, BarChart3, Blocks, Boxes, Brain, FileCheck2, Gauge, KeyRound, ListChecks, LogOut,
  ShieldCheck, UserCheck,
} from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import type { Role } from "../lib/types";

const ALL: Role[] = ["OPERATOR", "QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN"];
const NAV: { to: string; label: string; icon: any; roles: Role[] }[] = [
  { to: "/", label: "Executive", icon: Gauge, roles: ALL },
  { to: "/feed", label: "Live Feed", icon: Activity, roles: ALL },
  { to: "/inspections", label: "Inspections", icon: ListChecks, roles: ALL },
  { to: "/overrides", label: "Override Center", icon: UserCheck, roles: ["QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN"] },
  { to: "/explorer", label: "Blockchain Explorer", icon: Blocks, roles: ALL },
  { to: "/verification", label: "Verification Center", icon: ShieldCheck, roles: ALL },
  { to: "/risk", label: "Risk & Tampering", icon: AlertOctagon, roles: ["QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN"] },
  { to: "/models", label: "Model Registry", icon: Brain, roles: ALL },
  { to: "/reports", label: "Compliance Reports", icon: FileCheck2, roles: ["QUALITY_MANAGER", "AUDITOR", "ADMIN"] },
  { to: "/economics", label: "Economics", icon: BarChart3, roles: ["QUALITY_MANAGER", "AUDITOR", "ADMIN"] },
  { to: "/integrations", label: "Integrations", icon: Boxes, roles: ["ADMIN", "QUALITY_MANAGER"] },
];

export function Layout() {
  const { user, key, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const items = NAV.filter((n) => user && n.roles.includes(user.role));
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-ink-950 text-slate-300 md:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <img src="/favicon.svg" className="h-7 w-7" alt="" />
          <div>
            <div className="text-sm font-bold tracking-wide text-white">LEDGEIT</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Inspection integrity</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                clsx("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                  isActive ? "bg-ink-800 text-white" : "hover:bg-ink-900 hover:text-white")
              }
            >
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-ink-800 p-4 text-xs">
          <div className="font-medium text-white">{user?.full_name}</div>
          <div className="text-slate-500">{user?.employee_code} · {user?.role.replace("_", " ").toLowerCase()}</div>
          <div className="mt-2 flex items-center gap-1.5" title={key ? key.publicKeyB64 : "no signing key in this browser"}>
            <KeyRound size={12} className={key ? "text-emerald-400" : "text-amber-400"} />
            <span>{key ? "signing key ready" : "no signing key"}</span>
          </div>
          <button onClick={logout} className="mt-3 inline-flex items-center gap-1.5 text-slate-400 hover:text-white">
            <LogOut size={12} /> Sign out
          </button>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2 md:hidden">
          <span className="font-bold">LEDGEIT</span>
          <select aria-label="Go to page" className="input w-auto" value={items.find((n) => n.to !== "/" && pathname.startsWith(n.to))?.to ?? "/"}
            onChange={(e) => navigate(e.target.value)}>
            {items.map((n) => <option key={n.to} value={n.to}>{n.label}</option>)}
          </select>
        </div>
        <main className="mx-auto max-w-7xl px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
