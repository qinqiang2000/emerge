import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/Badge";
import { useT } from "@/i18n/useT";
import { useReadiness } from "@/stores/readiness";
import type {
  APIReadinessOut,
  EvidenceCoverage,
  QualityEstimate,
  RegressionHealth,
  RiskyField,
  SchemaMaturity,
} from "@/types/readiness";

const RISKY_TOP_N = 5;

function pct(x: number): number {
  return Math.round(x * 100);
}

function humaniseSlug(slug: string): string {
  if (!slug) return slug;
  const spaced = slug.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function ReadinessPanel({ projectId }: { projectId: number }) {
  const t = useT();
  const data = useReadiness((s) => s.data);
  const loading = useReadiness((s) => s.loading);
  const error = useReadiness((s) => s.error);
  const load = useReadiness((s) => s.load);

  useEffect(() => {
    if (Number.isFinite(projectId)) void load(projectId);
  }, [projectId, load]);

  if (error) {
    return (
      <section
        data-testid="readiness-panel"
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
        data-testid="readiness-panel"
        className="rounded-md border border-border-default bg-bg-elevated p-4"
      >
        <p className="text-sm text-fg-muted">{t("readiness.loading")}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section
        data-testid="readiness-panel"
        className="rounded-md border border-border-default bg-bg-elevated p-4"
      >
        <p className="text-sm text-fg-muted">{t("readiness.empty")}</p>
      </section>
    );
  }

  return <ReadinessBody data={data} />;
}

function ReadinessBody({ data }: { data: APIReadinessOut }) {
  const t = useT();
  const noProductionFeedback =
    data.regression_health.counterexamples_total === 0;
  return (
    <section
      data-testid="readiness-panel"
      className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <header>
        <h2 className="text-sm font-semibold text-fg-primary">
          {t("readiness.title")}
        </h2>
      </header>
      <dl className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
        <QualityRow q={data.quality_estimate} />
        <EvidenceRow e={data.evidence_coverage} />
        <MaturityRow m={data.schema_maturity} />
        <RegressionRow r={data.regression_health} />
      </dl>
      <RiskyFieldsRow
        risky={data.risky_fields}
        observationCount={data.quality_estimate.observation_count}
      />
      {noProductionFeedback ? (
        <p
          data-testid="readiness-no-feedback"
          className="rounded-sm border border-border-default bg-bg-muted p-2 text-xs text-fg-muted"
        >
          {t("readiness.no_feedback_callout")}
        </p>
      ) : null}
      <BlockersRow blockers={data.publish_blockers} />
      <WarningsRow warnings={data.warnings} />
    </section>
  );
}

function QualityRow({ q }: { q: QualityEstimate }) {
  const t = useT();
  // With zero judge observations the score is just the Beta prior — surfacing
  // it as a number falsely implies the model has been measured. Show "no
  // signal" copy until the first verdict lands.
  const hasSignal = q.observation_count > 0;
  return (
    <div data-testid="readiness-quality" className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-fg-muted">
        {t("readiness.quality_label")}
      </dt>
      <dd className="text-fg-primary">
        {hasSignal ? (
          <span>
            {t("readiness.quality_value", {
              point: pct(q.judge_precision),
              half: pct(Math.max(0, (q.ci_high - q.ci_low) / 2)),
            })}
          </span>
        ) : (
          <span className="text-fg-muted">{t("readiness.quality_no_signal")}</span>
        )}{" "}
        <span className="text-xs text-fg-muted">
          {t("readiness.quality_meta", {
            obs: q.observation_count,
            vibe: q.vibe_check_size,
          })}
        </span>
      </dd>
    </div>
  );
}

function EvidenceRow({ e }: { e: EvidenceCoverage }) {
  const t = useT();
  return (
    <div data-testid="readiness-evidence" className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-fg-muted">
        {t("readiness.evidence_label")}
      </dt>
      <dd className="text-fg-primary">
        <span>
          {t("readiness.evidence_value", {
            docs: e.annotated_docs,
            entities: e.annotated_entities,
            fields: e.annotated_fields,
          })}
        </span>{" "}
        <span className="text-xs text-fg-muted">
          {t("readiness.evidence_coverage", {
            ratio: pct(e.field_evidence_coverage_ratio),
          })}
        </span>
      </dd>
    </div>
  );
}

function MaturityRow({ m }: { m: SchemaMaturity }) {
  const t = useT();
  const { i18n } = useTranslation();
  const key = `readiness.maturity.${m.status}`;
  // unknown statuses must not leak the raw slug — fall back to humanised form.
  let label: string;
  if (i18n.exists(key)) {
    label = t(key);
  } else {
    if (typeof console !== "undefined") {
      console.warn(`[ReadinessPanel] unknown maturity status: ${m.status}`);
    }
    label = humaniseSlug(m.status);
  }
  return (
    <div data-testid="readiness-maturity" className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-fg-muted">
        {t("readiness.maturity_label")}
      </dt>
      <dd className="text-fg-primary">
        <span>{label}</span>{" "}
        <span className="text-xs text-fg-muted">
          {t("readiness.maturity_breaking_changes", {
            count: m.recent_schema_breaking_changes,
          })}
        </span>
      </dd>
    </div>
  );
}

function RegressionRow({ r }: { r: RegressionHealth }) {
  const t = useT();
  const total = r.counterexamples_total;
  if (total === 0) {
    return (
      <div data-testid="readiness-regression" className="flex flex-col gap-0.5">
        <dt className="text-xs uppercase tracking-wide text-fg-muted">
          {t("readiness.regression_label")}
        </dt>
        <dd className="text-fg-muted">{t("readiness.regression_no_feedback")}</dd>
      </div>
    );
  }
  // Only render the "passing N/total" line when the backend has actually
  // measured it (status is passing or failing). For status="unknown" the
  // component is a fallback constant — pretending it's a measurement
  // contradicts the "not yet computed" status line right below it.
  const measured = r.status === "passing" || r.status === "failing";
  const component = r.counterexample_component;
  const passing =
    measured && component !== null && component !== undefined
      ? Math.round(component * total)
      : null;
  const statusToneClass =
    r.status === "failing"
      ? "text-status-error"
      : r.status === "passing"
      ? "text-status-success"
      : "text-fg-muted";
  return (
    <div data-testid="readiness-regression" className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-fg-muted">
        {t("readiness.regression_label")}
      </dt>
      <dd className="text-fg-primary">
        {passing === null ? null : (
          <>
            <span>
              {t("readiness.regression_passing", { passing, total })}
            </span>{" "}
          </>
        )}
        <span
          data-testid="readiness-regression-status"
          className={`text-xs ${statusToneClass}`}
        >
          {t(`readiness.regression_status_${r.status}`)}
        </span>
      </dd>
    </div>
  );
}

function RiskyFieldsRow({
  risky,
  observationCount,
}: {
  risky: RiskyField[];
  observationCount: number;
}) {
  const t = useT();
  const sorted = [...risky].sort((a, b) => b.count - a.count);
  const top = sorted.slice(0, RISKY_TOP_N);
  const overflow = Math.max(0, sorted.length - RISKY_TOP_N);
  // Without any judge observations, an empty risky list isn't an "all clear"
  // — it's no signal at all. Differentiate so the panel doesn't read as
  // false reassurance on a fresh project.
  const emptyKey =
    observationCount === 0 ? "readiness.risky_no_signal" : "readiness.risky_empty";
  return (
    <div data-testid="readiness-risky" className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-fg-muted">
        {t("readiness.risky_label")}
      </span>
      {top.length === 0 ? (
        <span className="text-xs text-fg-muted">{t(emptyKey)}</span>
      ) : (
        <ul className="flex flex-wrap items-center gap-2">
          {top.map((f) => (
            <li key={f.field_name}>
              <Badge tone="warning">
                <span className="font-mono">{f.field_name}</span>
                <span className="ml-1 text-xs">({f.count})</span>
              </Badge>
            </li>
          ))}
          {overflow > 0 ? (
            <li className="text-xs text-fg-muted">
              {t("readiness.risky_more", { count: overflow })}
            </li>
          ) : null}
        </ul>
      )}
    </div>
  );
}

function BlockersRow({ blockers }: { blockers: string[] }) {
  const t = useT();
  const { i18n } = useTranslation();
  if (blockers.length === 0) return null;
  return (
    <div
      data-testid="readiness-blockers"
      className="flex flex-col gap-1 rounded-sm border border-status-error/40 bg-bg-muted p-2"
    >
      <span className="text-xs uppercase tracking-wide text-status-error">
        {t("readiness.blockers_label")}
      </span>
      <ul className="space-y-1">
        {blockers.map((slug) => (
          <li key={slug} className="text-sm text-fg-primary">
            {resolveSlug(slug, "blocker", t, i18n)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function WarningsRow({ warnings }: { warnings: string[] }) {
  const t = useT();
  const { i18n } = useTranslation();
  if (warnings.length === 0) return null;
  return (
    <div
      data-testid="readiness-warnings"
      className="flex flex-col gap-1 rounded-sm border border-status-warning/40 bg-bg-muted p-2"
    >
      <span className="text-xs uppercase tracking-wide text-status-warning">
        {t("readiness.warnings_label")}
      </span>
      <ul className="space-y-1">
        {warnings.map((slug) => (
          <li key={slug} className="text-sm text-fg-primary">
            {resolveSlug(slug, "warning", t, i18n)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function resolveSlug(
  slug: string,
  kind: "blocker" | "warning",
  t: (k: string) => string,
  i18n: { exists: (k: string) => boolean },
): string {
  // Single source of truth: if en.json has the key, use it; otherwise
  // humanise + warn. Keeping a hand-maintained slug whitelist on top of
  // i18n.exists adds drift risk without real safety.
  const key = `errors.readiness.${slug}`;
  if (i18n.exists(key)) return t(key);
  if (typeof console !== "undefined") {
    console.warn(`[ReadinessPanel] missing i18n key for ${kind}: ${slug}`);
  }
  return humaniseSlug(slug);
}
