import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useT } from "@/i18n/useT";
import { useAuth } from "@/stores/auth";

export function RegisterPage() {
  const t = useT();
  const { register, loading, error, token } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  if (token) return <Navigate to="/projects" replace />;
  return (
    <div className="mx-auto max-w-sm py-16">
      <Card>
        <h1 className="mb-4 text-xl font-semibold">{t("auth.register_title")}</h1>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void register(email, password);
          }}
        >
          <label className="block text-sm">
            <span className="text-fg-muted">{t("auth.email")}</span>
            <Input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-fg-muted">{t("auth.password")}</span>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              minLength={8}
            />
          </label>
          {error && <div className="text-sm text-status-error">{t(error)}</div>}
          <Button type="submit" disabled={loading} className="w-full">
            {t("auth.submit_register")}
          </Button>
          <div className="text-sm text-fg-muted">
            <Link to="/login" className="text-accent-primary">
              {t("auth.login_title")}
            </Link>
          </div>
        </form>
      </Card>
    </div>
  );
}
