import { useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ThemeToggle } from "./components/ThemeToggle";
import { ApiConsolePage } from "./pages/ApiConsole";
import { DocumentListPage } from "./pages/DocumentList";
import { ProjectCreatePage } from "./pages/ProjectCreate";
import { ProjectListPage } from "./pages/ProjectList";
import { ReviewInboxPage } from "./pages/ReviewInbox";
import { SchemaEditorPage } from "./pages/SchemaEditor";
import { StudioPage } from "./pages/Studio";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { useAuth } from "./stores/auth";
import { ThemeProvider } from "./theme/ThemeProvider";

function AuthGate({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
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
                  <ProjectListPage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/new"
              element={
                <AuthGate>
                  <ProjectCreatePage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/:id"
              element={
                <AuthGate>
                  <DocumentListPage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/:id/studio/:did"
              element={
                <AuthGate>
                  <StudioPage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/:id/schema"
              element={
                <AuthGate>
                  <SchemaEditorPage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/:id/api-console"
              element={
                <AuthGate>
                  <ApiConsolePage />
                </AuthGate>
              }
            />
            <Route
              path="/projects/:id/review"
              element={
                <AuthGate>
                  <ReviewInboxPage />
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
