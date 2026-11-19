import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import { PANELS } from "./lib/workspace";
import Login from "./pages/Login";
import PublicVerify from "./pages/PublicVerify";
import Workspace from "./pages/Workspace";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Old page URLs (bookmarks, screenshots, shared links) now open the matching panel on the single screen. */
function ToInspection() {
  const { id } = useParams();
  return <Navigate to={`/?inspection=${encodeURIComponent(id ?? "")}`} replace />;
}

const LEGACY_ROUTES: [string, string][] = [["feed", "/"], ...PANELS.map((p): [string, string] => [p.id, `/?panel=${p.id}`])];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify" element={<PublicVerify />} />
      <Route path="/verify/:code" element={<PublicVerify />} />
      <Route path="/" element={<Protected><Workspace /></Protected>} />
      <Route path="/inspections/:id" element={<ToInspection />} />
      {LEGACY_ROUTES.map(([path, to]) => <Route key={path} path={`/${path}`} element={<Navigate to={to} replace />} />)}
      <Route path="*" element={<div className="p-10 text-center text-slate-500">Page not found.</div>} />
    </Routes>
  );
}
