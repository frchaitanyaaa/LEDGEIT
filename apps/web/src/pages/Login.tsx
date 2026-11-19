import { Eye, EyeOff, Moon, ShieldCheck, Sun } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const DEMO = [
  ["qe@ledgeit.dev", "Quality Engineer"],
  ["qm@ledgeit.dev", "Quality Manager"],
  ["auditor@ledgeit.dev", "Auditor"],
  ["operator@ledgeit.dev", "Operator"],
  ["admin@ledgeit.dev", "Admin"],
];

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("qe@ledgeit.dev");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const { theme, toggle } = useTheme();
  if (user) return <Navigate to="/" replace />;
  return (
    <div className="app-bg relative flex min-h-screen items-center justify-center px-4">
      <button onClick={toggle} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="absolute right-4 top-4 rounded-full p-2 text-slate-500 hover:bg-brand-50 hover:text-brand-700">{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button>
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <img src="/favicon.svg" alt="" className="mx-auto h-12 w-12" />
          <h1 className="mt-3 text-2xl font-bold tracking-wide text-brand-700">LEDGEIT</h1>
          <p className="text-sm text-slate-500">A verifiable chain of custody for every AI inspection decision</p>
        </div>
        <form
          className="card space-y-4 p-6"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setErr(null);
            try {
              await login(email, password);
            } catch (x) {
              setErr(x);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <div className="relative">
              <input id="password" type={showPw ? "text" : "password"} className="input pr-10" value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
              <button type="button" onClick={() => setShowPw((v) => !v)} aria-label={showPw ? "Hide password" : "Show password"}
                aria-pressed={showPw} className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-500 hover:text-slate-700">
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <ErrorBox error={err} />
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <p className="flex items-start gap-1.5 text-xs text-slate-500">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" />
            On first sign-in this browser creates an Ed25519 signing key; your overrides and approvals are signed with it.
          </p>
        </form>
        <div className="card mt-4 p-3 text-xs text-slate-500">
          Demo users (password <code className="text-slate-800">ledgeit123</code>):
          <div className="mt-1 flex flex-wrap gap-1.5">
            {DEMO.map(([e, r]) => (
              <button key={e} type="button" onClick={() => { setEmail(e); setPassword("ledgeit123"); }}
                className="rounded bg-brand-50 px-2 py-0.5 text-brand-700 hover:bg-brand-100">{r}</button>
            ))}
          </div>
        </div>
        <p className="mt-4 text-center text-xs text-slate-500">
          Have a report or inspection code? <a className="text-brand-600 underline" href="/verify">Verify it publicly</a>
        </p>
      </div>
    </div>
  );
}
