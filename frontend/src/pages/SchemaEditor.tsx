import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { useT } from "@/i18n/useT";
import { useSchema } from "@/stores/schema";
import type { SchemaField } from "@/types/schema";

export function SchemaEditorPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const active = useSchema((s) => s.active);
  const lockStatus = useSchema((s) => s.lockStatus);
  const loading = useSchema((s) => s.loading);
  const saving = useSchema((s) => s.saving);
  const locking = useSchema((s) => s.locking);
  const error = useSchema((s) => s.error);
  const load = useSchema((s) => s.load);
  const loadLockStatus = useSchema((s) => s.loadLockStatus);
  const save = useSchema((s) => s.save);
  const lock = useSchema((s) => s.lock);
  const unlock = useSchema((s) => s.unlock);

  const [draft, setDraft] = useState<SchemaField[]>([]);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (Number.isFinite(projectId)) {
      void load(projectId);
      void loadLockStatus(projectId);
    }
  }, [load, loadLockStatus, projectId]);

  useEffect(() => {
    if (active !== null) {
      setDraft(active.schema);
      setNotes(active.global_notes);
    }
  }, [active]);

  const subnav = Number.isFinite(projectId) ? (
    <ProjectSubNav projectId={projectId} />
  ) : null;

  if (loading && active === null) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-4xl p-6">
          <p className="text-fg-muted">{t("schema.loading")}</p>
        </main>
      </>
    );
  }
  if (active === null) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-4xl p-6">
          <p className="text-fg-muted">{t("schema.empty")}</p>
        </main>
      </>
    );
  }

  const isLocked = active.locked;
  const canLock = lockStatus?.can_lock ?? false;
  const lockReason = lockStatus?.reason ?? null;

  function patchField(idx: number, patch: Partial<SchemaField>) {
    setDraft((rows) =>
      rows.map((f, i) => (i === idx ? { ...f, ...patch } : f)),
    );
  }

  function handleSave() {
    if (active === null) return;
    void save(projectId, draft, notes, active.model_id);
  }

  return (
    <>
    {subnav}
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-fg-primary">
            {t("schema.title")} v{active.version_number}
          </h1>
          <p className="text-xs text-fg-muted">{active.model_id}</p>
        </div>
        <div className="flex items-center gap-2">
          {isLocked ? (
            <Badge tone="success">{t("schema.locked_badge")}</Badge>
          ) : (
            <Badge tone="muted">{t("schema.unlocked_badge")}</Badge>
          )}
          {isLocked ? (
            <Button
              variant="secondary"
              disabled={locking}
              onClick={() => void unlock(projectId)}
            >
              {locking ? t("common.loading") : t("schema.unlock_button")}
            </Button>
          ) : (
            <Button
              disabled={!canLock || locking}
              onClick={() => void lock(projectId)}
            >
              {locking ? t("common.loading") : t("schema.lock_button")}
            </Button>
          )}
        </div>
      </header>

      {!isLocked && lockReason ? (
        <p className="text-sm text-fg-muted">{lockReason}</p>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-status-error">
          {t(error)}
        </p>
      ) : null}

      <section className="space-y-4">
        {draft.length === 0 ? (
          <p className="text-fg-muted">{t("schema.no_fields")}</p>
        ) : (
          draft.map((field, idx) => (
            <article
              key={field.name}
              className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4"
            >
              <header className="flex items-center justify-between">
                <span className="font-mono text-sm text-fg-primary">
                  {field.name}
                </span>
                <span className="text-xs text-fg-muted">{field.type}</span>
              </header>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-xs text-fg-muted">
                  {t("schema.field_description_label")}
                </span>
                <Textarea
                  rows={2}
                  disabled={isLocked}
                  value={field.description}
                  onChange={(e) =>
                    patchField(idx, { description: e.target.value })
                  }
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-fg-primary">
                <Switch
                  checked={field.required}
                  disabled={isLocked}
                  onCheckedChange={(checked) =>
                    patchField(idx, { required: checked })
                  }
                />
                {t("schema.field_required_label")}
              </label>
            </article>
          ))
        )}
      </section>

      <section className="space-y-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-fg-muted">{t("schema.notes_label")}</span>
          <Textarea
            rows={3}
            disabled={isLocked}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
      </section>

      <footer className="flex justify-end">
        <Button disabled={isLocked || saving} onClick={handleSave}>
          {saving ? t("common.loading") : t("common.save")}
        </Button>
      </footer>
    </main>
    </>
  );
}
