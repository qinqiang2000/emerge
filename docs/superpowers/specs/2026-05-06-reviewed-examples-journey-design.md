# Reviewed Examples Journey Design

> **Status:** v1 interaction redesign spec
> **Scope:** Product language, navigation, primary journey, and minimum UI/API wiring needed to make the current emerge workflow understandable to new users.
> **Decision:** Adopt the Documents-as-workbench direction. The internal model can stay close to the current code; the product surface must stop reading like an annotation platform.

## 1. Current Journey Confusion

The current implementation has the right safety invariants but exposes too many implementation concepts too early.

### 1.1 New users must infer the workflow from abstract tabs

Current navigation:

```text
Documents | Review | Schema | API
```

This looks simple, but it hides the sequence. A new user sees separate pages and has to guess whether to upload documents, review first, lock schema first, or publish first. The local demo explains the flow, but the app does not.

### 1.2 "Correction" sounds like it trains the extractor directly

Studio currently says `Save correction`. The hint says production does not change until activation, but the button still implies the correction itself is the learning object. That conflicts with the product truth:

- reviewed examples are ground truth and evidence;
- reviewed examples do not enter the runtime prompt;
- extraction rules are what enter the prompt;
- Improve extractor proposes rule changes from reviewed examples.

### 1.3 "Schema" is technically correct and product-wrong

`Schema` makes sense to engineers, but new users do not want to edit a schema. They want to tell the extractor what each field means. The actual user-facing asset is:

```text
Extraction rules = field descriptions + global notes + output field shape
```

The page can still edit `ProjectVersion.schema_snapshot` internally, but the UI should say `Extraction rules`.

### 1.4 Readiness and review are too high in the hierarchy

`API Readiness` is valuable, but on the Documents page it currently competes with the user's next action. For a fresh project, it shows low-signal details like no feedback, draft schema, no judge verdicts. That is correct but not guiding. A new user needs:

```text
1 Extract drafts -> 2 Review examples -> 3 Improve extractor -> 4 Publish API
```

Readiness should support publish decisions, not replace the journey.

### 1.5 "Review queue", "vibe-check", "counterexample", and "annotation" leak internal framing

Some of these words are already hidden in the UI, but they still appear in docs, tests, comments, and page mental models. The product surface should use:

| Internal concept | Product-facing concept |
|---|---|
| Prediction | Draft extraction |
| Annotation role=none | Reviewed example |
| Annotation role=counterexample | Regression case / production feedback |
| Schema | Extraction rules |
| Field description | Field rule |
| Global notes | Global extraction notes |
| AutoResearch | Improve extractor |
| Vibe-check set | Test set / regression checks |
| Active version | Draft rules version |
| Published version | Published API version |

## 2. Redesign Options

### Option A — Documents Workbench With Journey Stepper

Documents becomes the main workbench. It keeps upload, extract, document table, review entry, improve entry, readiness summary, and publish entry in one place. The top of the page shows the four-step journey:

```text
1 Extract drafts -> 2 Review examples -> 3 Improve extractor -> 4 Publish API
```

Navigation becomes:

```text
Documents | Review examples | Extraction rules | API
```

An `Improve extractor` page exists but is not a persistent top-level nav tab. It is reached from the stepper, Documents empty/progress states, and Extraction rules proposal cards.

Trade-off: This is the biggest UI rename/reflow, but it aligns the product with the actual workflow without a backend rewrite.

### Option B — Separate Guided Wizard

Create a dedicated first-run wizard that walks users through upload, extract, review, improve, and publish. Existing pages remain mostly unchanged for advanced users.

Trade-off: Lower risk to existing pages, but creates two flows. Users can still fall into old terminology after the wizard, and the product remains split between a guided path and an annotation-platform dashboard.

### Option C — Copy Polish Only

Keep the existing pages and routes. Rename obvious strings: `Schema` to `Extraction rules`, `Save correction` to `Save reviewed example`, and `Review queue` to `Review examples`.

Trade-off: Fastest path, but it does not solve the core problem: users still have to infer the workflow from sibling tabs.

### Recommendation

Use **Option A**. It is the smallest redesign that changes the user's mental model instead of only changing labels. It preserves the current backend invariants and most component boundaries, while making Documents the obvious place to move through the whole lifecycle.

## 3. Product Mental Model

The user is building a published extraction API, not maintaining a labeling dataset.

Core rules:

1. A draft extraction is the extractor's current answer for a document.
2. A reviewed example is the user's accepted or corrected answer for a document.
3. Reviewed examples are ground truth and evidence; they do not go into the runtime prompt.
4. Extraction rules are the readable instructions that do go into the runtime prompt.
5. Improve extractor uses reviewed examples and regression cases to propose extraction rule changes.
6. Proposals do not change production.
7. Production changes only when the user publishes an API version.
8. The public API reads only `Project.published_version_id`.

## 4. Target Information Architecture

### 4.1 Routes

Product-facing routes:

```text
/projects/:id                         Documents workbench
/projects/:id/examples                Review examples
/projects/:id/rules                   Extraction rules
/projects/:id/improve                 Improve extractor proposal page
/projects/:id/api                     API
/projects/:id/studio/:did             Review draft extraction for one document
```

Legacy routes remain as redirects for v1 compatibility:

```text
/projects/:id/review       -> /projects/:id/examples
/projects/:id/schema       -> /projects/:id/rules
/projects/:id/api-console  -> /projects/:id/api
```

The backend API paths do not need to be renamed in v1.

### 4.2 Navigation

Primary project nav:

```text
Documents | Review examples | Extraction rules | API
```

Rules:

- `Studio` is not a nav item. It is part of reviewing a document, and Documents remains current when the user is in Studio.
- `Improve extractor` is a workflow action, not a permanent nav tab. It can still have a route for deep links and tests.
- No product nav item says `Schema`, `Annotation`, `Prediction`, `Counterexample`, `Vibe-check`, or `AutoResearch`.

## 5. Documents Workbench

Documents is the main project page and should answer three questions immediately:

1. What should I do next?
2. Which documents need attention?
3. Is my API ready to publish?

### 5.1 Top Journey Stepper

The first content block is a four-step workbench header.

```text
Extract drafts        Review examples        Improve extractor        Publish API
[Upload / Extract] -> [Review next]       -> [Generate proposal]   -> [Open API]
```

Each step has:

- a short label;
- state: `not_started`, `available`, `in_progress`, `complete`, or `blocked`;
- one primary action;
- one sentence of state copy.

Suggested state mapping from existing data:

| Step | Complete when | Available when | Primary action |
|---|---|---|---|
| Extract drafts | at least one document has a latest prediction or `status=extracted` | project has uploaded documents | `Extract drafts` or `Re-extract drafts` |
| Review examples | `readiness.evidence_coverage.annotated_docs > 0` | at least one draft extraction exists | `Review next` |
| Improve extractor | latest improve run has an `output_version_id` or the current rules version source is `auto_research` | at least one reviewed example exists | `Improve extractor` |
| Publish API | project has `published_version_id` | active draft rules version is locked and readiness has no hard blockers | `Open API` or `Publish API version` |

Do not over-gate the stepper. It should guide, not become a second readiness engine. API publish remains gated by the API page and backend.

### 5.2 Documents Table

Default columns:

- File
- Draft extraction
- Reviewed example
- Needs attention
- Last updated

Current `status` values can remain in code, but product copy should translate them:

| Current status | Product copy |
|---|---|
| uploaded | Uploaded |
| extracting | Extracting draft |
| extracted | Draft ready |
| errored | Extraction failed |

`Reviewed example` should show `Not reviewed` or `Saved`, based on whether the document has a saved lab-side annotation. It must not say `Annotation`.

`Needs attention` uses risky fields / review queue data when present. If no judge has run, show `Not checked yet`, not false reassurance.

### 5.3 Empty States

Fresh project:

```text
Upload documents to create draft extractions.
Reviewed examples and extraction rules come after the first drafts.
```

Uploaded but not extracted:

```text
Documents uploaded. Extract drafts to see the first structured outputs.
```

Extracted but no reviewed examples:

```text
Drafts are ready. Review a few examples so the extractor has ground truth to learn from.
```

Reviewed examples but no improve proposal:

```text
Reviewed examples are saved. Generate an extraction rules proposal when you want the extractor to improve.
```

## 6. Studio: Review Draft Extraction

Studio becomes a document review page, not a correction task.

### 6.1 Title and Primary Action

Page title:

```text
Review draft extraction
```

Subtitle:

```text
Edit the fields until this example is correct. Saving creates a reviewed example; it does not change the published API.
```

Primary button:

```text
Save reviewed example
```

Success toast:

```text
Reviewed example saved
```

### 6.2 Left Preview Placeholder

v1.0 still does not render true PDF preview. The placeholder must say that clearly:

```text
Document preview is not available in v1.0.
Use the extracted fields on the right to review this document. Region selection and bounding boxes are not part of this version.
```

This avoids implying the user should draw regions or wait for a hidden preview feature.

### 6.3 Field Actions

The value textbox remains the correction path. The menu action should be reframed:

Current:

```text
Report issue
```

Target:

```text
Flag for rules
```

Dialog copy:

```text
Use this when changing the value is not enough: missing field, extra field, wrong entity count, or a rule problem. This saves review evidence but does not update extraction rules automatically.
```

This keeps the existing lab flag mechanism but connects it to Improve extractor.

## 7. Review Examples Page

`Review Inbox` becomes `Review examples`.

Sections:

| Current | Target |
|---|---|
| Required review | Needs review |
| Spot-check | Spot-check examples |
| All documents | Test set |

The page explains review work in product terms:

```text
Review examples are ground truth for checking and improving the extractor. They do not get inserted into the runtime prompt.
```

Draft-mode callout:

```text
Draft rules mode: reviewed examples stay visible while rules are changing, so you can re-check them after improving the extractor. Once rules are locked, this page focuses on unreviewed test-set items.
```

No UI text should mention `vibe-check`.

## 8. Extraction Rules Page

`SchemaEditorPage` becomes `ExtractionRulesPage` at `/projects/:id/rules`.

### 8.1 Page Header

Title:

```text
Extraction rules
```

Subtitle:

```text
Rules are the readable field instructions used by draft extraction and the published API version. Reviewed examples do not enter the prompt.
```

Version badge:

```text
Draft rules vN
Locked rules vN
```

Lock CTA:

```text
Lock rules
```

Unlock CTA:

```text
Edit draft rules
```

### 8.2 Field Labels

| Current | Target |
|---|---|
| Description | Field rule |
| Required | Required in API output |
| Global notes | Global extraction notes |
| No fields defined yet. Add fields to start extracting. | No extraction rules yet. Add a field rule or start from a template. |

The field card can keep field name/type because those affect the API contract, but descriptions must be framed as rules, not prose metadata.

### 8.3 Rule Locking

The UI should avoid making `lock` feel like a mysterious schema operation. Copy:

```text
Lock rules when the field set is stable enough to publish or run regression checks. Editing locked rules creates a new draft rules version. The published API stays unchanged until you publish.
```

## 9. Improve Extractor Page

The new `/projects/:id/improve` page is the main new UX surface. It uses existing AutoResearch primitives where possible, but product copy says `Improve extractor`.

### 9.1 Purpose

Use reviewed examples and regression cases to generate an extraction rules proposal.

The page must explicitly state:

```text
This creates a proposal for extraction rules. It does not change draft extraction, published API behavior, or the runtime prompt until you accept the proposal and re-extract.
```

### 9.2 Layout

```text
Improve extractor

Inputs
- Reviewed examples: N
- Regression cases: M
- Current draft rules: vN

[Generate proposal]

Latest proposal
- Status
- Proposed field rule changes
- Proposed global extraction notes changes
- Candidate draft rules version vN+1

[Use as draft rules] [Dismiss] [Open extraction rules]
```

### 9.3 Data Source

Minimum v1 implementation can use:

- `POST /api/v1/projects/{id}/auto-research/run` to generate a candidate ProjectVersion.
- `GET /api/v1/projects/{id}/auto-research/runs` to list proposal runs.
- `GET /api/v1/projects/{id}/versions` to find the candidate version.
- `POST /api/v1/projects/{id}/versions/{version_id}/activate` when the user clicks `Use as draft rules`.

The page must not auto-activate the candidate version.

### 9.4 Proposal Display

Render action history from `turn_history[].actions_applied` in user language:

| Action kind | Product copy |
|---|---|
| `edit_field_description` | Field rule changed |
| `add_field_examples` | Field examples added |
| `add_field` | Field added |
| `remove_field` | Field removed |
| `make_optional` | Field made optional |
| `make_required` | Field made required |
| `edit_global_notes` | Global extraction notes changed |
| `add_field_enum` | Allowed values changed |

If an action cannot be rendered, show `Rule change proposed` and the raw `kind` in a monospace developer detail. Do not show Python class names or AutoResearch terminology.

### 9.5 After Acceptance

After `Use as draft rules`, show:

```text
Draft rules updated. Re-extract drafts to check the proposal against your documents.
```

Primary next action:

```text
Re-extract drafts
```

Publishing remains on the API page.

## 10. API Page

`API Console` becomes `API`.

Keep the existing release-safety model:

- Production API version points at `published_version_id`.
- Draft rules version points at `active_version_id`.
- Publish requires a locked draft rules version.
- Contract diff is shown before publish.
- API keys are one-time reveal.
- Public feedback creates regression cases, not prompt examples.

Copy changes:

| Current | Target |
|---|---|
| Activate version for API | Publish API version |
| Lab / draft version | Draft rules version |
| Production API version | Published API version |
| Contract diff | API contract changes |
| Partial feedback example | Production feedback example |
| Send test feedback | Send test production feedback |

The API page should state:

```text
Only publishing changes `/extract/{api_code}`. Reviewing examples, improving the extractor, and editing draft rules do not affect production.
```

## 11. Readiness Hierarchy

Readiness remains important but moves down one level on Documents.

### 11.1 Documents Page

Show a compact summary under the journey stepper:

```text
API readiness: Draft rules need review
Reviewed examples: 2 docs
Regression: no production feedback yet
```

The detailed `ReadinessPanel` can be collapsed or placed below the table.

### 11.2 API Page

Show detailed readiness near the publish controls. This is where blockers and warnings belong.

### 11.3 Copy Rules

Use:

- `Reviewed examples`
- `Test set`
- `Regression cases`
- `API readiness`

Avoid:

- `Annotated`
- `Annotation`
- `Vibe-check`
- `Confidence score`
- `Counterexample`

## 12. Create Project

For v1, keep the current template-first creation but update the framing:

Title:

```text
Create an extraction API
```

Intro:

```text
Start from a template or a blank set of extraction rules. Upload documents next to create draft extractions.
```

Template section:

```text
Start with extraction rules
```

Empty project:

```text
Start blank
```

The disabled natural-language onboarding textarea can remain disabled, but its copy should not promise immediate v1.1. Use:

```text
Describe-and-bootstrap is not enabled in this build. Start from rules, then improve them with reviewed examples.
```

## 13. Documentation Updates

### 13.1 `docs/local-demo.md`

Rewrite the demo steps around the new journey:

1. Create extraction API.
2. Upload documents.
3. Extract drafts.
4. Save reviewed examples.
5. Open Extraction rules and lock rules.
6. Improve extractor to generate a rules proposal.
7. Re-extract drafts and check Review examples.
8. Publish API version.
9. Send production feedback and observe regression cases/readiness.

The demo must stop using `Save correction`, `Schema`, `Review Inbox`, `vibe-check`, and `Activate for API` as primary user-facing terms.

### 13.2 `overall-design.md`

Update the glossary and UI sections:

- `Annotation` remains DB/internal, but product-facing docs call it `Reviewed example`.
- `Schema` becomes `Extraction rules` in UI sections.
- `AutoResearch` becomes internal name for the `Improve extractor` product surface.
- The project workflow should be replaced with the four-step journey.
- The hard invariants remain unchanged: no bbox, no image few-shot, no automatic prompt injection from reviewed examples, no automatic publish, public API reads `published_version_id`.

## 14. Acceptance Criteria

### 14.1 User-facing terminology

In product UI tests, these labels must exist:

- `Review examples`
- `Extraction rules`
- `Save reviewed example`
- `Improve extractor`
- `Publish API version`
- `Published API version`
- `Draft rules version`

These labels must not appear in normal product UI:

- `Save correction`
- `Schema`
- `Annotation`
- `Prediction`
- `Counterexample`
- `Vibe-check`
- `AutoResearch`
- `Activate version for API`

Developer-only route names, backend tags, and comments may keep internal terms.

### 14.2 Journey behavior

- Fresh project Documents page shows the four-step journey.
- Uploading documents makes `Extract drafts` available.
- Extracted documents make `Review examples` available.
- Saving from Studio posts to the existing annotations endpoint but the UI calls the result a reviewed example.
- Saving reviewed examples does not call publish endpoints.
- Improve extractor can generate a proposal and does not auto-activate it.
- Accepting an improve proposal updates `active_version_id` only, never `published_version_id`.
- Publishing from API page changes `published_version_id` only through the existing publish endpoint.
- Legacy routes redirect to new routes.

### 14.3 Hard constraints

- v1.0 still does not render real PDF preview.
- No bbox or region annotation is introduced.
- No image few-shot is introduced.
- Reviewed examples are not injected into runtime prompts.
- Improve extractor proposals are explicit and reviewable.
- No automatic publish.
- Public API remains bound to `published_version_id`.

## 15. Implementation Notes

The first implementation should be mostly frontend and docs:

- Add a `ProjectJourneyStepper` component.
- Rename `ReviewInboxPage` product surface to `ReviewExamplesPage`.
- Rename `SchemaEditorPage` product surface to `ExtractionRulesPage`.
- Add an `ImproveExtractorPage` backed by existing auto-research/version endpoints.
- Update `ProjectSubNav`, routes, i18n catalog, and tests.
- Update `docs/local-demo.md` and `docs/superpowers/specs/2026-05-02-overall-design.md`.

Backend changes should be limited to gaps required by the UI. The likely useful backend addition is an optional auto-research scorer wiring or a proposal-friendly response shape, but the v1 plan should first try to compose existing endpoints.

## 16. Self-Review

- No requirement asks for bbox, PDF preview, image few-shot, automatic prompt injection, or automatic publish.
- The design keeps internal DB/API names stable where that reduces risk.
- The new Improve extractor page produces proposals and requires explicit acceptance.
- The API page remains the only production-changing surface.
- The route rename has legacy redirects, so existing links and tests can transition safely.
