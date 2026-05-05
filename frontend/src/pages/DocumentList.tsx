import { useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";
import { ReadinessPanel } from "@/components/ReadinessPanel";
import { Button } from "@/components/ui/Button";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/Table";
import { useT } from "@/i18n/useT";
import { useDocuments } from "@/stores/documents";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export function DocumentListPage() {
  const t = useT();
  const navigate = useNavigate();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const rows = useDocuments((s) => s.rows);
  const loading = useDocuments((s) => s.loading);
  const uploading = useDocuments((s) => s.uploading);
  const extracting = useDocuments((s) => s.extracting);
  const error = useDocuments((s) => s.error);
  const load = useDocuments((s) => s.load);
  const upload = useDocuments((s) => s.upload);
  const triggerExtract = useDocuments((s) => s.triggerExtract);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (Number.isFinite(projectId)) void load(projectId);
  }, [load, projectId]);

  function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) void upload(projectId, files);
    e.target.value = "";
  }

  return (
    <>
      {Number.isFinite(projectId) ? (
        <ProjectSubNav projectId={projectId} />
      ) : null}
      <main className="mx-auto max-w-5xl space-y-4 p-6">
      {Number.isFinite(projectId) ? (
        <ReadinessPanel projectId={projectId} />
      ) : null}
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-fg-primary">
          {t("documents.title")}
        </h1>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            data-testid="document-upload-input"
            className="hidden"
            onChange={handleFiles}
            accept="application/pdf,image/*"
          />
          <Button
            variant="secondary"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? t("common.loading") : t("documents.upload")}
          </Button>
          <Button
            disabled={extracting || rows.length === 0}
            onClick={() => void triggerExtract(projectId)}
          >
            {extracting ? t("common.loading") : t("documents.extract_remaining")}
          </Button>
        </div>
      </header>

      {error ? (
        <p role="alert" className="text-sm text-status-error">
          {t(error)}
        </p>
      ) : null}

      {loading && rows.length === 0 ? (
        <p className="text-fg-muted">{t("documents.list_loading")}</p>
      ) : rows.length === 0 ? (
        <p className="text-fg-muted">{t("documents.list_empty")}</p>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>{t("documents.filename")}</TH>
              <TH>{t("documents.status")}</TH>
              <TH>{t("documents.last_modified")}</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((d) => (
              <TR
                key={d.id}
                className="cursor-pointer hover:bg-bg-muted"
                onClick={() => navigate(`/projects/${projectId}/studio/${d.id}`)}
              >
                <TD className="text-fg-primary">{d.filename}</TD>
                <TD className="text-fg-muted">{d.status}</TD>
                <TD className="text-fg-muted">{formatDate(d.created_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      </main>
    </>
  );
}
