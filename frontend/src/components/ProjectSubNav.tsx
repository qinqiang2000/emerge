import { Link, useLocation } from "react-router-dom";

import { useT } from "@/i18n/useT";
import { cn } from "@/lib/cn";

export function ProjectSubNav({ projectId }: { projectId: number }) {
  const t = useT();
  const { pathname } = useLocation();
  const onSchema = pathname.endsWith(`/projects/${projectId}/schema`);
  const onApi = pathname.endsWith(`/projects/${projectId}/api-console`);
  const onDocuments = !onSchema && !onApi;

  return (
    <nav className="border-b border-border-default">
      <ul className="mx-auto flex max-w-6xl gap-4 px-6">
        <NavTab
          to={`/projects/${projectId}`}
          active={onDocuments}
          label={t("nav.documents")}
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
