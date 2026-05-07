import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/useT";

export type ProjectJourneyStepperProps = {
  hasDocuments: boolean;
  hasDrafts: boolean;
  reviewedDocs: number;
  hasImproveProposal: boolean;
  isPublished: boolean;
  canPublish: boolean;
  onExtract: () => void;
  onReview: () => void;
  onImprove: () => void;
  onPublish: () => void;
};

export function ProjectJourneyStepper({
  hasDocuments,
  hasDrafts,
  reviewedDocs,
  hasImproveProposal,
  isPublished,
  canPublish,
  onExtract,
  onReview,
  onImprove,
  onPublish,
}: ProjectJourneyStepperProps) {
  const t = useT();
  const steps = [
    {
      title: t("project_journey.extract_title"),
      meta: hasDrafts
        ? t("project_journey.extract_ready")
        : t("project_journey.extract_hint"),
      action: t("project_journey.extract_action"),
      disabled: !hasDocuments,
      active: hasDocuments && !hasDrafts,
      complete: hasDrafts,
      onClick: onExtract,
    },
    {
      title: t("project_journey.review_title"),
      meta:
        reviewedDocs > 0
          ? t("project_journey.review_ready", { count: reviewedDocs })
          : t("project_journey.review_hint"),
      action: t("project_journey.review_action"),
      disabled: !hasDrafts,
      active: hasDrafts && reviewedDocs === 0,
      complete: reviewedDocs > 0,
      onClick: onReview,
    },
    {
      title: t("project_journey.improve_title"),
      meta: hasImproveProposal
        ? t("project_journey.improve_ready")
        : t("project_journey.improve_hint"),
      action: t("project_journey.improve_action"),
      disabled: reviewedDocs <= 0,
      active: reviewedDocs > 0 && !hasImproveProposal,
      complete: hasImproveProposal,
      onClick: onImprove,
    },
    {
      title: t("project_journey.publish_title"),
      meta: isPublished
        ? t("project_journey.publish_ready")
        : t("project_journey.publish_hint"),
      action: t("project_journey.publish_action"),
      disabled: !(canPublish || isPublished),
      active: canPublish && !isPublished,
      complete: isPublished,
      onClick: onPublish,
    },
  ];

  return (
    <section
      data-testid="project-journey-stepper"
      className="rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <ol className="grid gap-3 md:grid-cols-4">
        {steps.map((step, index) => (
          <li
            key={step.title}
            className="flex min-w-0 flex-col gap-2 rounded-sm border border-border-default bg-bg-muted p-3"
          >
            <div className="flex items-start gap-2">
              <span
                aria-hidden
                className={
                  step.complete
                    ? "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-status-success text-xs font-semibold text-fg-inverse"
                    : step.active
                    ? "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-primary text-xs font-semibold text-accent-primary-fg"
                    : "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border-default text-xs font-semibold text-fg-muted"
                }
              >
                {index + 1}
              </span>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-fg-primary">
                  {step.title}
                </h2>
                <p className="text-xs text-fg-muted">{step.meta}</p>
              </div>
            </div>
            <Button
              size="sm"
              variant={step.complete ? "secondary" : "primary"}
              disabled={step.disabled}
              aria-label={step.title}
              onClick={step.onClick}
              className="mt-auto w-full"
            >
              {step.action}
            </Button>
          </li>
        ))}
      </ol>
    </section>
  );
}
