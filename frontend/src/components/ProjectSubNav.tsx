import { Link, useMatch } from "react-router-dom";

import { useT } from "@/i18n/useT";
import { cn } from "@/lib/cn";

export function ProjectSubNav({ projectId }: { projectId: number }) {
  const t = useT();
  // Match explicit legacy aliases so redirected URLs still show the right tab
  // while the navigation targets point at product-facing routes.
  const onRules = useMatch("/projects/:id/rules") !== null;
  const onLegacyRules = useMatch("/projects/:id/schema") !== null;
  const onApi = useMatch("/projects/:id/api") !== null;
  const onLegacyApi = useMatch("/projects/:id/api-console") !== null;
  const onExamples = useMatch("/projects/:id/examples") !== null;
  const onLegacyExamples = useMatch("/projects/:id/review") !== null;
  const onDocuments =
    !onRules &&
    !onLegacyRules &&
    !onApi &&
    !onLegacyApi &&
    !onExamples &&
    !onLegacyExamples;

  return (
    <nav className="border-b border-border-default">
      <ul className="mx-auto flex max-w-6xl gap-4 px-6">
        <NavTab
          to={`/projects/${projectId}`}
          active={onDocuments}
          label={t("nav.documents")}
        />
        <NavTab
          to={`/projects/${projectId}/examples`}
          active={onExamples || onLegacyExamples}
          label={t("nav.review_examples")}
        />
        <NavTab
          to={`/projects/${projectId}/rules`}
          active={onRules || onLegacyRules}
          label={t("nav.extraction_rules")}
        />
        <NavTab
          to={`/projects/${projectId}/api`}
          active={onApi || onLegacyApi}
          label={t("nav.api")}
        />
      </ul>
    </nav>
  );
}

function NavTab({
  to,
  active,
  label,
}: {
  to: string;
  active: boolean;
  label: string;
}) {
  return (
    <li>
      <Link
        to={to}
        aria-current={active ? "page" : undefined}
        className={cn(
          "inline-flex items-center border-b-2 px-2 py-2 text-sm font-medium transition-colors",
          active
            ? "border-accent-primary text-fg-primary"
            : "border-transparent text-fg-muted hover:text-fg-primary",
        )}
      >
        {label}
      </Link>
    </li>
  );
}
