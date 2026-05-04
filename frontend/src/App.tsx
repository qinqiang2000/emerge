import { useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ThemeToggle } from "./components/ThemeToggle";
import { useT } from "./i18n/useT";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { useAuth } from "./stores/auth";
import { ThemeProvider } from "./theme/ThemeProvider";

function AuthGate({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function ProjectListPlaceholder() {
  const t = useT();
  return <div className="p-4">{t("projects.list_placeholder")}</div>;
}

export default function App() {
  const init = useAuth((s) => s.init);
  useEffect(() => {
    void init();
  }, [init]);

  return (
    <ThemeProvider>
      <BrowserRouter>
        <div className="min-h-dvh bg-bg-surface text-fg-primary">
          <header className="flex items-center justify-end border-b border-border-default bg-bg-elevated px-4 py-2">
            <ThemeToggle />
          </header>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/projects"
              element={
                <AuthGate>
                  <ProjectListPlaceholder />
                </AuthGate>
              }
            />
            <Route path="*" element={<Navigate to="/projects" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}
