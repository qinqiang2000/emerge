import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useT } from "@/i18n/useT";
import {
  useStudio,
  type DocumentDetail,
  type EntityOutput,
} from "@/stores/studio";

function isDirty(a: EntityOutput[], b: EntityOutput[]): boolean {
  return JSON.stringify(a) !== JSON.stringify(b);
}

function baselineOutput(doc: DocumentDetail | null): EntityOutput[] {
  if (doc === null) return [];
  if (doc.latest_annotation?.output) return doc.latest_annotation.output;
  if (doc.latest_prediction?.output) return doc.latest_prediction.output;
  return [];
}

export function StudioPage() {
  const t = useT();
  const params = useParams<{ id: string; did: string }>();
  const projectId = Number(params.id);
  const documentId = Number(params.did);

  const doc = useStudio((s) => s.doc);
  const draft = useStudio((s) => s.draft);
  const loading = useStudio((s) => s.loading);
  const saving = useStudio((s) => s.saving);
  const error = useStudio((s) => s.error);
  const load = useStudio((s) => s.load);
  const setDraft = useStudio((s) => s.setDraft);
  const save = useStudio((s) => s.save);

  useEffect(() => {
    if (Number.isFinite(projectId) && Number.isFinite(documentId)) {
      void load(projectId, documentId);
    }
  }, [load, projectId, documentId]);

  const dirty = isDirty(draft, baselineOutput(doc));

  function updateField(entityIdx: number, key: string, value: string) {
    const next = draft.map((entity, i) =>
      i === entityIdx ? { ...entity, [key]: value } : entity,
    );
    setDraft(next);
  }

  const subnav = Number.isFinite(projectId) ? (
    <ProjectSubNav projectId={projectId} />
  ) : null;

  if (loading && doc === null) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-6xl p-6">
          <p className="text-fg-muted">{t("studio.loading")}</p>
        </main>
      </>
    );
  }
  if (doc === null) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-6xl p-6">
          <p className="text-fg-muted">{t("studio.empty")}</p>
        </main>
      </>
    );
  }

  return (
    <>
    {subnav}
    <main className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-fg-primary">{doc.filename}</h1>
          <p className="text-xs text-fg-muted">
            {doc.mime_type} · {doc.page_count} {t("studio.pages")} · {doc.status}
          </p>
        </div>
        <Button
          disabled={!dirty || saving}
          onClick={() => void save(projectId)}
        >
          {saving ? t("common.loading") : t("studio.save_correction")}
        </Button>
      </header>

      {error ? (
        <p role="alert" className="text-sm text-status-error">
          {t(error)}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-border-default bg-bg-elevated p-4">
          <p className="text-xs uppercase tracking-wide text-fg-muted">
            {t("studio.preview_placeholder_title")}
          </p>
          <p className="mt-2 text-sm text-fg-primary">{doc.filename}</p>
          <p className="text-xs text-fg-muted">
            {doc.mime_type} · {doc.page_count} {t("studio.pages")}
          </p>
          <p className="mt-2 text-xs text-fg-muted">
            {t("studio.preview_placeholder_hint")}
          </p>
        </section>

        <section className="space-y-3">
          {draft.length === 0 ? (
            <p className="text-fg-muted">{t("studio.no_entities")}</p>
          ) : (
            draft.map((entity, entityIdx) => (
              <article
                key={entityIdx}
                className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4"
              >
                <header className="text-xs uppercase tracking-wide text-fg-muted">
                  {t("studio.entity_label")} {entityIdx + 1}
                </header>
                <div className="space-y-2">
                  {Object.entries(entity).map(([key, value]) => (
                    <FieldRow
                      key={key}
                      fieldName={key}
                      value={value}
                      onChange={(v) => updateField(entityIdx, key, v)}
                    />
                  ))}
                </div>
              </article>
            ))
          )}
        </section>
      </div>
    </main>
    </>
  );
}

function FieldRow({
  fieldName,
  value,
  onChange,
}: {
  fieldName: string;
  value: unknown;
  onChange: (next: string) => void;
}) {
  const display =
    value === null || value === undefined
      ? ""
      : typeof value === "string"
        ? value
        : JSON.stringify(value);

  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-mono text-xs text-fg-muted">{fieldName}</span>
      <Input
        value={display}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
