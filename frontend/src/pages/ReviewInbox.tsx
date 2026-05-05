import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";
import { Badge } from "@/components/ui/Badge";
import { useT } from "@/i18n/useT";
import { useReview } from "@/stores/review";
import type { ReviewItemOut } from "@/types/review";

type SectionKey = "required" | "spot-check" | "all";

export function ReviewInboxPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const data = useReview((s) => s.data);
  const loading = useReview((s) => s.loading);
  const error = useReview((s) => s.error);
  const load = useReview((s) => s.load);

  useEffect(() => {
    if (Number.isFinite(projectId)) void load(projectId);
  }, [load, projectId]);

  return (
    <>
      {Number.isFinite(projectId) ? (
        <ProjectSubNav projectId={projectId} />
      ) : null}
      <main className="mx-auto max-w-5xl space-y-4 p-6">
        <header>
          <h1 className="text-xl font-semibold text-fg-primary">
            {t("review.page_title")}
          </h1>
        </header>

        {error ? (
          <p role="alert" className="text-sm text-status-error">
            {t(error)}
          </p>
        ) : null}

        {loading && !data ? (
          <p className="text-fg-muted">{t("review.loading")}</p>
        ) : null}

        {data ? (
          <div className="space-y-6">
            <ReviewSection
              kind="required"
              title={t("review.section_required")}
              hint={t("review.section_required_hint")}
              emptyCopy={t("review.section_required_empty")}
              rows={data.required_review}
              projectId={projectId}
            />
            <ReviewSection
              kind="spot-check"
              title={t("review.section_spot_check")}
              hint={t("review.section_spot_check_hint")}
              emptyCopy={t("review.section_spot_check_empty")}
              rows={data.spot_check}
              projectId={projectId}
            />
            <ReviewSection
              kind="all"
              title={t("review.section_all")}
              hint={t("review.section_all_hint")}
              emptyCopy={t("review.section_all_empty")}
              rows={data.all}
              projectId={projectId}
            />
          </div>
        ) : null}
      </main>
    </>
  );
}

function ReviewSection({
  kind,
  title,
  hint,
  emptyCopy,
  rows,
  projectId,
}: {
  kind: SectionKey;
  title: string;
  hint: string;
  emptyCopy: string;
  rows: ReviewItemOut[];
  projectId: number;
}) {
  const navigate = useNavigate();
  return (
    <section
      data-testid={`review-section-${kind}`}
      className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-fg-primary">{title}</h2>
        <span className="text-xs text-fg-muted">{rows.length}</span>
      </header>
      <p className="text-xs text-fg-muted">{hint}</p>
      {rows.length === 0 ? (
        <p className="rounded-sm border border-border-default bg-bg-muted p-2 text-xs text-fg-muted">
          {emptyCopy}
        </p>
      ) : (
        <ul className="space-y-1">
          {rows.map((row) => (
            <li
              key={row.id}
              data-testid={`review-row-${kind}-${row.id}`}
              role="button"
              tabIndex={0}
              className="flex cursor-pointer items-center justify-between gap-3 rounded-sm border border-border-default bg-bg-surface px-3 py-2 hover:bg-bg-muted"
              onClick={() => navigate(`/projects/${projectId}/studio/${row.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/projects/${projectId}/studio/${row.id}`);
                }
              }}
            >
              <span className="text-sm text-fg-primary">{row.filename}</span>
              {row.flagged_fields.length > 0 ? (
                <ul className="flex flex-wrap items-center gap-1">
                  {row.flagged_fields.map((field) => (
                    <li key={field}>
                      <Badge tone="warning">
                        <span className="font-mono">{field}</span>
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
