import { useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";

export function ImproveExtractorPage() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);

  return (
    <>
      {Number.isFinite(projectId) ? (
        <ProjectSubNav projectId={projectId} />
      ) : null}
      <main className="mx-auto max-w-4xl p-6">
        <h1 className="text-xl font-semibold text-fg-primary">
          Improve extractor
        </h1>
      </main>
    </>
  );
}
