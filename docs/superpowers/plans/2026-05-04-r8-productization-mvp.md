# R8 Productization MVP Implementation Plan (Overlay)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Required pre-read** before any phase:
> - `CLAUDE.md` — current red lines and milestone map
> - `docs/superpowers/specs/2026-05-02-overall-design.md` — single source of truth, especially §1.0, §2.1, §3.2, §4.5, §7, §8.1–8.5, §11.1–11.4
> - `docs/superpowers/plans/2026-05-04-r7_5-productization-release-readiness.md` — backend semantics this UI consumes (`published_version_id`, contract diff, readiness, partial feedback)
> - `docs/superpowers/plans/2026-05-03-r8-ui.md` — historical / full UI plan; this overlay reuses Tasks 1–6 (foundation) verbatim and refines / replaces Tasks 7–16 with a tighter MVP scope
>
> **Relationship to the historical R8 plan**: this document is a productization-scoped *overlay*. It does **not** replace `2026-05-03-r8-ui.md`; it picks the foundation tasks from that plan, narrows the feature surface, and re-orders work around the four R7.5-anchored product surfaces (API Console, API Readiness, Review Inbox, Field Evidence). When this overlay disagrees with the historical plan, this overlay wins for R8 execution.

**Goal:** Ship an end-to-end browser product on top of R1–R7.5 backends that demonstrates the four MVP product surfaces and the Software-3.0 feedback loop: (1) API Console with explicit publish + key reveal, (2) API Readiness Panel, (3) Review Inbox, (4) field-level evidence in Studio, (5) partial production feedback shape exposed to integrators and reusable inside Lab corrections.

**Architecture:**
- Vite 8 + React 19 + TypeScript 5.9 + Zustand 5 + react-router 6, matching `2026-05-03-r8-ui.md` Task 1 stack.
- Tailwind v3 with `darkMode: 'class'` and CSS-var semantic tokens — **no raw color classes** (`bg-gray-*`, `text-white` etc are forbidden). Token names: `bg-surface`, `bg-elevated`, `bg-muted`, `fg-primary`, `fg-muted`, `border-default`, `border-strong`, `accent-primary`, `status-success`, `status-warning`, `status-error`.
- Radix UI primitives wrapped shadcn-style under `components/ui/*`; icons from `lucide-react`.
- `react-i18next` with one English catalog at `src/i18n/locales/en.json`. Every visible string goes through `useT()`. Backend errors translate via `errors.<error_code>` envelope keys.
- Single `axios` client + `EmergeError` decoder (matches `2026-05-03-r8-ui.md` Task 5 verbatim).
- Zustand stores per concern. Async actions live inside the store.
- URL is the source of truth (`/projects/:id`, `/projects/:id/studio/:did`, `/projects/:id/api-console`, `/projects/:id/review`).

**Tech Stack:** Vite 8, React 19.2, TypeScript 5.9, Zustand 5, react-router-dom 6.26, Tailwind 3.4, Radix UI primitives, `lucide-react`, `react-pdf` (deferred — PDF preview is a placeholder in MVP), `react-i18next` 17, `axios` 1.7, `vitest` + `@testing-library/react`, `@playwright/test`.

**Out of scope for this MVP (defer to v1.1 / out of v1):**
- Schema editor chat mode (R8 historical Task 12) — form mode only.
- AutoResearch run viewer (R8 historical Task 13).
- NL-first project creation backend wiring (still UI placeholder, builtin templates + empty path are real).
- Saved named views, multi-Workspace switching UI, project clone, comparison view.
- Real PDF rendering — `react-pdf` plumbing is left to v1.1; Studio shows filename + status + page hint placeholder.
- Description Workbench lint/test-against-docs (spec §2.5 advanced features).

**MVP product priorities (drives phase ordering)** — per CLAUDE.md / R7.5 handoff:
1. API Console
2. API Readiness Panel
3. Review Inbox / feedback loop
4. Field-level evidence display
5. Walking-skeleton E2E

**Depends on:** R1 (auth + `/me`), R2 (projects + documents), R3 (versions + extract), R4 (annotations), R5 (scores + review queue + calibration), R7 (templates + api-keys + publish), R7.5 (`published_version_id`, readiness, contract-diff, partial feedback, field evidence). All of the above are landed on `r8-productization-mvp` branch as of 2026-05-04. R6 (AutoResearch) is **not** required for the MVP — the only AutoResearch surface in R8 historical plan (Task 12 chat mode) is deferred.

**Hard rules carried into UI (red lines):**
- v1 UI creates and displays only `ExtractionProject` / `project_type="extraction"`. Do **not** add MatchingProject / VerificationProject UI, routes, tabs, filters, copy, or mocks in this MVP.
- No image few-shot anywhere — Studio never offers "use this doc as example for the model".
- No bbox / coordinate UI. Field-level evidence is page + quote + rationale text only.
- API Console must communicate that the plaintext API key is shown **once**.
- API keys, tokens, provider secrets, and `backend/.env` values must not be read, printed, copied into frontend fixtures, logged, or committed. Snippets use placeholders such as `EMERGE_API_KEY` only.
- Public API surfaces published version, never active. UI must present `published_version_id` as the production pointer; `active_version_id` as the Lab/draft pointer; never collapse them.
- Counterexamples never feed runtime prompts. The partial-feedback UI explains feedback feeds AutoResearch / regression health, not next call's prompt.

---

## File Structure (delta over `2026-05-03-r8-ui.md`)

```text
frontend/
├── src/
│   ├── i18n/locales/en.json                  # extended catalog (api_console, readiness, review, evidence, feedback)
│   ├── lib/
│   │   ├── api.ts                            # from historical Task 5 (unchanged)
│   │   ├── cn.ts                             # from historical Task 4
│   │   └── format.ts                         # Intl.* helpers (date, percent, ratio)
│   ├── components/
│   │   ├── ui/*                              # Button, Input, Card, Dialog, Select, Tabs, Badge, Table, Toast (historical Task 4)
│   │   ├── ThemeToggle.tsx                   # historical Task 3
│   │   └── PageShell.tsx                     # NEW: top bar with theme toggle + workspace label + project breadcrumb
│   ├── stores/
│   │   ├── auth.ts                           # historical Task 6
│   │   ├── projects.ts                       # extended: publish/unpublish/rollback/listKeys/createKey/contractDiff
│   │   ├── documents.ts                      # historical Task 9 baseline
│   │   ├── studio.ts                         # extended for field evidence + partial corrections
│   │   ├── schema.ts                         # form-only baseline (historical Task 11)
│   │   ├── readiness.ts                      # NEW: GET /readiness
│   │   └── review.ts                         # NEW: GET /review-queue
│   ├── pages/
│   │   ├── Login.tsx                         # historical Task 6
│   │   ├── Register.tsx                      # historical Task 6
│   │   ├── ProjectList.tsx                   # historical Task 7 (with published-status badge)
│   │   ├── ProjectCreate.tsx                 # historical Task 8 (NL textarea is placeholder text only)
│   │   ├── DocumentList.tsx                  # extended: Review Inbox banner + Readiness header
│   │   ├── Studio.tsx                        # extended: field evidence popover + report-wrong (partial feedback)
│   │   ├── SchemaEditor.tsx                  # form mode only
│   │   ├── ReviewInbox.tsx                   # NEW: Review Inbox dedicated page (also embedded as banner on DocumentList)
│   │   └── ApiConsole.tsx                    # NEW: replaces historical PublishFlow.tsx
│   └── __tests__/                            # vitest specs
└── e2e/
    └── walking_skeleton.spec.ts              # extended to walk through API Console + Readiness
```

Tests created or extended in this overlay:

```text
frontend/src/__tests__/
├── readiness_panel.test.tsx
├── review_inbox.test.tsx
├── api_console.test.tsx
├── api_key_reveal_modal.test.tsx
├── field_evidence_popover.test.tsx
├── report_wrong_dialog.test.tsx
└── partial_feedback_payload.test.ts
frontend/e2e/
├── auth.spec.ts                              # historical Task 6
└── walking_skeleton.spec.ts                  # extended in R8.7
```

---

## Phase R8.0 — Frontend foundation reuse from historical R8

**Objective:** Stand up the frontend skeleton + the §11 cross-cutting layers (Vite/TS, i18n, theme tokens, base components, axios+EmergeError, auth pages). This phase **executes historical R8 Tasks 1–6 verbatim** — no scope changes from `2026-05-03-r8-ui.md`. Reproducing the code blocks here would diverge over time; instead, follow the historical plan tasks one-for-one.

**Files (created by historical tasks; do not retype here):**
- Tasks 1–6 of `docs/superpowers/plans/2026-05-03-r8-ui.md`. The full file paths are listed under each task there.

**Expected API endpoints used in this phase:**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET  /api/v1/me`

**Component / store names introduced (from historical plan):**
- Components: `ThemeProvider`, `ThemeToggle`, `Button`, `Input`, `Textarea`, `Card`, `Dialog`, `Select`, `Tabs`, `Switch`, `Badge`, `Table`/`THead`/`TR`/`TH`/`TD`.
- Stores: `useAuth`.
- Pages: `LoginPage`, `RegisterPage`.
- Hooks: `useT`, `useTheme`.
- Utilities: `cn`, `EmergeError`, `setAuthToken`, `api`.

**Tests to write (from historical plan):**
- `i18n.test.tsx`, `theme.test.tsx`, `button.test.tsx`, `api.test.ts` (all detailed in historical Tasks 2–5).
- Auth pages: smoke `auth.spec.ts` Playwright spec from historical Task 6.

**Commands to run (per task; all `cd frontend` first):**
- `npm install`
- `npm run build` — boot smoke after Task 1
- `npm test` — vitest after each of Tasks 2–6

**Commit messages (one per historical task; reuse verbatim):**
- `chore(frontend): bootstrap Vite + React 19 + TS + Vitest skeleton`
- `feat(frontend): i18n setup with English catalog and useT hook`
- `feat(frontend): light/dark/system theme with CSS-var token system`
- `feat(frontend): base Radix-wrapped components with token-only styling`
- `feat(frontend): axios client + EmergeError envelope decoder`
- `feat(frontend): auth store + login/register pages + auth gate`

**Acceptance criteria for R8.0:**
- `cd frontend && npm test` passes 4 specs (i18n, theme, Button, api).
- `cd frontend && npm run dev` boots `/login` in light + dark mode.
- Register a fresh user via the UI → JWT persisted to `localStorage.emerge.token` → `/projects` placeholder renders behind `<AuthGate>`.
- No raw `bg-gray-*`, `text-white`, `text-black`, `bg-white`, `bg-black` strings in `frontend/src/**/*.tsx` (grep guard, run as part of CI later — for the MVP a manual `rg` is enough).
- Catalog `en.json` contains the `auth.*`, `errors.*`, `common.*` namespaces (historical Task 2 listing).

**R8.0 deliberate non-features** (kept exactly as historical plan defines):
- Workspace switcher is hidden when the user belongs to one workspace.
- No SSE handler yet — extraction trigger blocks until response then re-fetches.
- No router-level error boundary.

---

## Phase R8.1 — Product shell: project list, document list, minimal Studio

**Objective:** Hand the user the Software-3.0 walking path: see projects, open one, see documents, click a row, edit JSON, save correction. This narrows historical Tasks 7–11 to the smallest surface that is honest about R7.5 semantics.

### R8.1.a Project list with `published` badge

**Files:**
- Modify (extend historical Task 7): `frontend/src/stores/projects.ts`
- Modify (extend historical Task 7): `frontend/src/pages/ProjectList.tsx`
- Create: `frontend/src/__tests__/project_list_published_badge.test.tsx`

The `Project` type in the store must include `published_version_id`, `api_code`, and `api_published_at` (already returned by `ProjectOut` per `backend/app/schemas/project.py`). The list page renders one badge per row:
- "Published" (status `success`) when `api_published_at != null && published_version_id != null`.
- "Draft" (muted) otherwise.

**Expected API endpoints:**
- `GET /api/v1/projects` → `list[ProjectOut]`

**Component / store names:**
- Store: `useProjects` (extended).
- Component: `<PublishedBadge published>` rendering `<Badge>` with `accent-primary` (published) or `border-default` muted (draft).

**Tests to write:**
- `project_list_published_badge.test.tsx`: seed `useProjects.setState({ rows: [...one published, one draft...] })`, assert exactly one "Published" and one "Draft" badge.

**Commands to run:**
- `cd frontend && npm test -- project_list`

**Commit message:**
- `feat(frontend): project list shows published/draft status from R7.5 pointer`

**Acceptance criteria:**
- A project with `api_published_at !== null` renders the Published badge; a project with `api_published_at === null` renders Draft.
- Clicking any row routes to `/projects/:id`.

### R8.1.b Project create dialog (Docs+NL placeholder + builtins + empty)

**Files:**
- Create: `frontend/src/stores/templates.ts`
- Create: `frontend/src/types/schema.ts` (manual mirror of backend `SchemaField`)
- Create: `frontend/src/pages/ProjectCreate.tsx`
- Modify: `frontend/src/App.tsx` (route `/projects/new`)
- Create: `frontend/src/__tests__/project_create.test.tsx`

NL-first onboarding from spec §2.1 is a *placeholder* in MVP: textarea is wired to no-op (with helper text "NL-first onboarding lands in v1.1"). Real flow uses (a) builtin templates → `POST /api/v1/projects { name, template_id }`; (b) Empty project → `POST /api/v1/projects { name, template_id: null }`.

**Expected API endpoints:**
- `GET  /api/v1/templates`
- `POST /api/v1/projects`

**Component / store names:**
- Store: `useTemplates` with `rows`, `load()`.
- Page: `ProjectCreatePage`.
- Type: `SchemaField` (mirrors backend `app/schemas/schema_field.py`).

**Tests to write:**
- `project_create.test.tsx`: seed `useTemplates.setState({ rows: [...one builtin japan_receipt...] })`; render; assert builtin name visible; assert "Empty project" button visible.

**Commands to run:**
- `cd frontend && npm test -- project_create`

**Commit message:**
- `feat(frontend): project creation dialog with builtin templates + empty path`

**Acceptance criteria:**
- 5 builtin templates (`china_vat`, `us_invoice`, `japan_receipt`, `de_rechnung`, `custom_blank`) appear when backend has them seeded.
- Clicking a builtin creates project with `template_id`; clicking "Empty project" creates with `template_id=null`; both navigate to `/projects/:newId`.

### R8.1.c Document list (no Inbox / Readiness yet)

**Files:**
- Create: `frontend/src/stores/documents.ts`
- Create: `frontend/src/pages/DocumentList.tsx`
- Modify: `frontend/src/App.tsx` (route `/projects/:id`)
- Create: `frontend/src/__tests__/document_list.test.tsx`

This task is the historical Task 9 reduced to **table + upload + extract** only. Filters / Inbox / Readiness header land in later phases.

**Expected API endpoints:**
- `GET  /api/v1/projects/{project_id}/documents`
- `POST /api/v1/projects/{project_id}/documents` (multipart files[])
- `POST /api/v1/projects/{project_id}/extract` (SSE — MVP just `await` then re-fetch)

**Component / store names:**
- Store: `useDocuments` with `rows`, `load(projectId)`, `upload(projectId, files)`, `triggerExtract(projectId)`.
- Page: `DocumentListPage`.

**Tests to write:**
- `document_list.test.tsx`: seed rows, assert filename + status columns; assert clicking row navigates to `/projects/:id/studio/:did`.

**Commands to run:**
- `cd frontend && npm test -- document_list`

**Commit message:**
- `feat(frontend): document list with upload + extract trigger`

**Acceptance criteria:**
- Upload multi-file → rows appear with `status=uploaded`.
- "Re-extract remaining" → after fetch, rows transition to `status=extracted` (or `errored`).
- Click row navigates to Studio.

### R8.1.d Minimal Studio (correction save, no evidence, no schema editor side panel)

**Files:**
- Create: `frontend/src/stores/studio.ts`
- Create: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/App.tsx` (route `/projects/:id/studio/:did`)
- Create: `frontend/src/__tests__/studio_save.test.tsx`

Studio loads the document detail (latest_prediction + latest_annotation), seeds `draft` from latest annotation if present else latest prediction, and saves `POST /annotations`. PDF preview is a `Card` placeholder that displays `filename`, `mime_type`, `page_count` only. **Field evidence popover is added in R8.5; report-wrong dialog is added in R8.6**.

**Expected API endpoints:**
- `GET  /api/v1/projects/{project_id}/documents/{document_id}` → `DocumentDetailOut`
- `POST /api/v1/projects/{project_id}/documents/{document_id}/annotations` → `AnnotationOut`

**Component / store names:**
- Store: `useStudio` with `doc`, `draft`, `load(pid, did)`, `setDraft(next)`, `save(pid)`.
- Page: `StudioPage`.

**Tests to write:**
- `studio_save.test.tsx`: seed `useStudio.setState` with a one-entity prediction; render; edit a field's input; click "Save correction"; assert `api.post` called with the patched output.

**Commands to run:**
- `cd frontend && npm test -- studio_save`

**Commit message:**
- `feat(frontend): minimal Studio with correction save`

**Acceptance criteria:**
- Loading `/projects/:id/studio/:did` fetches document detail and seeds entity cards from `latest_prediction.output` (or annotation override).
- Editing a field updates `draft`; clicking "Save correction" sends a `POST /annotations` with the `output` array and `parent_prediction_id`.
- After save, the page re-fetches and the new annotation seed is reflected.

### R8.1.e Schema editor (form mode only)

**Files:**
- Create: `frontend/src/stores/schema.ts`
- Create: `frontend/src/pages/SchemaEditor.tsx`
- Modify: `frontend/src/App.tsx` (route `/projects/:id/schema`)
- Create: `frontend/src/__tests__/schema_editor.test.tsx`

Reuse historical Task 11 verbatim. **Do not implement chat mode** (historical Task 12 is deferred to v1.1 — it depends on R6 + a not-yet-shipped researcher entry that accepts free-text user prompts).

**Expected API endpoints:**
- `GET   /api/v1/projects/{project_id}/versions/active`
- `GET   /api/v1/projects/{project_id}/lock-status`
- `PATCH /api/v1/projects/{project_id}/schema`
- `POST  /api/v1/projects/{project_id}/lock`
- `POST  /api/v1/projects/{project_id}/unlock`

**Component / store names:**
- Store: `useSchema` with `active`, `lockStatus`, `load(pid)`, `loadLockStatus(pid)`, `save(pid, schema, notes, modelId)`, `lock(pid)`, `unlock(pid)`.
- Page: `SchemaEditorPage`.

**Tests to write:**
- `schema_editor.test.tsx`: seed `useSchema.setState({ active: { ...one field... } })`; render; assert field name input is editable; assert lock button visible when not locked.

**Commands to run:**
- `cd frontend && npm test -- schema_editor`

**Commit message:**
- `feat(frontend): schema editor form mode with lock/unlock`

**Acceptance criteria:**
- Field name / description / required all editable; "Save" calls `PATCH /schema`.
- Lock state is visible in the page header.
- `GET /lock-status` reason is visible when the schema cannot be locked. The Lock button either disables with the backend reason or surfaces the 409 reason from `POST /lock`; it must not pretend a fresh project can lock immediately.
- Locked state flips Lock button → Unlock after the backend accepts `POST /lock`; unlocked → Lock after `POST /unlock`.

### R8.1 phase exit criteria

- `cd frontend && npm test` — all R8.0 + R8.1 specs green.
- Manual: register → create from a non-empty builtin such as `japan_receipt` → upload 2 PDFs → re-extract → click row → edit → save → re-open → annotation override visible. `custom_blank` is still valid for schema-authoring, but it is not the recommended extraction smoke path.
- `/projects/:id/schema` shows lock-status; after at least 2 saved corrections with a stable field set, lock/unlock works.

---

## Phase R8.2 — API Console + Publish Flow + API key reveal modal

**Objective:** Replace historical Task 14 (`PublishFlow.tsx`) with a richer **API Console** page that owns publishing, version pointers, contract diff, key management, and key reveal. This is **MVP priority #1** per CLAUDE.md.

### R8.2.a Projects store extensions for publish-side surfaces

**Files:**
- Modify: `frontend/src/stores/projects.ts`
- Create: `frontend/src/__tests__/projects_store_publish.test.ts`

Add to the existing `useProjects` store (or split a `useApiConsole` store — choose one based on file size; if `projects.ts` exceeds ~200 lines, split):

- `publish(projectId, api_code, projectVersionId?)` → `POST /api/v1/projects/{pid}/publish` body `{ api_code, project_version_id? }` → returns `ProjectOut`
- `unpublish(projectId)` → `POST /api/v1/projects/{pid}/unpublish` → returns `ProjectOut`
- `rollback(projectId, projectVersionId)` → `POST /api/v1/projects/{pid}/rollback` body `{ project_version_id }` → returns `ProjectOut`
- `loadContractDiff(projectId, fromVersionId?, toVersionId?)` → `GET /api/v1/projects/{pid}/contract-diff?from_version_id&to_version_id` → returns `ContractDiffOut`
- `listKeys(projectId)` → `GET /api/v1/projects/{pid}/api-keys` → `list[ApiKeyOut]`
- `createKey(projectId, name)` → `POST /api/v1/projects/{pid}/api-keys` body `{ name }` → returns `ApiKeyOnceOut` (`{ id, prefix, name, key }`) — caller MUST surface the plaintext `key` exactly once.
- `revokeKey(projectId, keyId)` → `DELETE /api/v1/projects/{pid}/api-keys/{key_id}` → returns `ApiKeyOut`

The store action that creates a key must **not** persist the plaintext `key` anywhere — it returns it in the resolved promise and the caller (the dialog) holds it in component state until dismissed.

**Tests to write:**
- `projects_store_publish.test.ts`: mock `api.post`, call `useProjects.getState().publish(1, "japan-receipts")`, assert URL + body. Same for `createKey` — assert returned promise resolves with the plaintext key shape.

**Commands to run:**
- `cd frontend && npm test -- projects_store_publish`

**Commit message:**
- `feat(frontend): publish/keys store actions for API Console`

**Acceptance criteria:**
- `publish` accepts optional `projectVersionId`; defaulting to backend default (`active_version_id`) when omitted.
- `createKey` returns the `key` plaintext to the caller exactly once; the store does not retain it on subsequent reads.

### R8.2.b API key reveal modal (one-time copy)

**Files:**
- Create: `frontend/src/components/ApiKeyRevealModal.tsx`
- Create: `frontend/src/__tests__/api_key_reveal_modal.test.tsx`

The modal shows the key in a `<code>` block, a Copy button (uses `navigator.clipboard.writeText`), and a strong warning ("This key is shown only once. Save it in your secrets manager now."). The modal cannot be dismissed without an explicit "I have copied it" confirmation; the close (X) is hidden until that checkbox is toggled. Theme-tested in light + dark.

**Expected API endpoints:** none (modal is purely a presentation surface for what `createKey` returned).

**Component / store names:**
- Component: `<ApiKeyRevealModal open onConfirmDismiss apiKey>` — props: `apiKey: { id, prefix, name, key }`, `open: boolean`, `onConfirmDismiss(): void`.

**Tests to write:**
- `api_key_reveal_modal.test.tsx`:
  1. Renders the plaintext key.
  2. The dismiss button is disabled until the user checks "I have copied it".
  3. Clicking Copy calls `navigator.clipboard.writeText` (mocked) with the plaintext.
  4. Aria role is `dialog`; copy button has `aria-label`.

**Commands to run:**
- `cd frontend && npm test -- api_key_reveal_modal`

**Commit message:**
- `feat(frontend): one-time API key reveal modal with copy + ack`

**Acceptance criteria:**
- The modal *cannot* be dismissed without ack; clipboard write is wired; the warning copy is present and uses `text-status-warning` token.
- After dismiss, the parent component never sees the plaintext again (verified by component test).

### R8.2.c API Console page

**Files:**
- Create: `frontend/src/pages/ApiConsole.tsx`
- Modify: `frontend/src/App.tsx` (route `/projects/:id/api-console`)
- Create: `frontend/src/__tests__/api_console.test.tsx`

Layout (top → bottom):

1. **Header**: project name + current `api_code` + Published / Draft badge.
2. **Versions block**: two side-by-side cards
   - "Production API version (`published_version_id`)" — version number + locked state + activated date.
   - "Lab / draft version (`active_version_id`)" — version number + locked state.
   These two pointers are *never* collapsed; UI labels them per spec §7.2 / §8.5.
3. **Contract diff block**: a `<Tabs>`-less inline panel that shows `loadContractDiff(pid, published_version_id, active_version_id)` items. Each item is a row: severity badge (breaking → `status-error`, non_breaking → `status-success`) + `kind` + `field_name` + `message`. If `has_breaking_changes`, a banner warns the user above the Activate-for-API button.
4. **Activate version for API** action: button bound to `publish(pid, api_code, project.active_version_id)` (the publish endpoint validates lock + same-project). On 409 (active not locked, schema empty) the surfaced `EmergeError` translates via `errors.<code>` into a friendly "Lock the schema first." banner.
5. **API code rename**: input + Save → calls the publish endpoint with `newApiCode` **and an explicit version pointer**. If the project is already published, pass `project.published_version_id` so a rename does not accidentally activate the Lab `active_version_id`; if there is no published pointer yet, pass the locked `active_version_id` as part of the first publish.
6. **Rollback**: a select of locked previous versions (`GET /versions` filtered by `locked=true`, current published excluded) + a Rollback button → `rollback(pid, versionId)`.
7. **Unpublish** danger button → `unpublish(pid)`.
8. **API keys table**: list of `ApiKeyOut` with prefix, name, last_used_at, created_at + Revoke button per row + "Create key" button which calls `createKey(pid, name)` and opens `<ApiKeyRevealModal>` with the response.
9. **Snippets**: static curl + Python + JS blocks templated against `api_code`. (No string interpolation of plaintext keys — snippets use `EMERGE_API_KEY` env placeholder.)
10. **Feedback example**: collapsed `<details>` panel showing the partial-feedback JSON shape (the same shape implemented in R8.6). Read-only docs.

**Expected API endpoints:**
- `GET  /api/v1/projects/{pid}` (refresh after publish/unpublish/rollback)
- `GET  /api/v1/projects/{pid}/versions`
- `GET  /api/v1/projects/{pid}/contract-diff`
- `POST /api/v1/projects/{pid}/publish`
- `POST /api/v1/projects/{pid}/unpublish`
- `POST /api/v1/projects/{pid}/rollback`
- `GET  /api/v1/projects/{pid}/api-keys`
- `POST /api/v1/projects/{pid}/api-keys`
- `DELETE /api/v1/projects/{pid}/api-keys/{kid}`

**Component / store names:**
- Page: `ApiConsolePage`.
- Local sub-components (single-file unless they exceed ~80 lines): `<ContractDiffList items has_breaking_changes>`, `<KeysTable rows onRevoke onCreate>`, `<VersionPointerCard label version locked activatedAt>`, `<SnippetsPanel apiCode>`.
- Store: `useProjects` (extended in R8.2.a). No new store unless file size demands a split.

**Tests to write:**
- `api_console.test.tsx`:
  1. Renders both pointers from a seeded project where `published_version_id !== active_version_id`.
  2. Renders contract-diff items with severity badges.
  3. Clicking "Create key" opens the reveal modal; mocking `createKey` returns a key; modal shows the plaintext.
  4. Activate button is disabled when `active.locked === false`.
  5. After revoke, the row disappears from the table.

**Commands to run:**
- `cd frontend && npm test -- api_console`

**Commit message:**
- `feat(frontend): API Console with publish, contract diff, keys, rollback`

**Acceptance criteria:**
- Page surfaces both `published_version_id` and `active_version_id` distinctly with spec §7.2 / §8.5 product labels ("Production API version" / "Lab / draft version").
- Activate-for-API button is gated on schema lock; backend 409 → friendly translated error banner; on success the published pointer updates and the page re-fetches.
- API code rename for an already-published project keeps `published_version_id` unchanged unless the user explicitly clicks Activate-for-API for a different locked version.
- API key reveal modal is the **only** path to obtain the plaintext key; reload of the API Console only shows prefix.
- Rollback only lists locked versions other than the currently published one.

### R8.2 phase exit criteria

- `npm test` green for R8.0–R8.2.
- Manual flow: lock active version → Activate for API → key create → modal shows plaintext → dismiss → reload → key prefix only → Revoke → row gone → Unpublish → public extract returns 403 (verified via `curl`).

---

## Phase R8.3 — API Readiness Panel

**Objective:** Render `GET /api/v1/projects/{pid}/readiness` as the project page's product-facing trust surface, replacing any "raw confidence number" placeholder. Mounted as the **DocumentList page header** and reused inside the API Console "Readiness summary" section.

**Files:**
- Create: `frontend/src/stores/readiness.ts`
- Create: `frontend/src/components/ReadinessPanel.tsx`
- Modify: `frontend/src/pages/DocumentList.tsx` (mount at top)
- Modify: `frontend/src/pages/ApiConsole.tsx` (mount near publish action)
- Create: `frontend/src/__tests__/readiness_panel.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json` (`readiness.*`, `readiness.warnings.*`, `readiness.publish_blockers.*`)

Layout per spec §4.5:

```text
┌─ API Readiness ───────────────────────────────────────────────────────┐
│ Quality 86% ± 8% (28 obs · vibe-check 12)                             │
│ Evidence  12 docs · 48 entities · 134 fields reviewed (62% w/ evidence)│
│ Schema    Lock candidate · 0 breaking changes in last 5               │
│ Regression 7 / 8 passing   (or "No production feedback yet")          │
│ Risky     tax_id (3) · currency (2)                                   │
│                                                                       │
│ ⚠  No production feedback yet — readiness here reflects Lab evidence  │
│    only. The first integrator call will populate regression data.     │
│                                                                       │
│ Publish blockers: empty_schema  ·  active_version_unlocked            │
└───────────────────────────────────────────────────────────────────────┘
```

Hard product rules captured in the panel:
- When `regression_health.counterexamples_total === 0`, show "No production feedback yet" — never "100%".
- Quality always shows a CI band: `point% ± half-CI%` plus `(N obs · vibe-check K)`.
- Risky fields are sorted by count desc; top 5 only; rest collapsed under "+N more".
- `publish_blockers` and `warnings` are translated via `errors.readiness.<key>` namespace; every key from `backend/app/services/readiness.py` is enumerated in `en.json` (see backend gaps below).

**Expected API endpoints:**
- `GET /api/v1/projects/{pid}/readiness` → `APIReadinessOut`

**Component / store names:**
- Store: `useReadiness` with `data: APIReadinessOut | null`, `loading`, `load(projectId)`.
- Component: `<ReadinessPanel projectId>` — fetches on mount + on `projectId` change.
- Sub-components: `<QualityBlock>`, `<EvidenceBlock>`, `<MaturityBlock>`, `<RegressionBlock>`, `<RiskyFieldsBlock>`, `<BlockersAndWarnings>`.
- Type mirror: `APIReadinessOut` in `frontend/src/types/readiness.ts` matching `backend/app/schemas/readiness.py`.

**Tests to write:**
- `readiness_panel.test.tsx`:
  1. Counterexamples = 0 → renders "No production feedback yet" and **does not** render a `100%` string.
  2. CI band is rendered as `<point>% ± <half>%` with `observation_count` visible.
  3. Risky fields list shows top 5 only with "+N more" affordance for excess.
  4. Each `publish_blockers[*]` resolves to a translated string (no raw `empty_schema` slug visible to user).
  5. Component renders correctly in both light and dark themes (smoke render test).

**Commands to run:**
- `cd frontend && npm test -- readiness_panel`

**Commit message:**
- `feat(frontend): API Readiness panel with CI band and no-feedback semantics`

**Acceptance criteria:**
- Mounted at the top of `/projects/:id` and inside `/projects/:id/api-console`.
- All `regression_health.status` values (`no_production_feedback`, `passing`, `failing`, `unknown`) render distinct copy.
- All `schema_maturity.status` values (`draft`, `stabilizing`, `lock_candidate`, `locked`) render distinct copy.
- Component never shows `100%` or `score = 1.0` when `counterexamples_total === 0` (test enforced).
- All blocker / warning slugs from `services/readiness.py` are present in `en.json`. (See "Backend gaps" — the canonical slug list must be enumerated; missing slug → fallback to humanised slug, but a console.warn is emitted in dev to catch drift.)

### R8.3 phase exit criteria

- `npm test` green for R8.0–R8.3.
- Manual: a fresh empty project shows blockers `active_version_unlocked`, `empty_schema`, and `schema_not_lock_candidate`; after a non-empty schema is stable, locked, and published, blockers clear; with no counterexamples, "No production feedback yet" persists.

---

## Phase R8.4 — Review Inbox

**Objective:** Surface `GET /api/v1/projects/{pid}/review-queue` as the **first thing the user sees** on the project page (spec §8.1) — `Required review`, `Spot-check`, `All`. MVP priority #3.

**Files:**
- Create: `frontend/src/stores/review.ts`
- Create: `frontend/src/components/ReviewInboxBanner.tsx`
- Create: `frontend/src/pages/ReviewInbox.tsx`
- Modify: `frontend/src/pages/DocumentList.tsx` (mount banner above table)
- Modify: `frontend/src/App.tsx` (route `/projects/:id/review`)
- Create: `frontend/src/__tests__/review_inbox.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json` (`review.*`)

Two surfaces sharing the same store:

1. **Banner** on `DocumentList` (`<ReviewInboxBanner projectId>`):
   ```
   Review Inbox
   7 need review · 2 spot-checks · 134 docs total
   [Review next]
   ```
   The "Review next" button navigates to the first item in `required_review` (or `spot_check` if `required_review` empty), opening Studio at `/projects/:id/studio/:did`.

2. **Dedicated page** `/projects/:id/review` (`ReviewInbox.tsx`):
   - Three sections: Required review (`required_review`), Spot-check (`spot_check`), All (`all`).
   - Each row shows filename + flagged_fields (already capped at 3 by backend).
   - Click row → Studio for that doc.

Note: review queue items only carry `id, filename, flagged_fields`. The MVP banner does **not** need entity counts or per-doc score — those live on the DocumentList table itself (already R8.1.c) and on the Readiness Panel (R8.3).

**Expected API endpoints:**
- `GET /api/v1/projects/{pid}/review-queue` → `ReviewQueueOut`

**Component / store names:**
- Store: `useReview` with `queue: ReviewQueueOut | null`, `loading`, `load(projectId)`.
- Components: `<ReviewInboxBanner projectId>`, `<ReviewInboxPage>` (renders three sections with `<Card>` per row).
- Type mirror: `ReviewItemOut`, `ReviewQueueOut` in `frontend/src/types/review.ts`.

**Tests to write:**
- `review_inbox.test.tsx`:
  1. Banner renders the three counts.
  2. "Review next" routes to `required_review[0].id` Studio path; if `required_review.length === 0`, falls back to `spot_check[0]`.
  3. Page renders three sections with the right ids.
  4. Empty queue: banner shows "All caught up" copy and "Review next" is disabled.

**Commands to run:**
- `cd frontend && npm test -- review_inbox`

**Commit message:**
- `feat(frontend): Review Inbox banner and page from /review-queue`

**Acceptance criteria:**
- Banner is on top of `/projects/:id` DocumentList.
- Page at `/projects/:id/review` shows all three sections.
- Clicking any item enters Studio.
- Empty queue states are explicit (no spinner, no "0 of 0 ...").

### R8.4 phase exit criteria

- `npm test` green for R8.0–R8.4.
- Manual: trigger judge run → some doc gets `down`/`uncertain` field → reload `/projects/:id` → Required review count increments → click "Review next" → Studio opens that doc.

---

## Phase R8.5 — Field Evidence display in Studio

**Objective:** Wire `latest_prediction.per_field_evidence` to a per-field Evidence popover in Studio (spec §8.2 evidence requirement). MVP priority #4.

> ⚠ **Backend gap to resolve as R8.5 Step 0** — see "Backend gaps" section. The current `GET /api/v1/projects/{pid}/documents/{did}` payload constructed in `backend/app/api/routes/documents.py` does **not** include `per_field_evidence` or `per_field_confidence` in `latest_prediction`. Either expand the dict literal in that route or add a sibling endpoint. R8.5 Step 0 below makes the change directly in the documents route.

### R8.5.0 Backend: surface field evidence + confidence in document detail

**Files:**
- Modify: `backend/app/api/routes/documents.py` (extend the `latest_prediction` payload dict)
- Create or extend: `backend/tests/test_document_detail_evidence.py`

Add `per_field_evidence` and `per_field_confidence` to the dict literal at `backend/app/api/routes/documents.py:89-99` so it becomes:

```python
payload["latest_prediction"] = (
    {
        "id": latest.id,
        "output": latest.output,
        "status": latest.status,
        "model_id": latest.model_id,
        "tokens_used": latest.tokens_used,
        "error_message": latest.error_message,
        "per_field_confidence": latest.per_field_confidence,
        "per_field_evidence": latest.per_field_evidence,
    }
    if latest
    else None
)
```

The data shape is JSON `{ "<entity_idx>": { "<field>": { page, quote, rationale, source_text_hash? } } }` per R7.5 spec §3.2 — **no bbox, coordinates, or visual regions** must appear here.

**Expected behavior:**
- Endpoint already exists; only payload composition changes.
- `DocumentDetailOut.latest_prediction` is `dict | None`, so adding keys is non-breaking.

**Tests to write (backend):**
- `test_document_detail_evidence.py`: create a Prediction with `per_field_evidence={"0":{"total":{"page":1,"quote":"Total ¥1,234","rationale":"tax-included"}}}` and `per_field_confidence={"0":{"total":"down"}}`. GET document detail, assert both keys present in `latest_prediction`. Assert no `bbox`, `region`, `coordinates` keys leak.

**Commands to run:**
- `cd backend && uv run pytest tests/test_document_detail_evidence.py -v`

**Commit message:**
- `feat(api): surface per-field evidence and confidence in document detail`

**Acceptance criteria:**
- `GET /api/v1/projects/{pid}/documents/{did}` payload includes `per_field_evidence` and `per_field_confidence` under `latest_prediction`.
- No bbox / coordinate / region key shapes are introduced.

### R8.5.1 Frontend: Evidence popover + confidence chip

**Files:**
- Modify: `frontend/src/stores/studio.ts` (extend `DocDetail` types to include `per_field_evidence`, `per_field_confidence`)
- Create: `frontend/src/components/FieldEvidencePopover.tsx`
- Modify: `frontend/src/pages/Studio.tsx` (per-field row gets popover trigger + confidence chip)
- Create: `frontend/src/__tests__/field_evidence_popover.test.tsx`
- Modify: `frontend/src/i18n/locales/en.json` (`studio.evidence.*`)

The popover is opened via a small Lucide `Quote` icon button next to each field row. Content:

```
Page 1
"Total ¥1,234"

Rationale
Used the tax-included total line.
```

If no evidence exists for a field: button is hidden. If evidence exists for the entity but not the field: button is hidden. If evidence has only a `rationale` and no `page`/`quote`: render rationale only; do not render an empty page line.

Confidence chip uses the same per-field map: `up` → no chip; `uncertain` → muted "uncertain" chip with `bg-muted`; `down` → `status-warning` chip "needs review".

**Hard rules** the component enforces (also in tests):
- The popover **never renders coordinate keys** even if backend leaks them (defense in depth: drop unknown keys client-side; emit `console.warn` in dev).
- No way to draw on the document.

**Expected API endpoints:**
- `GET /api/v1/projects/{pid}/documents/{did}` (already loaded by Studio).

**Component / store names:**
- Component: `<FieldEvidencePopover entityIndex fieldName evidenceMap>` (props: `evidenceMap: Record<string, Record<string, FieldEvidence>>` typed mirror of `per_field_evidence`).
- Component: `<ConfidenceChip verdict>` (props: `'up' | 'down' | 'uncertain' | undefined`).
- Type: `FieldEvidence` in `frontend/src/types/studio.ts`.

**Tests to write:**
- `field_evidence_popover.test.tsx`:
  1. With `evidenceMap[0].total = { page: 1, quote: "Total ¥1,234", rationale: "..." }`, popover opens and renders all three.
  2. With only `rationale` set, page/quote not rendered (no empty `Page` line).
  3. With no entry for field, the trigger button is not rendered.
  4. If backend leaks `bbox: [...]`, the popover does not render any coordinate; dev console.warn fires (assert via spy).
  5. ConfidenceChip: `down` shows warning style; `up` renders nothing; `uncertain` renders muted chip.

**Commands to run:**
- `cd frontend && npm test -- field_evidence_popover`

**Commit message:**
- `feat(frontend): Studio per-field evidence popover and confidence chip`

**Acceptance criteria:**
- Studio per-field rows show evidence button when evidence exists.
- Popover renders only `page`, `quote`, `rationale` (and never bbox-like keys, even if leaked).
- `down`/`uncertain` verdicts show a chip; `up` is silent.
- Light + dark theme rendering verified.

### R8.5 phase exit criteria

- `cd backend && uv run pytest tests/test_document_detail_evidence.py -v` green; full backend test suite still green.
- `cd frontend && npm test` green for R8.0–R8.5.
- Manual: a prediction with field evidence + verdicts → Studio shows quote popover + warning chip; a prediction without evidence → no popover; no bbox UI surfaces anywhere.

---

## Phase R8.6 — Partial Feedback UI (public shape exposed + in-Lab reuse)

**Objective:** Render the **partial feedback** payload shape (`{ request_id, corrections: [{entity_index, field_path, correct_value, comment}], issue_type, notes }`) in two places, both backed by `POST /extract/{api_code}/feedback`:

A. **API Console feedback example panel** (read-only docs + interactive "Send test feedback" form keyed by an existing API key).
B. **Studio "Report wrong field" dialog** that constructs the same JSON shape so users learn the contract — but in-Lab the dialog routes the same payload to `POST /annotations` (or to the public feedback endpoint, depending on key availability) so the developer experience is consistent across Lab and integration.

This phase intentionally reuses the existing partial-feedback contract (`backend/app/schemas/annotation.py FeedbackIn` + `apply_feedback_corrections`) — no new backend endpoints.

### R8.6.a Shared payload builder + serializer test

**Files:**
- Create: `frontend/src/lib/feedback.ts`
- Create: `frontend/src/__tests__/partial_feedback_payload.test.ts`

The module exports:

```ts
export type FeedbackIssueType =
  | "wrong_value" | "missing_field" | "extra_field" | "wrong_entity_count" | "other";

export interface FeedbackCorrection {
  entity_index: number;
  field_path: string;            // dotted with optional [n] indices, e.g. "line_items[2].price"
  correct_value: unknown;
  comment?: string;
}

export interface PartialFeedbackPayload {
  request_id: number;
  corrections: FeedbackCorrection[];
  issue_type?: FeedbackIssueType;
  notes?: string;
}

export function buildPartialFeedback(args: {
  predictionId: number;
  corrections: FeedbackCorrection[];
  issueType?: FeedbackIssueType;
  notes?: string;
}): PartialFeedbackPayload;

export function fieldPathFor(entityIndex: number, key: string, arrayIndex?: number): string;
```

`fieldPathFor` produces the dotted form (e.g. `"line_items[2].price"`), matching `backend/app/services/corrections.apply_feedback_corrections`.

**Tests to write:**
- `partial_feedback_payload.test.ts`:
  1. `fieldPathFor(0, "total")` → `"total"`.
  2. `fieldPathFor(0, "line_items", 2)` returns the leaf path piece `"line_items[2]"`; combined dotted form `"line_items[2].price"` works when chained.
  3. `buildPartialFeedback` enforces `request_id` is a positive int; throws if `corrections` is empty.
  4. `issue_type` only accepts the five literal values from the backend pydantic Literal.

**Commands to run:**
- `cd frontend && npm test -- partial_feedback_payload`

**Commit message:**
- `feat(frontend): partial feedback payload builder and types`

**Acceptance criteria:**
- The builder emits payloads bytes-equal to what backend `FeedbackIn` accepts (verified by a backend pydantic-validate round-trip in a follow-up integration test if convenient; otherwise rely on the unit test + R8.7 walking skeleton).

### R8.6.b API Console feedback example + interactive test form

**Files:**
- Modify: `frontend/src/pages/ApiConsole.tsx` (add feedback section)
- Create: `frontend/src/components/FeedbackTestForm.tsx`
- Modify: `frontend/src/i18n/locales/en.json` (`feedback.*`, `feedback.issue_type.*`)

The feedback section has two parts:
1. **Read-only example** — a `<pre>` block showing the payload shape with placeholder values + a `curl` snippet using `EMERGE_API_KEY` env var. Always visible.
2. **Interactive test form** — only visible when at least one API key exists; the user pastes their plaintext key into a transient input (kept only in component state, never persisted). Form fields:
   - `request_id` (number; helper text: "the prediction_id returned by /extract")
   - `entity_index` (default 0)
   - `field_path` (string; placeholder `"total"` or `"line_items[2].price"`)
   - `correct_value` (string; submitted as JSON-parsed; falls back to string)
   - `comment` (optional)
   - `issue_type` (Select with the 5 backend literals)
   - `notes` (optional textarea)

   On submit: `POST /extract/{api_code}/feedback` with `X-Api-Key` header; show success toast on 200 with returned `counterexample_id`; show translated `EmergeError` on failure.

The transient API key field is **never** stored — on form unmount or successful submit, it is cleared. A helper text reminds the user "Pasted key is not saved by the UI." Component test enforces this.

**Expected API endpoints:**
- `POST /extract/{api_code}/feedback` (public; X-Api-Key header) → `{ counterexample_id }`

**Component / store names:**
- Component: `<FeedbackTestForm apiCode>` (no store — transient component state only).

**Tests to write (added to `api_console.test.tsx` + new):**
- Read-only example renders the JSON shape with the four required keys (`request_id`, `corrections`, `issue_type`, `notes`).
- Form mount + submit: mock `axios.post`, assert URL `/extract/<code>/feedback`, header `X-Api-Key`, body matches `PartialFeedbackPayload`.
- Form unmount clears the key from internal state (assert via component test that re-mounting yields empty key field).

**Commands to run:**
- `cd frontend && npm test -- api_console`

**Commit message:**
- `feat(frontend): API Console partial-feedback example and test form`

**Acceptance criteria:**
- Example panel always visible; test form gated on existence of at least one API key.
- Plaintext key never persisted (no `localStorage`/store writes; verified).
- Successful submit shows the returned `counterexample_id` toast.

### R8.6.c Studio "Report wrong field" dialog (in-Lab use of the same shape)

**Files:**
- Create: `frontend/src/components/ReportWrongFieldDialog.tsx`
- Modify: `frontend/src/pages/Studio.tsx` (per-field "Report wrong" button)
- Modify: `frontend/src/stores/studio.ts` (`reportWrong({entityIndex, fieldPath, correctValue, issueType, notes})`)
- Create: `frontend/src/__tests__/report_wrong_dialog.test.tsx`

The dialog wraps the same builder from R8.6.a. In Lab, the user already has session JWT — there is no `X-Api-Key`. The store action posts a **regular Annotation** with the corrected output instead, by:

1. Loading the latest prediction's output;
2. Applying the single correction client-side (mirrors `apply_feedback_corrections` minimally — only needed for one path; or, for an MVP, fall back to the simpler approach of just letting the user save the whole annotation);
3. Calling `POST /api/v1/projects/{pid}/documents/{did}/annotations` with the merged output and `parent_prediction_id`.

The dialog shows the user the *equivalent* partial-feedback JSON (read-only collapsible "What integrators would send") so users learn the contract.

The dialog is opened via a small "Report wrong" affordance per field row (next to the evidence popover button from R8.5). Opening it pre-fills `entity_index`, `field_path`, and the current value; the user types the corrected value + optional comment + optional issue_type.

**Hard rules:**
- The dialog **must not** route to the public feedback endpoint from Lab — there is no API key available in Lab, and routing through the public path would require the user to copy a key, defeating the UX. Lab uses Annotations.
- The displayed JSON shape is identical to the public contract (the same builder).
- Counterexample semantics never apply in Lab (Annotations posted from Studio are `role=none`); the dialog explicitly says "This will be saved as a Lab correction. Production feedback uses the same JSON shape via /extract/<code>/feedback."

**Expected API endpoints:**
- `POST /api/v1/projects/{pid}/documents/{did}/annotations` (existing).

**Component / store names:**
- Component: `<ReportWrongFieldDialog open onOpenChange entityIndex fieldPath currentValue projectId documentId>`.
- Store action: `useStudio.getState().reportWrong({...})`.

**Tests to write:**
- `report_wrong_dialog.test.tsx`:
  1. Pre-fill: opens with the current value seeded.
  2. Submit: calls annotation POST with the patched output (single field changed), not the public feedback endpoint.
  3. The displayed "What integrators would send" JSON matches `PartialFeedbackPayload` shape with the right `field_path`.
  4. Cancel does not call any API.

**Commands to run:**
- `cd frontend && npm test -- report_wrong_dialog`

**Commit message:**
- `feat(frontend): Studio Report-wrong dialog reuses partial-feedback shape`

**Acceptance criteria:**
- A field row shows two icons in the MVP: evidence (R8.5) + report-wrong (R8.6).
- Submitting saves an Annotation visible in the latest_annotation on next reload.
- Public feedback shape is shown read-only in the dialog so the user learns the contract.

### R8.6 phase exit criteria

- `npm test` green for R8.0–R8.6.
- Manual: API Console → Send test feedback with a valid prediction_id from a recent public extract → counterexample_id returned → readiness `regression_health.counterexamples_total` increments. Separately: Studio → click "Report wrong" on a field → save → reload → annotation override visible.

---

## Phase R8.7 — Walking Skeleton E2E

**Objective:** A single Playwright spec that walks the full happy path, end-to-end, against live R1–R7.5 backend. Replaces historical Task 16 with a tighter, R7.5-aware journey.

**Files:**
- Modify: `frontend/e2e/walking_skeleton.spec.ts` (extends historical Task 16 sample)
- Create: `frontend/e2e/fixtures/sample.pdf` (any 1-page PDF)

Scenario:

1. Register a fresh user → land on `/projects`.
2. New project → non-empty builtin such as `japan_receipt` → land on `/projects/:id`. Do not use `custom_blank` for this E2E unless the test first authors and saves a non-empty schema.
3. Upload `sample.pdf` → row appears with `status=uploaded`.
4. Trigger extract → row transitions to `status=extracted` (allow 30s timeout).
5. Open Studio → edit one field → Save correction → re-open → annotation override visible. Repeat on a second uploaded document so backend lock-status has at least 2 saved corrections with a stable field set.
6. Navigate `/projects/:id/schema` → verify lock-status is passable → lock the schema.
7. Navigate `/projects/:id/api-console` → Activate-for-API → publish modal flow → key reveal modal → ack → modal closes.
8. Use the API Console "Send test feedback" form OR a `request.post` from Playwright with the freshly-revealed plaintext key + a known prediction_id from step 4 → success toast `counterexample_id`.
9. Navigate back to `/projects/:id` → ReadinessPanel `regression_health.counterexamples_total` ≥ 1.
10. Navigate `/projects/:id/review` → at least one section is non-empty (depends on whether judge has been triggered; the spec runs `POST /api/v1/projects/:id/judge` once before this step to materialise verdicts).

The test runs only when `EMERGE_E2E=1` is set, since it depends on a live backend with provider keys configured. In CI without provider, skip.

**Expected API endpoints (across the journey):**
- All of: `/api/v1/auth/*`, `/api/v1/me`, `/api/v1/projects`, `/api/v1/projects/{pid}`, `/api/v1/templates`, `/api/v1/projects/{pid}/documents`, `/api/v1/projects/{pid}/extract`, `/api/v1/projects/{pid}/documents/{did}`, `/api/v1/projects/{pid}/documents/{did}/annotations`, `/api/v1/projects/{pid}/versions/active`, `/api/v1/projects/{pid}/lock`, `/api/v1/projects/{pid}/publish`, `/api/v1/projects/{pid}/api-keys`, `/api/v1/projects/{pid}/readiness`, `/api/v1/projects/{pid}/review-queue`, `/api/v1/projects/{pid}/judge`, `/extract/{api_code}/feedback`.

**Component / store names:** none (E2E only).

**Tests to write:**
- `walking_skeleton.spec.ts` (the scenario above).

**Commands to run:**
- `cd backend && uv run uvicorn app.main:app --reload --port 8000` (in one shell)
- `cd frontend && npm run dev` (another shell)
- `cd frontend && npx playwright install` (one-time)
- `cd frontend && EMERGE_E2E=1 npm run e2e -- walking_skeleton`

**Commit message:**
- `test(frontend): walking-skeleton E2E covers publish + readiness + feedback`

**Acceptance criteria:**
- Spec passes against a live backend with provider keys.
- The `regression_health.counterexamples_total` increment is asserted via the readiness fetch.
- No bbox / coordinate selectors are queried (defense-in-depth lint of test code, manual).

### R8.7 phase exit criteria

- `EMERGE_E2E=1 npm run e2e` passes.
- All component tests still pass.
- `cd backend && uv run pytest -v` still green.

---

## Backend gaps surfaced by this overlay

| Gap | Where | Fix in this overlay |
|---|---|---|
| `latest_prediction` payload missing `per_field_evidence` and `per_field_confidence` | `backend/app/api/routes/documents.py:89-99` | R8.5.0 (small dict literal extension + test) |
| Canonical list of `publish_blockers` / `warnings` slugs returned by `services/readiness.py` is not a published enum; FE must mirror them in `errors.readiness.<slug>` keys | `backend/app/services/readiness.py` | R8.3 enumerates them in `en.json`; if drift occurs, dev `console.warn` flags it. Long-term: backend may export a `READINESS_SLUGS` enum; not blocking. |
| Studio Inline Teaching Proposal (spec §2.4) requires a backend "propose description patch from one correction" endpoint | n/a | **Out of MVP scope.** R8.6.c calls the existing Annotations route; the inline proposal flow is deferred to v1.1. |
| `versions` route filtering by `locked=true` is not currently a query parameter | `backend/app/api/routes/versions.py` | MVP filters client-side; if performance matters later, add `?locked=true`. |
| `GET /api/v1/projects/{pid}/api-keys` returns prefix only (correct), but list does not page | `backend/app/api/routes/publish.py` | MVP fine — projects are not expected to have many keys; defer pagination. |

## Ambiguities flagged for the executing agent

1. **R8.6 interpretation (in-Lab vs public)** — the user prompt asks for "Partial feedback UI using POST /extract/{api_code}/feedback shape". This overlay reads that as "use the **same JSON shape**" in two places: API Console (real public endpoint, requires plaintext API key) and Studio Report-wrong (Lab path uses Annotations). If the user intended only the public surface, drop R8.6.c (Studio dialog) and keep R8.6.a + R8.6.b.

2. **Schema editor chat mode** — historical Task 12 wires chat mode to AutoResearch, depending on R6 + a `RunIn.threshold` upper bound widening. This overlay defers chat mode entirely. Form mode covers spec §8.3 form mode and is honest about R7.5 semantics. If chat mode is a hard requirement, re-include historical Task 12 after R8.6.

3. **Real PDF preview** — Studio shows a placeholder card. `react-pdf` was in original Task 1 dependencies but real rendering is not wired. If this is a blocker, add an R8.1.f task to plumb `react-pdf` against `Document.file_path` (which the backend currently does not expose as a download URL — second backend gap; would need `GET /api/v1/projects/{pid}/documents/{did}/file`).

4. **Workspace switcher** — single-Workspace users do not see it; multi-Workspace UX is deferred. If multi-Workspace is in scope, restore historical Task 7's `<PageShell>` workspace switcher.

5. **Internationalisation drift** — every visible string must go through `useT`. If the executing agent introduces hardcoded strings, the test guard is `rg "[A-Z][a-z]+ [a-z]" frontend/src --type tsx` (heuristic; manual review in PR). Long-term: an ESLint rule.

---

## Dependency notes

| Phase | Backend slices required | Notes |
|---|---|---|
| R8.0 | R1 | Auth pages + `/me` |
| R8.1 | R2 + R3 + R4 + R7 (templates) | Walking path |
| R8.2 | R7 + R7.5 (publish/published_version_id/contract-diff/keys) | Replaces historical Task 14 |
| R8.3 | R5 + R7.5 (readiness) | New |
| R8.4 | R5 (review-queue) | New |
| R8.5 | R7.5 (field evidence storage) + small backend addition in R8.5.0 | Touches backend |
| R8.6 | R7.5 (partial feedback) + R4 (annotations) | No new backend endpoints |
| R8.7 | R1+R2+R3+R4+R5+R7+R7.5 | Live E2E |

R8.0 and R8.1 must land sequentially. R8.2 / R8.3 / R8.4 can technically run in parallel after R8.1 (different store + route surfaces), but the recommendation per CLAUDE.md priority is **R8.2 → R8.3 → R8.4 → R8.5 → R8.6 → R8.7** in series; each phase ends with a green test run + a commit, so subagent-driven execution is straightforward.

---

## Exit criteria for the entire R8 MVP

End-to-end browser flow on a fresh DB with R1–R7.5 backend:

1. `npm run dev` boots; `/login` renders in light + dark.
2. Register → `/projects` empty.
3. Create from a non-empty builtin such as `japan_receipt` → `/projects/:id` shows ReadinessPanel + Review Inbox banner + Document table. `custom_blank` is acceptable only if the user authors a non-empty schema before extraction/publish.
4. Upload + extract; rows transition to `extracted`.
5. Studio shows entity cards; field evidence popover available where evidence exists; confidence chips visible for `down`/`uncertain`.
6. Save correction → annotation override seen on reload.
7. Lock schema via `/projects/:id/schema`.
8. `/projects/:id/api-console` shows both Production and Lab pointers, contract diff, Activate-for-API, key creation modal (one-time reveal), feedback example, and "Send test feedback" form.
9. After publish + first feedback, ReadinessPanel `regression_health.counterexamples_total` is ≥ 1; the panel never says `100%` when total is 0.
10. Theme toggle works in every page in both modes.
11. `cd frontend && npm test` — all component tests pass.
12. `cd frontend && EMERGE_E2E=1 npm run e2e` — walking skeleton passes.
13. `cd backend && uv run pytest -v` — backend remains green after R8.5.0 patch.

After R8 MVP ships: v1.1 backlog (in priority order) — chat mode (historical Task 12), AutoResearch viewer (historical Task 13), real PDF preview, NL-first onboarding, Description Workbench lint/test-against-docs, multi-Workspace UX.
