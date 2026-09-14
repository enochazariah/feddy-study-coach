import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { TutorChat } from "./pages/TutorChat";
import { DemoWorkspace } from "./pages/DemoWorkspace";
import { Login } from "./pages/Login";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <main className="auth-loading" aria-live="polite">
        <p className="pill">Loading your study space...</p>
      </main>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/demo" element={<RequireAuth><DemoWorkspace /></RequireAuth>} />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/tutor"
        element={
          <RequireAuth>
            <TutorChat />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
