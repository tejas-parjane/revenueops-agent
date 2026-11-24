import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { useAuth } from './lib/auth';
import { Spinner } from './components/UI';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Overview from './pages/Overview';
import Pipeline from './pages/Pipeline';
import AgentWorkspace from './pages/AgentWorkspace';
import Approvals from './pages/Approvals';
import Activity from './pages/Activity';
import Integrations from './pages/Integrations';
import Settings from './pages/Settings';

function Protected() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <Spinner />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Protected />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Overview />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/agent" element={<AgentWorkspace />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
