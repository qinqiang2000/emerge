import { useEffect, useId } from "react";
import { useParams } from "react-router-dom";

import {
  ConfidenceChip,
  FieldEvidencePopover,
} from "@/components/FieldEvidencePopover";
import { FlagFieldMenu } from "@/components/FlagFieldMenu";
import { ProjectSubNav } from "@/components/ProjectSubNav";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { useT } from "@/i18n/useT";
import {
  useStudio,
  type DocumentDetail,
  type EntityOutput,
} from "@/stores/studio";
import type {
  ConfidenceVerdict,
  PerFieldEvidence,
} from "@/types/studio";

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
  const toast = useToast();

  useEffect(() => {
    if (Number.isFinite(projectId) && Number.isFinite(documentId)) {
      void load(projectId, documentId);
    }
  }, [load, projectId, documentId]);

  const dirty = isDirty(draft, baselineOutput(doc));

  async function handleSave() {
    // Dogfood follow-up #4: surface a "Saved" pill on success. The store's
    // `save` swallows network errors into `error` rather than throwing, so
    // re-read the latest store state to decide whether to toast. `save`
    // resets `error` to null on entry, so success means error is null.
    await save(projectId);
    if (useStudio.getState().error === null) {
      toast.show(t("common.saved"));
    }
  }

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
            {doc.mime_type} · {doc.status}
          </p>
          <p className="mt-1 max-w-2xl text-xs text-fg-muted">
            {t("studio.save_hint")}
          </p>
        </div>
        <Button
          disabled={!dirty || saving}
          onClick={() => void handleSave()}
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
          <p className="text-xs text-fg-muted">{doc.mime_type}</p>
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
                      entityIndex={entityIdx}
                      fieldName={key}
                      value={value}
                      projectId={projectId}
                      verdict={
                        doc.latest_prediction?.per_field_confidence?.[
                          String(entityIdx)
                        ]?.[key]
                      }
                      evidenceMap={doc.latest_prediction?.per_field_evidence ?? null}
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
  entityIndex,
  fieldName,
  value,
  projectId,
  verdict,
  evidenceMap,
  onChange,
}: {
  entityIndex: number;
  fieldName: string;
  value: unknown;
  projectId: number;
  verdict: ConfidenceVerdict | null | undefined;
  evidenceMap: PerFieldEvidence | null | undefined;
  onChange: (next: string) => void;
}) {
  // Dogfood follow-up #3: editing the textbox IS the correction; the
  // ⋮ menu only handles flag-without-correcting (e.g. unparseable, N/A).
  const labelId = useId();
  const display =
    value === null || value === undefined
      ? ""
      : typeof value === "string"
        ? value
        : JSON.stringify(value);

  return (
    <div className="flex flex-col gap-1 text-sm">
      <div className="flex items-center gap-2">
        <span id={labelId} className="font-mono text-xs text-fg-muted">
          {fieldName}
        </span>
        <ConfidenceChip verdict={verdict} />
        <FieldEvidencePopover
          entityIndex={entityIndex}
          fieldName={fieldName}
          evidenceMap={evidenceMap}
        />
        <FlagFieldMenu
          projectId={projectId}
          entityIndex={entityIndex}
          fieldName={fieldName}
        />
      </div>
      <Input
        aria-labelledby={labelId}
        value={display}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
