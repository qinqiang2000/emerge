import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/Table";
import { useT } from "@/i18n/useT";
import { isProjectPublished, useProjects, type Project } from "@/stores/projects";

function PublishedBadge({ project }: { project: Project }) {
  const t = useT();
  if (isProjectPublished(project)) {
    return <Badge tone="accent">{t("projects.published_badge")}</Badge>;
  }
  return <Badge tone="muted">{t("projects.draft_badge")}</Badge>;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString();
}

export function ProjectListPage() {
  const t = useT();
  const navigate = useNavigate();
  const rows = useProjects((s) => s.rows);
  const loading = useProjects((s) => s.loading);
  const load = useProjects((s) => s.load);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto max-w-5xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-fg-primary">
          {t("projects.title")}
        </h1>
        <Button onClick={() => navigate("/projects/new")}>
          {t("projects.create_button")}
        </Button>
      </header>

      {loading && rows.length === 0 ? (
        <p className="text-fg-muted">{t("projects.list_loading")}</p>
      ) : rows.length === 0 ? (
        <p className="text-fg-muted">{t("projects.list_empty")}</p>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>{t("projects.col_name")}</TH>
              <TH>{t("projects.col_status")}</TH>
              <TH>{t("projects.col_api_code")}</TH>
              <TH>{t("projects.col_created_at")}</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((p) => (
              <TR key={p.id} className="cursor-pointer hover:bg-bg-muted">
                <TD>
                  <Link
                    to={`/projects/${p.id}`}
                    className="text-fg-primary hover:text-accent-primary"
                  >
                    {p.name}
                  </Link>
                </TD>
                <TD>
                  <PublishedBadge project={p} />
                </TD>
                <TD className="font-mono text-xs text-fg-muted">
                  {p.api_code ?? "—"}
                </TD>
                <TD className="text-fg-muted">{formatDate(p.created_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </main>
  );
}
