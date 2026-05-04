# R8 continuation handoff — Prompt 2 onward

Generated: 2026-05-04 20:43 CST
Repo: `/Users/qinqiang02/colab/codespace/ai/emerge`
Branch to continue on: `r8-productization-mvp`

This document is a durable handoff for new Hermes / Claude Code sessions. It is intentionally **not** a replacement for the full plan. "No information loss" here means:

1. Keep the authoritative detailed task list in `docs/superpowers/plans/2026-05-04-r8-productization-mvp.md`.
2. Preserve live execution state, completed commits, red lines, phase ordering, gates, and post-MVP priorities here.
3. In a new session, read this file first, then jump into the exact phase section in the authoritative overlay plan.

---

## 0. Required pre-read in any new session

Read in this order:

1. `CLAUDE.md`
2. `docs/superpowers/plans/2026-05-04-r8-continuation-handoff.md` (this file)
3. `docs/superpowers/plans/2026-05-04-r8-productization-mvp.md` (authoritative R8 overlay)
4. For product semantics only when needed: `docs/superpowers/specs/2026-05-02-overall-design.md`
5. For historical frontend foundation details only when needed: `docs/superpowers/plans/2026-05-03-r8-ui.md`

Do **not** read, print, copy, or commit `backend/.env`, provider keys, JWTs, API key plaintext, tokens, or passwords. Snippets use placeholders such as `EMERGE_API_KEY` only.

---

## 1. Current live state

Latest confirmed state:

```text
branch: r8-productization-mvp
HEAD:   0552f74 test(frontend): stabilize theme localStorage tests
status: clean
```

R8 commits are intentionally **not** in local `main` as of the last merge check. Continue on `r8-productization-mvp` unless the user explicitly asks to merge. Do not push remote or create a remote branch unless the user explicitly asks.

Important reachability facts:

```text
b813e6f overlay plan                    in r8-productization-mvp, not in main
141adea R8.0 frontend bootstrap          in r8-productization-mvp, not in main
dbbdcdc R8.0 i18n                        in r8-productization-mvp, not in main
794e318 R8.0 theme                       in r8-productization-mvp, not in main
78b2de3 R8.0 base UI                     in r8-productization-mvp, not in main
4538284 R8.0 axios client                in r8-productization-mvp, not in main
4a269bd R8.0 auth gate                   in r8-productization-mvp, not in main
331a821 R8.0.1 lint/i18n hygiene         in r8-productization-mvp, not in main
0552f74 pre-Prompt2 theme test stabilization in r8-productization-mvp, not in main
```

Completed baseline:

```text
7aa4e0b feat(api): R7.5 publish hardening — global api_code, evidence allow-list, length, empty-schema gate
b813e6f docs: add R8 productization MVP overlay plan
141adea chore(frontend): bootstrap Vite + React 19 + TS + Vitest skeleton
dbbdcdc feat(frontend): i18n setup with English catalog and useT hook
794e318 feat(frontend): light/dark/system theme with CSS-var token system
78b2de3 feat(frontend): base Radix-wrapped components with token-only styling
4538284 feat(frontend): axios client + EmergeError envelope decoder
4a269bd feat(frontend): auth store + login/register pages + auth gate
331a821 chore(frontend): fix R8.0 lint and i18n hygiene
0552f74 test(frontend): stabilize theme localStorage tests
```

Known R7.5 backend baseline remains accepted:

```text
backend uv run pytest -v: 234 passed, 2 skipped, 4 warnings
Alembic empty DB upgrade to head: passed
```

---

## 2. R8.0.1 verification note before Prompt 2

`331a821` fixed the original lint issue and `0552f74` stabilized the Vitest/happy-dom `localStorage` setup that had caused `theme.test.tsx` to fail under this Node runtime.

Verified after `0552f74`:

```text
cd frontend && npm run lint: passed
cd frontend && npm test: 4 files / 9 tests passed
cd frontend && npm run build: passed
```

Root cause of the test issue: Node's experimental global `localStorage` was present but not a full DOM `Storage` implementation (`clear` was missing and i18next-browser-languagedetector emitted a `--localstorage-file` warning). `frontend/src/test-setup.ts` now installs a deterministic in-memory `Storage` mock on both `window.localStorage` and `globalThis.localStorage` before dynamically importing `@/i18n`.

Still run the normal health checks before starting Prompt 2:

```bash
cd /Users/qinqiang02/colab/codespace/ai/emerge/frontend
npm run lint
npm test
npm run build
```

---

## 3. Non-negotiable product and safety red lines

Carry these through every prompt and code review:

- v1 UI creates/displays only `ExtractionProject` / `project_type="extraction"`.
- Do not implement MatchingProject / VerificationProject UI, routes, copy, tabs, filters, mocks, or backend support.
- Public API surfaces `Project.published_version_id`, never `active_version_id`.
- Lab/editor may use `active_version_id`; publish/rename/rollback UI must make Production API version and Lab/draft version separate.
- No image few-shot. No example I/O pairs injected into runtime prompts.
- No bbox / coordinates / polygon / visual region / span UI or persistence. Field evidence is only `page`, `quote`, `rationale`, `source_text_hash`.
- Counterexamples / production feedback never enter runtime prompt; they feed review, regression health, and future AutoResearch evaluation.
- API key plaintext is shown exactly once after creation, only in component state / modal state. Never persist it to Zustand, localStorage, sessionStorage, fixtures, logs, docs, or tests.
- Every visible frontend string goes through `useT()` / `en.json`.
- Use semantic Tailwind token classes, not raw color classes such as `bg-gray-*`, `bg-white`, `bg-black`, `text-white`, `text-black`.
- Keep phases small; one phase or subphase per commit; stop after commit and ask for gate review.

---

## 4. Prompt mapping from here

The earlier Prompt 1 completed R8.0 frontend foundation. From here, use this numbering:

```text
Prompt 2 => R8.1 Product shell: project list, document list, minimal Studio, form schema editor
Prompt 3 => R8.2 API Console + publish flow + one-time API key reveal
Prompt 4 => R8.3 API Readiness Panel
Prompt 5 => R8.4 Review Inbox
Prompt 6 => R8.5 Field Evidence display in Studio, including the small backend payload gap
Prompt 7 => R8.6 Partial Feedback UI, public shape + in-Lab reuse
Prompt 8 => R8.7 Walking Skeleton E2E
```

Recommended series: **R8.1 → R8.2 → R8.3 → R8.4 → R8.5 → R8.6 → R8.7**.

R8.2 / R8.3 / R8.4 are technically parallel after R8.1, but keep them serial unless there is a strong reason to parallelize.

---

## 5. Prompt 2 — R8.1 Product shell

Authoritative detail: `2026-05-04-r8-productization-mvp.md`, section `Phase R8.1 — Product shell: project list, document list, minimal Studio`.

Objective: give the user the basic Software-3.0 walking path:

```text
projects -> create project -> documents -> upload/extract -> Studio -> edit output -> save correction -> schema form/lock view
```

Subtasks and expected commits:

```text
R8.1.a feat(frontend): project list shows published/draft status from R7.5 pointer
R8.1.b feat(frontend): project creation dialog with builtin templates + empty path
R8.1.c feat(frontend): document list with upload + extract trigger
R8.1.d feat(frontend): minimal Studio with correction save
R8.1.e feat(frontend): schema editor form mode with lock/unlock
```

Important scope cuts:

- No API Console yet.
- No Readiness Panel yet.
- No Review Inbox yet.
- No field evidence popover yet.
- No partial feedback UI yet.
- No schema chat mode.
- Real PDF preview remains a placeholder: filename, mime_type, page_count only.
- NL-first onboarding is placeholder copy only; real project creation uses builtin templates or empty project.

R8.1 phase gate:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
register -> create from non-empty builtin such as japan_receipt -> upload 2 PDFs -> re-extract -> click row -> edit -> save -> re-open -> annotation override visible
/projects/:id/schema shows lock-status; after at least 2 saved corrections with stable fields, lock/unlock works
```

Suggested Claude Code prompt:

```text
Continue R8 Productization MVP on branch r8-productization-mvp.

Pre-read:
- CLAUDE.md
- docs/superpowers/plans/2026-05-04-r8-continuation-handoff.md
- docs/superpowers/plans/2026-05-04-r8-productization-mvp.md

First verify R8.0.1 health:
- cd frontend && npm run lint
- cd frontend && npm test
- cd frontend && npm run build
If tests fail, fix only the test/setup issue as a tiny stabilization commit before product work.

Then implement only Phase R8.1 from the overlay plan:
- project list published/draft badge
- project create dialog with builtin templates + empty path
- document list with upload + extract trigger
- minimal Studio with correction save
- schema editor form mode with lock/unlock

Do not implement API Console, Readiness Panel, Review Inbox, field evidence UI, partial feedback UI, schema chat mode, AutoResearch viewer, MatchingProject, VerificationProject, bbox/coordinate UI, or real PDF preview.
Do not read or print secrets.
Every visible string must use i18n. Use semantic token classes only.

Run frontend lint/test/build. Commit each R8.1 subtask with the exact commit messages in the overlay plan, then stop and report.
```

---

## 6. Prompt 3 — R8.2 API Console + Publish Flow + API key reveal

Authoritative detail: overlay section `Phase R8.2 — API Console + Publish Flow + API key reveal modal`.

Objective: MVP priority #1. Replace historical `PublishFlow.tsx` with a richer API Console owning publishing, version pointers, contract diff, key management, snippets, and key reveal.

Expected commits:

```text
feat(frontend): publish/keys store actions for API Console
feat(frontend): one-time API key reveal modal with copy + ack
feat(frontend): API Console with publish, contract diff, keys, rollback
```

Key product requirements:

- Show Production API version (`published_version_id`) and Lab/draft version (`active_version_id`) as separate cards; never collapse them.
- Activate-for-API publishes an explicit version pointer and respects backend lock / empty schema gates.
- API code rename on an already-published project must keep `published_version_id` unchanged unless the user explicitly activates a different locked Lab version.
- One-time API key reveal modal is the only plaintext path. After dismiss/reload, only prefix is visible.
- Snippets use `EMERGE_API_KEY` placeholder only.
- Feedback example is read-only here; interactive feedback arrives in R8.6.

R8.2 gate:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
lock active version -> Activate for API -> create key -> modal shows plaintext -> dismiss -> reload -> prefix only -> revoke -> row gone -> unpublish -> public extract returns 403 via curl
```

---

## 7. Prompt 4 — R8.3 API Readiness Panel

Authoritative detail: overlay section `Phase R8.3 — API Readiness Panel`.

Objective: MVP priority #2. Render `GET /api/v1/projects/{pid}/readiness` as product-facing trust surface on project page and API Console.

Expected commit:

```text
feat(frontend): API Readiness panel with CI band and no-feedback semantics
```

Key product requirements:

- Show quality with CI band and observation counts.
- When `regression_health.counterexamples_total === 0`, show "No production feedback yet" and never show `100%`.
- Show evidence/maturity/regression/risky fields/blockers/warnings.
- Translate every blocker/warning slug in `en.json`; do not show raw `empty_schema`-style slugs to users.
- Mount at top of `/projects/:id` and inside `/projects/:id/api-console`.

R8.3 gate:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
fresh empty project shows blockers active_version_unlocked, empty_schema, schema_not_lock_candidate;
after non-empty schema is stable, locked, and published, blockers clear;
with zero counterexamples, no-production-feedback copy persists.
```

---

## 8. Prompt 5 — R8.4 Review Inbox

Authoritative detail: overlay section `Phase R8.4 — Review Inbox`.

Objective: MVP priority #3. Surface `GET /api/v1/projects/{pid}/review-queue` as banner on the project page and as dedicated `/projects/:id/review` page.

Expected commit:

```text
feat(frontend): Review Inbox banner and page from /review-queue
```

Key product requirements:

- Banner shows counts for Required review, Spot-check, All.
- `Review next` opens first required-review doc, or first spot-check doc if required is empty.
- Dedicated page shows three sections.
- Empty queue shows explicit "All caught up" state; no confusing `0 of 0`.

R8.4 gate:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
trigger judge run -> a doc gets down/uncertain field -> reload /projects/:id -> Required review count increments -> Review next opens Studio for that doc
```

---

## 9. Prompt 6 — R8.5 Field Evidence display

Authoritative detail: overlay section `Phase R8.5 — Field Evidence display in Studio`.

Objective: MVP priority #4. Show quote/page/rationale evidence and confidence chips in Studio.

Expected commits:

```text
feat(api): surface per-field evidence and confidence in document detail
feat(frontend): Studio per-field evidence popover and confidence chip
```

Backend gap to fix in R8.5.0:

- `GET /api/v1/projects/{pid}/documents/{did}` currently needs `latest_prediction.per_field_evidence` and `latest_prediction.per_field_confidence` surfaced in the payload.
- Add backend test `test_document_detail_evidence.py`.
- Ensure no bbox / coordinate / region key shapes are introduced.

Frontend requirements:

- Evidence button only appears where evidence exists.
- Popover renders only `page`, `quote`, `rationale`, and optionally `source_text_hash` if surfaced; it never renders bbox-like keys even if backend leaks them.
- Confidence chip: `up` silent, `uncertain` muted, `down` warning / needs review.
- Light and dark render smoke tested.

R8.5 gate:

```bash
cd backend && uv run pytest tests/test_document_detail_evidence.py -v
cd backend && uv run pytest -v
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
prediction with field evidence + verdicts -> Studio shows quote popover + warning chip;
prediction without evidence -> no popover;
no bbox UI surfaces anywhere.
```

---

## 10. Prompt 7 — R8.6 Partial Feedback UI

Authoritative detail: overlay section `Phase R8.6 — Partial Feedback UI`.

Objective: expose the public partial feedback shape and reuse the same mental model inside Lab.

Expected commits:

```text
feat(frontend): partial feedback payload builder and types
feat(frontend): API Console partial-feedback example and test form
feat(frontend): Studio Report-wrong dialog reuses partial-feedback shape
```

Key product requirements:

- Shared builder emits `{ request_id, corrections: [{ entity_index, field_path, correct_value, comment? }], issue_type?, notes? }`.
- API Console always shows read-only example; interactive form is gated on existing key and uses transient pasted API key component state only.
- Public feedback submit calls `POST /extract/{api_code}/feedback` with `X-Api-Key` and shows returned `counterexample_id`.
- Studio `Report wrong` dialog shows equivalent JSON shape but posts Lab Annotation through authenticated internal route; it must **not** call public feedback endpoint from Lab.
- Studio corrections are `role=none`; production feedback creates counterexamples.

R8.6 gate:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

Manual gate:

```text
API Console -> Send test feedback with valid prediction_id from recent public extract -> counterexample_id returned -> readiness regression_health.counterexamples_total increments;
Studio -> click Report wrong on field -> save -> reload -> annotation override visible.
```

---

## 11. Prompt 8 — R8.7 Walking Skeleton E2E

Authoritative detail: overlay section `Phase R8.7 — Walking Skeleton E2E`.

Objective: one Playwright spec proving the full browser product loop against a live backend with provider key configured by the environment, without printing any secret.

Expected commit:

```text
test(frontend): walking-skeleton E2E covers publish + readiness + feedback
```

Scenario:

```text
register fresh user
create project from non-empty builtin such as japan_receipt
upload sample PDF(s)
extract
open Studio, edit, save correction, re-open
repeat correction enough for lock-status
schema page: lock schema
API Console: publish, create key, one-time reveal, ack
send feedback using revealed key and known prediction_id
ReadinessPanel shows counterexamples_total >= 1 and no false 100% when total is 0
Review page has non-empty section after judge materialization
```

R8.7 gate:

```bash
# backend in one shell
cd backend && uv run uvicorn app.main:app --reload --port 8000

# frontend in another shell
cd frontend && npm run dev

# test shell
cd frontend && EMERGE_E2E=1 npm run e2e -- walking_skeleton
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
cd backend && uv run pytest -v
```

Do not print provider key presence beyond a boolean if absolutely necessary; never print the value.

---

## 12. Entire R8 MVP exit gate

R8 Productization MVP is not complete until all of this passes on a fresh-enough DB:

```text
1. /login renders in light and dark.
2. Register -> /projects empty.
3. Create from non-empty builtin such as japan_receipt -> /projects/:id shows ReadinessPanel + Review Inbox banner + Document table.
4. Upload + extract; rows transition to extracted or errored with clear state.
5. Studio shows entity cards; field evidence popover available where evidence exists; confidence chips visible for down/uncertain.
6. Save correction -> annotation override visible on reload.
7. Lock schema via /projects/:id/schema.
8. /projects/:id/api-console shows Production and Lab pointers, contract diff, Activate-for-API, one-time key reveal, feedback example, and Send test feedback form.
9. After publish + first feedback, ReadinessPanel regression_health.counterexamples_total >= 1.
10. Readiness never says 100% when counterexamples_total is 0.
11. Theme toggle works on every page in both modes.
12. cd frontend && npm run lint passes.
13. cd frontend && npm test passes.
14. cd frontend && npm run build passes.
15. cd frontend && EMERGE_E2E=1 npm run e2e passes.
16. cd backend && uv run pytest -v passes after R8.5.0 backend patch.
```

---

## 13. Post-R8 Productization MVP plan

Recommended order after R8 MVP ships:

### P0 — Release hardening / dogfood before adding more features

Goal: make the MVP safely demoable and repeatedly dogfoodable.

- Add a small release checklist / smoke script that runs frontend lint/test/build and backend tests.
- Add docs for local demo flow without secrets; examples only use `EMERGE_API_KEY` placeholders.
- Confirm API key one-time reveal behavior with tests.
- Confirm public API reads `published_version_id` after Lab active version changes.
- Check migration risk for global `api_code`: production/staging DB must have no duplicate non-null `api_code` before Alembic `0015`.
- Decide merge strategy into `main`. Because `origin/main` and local `main` have diverged in earlier checks, inspect branch graph first and do not push without user approval.

### P1 — v1.1 usability: schema editing becomes more AI-native

Priority features:

1. **Schema editor chat mode** (historical R8 Task 12, spec §8.3): NL instruction -> whitelist action toolkit -> diff preview -> Accept/Reject/Edit. Must write the same ProjectVersion structure as form mode. Do not allow free-form model writes.
2. **Inline teaching proposal** (spec §2.4): when user corrects a field, propose a readable description patch; user Accept/Edit/Just fix this doc. This likely needs a small backend proposal endpoint.
3. **Description Workbench lint + evidence panel + patch diff** (spec §2.5): lint vague/empty descriptions, show evidence/corrections/counterexample hits per field, test changed descriptions against selected docs. Examples are documentation, not runtime few-shot.

### P2 — v1.1 evolution transparency

Priority features:

1. **AutoResearch viewer** (historical R8 Task 13, spec §5): show turn history, diagnosis, chosen text-only actions, score deltas, and candidate ProjectVersion diff.
2. Manual `Run AutoResearch` button if backend R6 is ready; output remains candidate version and is never auto-promoted.
3. Optional semi-automatic trigger only after manual path is trustworthy.

### P3 — document experience polish

Priority features:

1. **Real PDF preview**: replace placeholder with document preview. Backend likely needs a safe file download endpoint such as `GET /api/v1/projects/{pid}/documents/{did}/file`; keep no bbox overlay.
2. Better upload/extract progress if batches become slow; SSE can replace MVP blocking fetch.
3. Better empty/error states for extraction failures.

### P4 — onboarding and integrator growth

Priority features:

1. **NL-first onboarding** (spec §2.1): docs + natural-language requirement -> schema draft + first predictions together. Keep generated schema as editable draft; never hide explicit descriptions.
2. API docs / SDK snippets beyond static snippets: possibly generated OpenAPI examples, typed Python/JS mini clients, and a Postman collection. Snippets still use placeholders only.
3. API readiness explainers and sample production-feedback loop for integrators.

### P5 — team / workspace / ops features

Defer until single-user extraction loop is clearly useful:

- Multi-Workspace switcher and admin settings.
- API usage visibility / rate limit UI.
- Key rotation UX.
- Webhooks or push notifications.
- Saved views, project clone, statistics dashboard, comparison view.
- Multi-user realtime collaboration / annotation locking.

### P6 — future project types only after extraction is stable

MatchingProject / VerificationProject remain future project types. Do not start these until extraction v1 has real usage signals and the product language for project types is settled.

---

## 14. New-session recovery commands

Use tools rather than relying on memory:

```bash
cd /Users/qinqiang02/colab/codespace/ai/emerge
git branch --show-current
git status --short
git log --oneline -12
```

If not already on the R8 branch:

```bash
git switch r8-productization-mvp
```

Before any phase implementation:

```bash
cd frontend && npm run lint
cd frontend && npm test
cd frontend && npm run build
```

For backend-touching R8.5 and final R8.7:

```bash
cd backend && uv run pytest -v
```

If a generated artifact appears, do not commit it unless it is intentionally part of the product. Common generated files to watch for:

```text
frontend/test-results/.last-run.json
frontend/tsconfig.app.tsbuildinfo
frontend/tsconfig.node.tsbuildinfo
frontend/dist/
```

---

## 15. Review style for future Hermes gates

For each completed prompt from Claude Code, Hermes should:

1. Load the relevant code-review / plan skill if available.
2. Check `git status --short`, branch, and recent commits.
3. Diff only from the previous accepted commit.
4. Search for red-line violations: MatchingProject, VerificationProject, bbox, coordinates, visual regions, spans, raw API keys/secrets, hardcoded visible strings, raw Tailwind colors.
5. Run relevant frontend lint/test/build; run backend tests if backend touched.
6. For API key flows, explicitly inspect that plaintext key is never persisted outside one-time modal/component state.
7. For public API flows, verify published version semantics are preserved.
8. Report pass/fail, exact failing commands, remaining risk, and the next prompt.

Do not auto-merge to `main` and do not push remote without explicit user instruction.
