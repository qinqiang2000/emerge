import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { useT } from "@/i18n/useT";
import { api, EmergeError } from "@/lib/api";
import { useTemplates, type Template } from "@/stores/templates";

export function ProjectCreatePage() {
  const t = useT();
  const navigate = useNavigate();
  const rows = useTemplates((s) => s.rows);
  const load = useTemplates((s) => s.load);

  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  const trimmedName = name.trim();
  const canSubmit = trimmedName.length > 0 && !submitting;

  async function createProject(templateId: number | null) {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = (
        await api.post("/api/v1/projects", {
          name: trimmedName,
          template_id: templateId,
        })
      ).data as { id: number };
      navigate(`/projects/${created.id}`);
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      setError(`errors.${code}`);
      setSubmitting(false);
    }
  }

  const builtins = rows.filter((r) => r.builtin);

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold text-fg-primary">
          {t("projects.create_dialog_title")}
        </h1>
        <p className="text-sm text-fg-muted">{t("projects.nl_placeholder_hint")}</p>
      </header>

      <section className="space-y-2">
        <Textarea
          rows={3}
          placeholder={t("projects.create_dialog_hint")}
          disabled
          aria-disabled
          className="opacity-60"
        />
      </section>

      <section className="space-y-2">
        <label htmlFor="project-name" className="text-sm font-medium text-fg-primary">
          {t("projects.name_label")}
        </label>
        <Input
          id="project-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("projects.name_placeholder")}
          autoFocus
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-fg-primary">
          {t("projects.create_browse_templates")}
        </h2>
        {builtins.length === 0 ? (
          <p className="text-sm text-fg-muted">{t("projects.templates_empty")}</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {builtins.map((tpl) => (
              <BuiltinCard
                key={tpl.id}
                template={tpl}
                disabled={!canSubmit}
                onSelect={() => void createProject(tpl.id)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="flex items-center justify-between border-t border-border-default pt-4">
        <p className="text-sm text-fg-muted">{t("projects.empty_project_hint")}</p>
        <Button
          variant="secondary"
          disabled={!canSubmit}
          onClick={() => void createProject(null)}
        >
          {t("projects.create_empty_project")}
        </Button>
      </section>

      {error ? (
        <p role="alert" className="text-sm text-status-error">
          {t(error)}
        </p>
      ) : null}
    </main>
  );
}

function BuiltinCard({
  template,
  disabled,
  onSelect,
}: {
  template: Template;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onSelect}
      className="flex w-full flex-col items-start gap-1 rounded-md border border-border-default bg-bg-elevated p-4 text-left text-fg-primary transition-colors hover:border-accent-primary disabled:opacity-50"
    >
      <span className="font-mono text-sm text-fg-primary">{template.name}</span>
      {template.description ? (
        <span className="text-xs text-fg-muted">{template.description}</span>
      ) : null}
    </button>
  );
}
