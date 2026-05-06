import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiKeyRevealModal } from "@/components/ApiKeyRevealModal";
import { FeedbackTestForm } from "@/components/FeedbackTestForm";
import { ProjectSubNav } from "@/components/ProjectSubNav";
import { ReadinessPanel } from "@/components/ReadinessPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/Table";
import { useT } from "@/i18n/useT";
import {
  isProjectPublished,
  useProjects,
  type ApiKeyOnce,
  type ContractDiff,
  type ProjectVersionMeta,
} from "@/stores/projects";

export function ApiConsolePage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  const project = useProjects((s) => s.rows.find((p) => p.id === projectId));
  const contractDiff = useProjects((s) => s.contractDiff);
  const versions = useProjects((s) => s.versions);
  const apiKeys = useProjects((s) => s.apiKeys);
  const loading = useProjects((s) => s.loading);
  const error = useProjects((s) => s.error);

  const loadOne = useProjects((s) => s.loadOne);
  const loadVersions = useProjects((s) => s.loadVersions);
  const loadContractDiff = useProjects((s) => s.loadContractDiff);
  const listKeys = useProjects((s) => s.listKeys);
  const createKey = useProjects((s) => s.createKey);
  const revokeKey = useProjects((s) => s.revokeKey);
  const publish = useProjects((s) => s.publish);
  const unpublish = useProjects((s) => s.unpublish);
  const rollback = useProjects((s) => s.rollback);

  const [activateApiCode, setActivateApiCode] = useState("");
  const [renameApiCode, setRenameApiCode] = useState("");
  const [rollbackTarget, setRollbackTarget] = useState<string>("");
  const [revealedKey, setRevealedKey] = useState<ApiKeyOnce | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(projectId)) return;
    void loadOne(projectId);
    void loadVersions(projectId);
    void loadContractDiff(projectId);
    void listKeys(projectId);
  }, [projectId, loadOne, loadVersions, loadContractDiff, listKeys]);

  useEffect(() => {
    if (project?.api_code) {
      setActivateApiCode(project.api_code);
      setRenameApiCode(project.api_code);
    }
  }, [project?.api_code]);

  const subnav = Number.isFinite(projectId) ? (
    <ProjectSubNav projectId={projectId} />
  ) : null;

  if (loading && !project) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-5xl p-6">
          <p className="text-fg-muted">{t("api_console.loading")}</p>
        </main>
      </>
    );
  }

  if (!project) {
    return (
      <>
        {subnav}
        <main className="mx-auto max-w-5xl p-6">
          <p className="text-fg-muted">{t("api_console.empty")}</p>
        </main>
      </>
    );
  }

  const activeVersion = versions.find((v) => v.id === project.active_version_id);
  const publishedVersion = versions.find(
    (v) => v.id === project.published_version_id,
  );
  const activeIsLocked = activeVersion?.locked ?? false;
  const isPublished = isProjectPublished(project);

  const lockedNonPublishedVersions = versions.filter(
    (v) => v.locked && v.id !== project.published_version_id,
  );

  async function handleActivate() {
    if (!project || !activeIsLocked) return;
    setActionError(null);
    try {
      await publish(
        projectId,
        activateApiCode,
        project.active_version_id ?? undefined,
      );
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  async function handleRename() {
    if (!project || !project.published_version_id) return;
    setActionError(null);
    try {
      // Spec §7.2: rename of an already-published project must keep
      // published_version_id unchanged. Pass it explicitly so the backend
      // does not default to active_version_id.
      await publish(projectId, renameApiCode, project.published_version_id);
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  async function handleRollback() {
    if (!rollbackTarget) return;
    setActionError(null);
    try {
      await rollback(projectId, Number(rollbackTarget));
      setRollbackTarget("");
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  async function handleUnpublish() {
    setActionError(null);
    try {
      await unpublish(projectId);
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  async function handleCreateKey() {
    setActionError(null);
    try {
      const once = await createKey(projectId, "default");
      setRevealedKey(once);
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  async function handleRevoke(keyId: number) {
    setActionError(null);
    try {
      await revokeKey(projectId, keyId);
    } catch (e) {
      setActionError(emergeMessage(e));
    }
  }

  return (
    <>
      {subnav}
      <main className="mx-auto max-w-5xl space-y-6 p-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-fg-primary">
              {t("api_console.title")}
            </h1>
            <p className="text-xs text-fg-muted">{project.name}</p>
          </div>
          {isPublished ? (
            <Badge tone="success">{t("projects.published_badge")}</Badge>
          ) : (
            <Badge tone="muted">{t("projects.draft_badge")}</Badge>
          )}
        </header>

        {(error || actionError) && (
          <p role="alert" className="text-sm text-status-error">
            {actionError ?? (error ? t(error) : null)}
          </p>
        )}

        <ReadinessPanel projectId={projectId} />

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <VersionPointerCard
            label={t("api_console.production_pointer")}
            sublabel={t("api_console.production_pointer_hint")}
            version={publishedVersion}
            activatedAt={project.api_published_at}
            testId="production-pointer"
          />
          <VersionPointerCard
            label={t("api_console.lab_pointer")}
            sublabel={t("api_console.lab_pointer_hint")}
            version={activeVersion}
            activatedAt={null}
            testId="lab-pointer"
          />
        </section>

        <ContractDiffSection diff={contractDiff} />

        <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
          <h2 className="text-sm font-semibold text-fg-primary">
            {t("api_console.activate_section")}
          </h2>
          <p className="text-xs text-fg-muted">
            {activeIsLocked
              ? t("api_console.activate_hint_locked")
              : t("api_console.activate_hint_unlocked")}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-fg-primary">
              <span>{t("api_console.api_code_label")}</span>
              <Input
                value={activateApiCode}
                onChange={(e) => setActivateApiCode(e.target.value)}
                placeholder={t("api_console.api_code_placeholder")}
                aria-label={t("api_console.activate_api_code_aria")}
              />
            </label>
            <Button
              disabled={!activeIsLocked || !activateApiCode}
              onClick={() => void handleActivate()}
            >
              {t("api_console.activate_button")}
            </Button>
          </div>
        </section>

        {isPublished ? (
          <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
            <h2 className="text-sm font-semibold text-fg-primary">
              {t("api_console.rename_section")}
            </h2>
            <p className="text-xs text-fg-muted">
              {t("api_console.rename_hint")}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 text-sm text-fg-primary">
                <span>{t("api_console.api_code_label")}</span>
                <Input
                  value={renameApiCode}
                  onChange={(e) => setRenameApiCode(e.target.value)}
                  aria-label={t("api_console.rename_api_code_aria")}
                />
              </label>
              <Button
                variant="secondary"
                disabled={!renameApiCode || renameApiCode === project.api_code}
                onClick={() => void handleRename()}
              >
                {t("api_console.rename_button")}
              </Button>
            </div>
          </section>
        ) : null}

        {isPublished && lockedNonPublishedVersions.length > 0 ? (
          <section className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4">
            <h2 className="text-sm font-semibold text-fg-primary">
              {t("api_console.rollback_section")}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={rollbackTarget}
                onChange={(e) => setRollbackTarget(e.target.value)}
                aria-label={t("api_console.rollback_select_aria")}
                className="rounded-md border border-border-default bg-bg-surface px-3 py-1.5 text-sm text-fg-primary"
              >
                <option value="">{t("api_console.rollback_select_placeholder")}</option>
                {lockedNonPublishedVersions.map((v) => (
                  <option key={v.id} value={String(v.id)}>
                    v{v.version_number}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                disabled={!rollbackTarget}
                onClick={() => void handleRollback()}
              >
                {t("api_console.rollback_button")}
              </Button>
            </div>
          </section>
        ) : null}

        {isPublished ? (
          <section className="space-y-2 rounded-md border border-status-error/40 bg-bg-elevated p-4">
            <h2 className="text-sm font-semibold text-status-error">
              {t("api_console.danger_section")}
            </h2>
            <p className="text-xs text-fg-muted">{t("api_console.unpublish_hint")}</p>
            <Button variant="danger" onClick={() => void handleUnpublish()}>
              {t("api_console.unpublish_button")}
            </Button>
          </section>
        ) : null}

        <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
          <header className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-fg-primary">
              {t("api_console.keys_section")}
            </h2>
            <Button onClick={() => void handleCreateKey()}>
              {t("api_console.create_key_button")}
            </Button>
          </header>
          {apiKeys.length === 0 ? (
            <p className="text-sm text-fg-muted">{t("api_console.keys_empty")}</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>{t("api_console.key_prefix_col")}</TH>
                  <TH>{t("api_console.key_name_col")}</TH>
                  <TH>{t("api_console.key_last_used_col")}</TH>
                  <TH>{t("api_console.key_created_col")}</TH>
                  <TH aria-label={t("api_console.key_actions_col")} />
                </TR>
              </THead>
              <TBody>
                {apiKeys.map((k) => (
                  <TR key={k.id}>
                    <TD className="font-mono text-xs text-fg-primary">{k.prefix}</TD>
                    <TD className="text-fg-muted">{k.name}</TD>
                    <TD className="text-fg-muted">{k.last_used_at ?? "—"}</TD>
                    <TD className="text-fg-muted">{formatDate(k.created_at)}</TD>
                    <TD>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleRevoke(k.id)}
                      >
                        {t("api_console.revoke_button")}
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </section>

        <SnippetsPanel apiCode={project.api_code} />

        <FeedbackExamplePanel
          apiCode={project.api_code}
          hasApiKey={apiKeys.length > 0}
        />
      </main>

      {revealedKey ? (
        <ApiKeyRevealModal
          open
          apiKey={revealedKey}
          onConfirmDismiss={() => setRevealedKey(null)}
        />
      ) : null}
    </>
  );
}

function emergeMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function VersionPointerCard({
  label,
  sublabel,
  version,
  activatedAt,
  testId,
}: {
  label: string;
  sublabel: string;
  version: ProjectVersionMeta | undefined;
  activatedAt: string | null;
  testId: string;
}) {
  const t = useT();
  return (
    <article
      data-testid={testId}
      className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <header>
        <h3 className="text-sm font-semibold text-fg-primary">{label}</h3>
        <p className="text-xs text-fg-muted">{sublabel}</p>
      </header>
      {version ? (
        <div className="space-y-1">
          <p className="font-mono text-sm text-fg-primary">v{version.version_number}</p>
          <p className="text-xs text-fg-muted">
            {version.locked
              ? t("api_console.pointer_locked")
              : t("api_console.pointer_unlocked")}
          </p>
          {activatedAt ? (
            <p className="text-xs text-fg-muted">
              {t("api_console.pointer_activated_at")}: {formatDate(activatedAt)}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-fg-muted">{t("api_console.pointer_empty")}</p>
      )}
    </article>
  );
}

function ContractDiffSection({ diff }: { diff: ContractDiff | null }) {
  const t = useT();
  if (!diff) return null;
  return (
    <section className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4">
      <h2 className="text-sm font-semibold text-fg-primary">
        {t("api_console.diff_section")}
      </h2>
      {diff.has_breaking_changes ? (
        <p className="text-sm text-status-error">
          {t("api_console.diff_breaking_warning")}
        </p>
      ) : null}
      {diff.items.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("api_console.diff_empty")}</p>
      ) : (
        <ul className="space-y-1">
          {diff.items.map((item, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <Badge tone={item.severity === "breaking" ? "error" : "success"}>
                {item.severity === "breaking"
                  ? t("api_console.diff_breaking_label")
                  : t("api_console.diff_non_breaking_label")}
              </Badge>
              <span className="font-mono text-xs text-fg-muted">{item.kind}</span>
              {item.field_name ? (
                <span className="font-mono text-xs text-fg-primary">
                  {item.field_name}
                </span>
              ) : null}
              <span className="text-fg-primary">{item.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SnippetsPanel({ apiCode }: { apiCode: string | null }) {
  const t = useT();
  const code = apiCode ?? "your-api-code";
  const curl = useMemo(
    () =>
      `curl -X POST "https://api.emerge.dev/extract/${code}" \\\n  -H "X-Api-Key: $EMERGE_API_KEY" \\\n  -F "file=@invoice.pdf"\n# {request_id, prediction_id, project_version_id, output: {entities: [...]}}`,
    [code],
  );
  const py = useMemo(
    () =>
      `import os, requests\nresp = requests.post(\n  f"https://api.emerge.dev/extract/${code}",\n  headers={"X-Api-Key": os.environ["EMERGE_API_KEY"]},\n  files={"file": open("invoice.pdf", "rb")},\n).json()\nentities = resp["output"]["entities"]\nrequest_id = resp["request_id"]   # echo back as feedback's request_id`,
    [code],
  );
  return (
    <section className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4">
      <h2 className="text-sm font-semibold text-fg-primary">
        {t("api_console.snippets_section")}
      </h2>
      <p className="text-xs text-fg-muted">{t("api_console.snippets_hint")}</p>
      <Snippet label="curl" body={curl} />
      <Snippet label="python" body={py} />
    </section>
  );
}

function Snippet({ label, body }: { label: string; body: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-fg-muted">{label}</p>
      <pre className="mt-1 overflow-x-auto rounded-sm border border-border-default bg-bg-muted p-2 font-mono text-xs text-fg-primary">
        <code>{body}</code>
      </pre>
    </div>
  );
}

function FeedbackExamplePanel({
  apiCode,
  hasApiKey,
}: {
  apiCode: string | null;
  hasApiKey: boolean;
}) {
  const t = useT();
  const example = `{\n  "request_id": 12345,\n  "corrections": [\n    {\n      "entity_index": 0,\n      "field_path": "total",\n      "correct_value": "1234"\n    }\n  ],\n  "issue_type": "wrong_value"\n}`;
  return (
    <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
      <details>
        <summary className="cursor-pointer text-sm font-semibold text-fg-primary">
          {t("api_console.feedback_example_title")}
        </summary>
        <p className="mt-2 text-xs text-fg-muted">
          {t("api_console.feedback_example_hint")}
        </p>
        <pre className="mt-2 overflow-x-auto rounded-sm border border-border-default bg-bg-muted p-2 font-mono text-xs text-fg-primary">
          <code>{example}</code>
        </pre>
      </details>

      <div className="space-y-2 border-t border-border-default pt-3">
        <h3 className="text-sm font-semibold text-fg-primary">
          {t("feedback.section_title")}
        </h3>
        <p className="text-xs text-fg-muted">{t("feedback.section_hint")}</p>
        {hasApiKey && apiCode ? (
          <FeedbackTestForm apiCode={apiCode} />
        ) : (
          <p className="text-xs text-fg-muted">{t("feedback.key_required")}</p>
        )}
      </div>
    </section>
  );
}

