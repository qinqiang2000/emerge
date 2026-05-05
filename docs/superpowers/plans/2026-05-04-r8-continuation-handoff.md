# R8 continuation handoff — R8.4 onward

Generated: 2026-05-04 20:43 CST
Last refreshed: 2026-05-05 (post R8.4 review inbox + chrome-devtools smoke + hygiene 22 resolved)
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
4. `docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md` (deferred fixups; sweep matching items as you touch the files in R8.3+)
5. For product semantics only when needed: `docs/superpowers/specs/2026-05-02-overall-design.md`
6. For historical frontend foundation details only when needed: `docs/superpowers/plans/2026-05-03-r8-ui.md`

Do **not** read, print, copy, or commit `backend/.env`, provider keys, JWTs, API key plaintext, tokens, or passwords. Snippets use placeholders such as `EMERGE_API_KEY` only.

---

## 1. Current live state (2026-05-05 refresh, post R8.4)

```text
branch:  r8-productization-mvp
HEAD:    8339780 docs(hygiene): track R8.4 smoke findings (45, 46) on banner copy
status:  clean
```

R8 commits remain on `r8-productization-mvp`, not in local or remote `main`. Continue here unless the user explicitly asks to merge / push.

### Phases done end-to-end on this branch

**R8.0 — Foundation** (Tasks 1–6 from historical plan, R8.0.1 hygiene): bootstrap, i18n, theme, base UI, axios client + EmergeError, auth gate.

**R8.1 — Product shell**: project list with published badge, project create with builtin templates + empty path, document list with upload + extract, minimal Studio with correction save, schema editor form-mode with lock/unlock. Plus: project sub-nav (Documents / Schema / API), auth boot-prime fix, Pages column drop, plan §314/323 doc fix.

**R8.2 — API Console**: publish/keys store actions, one-time API key reveal modal, API Console page (dual version pointers / contract diff / activate / rename / rollback / unpublish / keys / snippets / feedback example), Activate/Rename input split.

**Plus two backend fixes from R8.2 manual smoke** (`e7edcdf` + `d0d53ca`): UTC offset on serialized datetimes (7 Out schemas) + `publish()` no longer bumps `api_published_at` on pure rename.

**R8.3 — API Readiness Panel**: `useReadiness` Zustand store, `ReadinessPanel` component, `types/readiness.ts` mirror, full `errors.readiness.*` i18n catalog (9 backend slugs). Panel mounts at the top of `/projects/:id` (above Document table) AND inside `/projects/:id/api-console` (above Production pointer). Hard rules verified: `counterexamples_total === 0` → "No production feedback yet" (never `100%`); quality always shows CI band + (N obs · vibe-check K); risky fields top-5 with `+N more`; raw slugs never reach the user; unknown slugs fall back to humanised + `console.warn`. Plus follow-up commit `88b9836` after gate review: distinct copy per `regression_health.status`, null-safe `passing` approximation, cross-project race fix in `useReadiness.load()`, dropped redundant `KNOWN_*` whitelists. Plus hygiene sweeps in the same commit: (8) drop manual `Content-Type: multipart/form-data` from upload (axios sets the boundary); (17) lift `emergeCode`/`emergeErrorKey` helpers from 6 stores to `lib/api.ts`. Pushed back on reviewer suggestion to surface backend `schema_maturity.message` (English-only static copy that conflicts with the i18n red line; the translated `readiness.maturity.<status>` catalog already conveys the recommended action).

**R8.4 — Review Inbox**: `useReview` Zustand store, `ReviewInboxBanner` component (mounts on `/projects/:id` BETWEEN ReadinessPanel and Document table), `ReviewInboxPage` at `/projects/:id/review` (three sections — Required review / Spot-check / All — backed by the same store). Banner shows three counts (required_review · spot_check · all). "Review next" routes to first `required_review[0]`, falling back to first `spot_check[0]`; both buckets empty → button disabled and "All caught up" callout (never "0 of 0"). Each row in the dedicated page shows filename + flagged_fields chips (backend caps at 3) and routes to Studio. `types/review.ts` mirrors backend `ReviewQueueOut`/`ReviewItemOut`. `review.*` i18n namespace covers banner copy, section titles + hints, and per-section empty-state. Hygiene swept in the same commit: (22) `ProjectSubNav` migrated from `pathname.endsWith` (trailing-slash fragile) to `useMatch` pattern matching, plus a new "Review" sub-nav tab between Documents and Schema. Gate review: ready-to-merge, no Critical/Important findings; minor polish items only (banner `<dl>` separator markup, list `role="button"` could nest a `<button>`, plural copy). Smoke logged hygiene (45/46): banner "0 docs total" doesn't qualify the vibe-check semantics that the dedicated page hint already spells out; "1 need review" should pluralise to "1 needs review".

### Reverse-chronological commit list (this branch)

```text
8339780 docs(hygiene): track R8.4 smoke findings (45, 46) on banner copy
6df78f8 feat(frontend): Review Inbox banner and page from /review-queue
dc25193 docs(handoff): refresh after R8.3 readiness panel + smoke + hygiene 8/17
dd846d2 docs(hygiene): track R8.3 smoke finding (44) on quality CI with no obs
88b9836 fix(frontend): apply R8.3 gate-review fixes to ReadinessPanel
a20a42e feat(frontend): API Readiness panel with CI band and no-feedback semantics
664c24a docs: persist R8 hygiene tail + wire into handoff pre-read
79af378 docs(handoff): refresh after R8.1 + R8.2 + backend tz/rename fixes
d0d53ca fix(api): apply UTC datetime serializer to remaining Out schemas
e7edcdf fix(api): UTC offset on serialized datetimes + don't bump api_published_at on pure rename
035031c fix(frontend): split Activate and Rename inputs in API Console
e282200 feat(frontend): API Console with publish, contract diff, keys, rollback
82e5e56 feat(frontend): one-time API key reveal modal with copy + ack
67eb160 feat(frontend): publish/keys store actions for API Console
2432ae9 docs(plan): R8.1.e plan reflects read-only field name/type in v1
82be98d fix(frontend): drop "0 pages" from Studio header to match dropped column
80458c8 fix(frontend): boot-prime axios auth + drop misleading Pages column
dda952d feat(frontend): project sub-nav so the R8.1 walking path is reachable
9a1e20b feat(frontend): schema editor form mode with lock/unlock
c276e47 feat(frontend): minimal Studio with correction save
8a85022 feat(frontend): document list with upload + extract trigger
c84184e feat(frontend): project creation dialog with builtin templates + empty path
14edb0d feat(frontend): project list shows published/draft status from R7.5 pointer
0552f74 test(frontend): stabilize theme localStorage tests
331a821 chore(frontend): fix R8.0 lint and i18n hygiene
4a269bd feat(frontend): auth store + login/register pages + auth gate
4538284 feat(frontend): axios client + EmergeError envelope decoder
78b2de3 feat(frontend): base Radix-wrapped components with token-only styling
794e318 feat(frontend): light/dark/system theme with CSS-var token system
dbbdcdc feat(frontend): i18n setup with English catalog and useT hook
141adea chore(frontend): bootstrap Vite + React 19 + TS + Vitest skeleton
b813e6f docs: add R8 productization MVP overlay plan
```

### Health snapshot at HEAD

```text
cd frontend && npm run lint                : clean
cd frontend && npm test                    : 15 files / 83 tests passed
cd frontend && npm run build               : 438 KB / 137 KB gzipped
cd backend  && uv run pytest -q            : 237 passed, 2 skipped, 4 warnings
```

### Manual smoke completed (R8.1 + R8.2 + R8.3 + R8.4)

A real walking-path smoke ran against `dogfood@example.com` on project test1 (built from `japan_receipt` builtin, 2 Japanese parking-receipt PDFs uploaded + extracted with Gemini):

- R8.1: register → create → upload → extract → Studio edit + save → reload (override visible) → Schema lock + unlock. Found auth race + Pages-column-always-0 bug; both fixed in `80458c8`/`82be98d`.
- R8.2: lock → API tab → Activate → Create key (modal plaintext + Esc-blocked + ack-gated dismiss) → reload (prefix-only) → Rename → Unpublish → curl `/extract/japan-receipts-v2` → 403 → Re-publish → Revoke. Found timezone drift + `api_published_at` re-stamp on rename; both fixed in `e7edcdf`/`d0d53ca`.
- R8.3 (chrome-devtools-mcp driven): fresh empty project (`r83-smoke-empty`, project 3) → all 3 publish_blockers translated, no raw slugs, no `100%`, regression reads "No production feedback yet"; published `test1` (project 2) → blockers section disappears, schema reads "Locked"; light + dark theme renders both panels cleanly. Found one new UX hygiene item (44): quality reads ~80% ± 23% with 0 obs because of Beta prior — backend should surface null on `observation_count === 0`. Non-blocking; tracked in hygiene tail §3.
- R8.4 (chrome-devtools-mcp driven, project 2 published `test1`): banner mounts BETWEEN `API Readiness` and `Documents` h1 (correct vertical position); three counts read `0 need review · 0 spot-checks · 0 docs total`; "Review next" disabled; "All caught up" callout renders. `/projects/2/review` shows three sections with hints + per-section empty copy. Sub-nav order is `Documents · Review · Schema · API`; `aria-current="page"` lands on Review when on `/review`, on Documents when on `/projects/:id`. Dark theme clean; only console output is the pre-existing React Router future-flag warnings. Found two non-blocking hygiene items (45, 46): banner "0 docs total" doesn't qualify the vibe-check semantics that the dedicated page hint already spells out; pluralisation "1 need review" should be "1 needs review". Tracked in hygiene tail §3a.

Open UX findings from those smokes are tracked in the hygiene tail. See §13 below for the full carry-forward.

---

## 2. R8.5 entry point — read this then dive in

Authoritative R8.5 detail: `docs/superpowers/plans/2026-05-04-r8-productization-mvp.md`, section **Phase R8.5 — Field Evidence display in Studio** (around lines 604–714).

R8.5 in one paragraph: wire `latest_prediction.per_field_evidence` and `per_field_confidence` into Studio so each field row exposes a per-field Evidence popover (page / quote / rationale, no bbox) and a confidence chip (`up` silent, `uncertain` muted, `down` warning). Two parts: **R8.5.0** is a tiny backend payload extension — the existing `GET /api/v1/projects/{pid}/documents/{did}` route omits both fields and needs them surfaced under `latest_prediction`; add a backend test that asserts the keys are present and that no bbox / coordinate / region keys leak. **R8.5.1** is the frontend popover + chip wired into Studio per-field rows. Field-level evidence is the spec §8.2 trust surface; the popover button is hidden when no evidence exists, never renders coordinate keys even if backend leaks them, and emits `console.warn` on unknown keys in dev.

Suggested Claude Code prompt for the next session:

```text
Continue R8 Productization MVP on branch r8-productization-mvp at
/Users/qinqiang02/colab/codespace/ai/emerge.

Pre-read in order before any work:
1. CLAUDE.md
2. docs/superpowers/plans/2026-05-04-r8-continuation-handoff.md
3. docs/superpowers/plans/2026-05-04-r8-productization-mvp.md (overlay) — Phase R8.5 (R8.5.0 backend, R8.5.1 frontend)
4. docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md
5. docs/superpowers/specs/2026-05-02-overall-design.md §3.2 (per_field_evidence shape) and §8.2 (Studio evidence popover)

Verify health at HEAD before starting:
- cd frontend && npm run lint && npm test && npm run build
- cd backend  && uv run pytest -q

Then implement Phase R8.5 per the overlay, in two commits:

R8.5.0 — backend: surface `per_field_evidence` and `per_field_confidence`
under `latest_prediction` in `GET /api/v1/projects/{pid}/documents/{did}`
(see backend/app/api/routes/documents.py:89-99 dict literal). Add a new
backend test `tests/test_document_detail_evidence.py` that creates a
Prediction with both maps and asserts the keys land in the payload AND
that no `bbox`/`region`/`coordinates` keys leak. Commit message:
  feat(api): surface per-field evidence and confidence in document detail

R8.5.1 — frontend:
  - Extend `frontend/src/types/studio.ts` (or stores/studio.ts types)
    with `FieldEvidence` and the `per_field_*` maps.
  - Create `frontend/src/components/FieldEvidencePopover.tsx`:
    button hidden when no evidence; popover renders only `page`,
    `quote`, `rationale` (and `source_text_hash` if surfaced). Drops
    unknown keys client-side and console.warn in dev. NEVER renders
    bbox / region / coordinates keys, even if backend leaks them.
  - Create `<ConfidenceChip verdict>` for `up | uncertain | down`:
    `up` silent, `uncertain` muted, `down` status-warning.
  - Wire both into `frontend/src/pages/Studio.tsx` per-field rows.
  - Mirror `studio.evidence.*` strings in `en.json`.
  - TDD: write `frontend/src/__tests__/field_evidence_popover.test.tsx`
    first; cover the happy path, the rationale-only path, the
    no-evidence path, the bbox-leak defense, and the three chip
    verdicts. Watch RED → implement → GREEN.

Conventions established in R8.1–R8.4 (carry through):
- TDD: spec test first, watch RED, implement, watch GREEN
- useT() for every visible string; semantic Tailwind tokens only
- EmergeError → errors.<code> i18n; Zustand store with
  data / loading / error using emergeErrorKey from lib/api
- After EACH commit (R8.5.0 backend AND R8.5.1 frontend), dispatch a
  code-reviewer via superpowers:requesting-code-review skill (NOT a
  bare general-purpose agent — see memory
  feedback_gate_review_subagent.md).
- When you touch a file, sweep matching items from the hygiene tail in
  the same commit. Mirror every visible string into en.json.
- After both commits, refresh the handoff doc and STOP for human
  checkpoint before R8.6.

R8.5 hard rules (CLAUDE.md + spec §3.2 / §8.2):
- Field-level evidence is page + quote + rationale text only.
  No bbox, coordinates, regions, polygons, spans, or visual overlays.
  No way to draw on the document.
- Popover button is hidden when no evidence exists for the field.
- Confidence chip: `up` renders nothing, `uncertain` renders muted
  chip, `down` renders status-warning chip.
- The popover defends against bbox-key leakage from backend by
  ignoring unknown keys and console.warn in dev.
- Backend payload only adds keys; do not change `DocumentDetailOut`
  shape semantics or break existing tests.

Out of scope: Partial Feedback (R8.6), Walking Skeleton E2E (R8.7),
AutoResearch viewer, MatchingProject, VerificationProject,
real PDF preview, Studio entity nav / collapse, "Report wrong" dialog
(that lands in R8.6 next to the evidence popover). Never read or
print secrets.

R8.4 context the new session should know:
- ReviewInboxBanner mounts on /projects/:id between ReadinessPanel
  and the Document table; dedicated /projects/:id/review page lives
  at the new "Review" sub-nav tab.
- ProjectSubNav uses useMatch (pattern-based, trailing-slash safe).
- emergeCode + emergeErrorKey helpers live in lib/api.ts (use them).
- chrome-devtools-mcp smoke against project 2 (test1) verified R8.4
  in light + dark; no console errors beyond pre-existing react-router
  future-flag warnings.
- Hygiene tail item (44): quality % renders ~80% ± 23% on 0 obs due
  to Beta prior — backend should surface null on
  `observation_count === 0`. R8.5 backend payload work is the natural
  place to also fix (44); if you do, sweep it in the R8.5.0 commit.
- Hygiene (45): banner "0 docs total" needs vibe-check qualifier
  copy; (46) plural "1 needs review" — both deferred, sweep when
  the affected file is next touched.
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

## 4. Prompt mapping — where we are

```text
Prompt 1 (DONE)  => R8.0 frontend foundation
Prompt 2 (DONE)  => R8.1 Product shell + sub-nav + auth boot-prime + Pages drop
Prompt 3 (DONE)  => R8.2 API Console + publish flow + one-time API key reveal
                    + backend tz / api_published_at fixes
Prompt 4 (DONE)  => R8.3 API Readiness Panel + gate-review fixes + hygiene 8/17
Prompt 5 (DONE)  => R8.4 Review Inbox + sub-nav useMatch + hygiene 22
Prompt 6 (NEXT)  => R8.5 Field Evidence display in Studio (incl small backend payload gap)
Prompt 7         => R8.6 Partial Feedback UI, public shape + in-Lab reuse
Prompt 8         => R8.7 Walking Skeleton E2E
```

§5–§7 below preserve the historical R8.1 / R8.2 / R8.3 prompts as reference for the patterns those phases established; new sessions don't need to re-implement them. Skip directly to §8 (R8.4) when starting fresh.

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
