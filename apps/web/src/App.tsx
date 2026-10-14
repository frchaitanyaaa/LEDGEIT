import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import Economics from "./pages/Economics";
import Executive from "./pages/Executive";
import Explorer from "./pages/Explorer";
import InspectionDetail from "./pages/InspectionDetail";
import Inspections from "./pages/Inspections";
import Integrations from "./pages/Integrations";
import LiveFeed from "./pages/LiveFeed";
import Login from "./pages/Login";
import Models from "./pages/Models";
import Overrides from "./pages/Overrides";
import PublicVerify from "./pages/PublicVerify";
import Reports from "./pages/Reports";
import Risk from "./pages/Risk";
import VerificationCenter from "./pages/VerificationCenter";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify" element={<PublicVerify />} />
      <Route path="/verify/:code" element={<PublicVerify />} />
      <Route element={<Protected />}>
        <Route index element={<Executive />} />
        <Route path="feed" element={<LiveFeed />} />
        <Route path="inspections" element={<Inspections />} />
        <Route path="inspections/:id" element={<InspectionDetail />} />
        <Route path="overrides" element={<Overrides />} />
        <Route path="explorer" element={<Explorer />} />
        <Route path="verification" element={<VerificationCenter />} />
        <Route path="risk" element={<Risk />} />
        <Route path="models" element={<Models />} />
        <Route path="reports" element={<Reports />} />
        <Route path="economics" element={<Economics />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="*" element={<div className="p-10 text-center text-slate-500">Page not found.</div>} />
      </Route>
    </Routes>
  );
}
