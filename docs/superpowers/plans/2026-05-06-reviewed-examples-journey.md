# Reviewed Examples Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe emerge's v1 UI from annotation/schema terminology into a guided reviewed-examples journey: Create project -> Upload docs -> Extract drafts -> Review examples -> Improve extractor -> Re-extract/check -> Publish API.

**Architecture:** Keep the existing backend model and safety invariants. The main change is frontend routing, navigation, copy, and one new Improve extractor page that composes existing auto-research/version endpoints. Documents becomes the project workbench with a journey stepper above the table.

**Tech Stack:** Vite + React 19 + TypeScript + Zustand + react-router 6 + Tailwind semantic tokens + Vitest/Testing Library + Playwright; backend remains FastAPI/SQLAlchemy and is touched only for optional improve-scorer wiring.

---

## Design Inputs

- Spec: `docs/superpowers/specs/2026-05-06-reviewed-examples-journey-design.md`
- Existing overall design: `docs/superpowers/specs/2026-05-02-overall-design.md`
- Current local demo: `docs/local-demo.md`
- Current frontend route shell: `frontend/src/App.tsx`
- Current project nav: `frontend/src/components/ProjectSubNav.tsx`
- Current pages: `DocumentList.tsx`, `Studio.tsx`, `ReviewInbox.tsx`, `SchemaEditor.tsx`, `ApiConsole.tsx`

## File Structure

- `frontend/src/App.tsx`: Owns project route aliases and legacy redirects.
- `frontend/src/components/ProjectSubNav.tsx`: Product-facing nav labels and active-state matching.
- `frontend/src/components/ProjectJourneyStepper.tsx`: New Documents workbench stepper.
- `frontend/src/pages/DocumentList.tsx`: Main workbench composition and document table copy.
- `frontend/src/pages/Studio.tsx`: Per-document reviewed-example copy.
- `frontend/src/pages/ReviewInbox.tsx`: Product surface becomes Review examples.
- `frontend/src/pages/SchemaEditor.tsx`: Product surface becomes Extraction rules.
- `frontend/src/pages/ImproveExtractor.tsx`: New proposal page.
- `frontend/src/stores/improve.ts`: New Zustand store for auto-research runs and draft-rule activation.
- `frontend/src/i18n/locales/en.json`: All user-facing text.
- `frontend/src/__tests__/*.test.tsx`: Unit tests for every visible behavior.
- `frontend/e2e/walking_skeleton.spec.ts`: End-to-end journey copy and route updates.
- `docs/local-demo.md`: Demo script aligned to the new journey.
- `docs/superpowers/specs/2026-05-02-overall-design.md`: Canonical design terminology update.

---

### Task 1: Route Aliases and Project Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ProjectSubNav.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/project_sub_nav.test.tsx`

- [ ] **Step 1: Write failing nav/route tests**

Replace the route matrix in `frontend/src/__tests__/project_sub_nav.test.tsx` so it covers the new product routes and legacy redirects.

```tsx
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects/:id" element={<ProjectSubNav projectId={7} />} />
        <Route path="/projects/:id/studio/:did" element={<ProjectSubNav projectId={7} />} />
        <Route path="/projects/:id/examples" element={<ProjectSubNav projectId={7} />} />
        <Route path="/projects/:id/rules" element={<ProjectSubNav projectId={7} />} />
        <Route path="/projects/:id/api" element={<ProjectSubNav projectId={7} />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("renders Documents, Review examples, Extraction rules, and API links", () => {
  renderAt("/projects/7");
  expect(screen.getByRole("link", { name: /^documents$/i })).toHaveAttribute("href", "/projects/7");
  expect(screen.getByRole("link", { name: /^review examples$/i })).toHaveAttribute("href", "/projects/7/examples");
  expect(screen.getByRole("link", { name: /^extraction rules$/i })).toHaveAttribute("href", "/projects/7/rules");
  expect(screen.getByRole("link", { name: /^api$/i })).toHaveAttribute("href", "/projects/7/api");
});

it("marks Review examples current on /projects/:id/examples", () => {
  renderAt("/projects/7/examples");
  expect(screen.getByRole("link", { name: /^review examples$/i })).toHaveAttribute("aria-current", "page");
});

it("marks Extraction rules current on /projects/:id/rules", () => {
  renderAt("/projects/7/rules");
  expect(screen.getByRole("link", { name: /^extraction rules$/i })).toHaveAttribute("aria-current", "page");
});

it("marks API current on /projects/:id/api", () => {
  renderAt("/projects/7/api");
  expect(screen.getByRole("link", { name: /^api$/i })).toHaveAttribute("aria-current", "page");
});
```

Add a route-level test in the same file or a small new `frontend/src/__tests__/app_routes.test.tsx`:

```tsx
it("legacy project routes redirect to product-facing routes", async () => {
  render(
    <MemoryRouter initialEntries={["/projects/7/schema"]}>
      <Routes>
        <Route path="/projects/:id/schema" element={<Navigate to="/projects/7/rules" replace />} />
        <Route path="/projects/:id/rules" element={<div>rules-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByText("rules-page")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- project_sub_nav.test.tsx
```

Expected: FAIL because `/examples`, `/rules`, and new labels are not implemented.

- [ ] **Step 3: Implement routes and nav**

Update `frontend/src/App.tsx` imports and routes. Keep component filenames for this task; product labels change now, component renames can happen later.

```tsx
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { ImproveExtractorPage } from "./pages/ImproveExtractor";

function ProjectRedirect({ to }: { to: "examples" | "rules" | "api" }) {
  const params = useParams<{ id: string }>();
  return <Navigate to={`/projects/${params.id}/${to}`} replace />;
}
```

Add product-facing routes and legacy redirects:

```tsx
<Route path="/projects/:id/examples" element={<AuthGate><ReviewInboxPage /></AuthGate>} />
<Route path="/projects/:id/review" element={<AuthGate><ProjectRedirect to="examples" /></AuthGate>} />
<Route path="/projects/:id/rules" element={<AuthGate><SchemaEditorPage /></AuthGate>} />
<Route path="/projects/:id/schema" element={<AuthGate><ProjectRedirect to="rules" /></AuthGate>} />
<Route path="/projects/:id/api" element={<AuthGate><ApiConsolePage /></AuthGate>} />
<Route path="/projects/:id/api-console" element={<AuthGate><ProjectRedirect to="api" /></AuthGate>} />
<Route path="/projects/:id/improve" element={<AuthGate><ImproveExtractorPage /></AuthGate>} />
```

Update `frontend/src/components/ProjectSubNav.tsx`:

```tsx
const onRules = useMatch("/projects/:id/rules") !== null;
const onLegacyRules = useMatch("/projects/:id/schema") !== null;
const onApi = useMatch("/projects/:id/api") !== null;
const onLegacyApi = useMatch("/projects/:id/api-console") !== null;
const onExamples = useMatch("/projects/:id/examples") !== null;
const onLegacyExamples = useMatch("/projects/:id/review") !== null;
const onDocuments = !onRules && !onLegacyRules && !onApi && !onLegacyApi && !onExamples && !onLegacyExamples;
```

Change tab targets:

```tsx
<NavTab to={`/projects/${projectId}`} active={onDocuments} label={t("nav.documents")} />
<NavTab to={`/projects/${projectId}/examples`} active={onExamples || onLegacyExamples} label={t("nav.review_examples")} />
<NavTab to={`/projects/${projectId}/rules`} active={onRules || onLegacyRules} label={t("nav.extraction_rules")} />
<NavTab to={`/projects/${projectId}/api`} active={onApi || onLegacyApi} label={t("nav.api")} />
```

Update `frontend/src/i18n/locales/en.json`:

```json
"nav": {
  "documents": "Documents",
  "review_examples": "Review examples",
  "extraction_rules": "Extraction rules",
  "api": "API"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && npm run test -- project_sub_nav.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/ProjectSubNav.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/project_sub_nav.test.tsx
git commit -m "feat(ui): rename project navigation around reviewed examples"
```

---

### Task 2: Documents Workbench Journey Stepper

**Files:**
- Create: `frontend/src/components/ProjectJourneyStepper.tsx`
- Modify: `frontend/src/pages/DocumentList.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/project_journey_stepper.test.tsx`
- Test: `frontend/src/__tests__/document_list.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/__tests__/project_journey_stepper.test.tsx`.

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProjectJourneyStepper } from "@/components/ProjectJourneyStepper";

describe("ProjectJourneyStepper", () => {
  it("renders the four-step reviewed examples journey", () => {
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={2}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByText("Extract drafts")).toBeInTheDocument();
    expect(screen.getByText("Review examples")).toBeInTheDocument();
    expect(screen.getByText("Improve extractor")).toBeInTheDocument();
    expect(screen.getByText("Publish API")).toBeInTheDocument();
  });

  it("disables Review examples until draft extractions exist", () => {
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts={false}
        reviewedDocs={0}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={vi.fn()}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /review examples/i })).toBeDisabled();
  });

  it("calls the Improve extractor action when reviewed examples exist", () => {
    const onImprove = vi.fn();
    render(
      <ProjectJourneyStepper
        hasDocuments
        hasDrafts
        reviewedDocs={3}
        hasImproveProposal={false}
        isPublished={false}
        canPublish={false}
        onExtract={vi.fn()}
        onReview={vi.fn()}
        onImprove={onImprove}
        onPublish={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /improve extractor/i }));
    expect(onImprove).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- project_journey_stepper.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement `ProjectJourneyStepper`**

Create `frontend/src/components/ProjectJourneyStepper.tsx`.

```tsx
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

type Props = {
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

type Step = {
  title: string;
  copy: string;
  done: boolean;
  disabled: boolean;
  button: string;
  action: () => void;
};

export function ProjectJourneyStepper(props: Props) {
  const steps: Step[] = [
    {
      title: "Extract drafts",
      copy: props.hasDrafts
        ? "Draft extractions are ready to review."
        : props.hasDocuments
          ? "Run extraction to create structured drafts."
          : "Upload documents to start.",
      done: props.hasDrafts,
      disabled: !props.hasDocuments,
      button: props.hasDrafts ? "Re-extract drafts" : "Extract drafts",
      action: props.onExtract,
    },
    {
      title: "Review examples",
      copy:
        props.reviewedDocs > 0
          ? `${props.reviewedDocs} reviewed example${props.reviewedDocs === 1 ? "" : "s"} saved.`
          : "Save ground truth examples from draft extractions.",
      done: props.reviewedDocs > 0,
      disabled: !props.hasDrafts,
      button: "Review examples",
      action: props.onReview,
    },
    {
      title: "Improve extractor",
      copy: props.hasImproveProposal
        ? "A rules proposal exists for this extractor."
        : "Generate extraction rule changes from reviewed examples.",
      done: props.hasImproveProposal,
      disabled: props.reviewedDocs === 0,
      button: "Improve extractor",
      action: props.onImprove,
    },
    {
      title: "Publish API",
      copy: props.isPublished
        ? "A published API version is live."
        : props.canPublish
          ? "Publish the locked rules version when ready."
          : "Lock rules before publishing.",
      done: props.isPublished,
      disabled: !props.canPublish && !props.isPublished,
      button: props.isPublished ? "Open API" : "Publish API",
      action: props.onPublish,
    },
  ];

  return (
    <section data-testid="project-journey-stepper" className="rounded-md border border-border-default bg-bg-elevated p-4">
      <ol className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {steps.map((step, idx) => (
          <li key={step.title} className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone={step.done ? "success" : "muted"}>{idx + 1}</Badge>
              <h2 className="text-sm font-semibold text-fg-primary">{step.title}</h2>
            </div>
            <p className="min-h-10 text-xs text-fg-muted">{step.copy}</p>
            <Button size="sm" variant={idx === 0 ? "primary" : "secondary"} disabled={step.disabled} onClick={step.action}>
              {step.button}
            </Button>
          </li>
        ))}
      </ol>
    </section>
  );
}
```

- [ ] **Step 4: Wire it into Documents**

Modify `frontend/src/pages/DocumentList.tsx`.

```tsx
import { ProjectJourneyStepper } from "@/components/ProjectJourneyStepper";
import { useReadiness } from "@/stores/readiness";
import { useReview } from "@/stores/review";
import { isProjectPublished, useProjects } from "@/stores/projects";
```

Inside the component:

```tsx
const readiness = useReadiness((s) => s.data);
const review = useReview((s) => s.data);
const project = useProjects((s) => s.rows.find((p) => p.id === projectId));
const loadProject = useProjects((s) => s.loadOne);

useEffect(() => {
  if (Number.isFinite(projectId)) void loadProject(projectId);
}, [loadProject, projectId]);

const hasDocuments = rows.length > 0;
const hasDrafts = rows.some((row) => row.status === "extracted");
const reviewedDocs = readiness?.evidence_coverage.annotated_docs ?? 0;
const canPublish = (readiness?.publish_blockers.length ?? 1) === 0;
const published = project ? isProjectPublished(project) : false;
const hasImproveProposal = false;
```

Render the stepper before the readiness panel:

```tsx
<ProjectJourneyStepper
  hasDocuments={hasDocuments}
  hasDrafts={hasDrafts}
  reviewedDocs={reviewedDocs}
  hasImproveProposal={hasImproveProposal}
  isPublished={published}
  canPublish={canPublish}
  onExtract={() => void triggerExtract(projectId)}
  onReview={() => {
    const next = review?.required_review[0] ?? review?.spot_check[0] ?? review?.all[0] ?? null;
    if (next) navigate(`/projects/${projectId}/studio/${next.id}`);
    else navigate(`/projects/${projectId}/examples`);
  }}
  onImprove={() => navigate(`/projects/${projectId}/improve`)}
  onPublish={() => navigate(`/projects/${projectId}/api`)}
/>
```

- [ ] **Step 5: Update Documents copy tests**

In `frontend/src/__tests__/document_list.test.tsx`, assert the stepper appears and table copy says `Draft ready`.

```tsx
expect(await screen.findByTestId("project-journey-stepper")).toBeInTheDocument();
expect(screen.getByText("Draft ready")).toBeInTheDocument();
expect(screen.queryByText("extracted")).not.toBeInTheDocument();
```

Update the status render in `DocumentListPage` with a helper:

```tsx
function documentStatusLabel(status: string): string {
  if (status === "uploaded") return "Uploaded";
  if (status === "extracting") return "Extracting draft";
  if (status === "extracted") return "Draft ready";
  if (status === "errored") return "Extraction failed";
  return status;
}
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd frontend && npm run test -- project_journey_stepper.test.tsx document_list.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ProjectJourneyStepper.tsx frontend/src/pages/DocumentList.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/project_journey_stepper.test.tsx frontend/src/__tests__/document_list.test.tsx
git commit -m "feat(ui): add reviewed examples journey stepper"
```

---

### Task 3: Studio Becomes "Review Draft Extraction"

**Files:**
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/components/FlagFieldMenu.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/studio_save.test.tsx`
- Test: `frontend/src/__tests__/flag_field_menu.test.tsx`

- [ ] **Step 1: Write failing Studio copy tests**

In `frontend/src/__tests__/studio_save.test.tsx`, change the visible copy assertions.

```tsx
expect(screen.getByText(/review draft extraction/i)).toBeInTheDocument();
expect(screen.getByText(/saving creates a reviewed example/i)).toBeInTheDocument();
expect(screen.getByText(/does not change the published api/i)).toBeInTheDocument();
expect(screen.getByRole("button", { name: /save reviewed example/i })).toBeDisabled();
expect(screen.getByText(/document preview is not available in v1\.0/i)).toBeInTheDocument();
expect(screen.getByText(/region selection and bounding boxes are not part of this version/i)).toBeInTheDocument();
```

Update the POST test:

```tsx
fireEvent.click(screen.getByRole("button", { name: /save reviewed example/i }));
```

Update toast test:

```tsx
expect(viewport.textContent ?? "").toMatch(/reviewed example saved/i);
```

- [ ] **Step 2: Write failing flag menu copy tests**

In `frontend/src/__tests__/flag_field_menu.test.tsx`, assert new copy:

```tsx
fireEvent.click(screen.getByRole("button", { name: /flag for rules/i }));
expect(await screen.findByRole("dialog")).toHaveTextContent(/changing the value is not enough/i);
expect(screen.getByText(/does not update extraction rules automatically/i)).toBeInTheDocument();
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend && npm run test -- studio_save.test.tsx flag_field_menu.test.tsx
```

Expected: FAIL because the old strings still render.

- [ ] **Step 4: Implement Studio copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"studio": {
  "page_title": "Review draft extraction",
  "save_reviewed_example": "Save reviewed example",
  "save_hint": "Edit the fields until this example is correct. Saving creates a reviewed example; it does not change the published API.",
  "saved_reviewed_example": "Reviewed example saved",
  "preview_placeholder_title": "Document preview",
  "preview_placeholder_hint": "Document preview is not available in v1.0. Use the extracted fields on the right to review this document. Region selection and bounding boxes are not part of this version."
}
```

Modify `frontend/src/pages/Studio.tsx`:

```tsx
<h1 className="text-xl font-semibold text-fg-primary">{t("studio.page_title")}</h1>
<p className="text-xs text-fg-muted">{doc.filename}</p>
<p className="mt-1 max-w-2xl text-xs text-fg-muted">{t("studio.save_hint")}</p>
```

Update the save toast:

```tsx
toast.show(t("studio.saved_reviewed_example"));
```

Update the primary button:

```tsx
{saving ? t("common.loading") : t("studio.save_reviewed_example")}
```

- [ ] **Step 5: Implement flag menu copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"flag": {
  "trigger_label": "Flag for rules",
  "trigger_aria": "Flag {{field}} for extraction rules",
  "dialog_title": "Flag for extraction rules",
  "dialog_hint": "Use this when changing the value is not enough: missing field, extra field, wrong entity count, or a rule problem. This saves review evidence but does not update extraction rules automatically."
}
```

No endpoint changes are needed.

- [ ] **Step 6: Run tests**

Run:

```bash
cd frontend && npm run test -- studio_save.test.tsx flag_field_menu.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Studio.tsx frontend/src/components/FlagFieldMenu.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/studio_save.test.tsx frontend/src/__tests__/flag_field_menu.test.tsx
git commit -m "feat(ui): save reviewed examples from Studio"
```

---

### Task 4: Review Inbox Becomes Review Examples

**Files:**
- Modify: `frontend/src/pages/ReviewInbox.tsx`
- Modify: `frontend/src/components/ReviewInboxBanner.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/review_inbox.test.tsx`

- [ ] **Step 1: Write failing tests**

In `frontend/src/__tests__/review_inbox.test.tsx`, update page and banner expectations:

```tsx
expect(await screen.findByText("Review examples")).toBeInTheDocument();
expect(screen.getByText(/review examples are ground truth/i)).toBeInTheDocument();
expect(screen.getByText(/do not get inserted into the runtime prompt/i)).toBeInTheDocument();
```

Update section assertions:

```tsx
expect(await screen.findByTestId("review-section-required")).toHaveTextContent("Needs review");
expect(screen.getByTestId("review-section-spot-check")).toHaveTextContent("Spot-check examples");
expect(screen.getByTestId("review-section-all")).toHaveTextContent("Test set");
```

Update draft mode callout:

```tsx
expect(callout.textContent ?? "").toMatch(/draft rules mode/i);
expect(callout.textContent ?? "").toMatch(/reviewed examples stay visible/i);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- review_inbox.test.tsx
```

Expected: FAIL on old `Review queue`, `Required review`, and `vibe-check` copy.

- [ ] **Step 3: Implement i18n copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"review": {
  "title": "Review examples",
  "page_title": "Review examples",
  "intro": "Review examples are ground truth for checking and improving the extractor. They do not get inserted into the runtime prompt.",
  "required_count": "{{count}} need review",
  "spot_check_count": "{{count}} spot-check examples",
  "all_count": "{{count}} in test set",
  "review_next": "Review next example",
  "section_required": "Needs review",
  "section_spot_check": "Spot-check examples",
  "section_all": "Test set",
  "section_required_hint": "Draft extractions where the checker flagged at least one field.",
  "section_spot_check_hint": "Clean-looking draft extractions worth sampling.",
  "section_all_hint": "Draft extractions currently used for review and checks.",
  "draft_mode_callout": "Draft rules mode: reviewed examples stay visible while rules are changing, so you can re-check them after improving the extractor. Once rules are locked, this page focuses on unreviewed test-set items.",
  "needs_judge": "Waiting on checks for {{count}} draft extraction(s).",
  "empty_pool": "No draft extractions in the test set yet. Extract drafts to start reviewing."
}
```

- [ ] **Step 4: Render intro copy**

Modify `frontend/src/pages/ReviewInbox.tsx` header:

```tsx
<header className="space-y-1">
  <h1 className="text-xl font-semibold text-fg-primary">{t("review.page_title")}</h1>
  <p className="max-w-3xl text-sm text-fg-muted">{t("review.intro")}</p>
</header>
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd frontend && npm run test -- review_inbox.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ReviewInbox.tsx frontend/src/components/ReviewInboxBanner.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/review_inbox.test.tsx
git commit -m "feat(ui): rename review queue to review examples"
```

---

### Task 5: Schema Editor Becomes Extraction Rules

**Files:**
- Modify: `frontend/src/pages/SchemaEditor.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/schema_editor.test.tsx`

- [ ] **Step 1: Write failing tests**

Update `frontend/src/__tests__/schema_editor.test.tsx`:

```tsx
expect(screen.getByRole("heading", { name: /extraction rules/i })).toBeInTheDocument();
expect(screen.getByText(/reviewed examples do not enter the prompt/i)).toBeInTheDocument();
expect(screen.getByText("Field rule")).toBeInTheDocument();
expect(screen.getByText("Global extraction notes")).toBeInTheDocument();
expect(screen.getByRole("button", { name: /^lock rules$/i })).toBeInTheDocument();
```

Update lock disabled test:

```tsx
expect(screen.getByRole("button", { name: /^lock rules$/i })).toBeDisabled();
```

Update locked test:

```tsx
expect(screen.getByRole("button", { name: /^edit draft rules$/i })).toBeInTheDocument();
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- schema_editor.test.tsx
```

Expected: FAIL on old `Schema`, `Description`, `Global notes`, and `Lock schema` copy.

- [ ] **Step 3: Implement extraction-rules copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"schema": {
  "title": "Extraction rules",
  "subtitle": "Rules are the readable field instructions used by draft extraction and the published API version. Reviewed examples do not enter the prompt.",
  "lock_button": "Lock rules",
  "unlock_button": "Edit draft rules",
  "loading": "Loading extraction rules…",
  "empty": "No active draft rules version found for this project.",
  "no_fields": "No extraction rules yet. Add a field rule or start from a template.",
  "locked_badge": "Locked rules",
  "unlocked_badge": "Draft rules",
  "field_description_label": "Field rule",
  "field_required_label": "Required in API output",
  "notes_label": "Global extraction notes",
  "lock_hint": "Lock rules when the field set is stable enough to publish or run regression checks. Editing locked rules creates a new draft rules version. The published API stays unchanged until you publish."
}
```

Modify `frontend/src/pages/SchemaEditor.tsx` header:

```tsx
<h1 className="text-xl font-semibold text-fg-primary">
  {t("schema.title")} v{active.version_number}
</h1>
<p className="max-w-2xl text-xs text-fg-muted">{t("schema.subtitle")}</p>
```

Render the lock hint under the header when unlocked:

```tsx
{!isLocked ? (
  <p className="rounded-sm border border-border-default bg-bg-muted p-2 text-xs text-fg-muted">
    {t("schema.lock_hint")}
  </p>
) : null}
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd frontend && npm run test -- schema_editor.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SchemaEditor.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/schema_editor.test.tsx
git commit -m "feat(ui): present schema as extraction rules"
```

---

### Task 6: Improve Extractor Proposal Page

**Files:**
- Create: `frontend/src/stores/improve.ts`
- Create: `frontend/src/pages/ImproveExtractor.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/improve_extractor.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/__tests__/improve_extractor.test.tsx`.

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { ImproveExtractorPage } from "@/pages/ImproveExtractor";
import { useImprove } from "@/stores/improve";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/7/improve"]}>
      <Routes>
        <Route path="/projects/:id/improve" element={<ImproveExtractorPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ImproveExtractorPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useImprove.setState({ runs: [], loading: false, running: false, error: null });
  });

  it("explains that reviewed examples produce a proposal, not production changes", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
    renderPage();
    expect(await screen.findByRole("heading", { name: /improve extractor/i })).toBeInTheDocument();
    expect(screen.getByText(/creates a proposal for extraction rules/i)).toBeInTheDocument();
    expect(screen.getByText(/does not change draft extraction, published api behavior, or the runtime prompt/i)).toBeInTheDocument();
  });

  it("POSTs auto-research run when Generate proposal is clicked", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        id: 11,
        project_id: 7,
        status: "completed",
        output_version_id: 33,
        turn_history: [{ actions_applied: [{ kind: "edit_field_description", field_name: "total", new_text: "Tax-included total" }] }],
      },
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /generate proposal/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/projects/7/auto-research/run", { max_turn: 5 }));
    expect(await screen.findByText(/field rule changed/i)).toBeInTheDocument();
  });

  it("accepting a proposal activates draft rules, not publish", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: [{
        id: 11,
        project_id: 7,
        status: "completed",
        output_version_id: 33,
        turn_history: [{ actions_applied: [{ kind: "edit_global_notes", text: "Always return JPY" }] }],
      }],
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /use as draft rules/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/v1/projects/7/versions/33/activate"));
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining("/publish"), expect.anything());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- improve_extractor.test.tsx
```

Expected: FAIL because the store/page do not exist.

- [ ] **Step 3: Implement improve store**

Create `frontend/src/stores/improve.ts`.

```ts
import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";

export type ImproveRun = {
  id: number;
  project_id: number;
  status: string;
  output_version_id: number | null;
  turn_history: Array<{
    diagnosis?: string;
    actions_applied?: Array<Record<string, unknown>>;
    failed_actions?: Array<Record<string, unknown>>;
  }>;
};

type ImproveState = {
  runs: ImproveRun[];
  loading: boolean;
  running: boolean;
  error: string | null;
  load: (projectId: number) => Promise<void>;
  run: (projectId: number) => Promise<void>;
  useAsDraftRules: (projectId: number, versionId: number) => Promise<void>;
};

export const useImprove = create<ImproveState>((set, get) => ({
  runs: [],
  loading: false,
  running: false,
  error: null,

  async load(projectId) {
    set({ loading: true, error: null });
    try {
      const runs = (await api.get(`/api/v1/projects/${projectId}/auto-research/runs`)).data as ImproveRun[];
      set({ runs, loading: false });
    } catch (e) {
      set({ loading: false, error: emergeErrorKey(e) });
    }
  },

  async run(projectId) {
    set({ running: true, error: null });
    try {
      const run = (await api.post(`/api/v1/projects/${projectId}/auto-research/run`, { max_turn: 5 })).data as ImproveRun;
      set({ runs: [run, ...get().runs] });
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ running: false });
    }
  },

  async useAsDraftRules(projectId, versionId) {
    set({ error: null });
    try {
      await api.post(`/api/v1/projects/${projectId}/versions/${versionId}/activate`);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    }
  },
}));
```

- [ ] **Step 4: Implement improve page**

Create `frontend/src/pages/ImproveExtractor.tsx`.

```tsx
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { ProjectSubNav } from "@/components/ProjectSubNav";
import { Button } from "@/components/ui/Button";
import { useT } from "@/i18n/useT";
import { useImprove, type ImproveRun } from "@/stores/improve";

function actionLabel(action: Record<string, unknown>): string {
  const kind = String(action.kind ?? "");
  if (kind === "edit_field_description") return "Field rule changed";
  if (kind === "add_field_examples") return "Field examples added";
  if (kind === "add_field") return "Field added";
  if (kind === "remove_field") return "Field removed";
  if (kind === "make_optional") return "Field made optional";
  if (kind === "make_required") return "Field made required";
  if (kind === "edit_global_notes") return "Global extraction notes changed";
  if (kind === "add_field_enum") return "Allowed values changed";
  return "Rule change proposed";
}

function actionsFor(run: ImproveRun): Record<string, unknown>[] {
  return run.turn_history.flatMap((turn) => turn.actions_applied ?? []);
}

export function ImproveExtractorPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const runs = useImprove((s) => s.runs);
  const loading = useImprove((s) => s.loading);
  const running = useImprove((s) => s.running);
  const error = useImprove((s) => s.error);
  const load = useImprove((s) => s.load);
  const run = useImprove((s) => s.run);
  const useAsDraftRules = useImprove((s) => s.useAsDraftRules);

  useEffect(() => {
    if (Number.isFinite(projectId)) void load(projectId);
  }, [load, projectId]);

  const latest = runs[0] ?? null;

  return (
    <>
      {Number.isFinite(projectId) ? <ProjectSubNav projectId={projectId} /> : null}
      <main className="mx-auto max-w-5xl space-y-6 p-6">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold text-fg-primary">{t("improve.title")}</h1>
          <p className="max-w-3xl text-sm text-fg-muted">{t("improve.intro")}</p>
        </header>

        {error ? <p role="alert" className="text-sm text-status-error">{t(error)}</p> : null}

        <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
          <h2 className="text-sm font-semibold text-fg-primary">{t("improve.generate_title")}</h2>
          <p className="text-xs text-fg-muted">{t("improve.generate_hint")}</p>
          <Button disabled={running || loading} onClick={() => void run(projectId)}>
            {running ? t("common.loading") : t("improve.generate_button")}
          </Button>
        </section>

        {latest ? (
          <section className="space-y-3 rounded-md border border-border-default bg-bg-elevated p-4">
            <header>
              <h2 className="text-sm font-semibold text-fg-primary">{t("improve.latest_title")}</h2>
              <p className="text-xs text-fg-muted">{t("improve.status", { status: latest.status })}</p>
            </header>
            <ul className="space-y-1">
              {actionsFor(latest).map((action, idx) => (
                <li key={idx} className="text-sm text-fg-primary">
                  {actionLabel(action)}
                  {typeof action.field_name === "string" ? (
                    <span className="ml-2 font-mono text-xs text-fg-muted">{action.field_name}</span>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={latest.output_version_id === null}
                onClick={() => latest.output_version_id ? void useAsDraftRules(projectId, latest.output_version_id) : undefined}
              >
                {t("improve.use_as_draft_rules")}
              </Button>
              <Link
                to={`/projects/${projectId}/rules`}
                className="inline-flex items-center justify-center rounded-md border border-border-default bg-bg-elevated px-3 py-1.5 text-sm font-medium text-fg-primary transition-opacity hover:bg-bg-muted"
              >
                {t("improve.open_rules")}
              </Link>
            </div>
          </section>
        ) : null}
      </main>
    </>
  );
}
```

- [ ] **Step 5: Add i18n copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"improve": {
  "title": "Improve extractor",
  "intro": "This creates a proposal for extraction rules. It does not change draft extraction, published API behavior, or the runtime prompt until you accept the proposal and re-extract.",
  "generate_title": "Generate extraction rules proposal",
  "generate_hint": "Use reviewed examples and regression cases to propose rule changes. Reviewed examples are not inserted into the runtime prompt.",
  "generate_button": "Generate proposal",
  "latest_title": "Latest proposal",
  "status": "Status: {{status}}",
  "use_as_draft_rules": "Use as draft rules",
  "open_rules": "Open extraction rules"
}
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd frontend && npm run test -- improve_extractor.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/improve.ts frontend/src/pages/ImproveExtractor.tsx frontend/src/App.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/improve_extractor.test.tsx
git commit -m "feat(ui): add improve extractor proposal page"
```

---

### Task 7: API Page Publish Terminology

**Files:**
- Modify: `frontend/src/pages/ApiConsole.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Test: `frontend/src/__tests__/api_console.test.tsx`

- [ ] **Step 1: Write failing tests**

Update `frontend/src/__tests__/api_console.test.tsx` expectations:

```tsx
expect(await screen.findByRole("heading", { name: /^api$/i })).toBeInTheDocument();
expect(screen.getByText(/only publishing changes/i)).toBeInTheDocument();
expect(screen.getByTestId("production-pointer")).toHaveTextContent("Published API version");
expect(screen.getByTestId("lab-pointer")).toHaveTextContent("Draft rules version");
expect(screen.getByRole("button", { name: /publish api version/i })).toBeDisabled();
expect(screen.queryByText(/activate version for api/i)).not.toBeInTheDocument();
```

Update enabled publish test:

```tsx
expect(screen.getByRole("button", { name: /publish api version/i })).not.toBeDisabled();
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm run test -- api_console.test.tsx
```

Expected: FAIL on old `API Console`, `Activate for API`, and `Lab / draft version` labels.

- [ ] **Step 3: Implement API copy**

Update `frontend/src/i18n/locales/en.json`:

```json
"api_console": {
  "title": "API",
  "intro": "Only publishing changes /extract/{api_code}. Reviewing examples, improving the extractor, and editing draft rules do not affect production.",
  "production_pointer": "Published API version",
  "production_pointer_hint": "What integrators see at /extract/{api_code}",
  "lab_pointer": "Draft rules version",
  "lab_pointer_hint": "Working rules version. Publish it when ready.",
  "diff_section": "API contract changes",
  "activate_section": "Publish API version",
  "activate_hint_locked": "Draft rules are locked and ready. Publishing updates the production API version.",
  "activate_hint_unlocked": "Lock extraction rules before publishing.",
  "activate_button": "Publish API version",
  "feedback_example_title": "Production feedback example",
  "feedback_example_hint": "Production callers POST corrections to /extract/{api_code}/feedback. Feedback becomes regression cases, not prompt examples."
}
```

Modify `frontend/src/pages/ApiConsole.tsx` header:

```tsx
<h1 className="text-xl font-semibold text-fg-primary">{t("api_console.title")}</h1>
<p className="max-w-3xl text-xs text-fg-muted">{t("api_console.intro")}</p>
```

Function names can remain `handleActivate` in this task; changing internals is unnecessary.

- [ ] **Step 4: Run tests**

Run:

```bash
cd frontend && npm run test -- api_console.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ApiConsole.tsx frontend/src/i18n/locales/en.json frontend/src/__tests__/api_console.test.tsx
git commit -m "feat(ui): rename api console publish surface"
```

---

### Task 8: Terminology Regression Test

**Files:**
- Create: `frontend/src/__tests__/terminology.test.ts`

- [ ] **Step 1: Write failing terminology test**

Create `frontend/src/__tests__/terminology.test.ts`.

```ts
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap(collectStrings);
  }
  return [];
}

describe("product terminology", () => {
  it("uses reviewed-examples language in normal UI strings", () => {
    const all = collectStrings(en).join("\n");
    expect(all).toContain("Reviewed example");
    expect(all).toContain("Extraction rules");
    expect(all).toContain("Improve extractor");
    expect(all).toContain("Published API version");
  });

  it("does not expose annotation-platform terms in normal UI strings", () => {
    const all = collectStrings(en).join("\n");
    expect(all).not.toMatch(/\bSave correction\b/i);
    expect(all).not.toMatch(/\bVibe-check\b/i);
    expect(all).not.toMatch(/\bCounterexample\b/i);
    expect(all).not.toMatch(/\bAutoResearch\b/i);
    expect(all).not.toMatch(/\bActivate version for API\b/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails if old strings remain**

Run:

```bash
cd frontend && npm run test -- terminology.test.ts
```

Expected: PASS only after Tasks 1-7 have removed the old product strings from `en.json`.

- [ ] **Step 3: Fix any remaining catalog strings**

Search:

```bash
rg -n "Save correction|Vibe-check|Counterexample|AutoResearch|Activate version for API|\\bSchema\\b|\\bAnnotation\\b|\\bPrediction\\b" frontend/src/i18n/locales/en.json
```

Allowed result: no matches for normal product strings. If `Schema` appears only as part of an internal error key, move it behind developer-only copy or rename it to `Extraction rules`.

- [ ] **Step 4: Run all frontend unit tests**

Run:

```bash
cd frontend && npm run test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/__tests__/terminology.test.ts frontend/src/i18n/locales/en.json
git commit -m "test(ui): guard reviewed examples terminology"
```

---

### Task 9: Local Demo and Overall Design Docs

**Files:**
- Modify: `docs/local-demo.md`
- Modify: `docs/superpowers/specs/2026-05-02-overall-design.md`

- [ ] **Step 1: Write documentation acceptance checks**

Run these commands before editing to see current failures:

```bash
rg -n "Save correction|Schema|Review Inbox|vibe-check|Activate for API|AutoResearch" docs/local-demo.md docs/superpowers/specs/2026-05-02-overall-design.md
```

Expected: Matches exist.

- [ ] **Step 2: Update `docs/local-demo.md` journey headings**

Rewrite the main flow headings to:

```markdown
## 2. 注册并创建第一个 extraction API
## 3. 上传文档并 Extract drafts
## 4. Review examples
## 5. 锁定 Extraction rules
## 6. Improve extractor 生成规则提案
## 7. Re-extract drafts 并检查 Review examples
## 8. Publish API version、密钥揭示、公开抽取
## 9. Production feedback → regression cases → readiness
```

Replace user-facing command names:

```text
Save correction -> Save reviewed example
Schema -> Extraction rules
Review Inbox -> Review examples
Activate for API -> Publish API version
AutoResearch -> Improve extractor
```

Keep internal terms only where the doc explicitly explains backend invariants. When an internal term is necessary, write it as:

```markdown
内部仍存为 `Annotation(role=none)`，但演示里把它称为 reviewed example。
```

- [ ] **Step 3: Update `overall-design.md` terminology**

Patch these sections:

- Glossary: add `Reviewed example` as product-facing term and mark `Annotation` as internal DB name.
- §2 User workflow: replace the old main loop with the four-step journey.
- §5 AutoResearch heading: write `AutoResearch (product surface: Improve extractor)`.
- §8 UI layout: replace `Schema editor`, `Review Inbox`, and `Save correction` with the new names.
- §8.5 Product terminology: update the table to match the new spec.
- §9 scope: say `Extraction rules / Improve extractor / Reviewed examples`.

Use this invariant paragraph unchanged:

```markdown
Reviewed examples are ground truth and evidence. They do not enter the runtime prompt. Improve extractor may use them to generate an extraction rules proposal, but only extraction rules (field rules + global extraction notes) are composed into the runtime prompt. Publishing remains explicit through `published_version_id`.
```

- [ ] **Step 4: Run documentation checks**

Run:

```bash
rg -n "Save correction|Review Inbox|vibe-check|Activate for API" docs/local-demo.md docs/superpowers/specs/2026-05-02-overall-design.md
```

Expected: no matches.

Run:

```bash
rg -n "Annotation|Prediction|Counterexample|AutoResearch|Schema" docs/local-demo.md docs/superpowers/specs/2026-05-02-overall-design.md
```

Expected: matches are allowed only in glossary/internal invariant sections, and each match is accompanied by product-facing wording nearby.

- [ ] **Step 5: Commit**

```bash
git add docs/local-demo.md docs/superpowers/specs/2026-05-02-overall-design.md
git commit -m "docs: align design around reviewed examples journey"
```

---

### Task 10: Walking Skeleton E2E Copy and Routes

**Files:**
- Modify: `frontend/e2e/walking_skeleton.spec.ts`

- [ ] **Step 1: Update E2E expectations**

Change route visits:

```ts
await page.goto(`/projects/${projectId}/rules`);
await page.goto(`/projects/${projectId}/api`);
await page.goto(`/projects/${projectId}/examples`);
```

Change button labels:

```ts
const saveButton = page.getByRole("button", { name: /save reviewed example/i });
const lockBtn = page.getByRole("button", { name: /lock rules/i });
await page.getByRole("button", { name: /publish api version/i }).click();
```

Change heading assertions:

```ts
await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
await expect(page.getByTestId("project-journey-stepper")).toBeVisible();
await expect(page.getByRole("heading", { name: /review examples/i })).toBeVisible();
```

- [ ] **Step 2: Run non-live frontend checks**

Run:

```bash
cd frontend && npm run test
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Run optional live E2E**

Run only with backend and provider configured:

```bash
cd frontend && EMERGE_E2E=1 npm run e2e -- walking_skeleton.spec.ts
```

Expected: PASS. If provider is unavailable, record that live E2E was not run.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/walking_skeleton.spec.ts
git commit -m "test(e2e): follow reviewed examples journey"
```

---

### Task 11: Final Verification

**Files:**
- No source edits expected unless verification finds a defect.

- [ ] **Step 1: Run frontend unit test suite**

```bash
cd frontend && npm run test
```

Expected: all tests PASS.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: TypeScript build and Vite build PASS.

- [ ] **Step 3: Run backend tests if backend was touched**

```bash
cd backend && uv run pytest -v
```

Expected: all backend tests PASS. If no backend files changed, this is optional but recommended.

- [ ] **Step 4: Run terminology scans**

```bash
rg -n "Save correction|Vibe-check|Activate version for API|AutoResearch" frontend/src/i18n/locales/en.json frontend/src/pages frontend/src/components
```

Expected: no matches.

```bash
rg -n "published_version_id" backend/app/api/routes/public.py backend/tests/test_public_extract.py
```

Expected: existing public API safety tests still show the public route reads `published_version_id`.

- [ ] **Step 5: Commit final fixes if needed**

If verification required edits:

```bash
git add <changed-files>
git commit -m "fix(ui): polish reviewed examples journey"
```

If no edits were required, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Current journey confusion is addressed by Tasks 1-5 and docs Task 9.
- 2-3 options and recommendation are in the spec.
- Documents workbench and four-step journey are implemented in Task 2.
- Navigation becomes Documents / Review examples / Extraction rules / API in Task 1.
- Studio primary action becomes Save reviewed example in Task 3.
- Improve extractor entry/page is implemented in Task 6.
- Readiness hierarchy is addressed by the stepper and API publish copy in Tasks 2 and 7.
- Docs updates are explicit in Task 9.
- Hard constraints remain unchanged; no task adds PDF preview, bbox, image few-shot, automatic prompt injection, automatic publish, or public API reads from active version.

Placeholder scan:

- No task contains unresolved placeholder markers or unspecified "add tests" instructions.
- Each task names exact files, test commands, and expected outcomes.

Type consistency:

- New frontend store names use `ImproveRun`, `useImprove`, `run`, and `useAsDraftRules` consistently.
- New routes use `/examples`, `/rules`, `/improve`, and `/api` consistently.
- Product terminology uses `reviewed example`, `extraction rules`, `draft rules`, and `published API version`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-reviewed-examples-journey.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
