# R8 continuation handoff — R8.4 onward

Generated: 2026-05-04 20:43 CST
Last refreshed: 2026-05-05 (post R8.7 smoke-finding sweep: spot-check semantic + Draft callout + panel auto-refresh)
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

## 1. Current live state (2026-05-05 refresh, post smoke-finding sweep)

```text
branch:  r8-productization-mvp
HEAD:    137dd3f fix(frontend): panels auto-refresh after document mutations
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

**R8.5 — Field Evidence display**: split into two commits per overlay.
- **R8.5.0 backend** (`1195259`): extended `latest_prediction` payload in `backend/app/api/routes/documents.py` with `per_field_evidence` and `per_field_confidence` (5-line dict-literal addition; reads existing nullable JSON columns; no schema change). New test file `backend/tests/test_document_detail_evidence.py` pins the happy path, the read-side pass-through for sanitised evidence, and a third null-handling case asserting both keys are *present* (not just truthy) so the frontend can read them without `in`-guarding. Gate review feedback applied in `3c1428b`: renamed the leak-defense test to `test_document_detail_passes_through_sanitized_evidence_unchanged` (the original framing was tautological because clean seed data trivially passes a "no forbidden keys" probe), replaced `repr(body)` substring search with a recursive key-walk to avoid false positives on legitimate values, and pointed the production comment at `app/engine/extract.py::_sanitize_evidence` (the actual write-time defense boundary) instead of a sibling test file. 240 backend tests pass (was 237).
- **R8.5.1 frontend** (`1a5a3e9`): new `frontend/src/types/studio.ts` with `FieldEvidence`, `PerFieldEvidence`, `PerFieldConfidence`, `ConfidenceVerdict`, plus `EVIDENCE_ALLOWED_KEYS` runtime allow-list (single source of truth for the runtime sanitiser AND the type). New `FieldEvidencePopover` and `ConfidenceChip` components. Popover trigger only renders when at least one allow-listed key exists for `(entityIndex, fieldName)`; when backend leaks bbox/coordinates/polygon/region/span keys, `pickAllowedKeys` drops them, `console.warn`s, and the popover never renders coordinate values to the DOM (allow-list, not deny-list). Click-outside (mousedown), Escape, and trigger toggle all dismiss the panel. ConfidenceChip is silent on `up`, muted (`bg-bg-muted`) on `uncertain`, and warning-bordered/colored on `down`. Wired into `Studio.tsx` per-field rows, which required restructuring the wrapping `<label>` into a `useId()`-backed `aria-labelledby` pattern (popover `<button>` cannot be nested in a `<label>` that also wraps the input — clicking the button would steal focus). `studio.evidence.*` and `studio.confidence.*` i18n namespaces. 14 component tests including three close-behavior cases added in `bd43798` after gate review.

R8.5 gate review (subagent): both commits ready-to-merge with no Critical/Important findings. Backend reviewer's only Important note (tautological leak-defense test) was applied as `3c1428b`. Frontend reviewer's only Minor that warranted action (no close-behavior tests) was applied as `bd43798`. Other minor notes were either (a) cosmetic dead branches in ConfidenceChip's silent path that defensive-code as designed, (b) `console.warn` unconditionality matching existing `ReadinessPanel` precedent, or (c) premature DRY suggestions to be revisited when R8.6 needs the same sanitiser.

**R8.6 — Partial Feedback UI**: split into three feature commits + one gate-fix + one test-coverage commit.
- **R8.6.a builder + types** (`b9d4584`): new `frontend/src/lib/feedback.ts` exporting `FeedbackIssueType` (literal union of the five backend Literal values), `FEEDBACK_ISSUE_TYPES` runtime tuple, `FeedbackCorrection`, `PartialFeedbackPayload`, `buildPartialFeedback({predictionId, corrections, issueType?, notes?})`, and `fieldPathFor(entityIndex, key, arrayIndex?)`. Pure validating builder, no axios, no key handling. 15 specs cover dotted/array path composition, the arrayIndex-0-not-falsy edge, omission of optional issue_type/notes, empty-corrections rejection, positive integer request_id, the five issue_type literals, and per-correction field_path / entity_index validation.
- **R8.6.b API Console form** (`92937de` + gate-fix `f8f845e`): expanded the existing read-only "Partial feedback example" panel into a dual surface — JSON example + curl snippet stay always visible, and a new interactive `<FeedbackTestForm apiCode>` mounts beneath when `apiKeys.length > 0`. Pasted plaintext API key lives only in component state (cleared on success and on unmount via `useEffect` cleanup); two specs pin this — `Storage.prototype.setItem` spy confirms no localStorage write contains the plaintext, and an unmount-remount cycle yields an empty key field. Submit POSTs to `/extract/{api_code}/feedback` with `X-Api-Key`, surfaces the returned `counterexample_id`, and translates `EmergeError` via `emergeErrorKey`. `correct_value` JSON-parses with plain-string fallback. Gate review (subagent) flagged two Important findings, both fixed in `f8f845e`: (1) JWT-bleed onto the public-feedback POST — the shared axios instance carries `Authorization: Bearer <jwt>` on `defaults.headers.common`, which would smuggle a session credential onto a public boundary that authenticates only via X-Api-Key; now we explicitly set `Authorization: undefined` on the per-request `headers` (axios v1 drops headers whose value is undefined), with a new spec asserting the recorded `opts.headers.Authorization` is falsy. (2) Wrong i18n key on bad entity_index — added `feedback.errors.entity_index_must_be_non_negative` and a spec asserting the alert text matches. Plus three minor cleanups: `canSubmit` now requires `requestIdStr.length > 0`; dead `feedback.errors.field_path_required` branch removed; unused `feedback.errors.key_required` and `feedback.issue_type_placeholder` keys dropped. R8.6.a reviewer's deferred-validation note about `fieldPathFor` not validating its `key` was correctly carried into R8.6.c (first real caller); R8.6.b takes `field_path` as free-text input.
- **R8.6.c Studio Report-wrong dialog** (`69bfdc8` + test-coverage follow-up `9e44b1f`): new `frontend/src/components/ReportWrongFieldDialog.tsx` opens via a Flag-icon trigger button per `FieldRow`, sitting in the same R8.5 affordance flex row alongside `ConfidenceChip` and `FieldEvidencePopover`. Pre-fills `entityIndex`, computed `fieldPath` (via `fieldPathFor`, which now validates the identifier regex), and read-only current value; user types corrected value into a single Input. A `<details>` panel "What integrators would send" renders the equivalent `PartialFeedbackPayload` JSON via `buildPartialFeedback(...)` so users see the public contract without sending it. Save calls a new `useStudio.reportWrong({projectId, entityIndex, fieldName, correctValue})` store action that loads the latest baseline (annotation if present, else prediction), patches the single field, and POSTs `/api/v1/projects/{pid}/documents/{did}/annotations` with `parent_prediction_id`. Lab MUST NOT call `/extract/.../feedback`; the test pins this with a per-call URL assertion. The dialog disables Save when `latest_prediction.id` is null and shows an inline alert. Gate-review verdict: Ready-to-merge, no Critical/Important. R8.6.a deferred-validation item (#1) folded in: `fieldPathFor` now validates `key` against the backend `_SEG` identifier regex `/^[a-zA-Z_][a-zA-Z0-9_]*$/` and rejects non-non-negative-integer arrayIndex, with two new specs in `partial_feedback_payload.test.ts` covering the rejection paths. Reviewer's two Minor test-gap recommendations (Save-disabled empty-state + non-string `currentValue` JSON.stringify seeding) landed as `9e44b1f`. **Plan signature deviations**, both improvements, both intentional: (a) the dialog takes `fieldName: string` instead of the planned `fieldPath: string` and routes through `fieldPathFor` so the validation runs in a single source of truth; (b) the planned `issueType`/`notes` props on `reportWrong` were dropped because they are partial-feedback envelope metadata with no Annotation columns to map to — threading them through would silently drop `issue_type` and `notes` is already redundant with the dialog's free-text edit. The visible "What integrators would send" panel is the contract-teaching surface; users don't need to fill the metadata in Lab.

R8.6 gate reviews (3 subagent rounds): all green, no Critical, two Important during R8.6.b (both fixed in `f8f845e`), two Minor test-gap follow-ups during R8.6.c (both fixed in `9e44b1f`). Other Minor items deferred (stylistic renames, Flag-icon discoverability, no-op annotation guard, Radix `act()` warning suppression).

**R8.7 — Walking Skeleton E2E** (`151e2de`): single Playwright spec `frontend/e2e/walking_skeleton.spec.ts` (~210 lines) gated on `EMERGE_E2E=1`, plus `frontend/e2e/fixtures/sample.pdf` (320 KB Japanese parking receipt; same PDF the dogfood project 2 uses for real-world Gemini extraction). Walks register → create from `japan_receipt` → upload×3 → extract → 2 corrections (with field name discovered live via `page.request` against `documents/{did}` so the spec doesn't guess Gemini's output shape) → schema lock → API Console activate-for-API → key reveal modal → public `/extract/{api_code}/feedback` POST with `X-Api-Key` (via `page.request.post` so plaintext never traverses a logged form input) → readiness `regression_health.counterexamples_total ≥ 1` (asserted both via API and via UI absence of `data-testid="readiness-no-feedback"`) → `/projects/:id/review` `[data-testid^="review-row-"]` non-empty.

Two **forced adaptations** vs the overlay R8.7 recipe, both surfaced by the live run and documented in spec comments:

1. **Upload 3 PDFs, not 2.** Vibe-check pool excludes docs covered by saved annotations (`recompute.py:24-56` / spec §4.1). After my 2 corrections satisfy lock-status, both corrected docs leave the pool, so review-queue's `all` section would be empty. The 3rd uncorrected doc keeps `all` populated without needing judge verdicts.
2. **Drop the `/judge` POST.** `get_judge_provider()` (`backend/app/engine/judge.py:58-63`) raises `NotImplementedError` in production until R6 wires the pro-model judge — tests substitute via `dependency_overrides`, but a live POST returns 500. The plan's recipe assumed it worked live; the spec asserts the review-queue surface with what's actually populated (the unannotated 3rd doc in `all` and `spot_check`).

Plaintext key handling (the most security-sensitive piece): read once from the modal's `code[aria-label="API key plaintext"]` via `.textContent()`, passed to `page.request.post` as `X-Api-Key`, never `console.log`'d, never written to test artifacts (verified via `grep -r "ek_[A-Za-z0-9]{6,}" frontend/test-results/` returning empty). JWT read from `localStorage.emerge.token` follows the same pattern.

Live run validated end-to-end against running `uv run uvicorn app.main:app --reload --port 8000` with `GOOGLE_API_KEY` set + proxy reachable (Gemini calls require `127.0.0.1:7890` on this machine — when the proxy is down, `extract_document` fails with `httpx.ConnectError`, error_message is empty in DB because `str(httpx.ConnectError())` returns `''`). Total runtime: 21 s with warm Gemini, expect ~60-120 s on cold start.

**R8.7 hygiene-tail closure** — both backend gaps surfaced by the walking-skeleton ran to ground in this session:

- **Gap #51 → `9659493` + `f0b51e4`**: vibe-check pool now relaxes during schema iteration. New helper `vibe_check_includes_corrected(session, project_id) -> bool` returns True iff active version is draft or absent; new `ignore_annotations` kwarg on `vibe_check_predictions_query`. Four call-sites updated (recompute, readiness, /review-queue, /judge). Default kwarg preserves spec §4.1 — direct callers and the original `test_vibe_check_excludes_documents_with_saved_annotation` are unchanged. After the gate review flagged a route-level test gap, `f0b51e4` adds an integration test that flips lock state and asserts the corrected doc disappears from both /review-queue.all and /judge.judged_predictions. UX shape: the **Lock schema** action now means more — "from now on /review-queue is the production-monitoring surface, not the iteration scratch pad". No new UI, no new mental model.
- **Gap #50 → `fa72157` + `60f136d`**: `GeminiJudgeProvider` wires the production /judge path on `settings.default_model_pro` per CLAUDE.md model-tier-split memory. Mirrors `GeminiProvider`'s client-injection pattern so unit tests stay offline. `judge()` routes the protocol's full `system` prompt through Gemini's `system_instruction` slot (NOT a user-text Part — the system frame already carries schema + predicted_output, blurring would let the model treat them as conversation). Defensive shape-check drops malformed verdicts/literals/shapes per-entry to keep `JudgeCalibration` clean downstream. `get_judge_provider` raises a clearer `NotImplementedError` for `default_provider="openai"` with a pointer to `dependency_overrides`. 8 unit tests + the walking-skeleton E2E exercise the full path; reviewer's "_FakeSettings defined after callers" nit fixed in `60f136d`.
- **Walking-skeleton update → `8a317e4`**: `/judge` POST is back in the spec, asserts `judged_predictions.length >= 1`. After lock the vibe-check pool only contains the uncorrected 3rd doc, so judge runs on exactly 1 prediction (or 0 on a Gemini Pro 503-transient). `>= 1` is the right loud-fail gate — 0 means the wiring rotted. Live re-run: 1.3 min wall-clock with warm Gemini.

Real Gemini Pro behavior in the receipt smoke: judges parking-receipt `shop_name` as `down` consistently across 8 entities, `issue_date` and `total_amount` as `up`. The risky_fields and required_review surfaces are now genuinely populated end-to-end.

**Manual browser smoke of the new vibe-check lifecycle (chrome-devtools-mcp on project 10) surfaced three follow-on UX findings, all resolved in this session:**

- **Smoke #3 → `b950277`** (gap surfaced by #51, not introduced): docs without `per_field_confidence` were landing in `Spot-check` ("AI says fine, verify") even though the judge had never said anything. Three-line backend change in `get_review_queue`: only docs with non-empty per_field_confidence enter `up_only` (and therefore can be sampled into `spot_check`). New backend test pins the behavior.
- **Smoke #1 → `d4182cd`** (#51 follow-on UX): a user who saved a correction in Draft mode then opened `/review` saw the doc still there with no on-page explanation — natural "didn't I just fix that?" confusion. Backend: `ReviewQueueOut` now carries `schema_locked: bool` derived from the same `vibe_check_includes_corrected` helper (single source of truth, no second round trip). Frontend: `ReviewInboxPage` renders a one-line callout above the three sections when `!schema_locked`: *"Schema is in Draft — corrected documents stay here so you can revisit them. Lock the schema when you're done iterating; corrected docs leave the queue at that point."* Two new component tests pin show/hide.
- **Smoke #2 → `137dd3f`** (pre-existing, not #51-introduced): `ReadinessPanel` + `ReviewInboxBanner` showed stale state after upload/extract/save-correction — user had to reload the page to see updated counts. Pragmatic fix: `documents.ts` and `studio.ts` fire `useReadiness.load(projectId) + useReview.load(projectId)` after each mutation. Fire-and-forget so a transient panel-fetch failure can't block the mutation. Two new component tests pin the wiring.

After all three fixes, the iteration loop reads coherently in the browser: upload → extract → see panels update live → open Studio → edit → save → see panels update live + see the doc still in `/review` with a clear explanation of why → lock schema → callout disappears + corrected doc exits the pool. Spec §4.1 wording (committed in `6cf7686`) and observed behavior match.

### Reverse-chronological commit list (this branch)

```text
137dd3f fix(frontend): panels auto-refresh after document mutations
d4182cd feat(frontend): Draft-mode callout explains why corrected docs stay in /review
b950277 fix(api): spot-check requires actual judge verdicts
6cf7686 docs(spec): vibe-check pool definition is lifecycle-aware
6e5e51d docs(handoff): drop orphan duplicate Historical header
6dcf006 docs(handoff): refresh after R8.7 hygiene-tail closure (#50 + #51)
8a317e4 test(frontend): re-enable /judge POST in walking-skeleton
60f136d refactor(test): hoist _FakeSettings above its callers
fa72157 feat(api): wire production GeminiJudgeProvider for /judge
f0b51e4 test(api): pin route-level lock-flip behavior for vibe-check pool
9659493 feat(api): vibe-check pool relaxes during schema iteration
97eadbd docs(handoff): refresh after R8.7 walking-skeleton + flag judge-provider gap
151e2de test(frontend): walking-skeleton E2E covers publish + readiness + feedback
1c51bad docs(handoff): refresh after R8.6 partial-feedback builder + form + dialog
9e44b1f test(frontend): cover Report-wrong empty-state and non-string seeding
69bfdc8 feat(frontend): Studio Report-wrong dialog reuses partial-feedback shape
f8f845e fix(frontend): apply R8.6.b gate-review fixes to FeedbackTestForm
92937de feat(frontend): API Console partial-feedback example and test form
b9d4584 feat(frontend): partial feedback payload builder and types
e0cd152 docs(hygiene): track R8.5 smoke findings (47/48/49)
6885183 docs(handoff): refresh after R8.5 evidence popover + chip + gate-review polish
bd43798 test(frontend): cover popover dismissal paths and clarify allow-list intent
1a5a3e9 feat(frontend): Studio per-field evidence popover and confidence chip
3c1428b test(api): rename evidence pass-through test and use real key-walk
1195259 feat(api): surface per-field evidence and confidence in document detail
ca670f9 docs(handoff): refresh after R8.4 review inbox + smoke + hygiene 22 resolved
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
cd frontend && npm test                    : 19 files / 141 tests passed
cd frontend && npm run build               : 455 KB / 141 KB gzipped
cd frontend && EMERGE_E2E=1 npx playwright test walking_skeleton : 1 passed (21.2s, warm Gemini)
cd frontend && npm test                    : 141 passed (was 137; +2 review-callout, +1 doc-list auto-refresh, +1 studio auto-refresh)
cd backend  && uv run pytest -q            : 253 passed, 2 skipped, 4 warnings (post-hygiene closure + smoke sweep: +3 vibe-check helper, +1 route-level lock flip, +8 GeminiJudgeProvider, +1 spot-check semantic)
```

### Manual smoke completed (R8.1 + R8.2 + R8.3 + R8.4 + R8.7 automated)

- R8.7 (Playwright, project 5 `walk-1777984097879`, dogfood email `e2e-walking-{stamp}@e.com`): full happy-path automated. Captured timing — 21.2s end-to-end with Gemini already warm (3 PDFs × ~5s each for extract dominated). On a cold network, expect 60-120s for the first extract. Found two real backend gaps (now in §13 below): (a) `get_judge_provider` raises `NotImplementedError` in production code path — `/judge` returns 500 outside test harness; (b) vibe-check pool semantics correctly exclude annotated docs from review-queue, which the spec works around with a 3rd uncorrected doc. Operational note: spec does not auto-skip on connectivity failure; if the local proxy (Clash on `127.0.0.1:7890` here) is down or the backend lost its proxy env, extract calls fail silently as `httpx.ConnectError` → `error_message=''` in DB → docs go to `errored`. Restart pattern when proxy is down: `https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 uv run uvicorn app.main:app --reload --port 8000`.


- R8.5 (chrome-devtools-mcp driven, project 2 published `test1`, dogfood@example.com): seeded `per_field_evidence` + `per_field_confidence` directly into pred 2 (doc 3) and pred 3 (doc 2) since Gemini's existing predictions didn't carry them, then walked all six UI branches. State A (no evidence + no verdict on `issue_date` rows) shows neither chip nor button. State B (`up` + full evidence) shows button only, no chip. State C (`uncertain` + rationale-only) shows muted chip + button; popover renders only the rationale section, no Page line, no blockquote — the exact rationale-only branch the unit test pins. State D (`down` + full evidence) shows warning-bordered chip "NEEDS REVIEW" + button; popover renders Page 1 + 計 ¥330 (blockquote) + Rationale. State E (rationale-only) covered within C. State F (`down` + evidence with bbox/coordinates/region keys) verified the FE allow-list: popover rendered Page + Quote + Rationale, **no** forbidden keys reached the DOM, and `[FieldEvidencePopover] dropped forbidden/unknown evidence keys ... (spec §3.2 — no bbox/coordinates/region/polygon/span)` fired in the console. Toggle-close, Escape-close, and click-outside-close all confirmed. Dark theme: dialog `bg-bg-surface` resolves to `rgb(9,9,11)`, text `fg-primary` `rgb(244,244,245)`, border `border-default` `rgb(63,63,70)`; warning chip text+border `rgb(245,158,11)` against the dark surface — high-contrast, no AA concerns. Found two new hygiene items (47/48): `pickAllowedKeys` re-warns on every render (8× on a single field after a few toggles); `source_text_hash` is in the allow-list but not rendered in the popover JSX. Plus operational note (49): pred 2 + pred 3 in the dogfood DB now carry seeded evidence/confidence — forbidden keys were stripped post-smoke; spec-allowed keys retained for R8.6 to reuse.


A real walking-path smoke ran against `dogfood@example.com` on project test1 (built from `japan_receipt` builtin, 2 Japanese parking-receipt PDFs uploaded + extracted with Gemini):

- R8.1: register → create → upload → extract → Studio edit + save → reload (override visible) → Schema lock + unlock. Found auth race + Pages-column-always-0 bug; both fixed in `80458c8`/`82be98d`.
- R8.2: lock → API tab → Activate → Create key (modal plaintext + Esc-blocked + ack-gated dismiss) → reload (prefix-only) → Rename → Unpublish → curl `/extract/japan-receipts-v2` → 403 → Re-publish → Revoke. Found timezone drift + `api_published_at` re-stamp on rename; both fixed in `e7edcdf`/`d0d53ca`.
- R8.3 (chrome-devtools-mcp driven): fresh empty project (`r83-smoke-empty`, project 3) → all 3 publish_blockers translated, no raw slugs, no `100%`, regression reads "No production feedback yet"; published `test1` (project 2) → blockers section disappears, schema reads "Locked"; light + dark theme renders both panels cleanly. Found one new UX hygiene item (44): quality reads ~80% ± 23% with 0 obs because of Beta prior — backend should surface null on `observation_count === 0`. Non-blocking; tracked in hygiene tail §3.
- R8.4 (chrome-devtools-mcp driven, project 2 published `test1`): banner mounts BETWEEN `API Readiness` and `Documents` h1 (correct vertical position); three counts read `0 need review · 0 spot-checks · 0 docs total`; "Review next" disabled; "All caught up" callout renders. `/projects/2/review` shows three sections with hints + per-section empty copy. Sub-nav order is `Documents · Review · Schema · API`; `aria-current="page"` lands on Review when on `/review`, on Documents when on `/projects/:id`. Dark theme clean; only console output is the pre-existing React Router future-flag warnings. Found two non-blocking hygiene items (45, 46): banner "0 docs total" doesn't qualify the vibe-check semantics that the dedicated page hint already spells out; pluralisation "1 need review" should be "1 needs review". Tracked in hygiene tail §3a.

Open UX findings from those smokes are tracked in the hygiene tail. See §13 below for the full carry-forward.

---

## 2. Next: R8 MVP exit-gate audit → §13 P0 release hardening

R8.7 + both hygiene-tail backend gaps now landed. The R8 Productization MVP is **functionally complete and end-to-end validated on this branch**. The §12 exit gate is satisfied: every item is covered by either automated CI (`npm run lint && npm test && npm run build && uv run pytest`) or the walking-skeleton E2E.

§13 P0 status (2026-05-05 sweep):
1. ~~Release-checklist script~~ — `scripts/release-checklist.sh` runs lint/test/build/pytest in series with PASS/FAIL summary; `EMERGE_E2E=1` adds the Playwright walking-skeleton step. Per-step logs land in gitignored `.release-checklist-logs/`. Smoke verified: 4 pass, 1 skip on this HEAD.
2. ~~Local demo doc~~ — `docs/local-demo.md` mirrors the Playwright spec; all snippets use the `EMERGE_API_KEY` placeholder. Includes the proxy / extract-error / lock-status / api_code-duplicate troubleshooting paragraphs the smokes surfaced.
3. **API-key one-time-reveal contract test** — `frontend/src/__tests__/api_key_reveal_modal.test.tsx` covers Copy / dismiss-ack / one-shot render but does **not** assert "plaintext never written to localStorage". The `Storage.prototype.setItem` spy assertion the handoff line referenced lives in the **FeedbackTestForm** test, which is a different surface (transient-paste rather than reveal). Recommend a tiny follow-up to add the `setItem` spy to `api_key_reveal_modal.test.tsx` so both plaintext surfaces are pinned with the same shape. Non-blocking — modal source already has no localStorage write path.
4. ~~`published_version_id` semantics~~ — already covered: `backend/tests/test_publish_routes.py` has 9 explicit `published_version_id` assertions (rollback, rename-doesn't-republish, lab-activate-doesn't-bump). Walking-skeleton E2E re-exercises the publish path live.
5. ~~`api_code` uniqueness pre-migration check~~ — `scripts/check_api_code_uniqueness.py` chdirs to `backend/` then runs the `GROUP BY api_code HAVING COUNT(*) > 1` SELECT against `settings.database_url`. Exit 0 = clean, 2 = duplicates printed. Smoke-verified (clean) on the current dev DB.
6. ~~Merge strategy review~~ — branch graph is **linear**, no divergence. Details below.

### Branch graph audit (2026-05-05)

```text
origin/main          25b830b  test(engine): add Gemini live smoke + SOCKS proxy support  (R6 era)
                       │  +67 commits  (all R7 / R7.5 — incl. alembic 0015 global api_code)
local main           7aa4e0b  feat(api): R7.5 publish hardening
                       │  +61 commits  (all R8 productization MVP — no further alembic)
r8-productization-mvp 45f82b8  docs(handoff): refresh after smoke-finding sweep
```

`git merge-base origin/main r8 == 25b830b`; `git merge-base main r8 == 7aa4e0b`. r8 is a strict descendant of local main, which is a strict descendant of origin/main. Every prospective merge is a fast-forward.

Recommended path (Option B, two reviewable checkpoints):

1. **Push local main to origin/main first.** This is just R7.5; it's the publishing/readiness backend the R8 UI builds on. Lands alembic 0015 on origin so the next ff-push doesn't carry a schema change. Discipline before the push: `cd backend && uv run python ../scripts/check_api_code_uniqueness.py` against any DB the migration will eventually run on.
2. **Then ff-merge `r8-productization-mvp` → main and push.** All 61 commits are R8 frontend + a few engine/judge gaps; no migration. This is where the dogfood walk in `docs/local-demo.md` lives, so the post-push verification is "open <http://localhost:5173> on a fresh clone, walk the demo doc end-to-end".

Option A (single ff push) is functionally identical end-state but combines 128 commits into one origin update — tolerable for one-developer dogfood, but Option B gives you a clean R7.5 / R8 split for later bisects.

Either way: do not push without user approval, and do not force-push to main under any circumstances.

Two minor gate-review items remain open from this session (both deferrable):

- **Naming**: `ignore_annotations=include_corrected` reads as a double negative. Reviewer suggested renaming the kwarg to `include_corrected_docs` so both layers share the word. Sweep when `recompute.py` is next touched.
- **Helper roundtrips**: `vibe_check_includes_corrected` does two SELECTs (project, then version) instead of a join. Tiny on SQLite, real on Postgres for hot endpoints. Profile-driven; defer.

Once R8 MVP exit-gate is signed off, the v1.1 backlog (§13 P1+) opens up: schema-editor chat mode, AutoResearch viewer, real PDF preview, NL-first onboarding.

### Historical R8.7 entry detail (kept for reference)

Authoritative R8.7 detail: `docs/superpowers/plans/2026-05-04-r8-productization-mvp.md`, section **Phase R8.7 — Walking Skeleton E2E** (around lines 879+).

R8.7 in one paragraph: a single Playwright spec that walks the full happy path, end-to-end, against a live backend with provider key configured by the environment, without printing any secret. Touches every R8 surface: register → create from non-empty builtin (`japan_receipt`) → upload sample PDF(s) → extract → Studio edit + save correction (loop on a second doc to satisfy lock-status) → Schema lock → API Console Activate-for-API + create key + one-time reveal + ack → Send test feedback (form OR `request.post` from Playwright) with the freshly-revealed plaintext key + a known prediction_id → ReadinessPanel `regression_health.counterexamples_total >= 1` → `/projects/:id/review` has at least one section non-empty (after `POST /api/v1/projects/:id/judge` to materialise verdicts).

Suggested Claude Code prompt for the next session:

```text
Continue R8 Productization MVP on branch r8-productization-mvp at
/Users/qinqiang02/colab/codespace/ai/emerge.

Pre-read in order before any work:
1. CLAUDE.md
2. docs/superpowers/plans/2026-05-04-r8-continuation-handoff.md
3. docs/superpowers/plans/2026-05-04-r8-productization-mvp.md (overlay) — Phase R8.7 (Walking Skeleton E2E)
4. docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md
5. docs/superpowers/specs/2026-05-02-overall-design.md §1, §7 (publish / API key flow)
6. frontend/playwright.config.ts and any existing frontend/e2e/* skeletons

Verify health at HEAD before starting:
- cd frontend && npm run lint && npm test && npm run build
- cd backend  && uv run pytest -q
- Confirm a provider key (Gemini / Anthropic) is configured for the
  backend so /extract works end-to-end. Do NOT print the value.

Then implement Phase R8.7 per the overlay (one commit):

R8.7 — Walking Skeleton E2E:
  - Create frontend/e2e/walking_skeleton.spec.ts (scenario in §11 of
    this handoff and overlay lines ~879+).
  - Add frontend/e2e/fixtures/sample.pdf (any 1-page PDF).
  - The spec must:
    - register fresh user → /projects empty
    - create from a non-empty builtin (japan_receipt) → /projects/:id
      shows ReadinessPanel + Review Inbox banner + Document table
    - upload sample.pdf → row appears with status=uploaded
    - trigger extract → row transitions to status=extracted
      (allow generous timeout — 60s — for cold provider call)
    - open Studio → edit one field → Save correction → re-open →
      annotation override visible. Repeat for a 2nd uploaded doc so
      lock-status has 2+ saved corrections with stable fields.
    - /projects/:id/schema → lock the schema
    - /projects/:id/api-console → Activate-for-API → create key →
      modal plaintext + ack → close
    - In the SAME tab: paste the freshly-revealed plaintext key into
      the FeedbackTestForm + a known prediction_id from step 4 →
      counterexample_id surfaces. (Or use Playwright request.post if
      that is more reliable; the spec must NOT print the key value
      to test logs.)
    - Trigger POST /api/v1/projects/:id/judge so vibe-check verdicts
      materialise; verify ReadinessPanel
      regression_health.counterexamples_total >= 1.
    - /projects/:id/review has at least one section non-empty.
  - Scenario MUST NOT log the plaintext API key, the JWT, or the
    provider key. Use page.evaluate to fetch DOM contents only when
    necessary.
  - Commit: test(frontend): walking-skeleton E2E covers publish + readiness + feedback

Conventions to carry through (R8.1–R8.6):
- After the commit, dispatch superpowers:requesting-code-review (NOT
  a bare general-purpose agent — see memory
  feedback_gate_review_subagent.md). The R8.7 reviewer should look
  for:
  * No secrets printed (X-Api-Key plaintext, JWT, provider key).
  * Selectors using accessible queries (getByRole / getByLabelText
    where possible) rather than CSS classes that may churn.
  * Generous waits keyed on observable state (status=extracted,
    counterexamples_total >= 1) rather than fixed sleeps.
  * The judge call is fired BEFORE asserting the review queue, not
    after.
- When you touch hygiene-tail items naturally (44 quality CI when 0
  obs, 45/46 review-inbox banner plural copy, 47/48 popover
  console.warn dedupe + source_text_hash render) sweep them in the
  same commit. Items (49) operational note about seeded predictions
  in the dogfood DB is informational only.
- After the commit, refresh this handoff doc once more and STOP for
  the human R8 MVP exit-gate review (see §12).

R8.7 hard rules:
- Never read, print, or log secrets — provider key, JWT, X-Api-Key
  plaintext.
- E2E spec must run against a real backend with a real provider key;
  if the provider call fails, the spec SHOULD fail (don't auto-skip).
  Local dev convenience: an env flag (EMERGE_E2E=1) gates the spec.
- The spec MUST exercise the publish flow against /extract/{api_code}
  with the freshly-revealed key — that is the whole point of the
  walking skeleton.
- No bbox / coordinates / regions / polygons / spans anywhere
  (continues from R8.5/R8.6).

Out of scope for R8.7 (and R8 MVP entirely): AutoResearch viewer,
MatchingProject, VerificationProject, real PDF preview, Studio entity
nav / collapse, schema chat mode, NL-first onboarding.

R8.6 context the new session should know:
- lib/feedback.ts is the single shared serializer for both the
  public-facing API Console form and the in-Lab Studio Report-wrong
  dialog. fieldPathFor now validates the identifier regex; reuse it.
- components/FeedbackTestForm.tsx keeps the pasted plaintext API key
  in component state only (cleared on success + on unmount). The
  axios `Authorization` header is explicitly overridden to undefined
  on the public-feedback POST so the JWT does not bleed onto the
  public boundary.
- components/ReportWrongFieldDialog.tsx mirrors the partial-feedback
  shape READ-ONLY for users to learn the contract, but Lab posts to
  /annotations. The Flag-icon trigger sits in the FieldRow flex row
  next to the evidence popover button (R8.5).
- stores/studio.ts now exposes reportWrong({projectId, entityIndex,
  fieldName, correctValue}) that piggybacks the existing
  /annotations endpoint and inherits role=none from
  save_correction(...).
- Hygiene tail items (44, 45, 46, 47, 48) are still open; (49) is
  operational. Don't expand R8.7 scope to chase them unless the E2E
  spec naturally re-touches the same files.
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
Prompt 6 (DONE)  => R8.5 Field Evidence display (backend payload + popover/chip)
Prompt 7 (DONE)  => R8.6 Partial Feedback UI: builder + API Console form
                    + Studio Report-wrong dialog (gate-fix in f8f845e,
                    test-coverage follow-up in 9e44b1f)
Prompt 8 (DONE)  => R8.7 Walking Skeleton E2E (151e2de) + hygiene-tail
                    closure: gap #51 vibe-check lifecycle (9659493 +
                    f0b51e4), gap #50 GeminiJudgeProvider (fa72157 +
                    60f136d), /judge re-enabled in spec (8a317e4),
                    spec §4.1 update (6cf7686), smoke sweep
                    (b950277 spot-check + d4182cd Draft callout +
                    137dd3f panel auto-refresh).
NEXT             => §13 P0 Release hardening / dogfood. R8 MVP
                    exit-gate satisfied. Iteration loop reads coherently
                    end-to-end in the browser (verified via chrome-
                    devtools-mcp on project 10).
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
