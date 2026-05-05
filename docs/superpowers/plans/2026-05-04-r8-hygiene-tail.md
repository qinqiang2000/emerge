# R8 hygiene tail

Carry-forward list of deferred fixups surfaced during R8.0–R8.2 gate reviews and manual smoke. Triaged as "real but non-blocking" — none of these are red-line violations or correctness bugs that block the next phase.

**How to consume**: when you touch a file in R8.3+, sweep relevant items in the same commit. Items tagged with phase numbers (R8.5 / R8.6 / R8.7) are best deferred until those phases naturally re-touch the code. Items without a phase tag are free-running cleanup.

**Conventions**:
- `(N)` is a stable item id. Once resolved, mark with `~~(N)~~ → fixed in <hash>` in §4.
- "Origin" labels: `gate-review` (subagent reviewer), `smoke` (manual browser walk), `reviewer-cross-cutting` (phase-end observation).
- Treat as advisory; the overlay plan (`2026-05-04-r8-productization-mvp.md`) and CLAUDE.md remain authoritative.

---

## 1. R8.1 carryover

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| 1 | gate-review (R8.1.b) | `pages/ProjectCreate.tsx:42` | Clear `error` state when `name` input changes (currently the failure banner lingers across edits). |
| 2 | gate-review (R8.1.b) | `__tests__/project_create.test.tsx` | Add error-path assertion (backend rejects → role=alert renders) and disabled-textarea presence assertion. |
| 3 | gate-review (R8.1.b) | `__tests__/project_create.test.tsx` | `afterEach` should reset `useTemplates` to empty (currently leaks; no other suite reads it today, so latent). |
| 4 | gate-review (R8.1.b) | `pages/ProjectCreate.tsx` | Whitelist guard for `setError(\`errors.${code}\`)` — unknown codes hit the missing-key fallback. |
| 5 | gate-review (R8.1.b) | `pages/ProjectCreate.tsx` | Optional: textarea placeholder also reads "Coming in v1.1" (currently the helper text says it but the field placeholder still says "Describe it..."). |
| 6 | gate-review (R8.1.a–e) | `App.tsx`, test setup | React Router v7 `future` flag silencer — every test using MemoryRouter logs the v7 future warnings. Add `future={{v7_startTransition: true, v7_relativeSplatPath: true}}`. |
| 7 | gate-review (R8.1.c onward), smoke | `__tests__/document_list.test.tsx`, `studio_save.test.tsx`, `schema_editor.test.tsx`, `api_console.test.tsx` | `act()` warnings — `useEffect → store.load()` promise chain triggers setState outside `act`. Replace per-test `settle()` with per-assertion `waitFor(...)`, or skip auto-load in tests via a flag, or migrate to MSW. **R8.2.c reuses the same pattern** (#41). |
| ~~8~~ | gate-review (R8.1.c) | `stores/documents.ts:55-57` | ~~Drop manual `Content-Type: multipart/form-data` — axios sets it correctly with boundary.~~ Resolved — see §4. |
| 9 | gate-review (R8.1.c) | `pages/DocumentList.tsx:54` | `accept="application/pdf,image/*"` includes images even though backend doesn't process them; align with R8.5 evidence work. |
| 10 | gate-review (R8.1.d) | `pages/Studio.tsx:154` | `<label>` wraps `<Input>` without explicit `htmlFor`/`id` for a11y. |
| 11 | gate-review (R8.1.d), smoke | `pages/Studio.tsx` field rendering | **JSON.stringify type-coercion**: number `100` becomes string `"100"`, boolean `true` becomes `"true"` on save. R8.5 evidence-aware editor naturally fixes; track explicitly so v1 GA does not ship lossy mode. |
| 12 | gate-review (R8.1.d) | `pages/Studio.tsx:14` ↔ `stores/studio.ts:51` | `baselineOutput()` duplicates `seedDraft()`. Export `seedDraft` from store and reuse. |
| 13 | gate-review (R8.1.d), smoke | `pages/Studio.tsx`, ApiConsole | No save-success toast on Studio / Activate / Unpublish / Revoke. MVP fine; add a small `useToast` hook later. |
| 14 | gate-review | cross-cutting | Optional `renderErrorKey(t, errKey)` helper for symmetry with future toasts. |
| 15 | gate-review (R8.1.e) | `pages/SchemaEditor.tsx` | Save POSTs even with no diff → no-op `version_number` bump on backend. Add dirty-check modeled on Studio. |
| 16 | gate-review (R8.1.e) | `pages/SchemaEditor.tsx:41-44` | Sync useEffect on `active` may overwrite in-flight local edits. Guard with `JSON.stringify` equality. |
| ~~17~~ | gate-review (R8.1.e), reviewer-cross-cutting | Cross-store | ~~`errors.${code}` envelope mapping repeats in 6 stores; lift `emergeCode()` helper to `lib/api.ts`.~~ Resolved — see §4. |
| 18 | gate-review (R8.1.e) | Test helpers | `settle()` helper copy-pasted in 3+ specs; extract to `__tests__/_helpers/settle.ts`. |
| 19 | gate-review (R8.1.e) | `i18n/locales/en.json` | `schema.tab_form` and `schema.lock_status_blocked` defined but unused (`tab_chat` is the explicit chat-mode placeholder per overlay; keep). |
| 20 | gate-review (R8.1.e) | `pages/SchemaEditor.tsx:163-168` | Notes Textarea renders even when `draft.length === 0` — cosmetic inconsistency with no-fields empty state. |
| ~~22~~ | gate-review (sub-nav) | `components/ProjectSubNav.tsx:9-11` + `__tests__/project_sub_nav.test.tsx` | ~~Trailing-slash matcher fragility — `pathname.endsWith` would mark all tabs inactive on `/projects/7/api-console/`. Add hardening test or switch to `useMatch`.~~ Resolved — see §4. |
| 23 | gate-review (sub-nav) | `pages/SchemaEditor.tsx`, `Studio.tsx` | Cosmetic: success branches use outdented fragments; let prettier or wrapping div tidy. |
| 25 | gate-review (auth boot-prime) | `stores/auth.ts:19, :25` | Double-read of `emerge.token` from localStorage — now redundant with `bootAuthFromStorage()` in `lib/api.ts`. Cleanup candidate. |
| 26 | gate-review (auth boot-prime) | `__tests__/api.test.ts` | `bootAuthFromStorage` tests only exercise the helper, not the import-time auto-call. Add `vi.resetModules() + dynamic import()` test. |
| 27 | smoke | `frontend/public/` | Missing `favicon.ico` — 404 in console on every page load. Cosmetic. |
| 28 | smoke (R8.1) | `pages/Studio.tsx` header | Project name not visible anywhere on `/projects/:id/studio/:did` — user has to read URL bar. |
| 29 | smoke (R8.1) | `pages/Studio.tsx` | 8-entity scroll, no entity nav / collapse-by-default. |
| 30 | gate-review / smoke (R8.1.e) | `pages/SchemaEditor.tsx` | Positive `can_lock` state has no UI hint — just a bare Lock button. A green "Ready to lock" line would close the loop. |

---

## 2. R8.2 minors

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| 32 | gate-review (R8.2.a) | `stores/projects.ts` `ContractDiff` type | `from_version_id` typed `number \| null \| undefined`; tighten to `number \| null` to mirror pydantic exactly. |
| 33 | gate-review (R8.2.a) | Cross-store convention | `api.post(url)` single-arg form for empty-body POSTs is now used in `unpublish`. Document the convention or wrap in a tiny helper. |
| 34 | gate-review (R8.2.b) | `components/ApiKeyRevealModal.tsx:21-23` | `setTimeout` for "Copied" reset is not cleared on unmount. Wrap in useEffect cleanup. |
| 35 | gate-review (R8.2.b) | `__tests__/api_key_reveal_modal.test.tsx:47-50` | `Object.defineProperty(navigator, "clipboard", ...)` bypasses `vi.spyOn`/`restoreAllMocks` — leaks across tests. Use `vi.stubGlobal`. |
| 36 | gate-review (R8.2.b) | `__tests__/api_key_reveal_modal.test.tsx` | Test gap: assert post-dismiss `onConfirmDismiss` called with no arguments and that the plaintext is not re-emitted. |
| 37 | gate-review (R8.2.b) | `__tests__/api_key_reveal_modal.test.tsx` | No dark-theme smoke render — token-only styling makes it implicitly fine; flag if R8 ever adds a theme test harness. |
| 38 | gate-review (R8.2.b) | `components/ApiKeyRevealModal.tsx` warning | `text-status-warning` vs `bg-bg-surface` may not meet WCAG AA contrast in dark mode. Verify with axe / contrast checker. |
| 39 | gate-review (R8.2.c) | `pages/ApiConsole.tsx:172-176` | `actionError` (raw EN backend message) and `error` (i18n key) mixed in one `<p>`. Map EmergeError.code → `api_console.errors.<code>` for translatable surfaces. |
| 40 | gate-review (R8.2.c) | `backend/app/api/routes/versions.py` GET `/versions` | Backend returns full `ProjectVersionOut` (schema + global_notes + model_id) just to render `version_number + locked` in the rollback select. Add `?meta=true` query param for a slim variant. |
| 41 | gate-review (R8.2.c) | `__tests__/api_console.test.tsx` | `act()` warnings — same pattern as #7; fold into the cross-spec fix. |
| 42 | gate-review (R8.2.c), smoke | E2E (R8.7) | Add a rename-doesn't-activate-Lab regression test (Playwright path). The unit test surface caught the Activate/Rename input collision; E2E should pin the spec §7.2 invariant. |
| 43 | gate-review (post tz fix) | `backend/app/schemas/*.py` | The 7 `_serialize_dt` blocks across schemas (R8.2 + the 4 preempted ones) duplicate the same body. Refactor to `Annotated[datetime, PlainSerializer(...)]` or a small mixin. Cosmetic; explicit declaration is easier to grep so leave until coverage expands. |

---

## 3. R8.3 minors

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| 44 | smoke (R8.3) | `backend/app/services/readiness.py` quality + `frontend/src/components/ReadinessPanel.tsx` `QualityRow` | When `observation_count === 0` (and tp/fp both 0), the Bayesian prior surfaces as e.g. `80% ± 23%` next to a small "0 obs · vibe-check 0" tag. Technically correct but visually reads like an earned signal. Two options: (a) frontend mutes / hides the percentage when `observation_count === 0` (5-line `QualityRow` change); (b) backend returns `judge_precision = null` / null CI bounds when `observation_count === 0` and frontend renders "Not enough data" copy. Option (b) is cleaner — flag for whenever readiness payload is next touched (R8.5 evidence work would naturally re-touch the document detail / readiness path). Non-blocking. |

---

## 3b. R8.5 minors

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| 47 | smoke (R8.5) | `frontend/src/components/FieldEvidencePopover.tsx:12-38` (`pickAllowedKeys`) | `console.warn` re-fires on every render. Doc-3 smoke logged "[FieldEvidencePopover] dropped forbidden/unknown evidence keys ... (8 times)" from a single bbox-leaked cell after a few popover open/close toggles — `pickAllowedKeys` runs in the render path and is invoked again on each `setOpen` state change. Frontend reviewer's minor #3 already flagged unconditional `console.warn`; this is the noisier sibling. Cheapest fix: hoist sanitisation to a `useMemo` keyed on `(entityIndex, fieldName, evidenceMap)` so the warn fires at most once per cell-shape change. Sweep when `FieldEvidencePopover.tsx` is next touched (likely R8.6 if the same allow-list pattern is reused for the partial-feedback transient key form). |
| 48 | smoke (R8.5) | `frontend/src/components/FieldEvidencePopover.tsx` popover JSX | `source_text_hash` is in `EVIDENCE_ALLOWED_KEYS` (so it doesn't trigger drift `console.warn`) but the popover JSX never renders it. Plan said "and optionally `source_text_hash` if surfaced", which left this ambiguous. Two options: (a) render as small monospace footer like `hash: abc123de…` for diagnostic users; (b) drop from the allow-list so future drift surfaces it as a console.warn. Default toward (a) — diagnostic surface is non-empty and it gives integrators something to reference in support tickets. Non-blocking. |
| 49 | smoke (R8.5) operational | dogfood SQLite DB pred 2 + pred 3 | R8.5 smoke seeded `per_field_evidence` and `per_field_confidence` on the existing predictions (Gemini didn't return them). Forbidden bbox/coordinates/region keys were stripped post-smoke; spec-allowed keys remain. R8.6 smoke can reuse this seed; if a fresh re-extract is wanted, null both columns or `DELETE` the predictions and re-trigger extract. |

---

## 3c. R8.7 backend gaps surfaced

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| ~~50~~ | smoke (R8.7) | `backend/app/engine/judge.py:58-63` (`get_judge_provider`) | ~~Production `/judge` cannot be exercised...~~ Resolved — see §4. |
| ~~51~~ | smoke (R8.7) | `backend/app/engine/recompute.py:24-56` (`vibe_check_predictions_query`) | ~~Counterintuitive interaction: vibe-check pool excludes corrected docs immediately on save...~~ Resolved — see §4. |
| 52 | smoke (R8.7) operational | `backend/app/engine/extract.py:117-130` error_message capture | When `httpx.ConnectError` fires (e.g. proxy down, DNS failure), `str(exc)` returns `''`, so `prediction.error_message` is the empty string — UI shows "errored" with no diagnostic, and inspecting the DB gives nothing. Cheapest fix: replace `str(exc)[:1900]` with `f"{type(exc).__name__}: {str(exc) or '(no message)'}"[:1900]` so at least the exception class is captured. Sweep when extract.py is next touched (R6 territory likely). |
| 53 | gate-review (#51 follow-up) | `backend/app/engine/recompute.py` `ignore_annotations`/`include_corrected` naming | Double-negative in the call-site `ignore_annotations=include_corrected` reads awkwardly. Reviewer suggested renaming the kwarg to `include_corrected_docs` so both layers share the same word. Cosmetic; sweep when recompute.py is next touched. |
| 54 | gate-review (#51 follow-up) | `backend/app/engine/recompute.py` `vibe_check_includes_corrected` | Helper does two SELECTs (project, then version) instead of one join. Tiny on SQLite, real on Postgres for hot endpoints (readiness, review-queue, judge all call it). Fold into `select(Project, ProjectVersion).join(...)` when profiling shows it matters. Defer. |
| 55 | gate-review (#50 follow-up) | `backend/tests/test_gemini_judge_provider.py` | Two `_FakeSettings` `monkeypatch` tests don't replace `genai.Client` — they rely on the SDK's permissive `Client(api_key="test-key")` constructor not making a network call at construction time. If the SDK adds a connectivity probe in a future version, these tests start hitting the network. Mitigation: `monkeypatch.setattr("app.engine.providers.gemini_judge_provider.genai.Client", lambda **_: object())`. Defer. |
| 56 | gate-review (#50 follow-up) | `backend/app/engine/providers/gemini_judge_provider.py` | No unit test pinning that `judge()` does NOT swallow network exceptions — `run_judge`'s outer `except Exception` does, so the observable behavior (per_field_confidence={}) is correct, but a test at the provider layer would document the contract explicitly. Add when next touching this file. |
| 57 | gate-review (#50 follow-up) | `backend/app/engine/providers/gemini_judge_provider.py` | Defensive shape-check silently drops malformed verdict entries. Reviewer suggested adding `log.warning("judge returned malformed entries: dropped N")` so ops has signal when the model drifts. Non-blocking. |

---

## 3a. R8.4 minors

| # | Origin | File / area | Item |
|---|--------|-------------|------|
| 45 | smoke (R8.4) | `frontend/src/components/ReviewInboxBanner.tsx` "all docs" count + en.json `review.all_count` | On project 2 (test1) the banner reads `0 docs total` while the Documents table below clearly shows 2 extracted docs. Backend semantics are correct: `review-queue.all` is the vibe-check pool, which is empty until judge has run. The dedicated `/review` page footer-hint already qualifies this ("Every document in the current vibe-check set."), but the banner does not — the bare phrase reads like "no documents exist". Suggest re-wording to `0 in vibe-check` (or appending `· vibe-check` chip) so the discrepancy with the table is self-explanatory. Non-blocking; tracked for R8.5 territory where the readiness/judge wiring is next touched. |
| 46 | smoke (R8.4) | `frontend/src/i18n/locales/en.json` `review.required_count` etc. | Pluralisation: "1 need review" should be "1 needs review"; same for `spot_check_count` / `all_count`. i18next supports `_one` / `_other` keys. Cosmetic; current count copy is acceptable at scale > 1. |

---

## 4. Resolved (kept for audit trail)

- ~~(21)~~ ProjectSubNav explicit `onApi` check → fixed in `e282200` (R8.2.c).
- ~~(24)~~ Plan §314/323 read-only field name/type wording → fixed in `2432ae9`.
- ~~(31)~~ ApiConsole Activate/Rename Input collision → fixed in `035031c`.
- ~~(timezone-A)~~ UTC offset on Out schema datetimes → fixed in `e7edcdf` + `d0d53ca`.
- ~~(rename-B)~~ `publish()` no longer re-stamps `api_published_at` on pure rename → fixed in `e7edcdf`.
- ~~(auth-race)~~ Auth boot-prime — JWT attached at `lib/api.ts` module load → fixed in `80458c8`.
- ~~(pages-col)~~ Backend `Document.page_count` always 0 → frontend dropped the column → fixed in `80458c8` + `82be98d`.
- ~~(8)~~ `stores/documents.ts` manual `Content-Type: multipart/form-data` dropped (axios sets the boundary itself) → fixed in the R8.3 readiness-panel commit; tests updated to assert no manual header.
- ~~(17)~~ Cross-store `emergeCode()` lifted to `lib/api.ts` as `emergeCode` + `emergeErrorKey` helpers; all 6 stores migrated → fixed in the R8.3 readiness-panel commit.
- ~~(22)~~ ProjectSubNav trailing-slash fragility → switched from `pathname.endsWith` to `useMatch` (path-pattern based, tolerant of trailing slashes and nested children). Test asserts Review tab href + active state. Fixed in the R8.4 review-inbox commit.
- ~~(50)~~ `get_judge_provider` `NotImplementedError` in production → wired `GeminiJudgeProvider` on `settings.default_model_pro` per CLAUDE.md model-tier-split memory. 8 unit tests in `test_gemini_judge_provider.py` pin request shape + parsing + routing. Live verified by walking-skeleton E2E (`gemini-3.1-pro-preview` returns sensible verdicts on receipt PDFs — `shop_name=down`, `issue_date=up`, `total_amount=up`). Fixed in `fa72157` + `60f136d` (gate-review fixture-order nit).
- ~~(51)~~ Vibe-check pool excludes corrected docs immediately on save → coupled pool semantics to schema lifecycle: relaxed during draft, strict (spec §4.1) once locked. New helper `vibe_check_includes_corrected(session, project_id) -> bool`; new `ignore_annotations` kwarg on `vibe_check_predictions_query`. Four call-sites updated (recompute, readiness, /review-queue, /judge). Default kwarg preserves spec §4.1 — direct callers and the original test_vibe_check_excludes_documents_with_saved_annotation are unchanged. Route-level lock-flip integration test in `f0b51e4` pins the wire-up. Fixed in `9659493` + `f0b51e4`.

---

## 5. Smoke findings not yet ticketed

These came up during the R8.1 / R8.2 manual walks; none are blockers but worth flagging when their phase lands.

- (R8.2 smoke / minor) Modal NAME label + value both uppercased via CSS `uppercase`. A custom name like `MyKey-2` renders `MYKEY-2`. Move uppercase to label span only.
- (R8.2 smoke / minor) Copy button has no `aria-live` region — screen reader users get no audible "Copied" confirmation.
- (R8.2 smoke / minor) Snippet URL hardcodes `https://api.emerge.dev/...` even on dev. Use `window.location.origin` or an env var.
- (R8.2 smoke / not-tested-yet) Rollback flow needs ≥2 locked versions; only `v0` exists in the smoke project. Defer to E2E.
- (R8.2 smoke / not-tested-yet) Contract-diff `has_breaking_changes` does not currently gate publish on backend; flag whether MVP needs a UI confirm modal.
- (R8.2 smoke / not-tested-yet) `api_code` 409 conflict (two projects, same code) untested in UI; deferred to E2E.

---

## 6. Maintenance

- After each phase commit, dispatch the gate-review subagent (per memory `feedback_gate_review_subagent.md`). Append fresh items here with the next free `(N)` and an origin tag.
- When closing items, move the line to §4 with the resolving commit hash. Don't delete — the audit trail is cheap and the file is small.
- If this file grows past ~80 items, time to take a sweep commit: pick a coherent batch (e.g. all i18n hygiene, or all act() warnings) and resolve them in one focused PR before R8.X+1.
