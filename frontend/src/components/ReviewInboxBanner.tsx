import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/useT";
import { useReview } from "@/stores/review";
import type { ReviewItemOut, ReviewQueueOut } from "@/types/review";

export function ReviewInboxBanner({ projectId }: { projectId: number }) {
  const t = useT();
  const navigate = useNavigate();
  const data = useReview((s) => s.data);
  const loading = useReview((s) => s.loading);
  const error = useReview((s) => s.error);
  const load = useReview((s) => s.load);

  useEffect(() => {
    if (Number.isFinite(projectId)) void load(projectId);
  }, [projectId, load]);

  if (error) {
    return (
      <section
        data-testid="review-inbox-banner"
        className="rounded-md border border-status-error/40 bg-bg-elevated p-4"
      >
        <p role="alert" className="text-sm text-status-error">
          {t(error)}
        </p>
      </section>
    );
  }

  if (loading && !data) {
    return (
      <section
        data-testid="review-inbox-banner"
        className="rounded-md border border-border-default bg-bg-elevated p-4"
      >
        <p className="text-sm text-fg-muted">{t("review.loading")}</p>
      </section>
    );
  }

  if (!data) return null;

  return <ReviewInboxBannerBody data={data} projectId={projectId} navigate={navigate} />;
}

function ReviewInboxBannerBody({
  data,
  projectId,
  navigate,
}: {
  data: ReviewQueueOut;
  projectId: number;
  navigate: ReturnType<typeof useNavigate>;
}) {
  const t = useT();
  const next: ReviewItemOut | null =
    data.required_review[0] ?? data.spot_check[0] ?? null;
  const queueEmpty = data.required_review.length === 0 && data.spot_check.length === 0;
  // Distinguish three empty states so the user knows which lever to pull:
  //   1. no docs at all → upload/extract path
  //   2. docs exist but no judge verdicts → run judge
  //   3. judge ran and everyone is clean → all caught up
  // Without an explicit `judged_count` from the backend we use the
  // spot-check sample as a proxy for "judge has run" — it's only populated
  // from up_only verdicts, so its presence implies at least one judge pass.
  const emptyKey =
    data.all.length === 0
      ? "review.empty_pool"
      : queueEmpty && data.spot_check.length === 0
      ? "review.needs_judge"
      : "review.all_caught_up";

  return (
    <section
      data-testid="review-inbox-banner"
      className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-fg-primary">
          {t("review.title")}
        </h2>
        <Button
          size="sm"
          disabled={next === null}
          onClick={() =>
            next
              ? navigate(`/projects/${projectId}/studio/${next.id}`)
              : undefined
          }
        >
          {t("review.review_next")}
        </Button>
      </header>

      <dl className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg-muted">
        <div className="flex items-center gap-1">
          <dt className="sr-only">{t("review.section_required")}</dt>
          <dd
            data-testid="review-required-count"
            className="text-fg-primary"
          >
            {t("review.required_count", { count: data.required_review.length })}
          </dd>
        </div>
        <span aria-hidden className="text-fg-muted">·</span>
        <div className="flex items-center gap-1">
          <dt className="sr-only">{t("review.section_spot_check")}</dt>
          <dd
            data-testid="review-spot-check-count"
            className="text-fg-primary"
          >
            {t("review.spot_check_count", { count: data.spot_check.length })}
          </dd>
        </div>
        <span aria-hidden className="text-fg-muted">·</span>
        <div className="flex items-center gap-1">
          <dt className="sr-only">{t("review.section_all")}</dt>
          <dd
            data-testid="review-all-count"
            className="text-fg-primary"
          >
            {t("review.all_count", { count: data.all.length })}
          </dd>
        </div>
      </dl>

      {queueEmpty ? (
        <p
          data-testid="review-all-caught-up"
          data-empty-state={emptyKey.split(".")[1]}
          className="rounded-sm border border-border-default bg-bg-muted p-2 text-xs text-fg-muted"
        >
          {t(emptyKey, { count: data.all.length })}
        </p>
      ) : null}
    </section>
  );
}
