import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { useAuth } from "../lib/auth";

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
  if (user) return <Navigate to="/" replace />;
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center text-white">
          <img src="/favicon.svg" alt="" className="mx-auto h-12 w-12" />
          <h1 className="mt-3 text-2xl font-bold tracking-wide">LEDGEIT</h1>
          <p className="text-sm text-slate-400">A verifiable chain of custody for every AI inspection decision</p>
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
            <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          <ErrorBox error={err} />
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <p className="flex items-start gap-1.5 text-xs text-slate-500">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" />
            On first sign-in this browser creates an Ed25519 signing key; your overrides and approvals are signed with it.
          </p>
        </form>
        <div className="mt-4 rounded-lg bg-ink-900 p-3 text-xs text-slate-400">
          Demo users (password <code className="text-slate-200">ledgeit123</code>):
          <div className="mt-1 flex flex-wrap gap-1.5">
            {DEMO.map(([e, r]) => (
              <button key={e} type="button" onClick={() => { setEmail(e); setPassword("ledgeit123"); }}
                className="rounded bg-ink-800 px-2 py-0.5 text-slate-200 hover:bg-ink-700">{r}</button>
            ))}
          </div>
        </div>
        <p className="mt-4 text-center text-xs text-slate-500">
          Have a report or inspection code? <a className="text-brand-100 underline" href="/verify">Verify it publicly</a>
        </p>
      </div>
    </div>
  );
}
