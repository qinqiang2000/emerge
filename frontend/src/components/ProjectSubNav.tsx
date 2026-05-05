import { Link, useMatch } from "react-router-dom";

import { useT } from "@/i18n/useT";
import { cn } from "@/lib/cn";

export function ProjectSubNav({ projectId }: { projectId: number }) {
  const t = useT();
  // useMatch tolerates trailing slashes and nested children; pathname.endsWith
  // would silently flip every tab to inactive on `/projects/7/api-console/`.
  const onSchema = useMatch("/projects/:id/schema") !== null;
  const onApi = useMatch("/projects/:id/api-console") !== null;
  const onReview = useMatch("/projects/:id/review") !== null;
  const onDocuments = !onSchema && !onApi && !onReview;

  return (
    <nav className="border-b border-border-default">
      <ul className="mx-auto flex max-w-6xl gap-4 px-6">
        <NavTab
          to={`/projects/${projectId}`}
          active={onDocuments}
          label={t("nav.documents")}
        />
        <NavTab
          to={`/projects/${projectId}/review`}
          active={onReview}
          label={t("nav.review")}
        />
        <NavTab
          to={`/projects/${projectId}/schema`}
          active={onSchema}
          label={t("nav.schema")}
        />
        <NavTab
          to={`/projects/${projectId}/api-console`}
          active={onApi}
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
