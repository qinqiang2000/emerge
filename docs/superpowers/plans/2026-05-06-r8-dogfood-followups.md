# R8 dogfood follow-ups (2026-05-06)

Carry-forward fixes surfaced by the 2026-05-06 manual dogfood walk on
`docs/local-demo.md`. The trust-side fixes (Readiness/Review/register
copy) already shipped in commit `1ba770e`; this doc is the **remaining
queue** the user explicitly approved during that session.

**How to consume**: items are stable-numbered. Decision direction
already locked-in by the user is in **bold** under each item — do not
re-litigate; if a constraint blocks, raise before deviating.

**Branch**: `r8-productization-mvp`. Cross-references:
- Trust fixes already shipped: commit `1ba770e`
- Adjacent hygiene queue: `2026-05-04-r8-hygiene-tail.md` (item #13
  "no save-success toast" overlaps with #4 below — resolve here).

---

## Decided scope

### #1 — Public extract must not pollute the Lab Document table

**Direction: public extract does NOT create rows in `documents`.**

Today, `POST /extract/{api_code}` (with X-Api-Key) creates a `Document`
row + `Prediction` row, both visible in the editor's
`/projects/:id` Documents table and pulled into the vibe-check pool.
Dogfood surfaced `sample.pdf` and `tiny.pdf` (both from integrator-side
curl) showing up under the user's editor view alongside their own
uploads. Two problems:

- **Workspace contamination** — editor sees integrator activity mixed
  with their own corrections. Confusing on a single-tenant local demo;
  damaging once a project has real integrator traffic.
- **Vibe-check skew** — public-traffic predictions feed into the same
  pool the editor reviews. Editor-side review/correction signal gets
  diluted.

Approach (suggested, not mandated):
- Either drop the `Document` row entirely on public extract — store
  only the `Prediction` against an ephemeral file_blob reference, OR
- Add `Document.source: "lab" | "public_api"` (default `"lab"`),
  filter the editor's list-documents API + vibe-check pool to
  `source = "lab"`, and surface public-traffic predictions on a
  separate page (out of scope for this PR — leave a `TODO(integrator-traffic-view)`).

Either way needs an alembic migration if the schema changes. Keep
public-API's `Prediction` rows so feedback / counterexamples still
correlate by `prediction_id`.

Files to start from:
- `backend/app/routers/public_extract.py` (the public POST handler)
- `backend/app/models/document.py`
- `backend/app/services/vibe_check.py` (pool selection)
- `backend/app/routers/documents.py` (editor list endpoint)

Test entry points: `backend/tests/test_public_extract.py`,
`backend/tests/test_vibe_check.py`.

---

### #2 — Public ExtractResponse shape diverges from `docs/local-demo.md`

**Direction: change the backend response to match the doc, with
explicit `output` envelope.**

Today's response: `{entities, prediction_id, project_version}`
Doc-promised: `{request_id, prediction_id, project_version_id, output, ...}`

Diff:
- `entities` (top-level) → `output.entities` (envelope opens room for
  `output.confidence`, `output.field_evidence`, etc. without further
  shape churn)
- `project_version` → `project_version_id` (rename for consistency
  with `prediction_id`)
- add `request_id` (mirror of `prediction_id` so feedback POST's
  `request_id` field has an obvious source)

This is a **breaking change** for any existing integrator. Local
walkthrough is the only consumer today — safe pre-GA. Bump the
response version somewhere obvious if you want a guard rail
(`X-Emerge-API-Version` header, or `version: "1"` in the JSON), but
the user did not require it.

Files:
- `backend/app/schemas/extract.py` (or wherever ExtractResponse lives)
- `backend/app/routers/public_extract.py`
- `frontend/src/components/ApiConsole.tsx` snippets — update the curl
  + python examples to show parsing `response["output"]["entities"]`
  + sending `response["request_id"]` back as feedback
- `docs/local-demo.md` should already be correct — re-grep to verify

Tests to update: `backend/tests/test_public_extract.py`,
`backend/tests/test_partial_feedback.py` if it asserts response shape.

---

### #3 — Studio dual affordance (textbox + "Report this field as wrong" button)

**Direction: drop the per-field "Report this field as wrong" button.
Editing the value IS the correction. Add a row-level overflow ⋮ menu
where a user can flag-without-correcting (e.g., "model output is
unparseable", "field doesn't apply").**

Rationale: today every field has an editable textbox **and** a button.
A first-time user reads both for ~10s wondering if they're different
intents. Editing already produces a partial-feedback Annotation; the
button additionally produces a no-correct-value Annotation with
`issue_type` set. Two paths for the same outcome 90% of the time.

Files:
- `frontend/src/pages/Studio.tsx` (per-field render)
- `frontend/src/components/ui/DropdownMenu.tsx` (or whatever the
  Radix wrapper is named) for the ⋮ menu
- backend partial-feedback contract already supports `correct_value:
  null` with a non-null `issue_type` — no backend change needed

Update: `frontend/src/__tests__/studio_save.test.tsx`.

---

### #4 — Save correction has no toast

**Direction: 2-second auto-dismiss "Saved" pill, top-right of the
Studio header. No new dependency — useEffect-based state.**

Overlaps with `2026-05-04-r8-hygiene-tail.md` item #13 ("No
save-success toast on Studio / Activate / Unpublish / Revoke. MVP
fine; add a small `useToast` hook later."). Resolve here, then
mark hygiene-tail #13 as fixed.

While we're touching it, give Activate / Unpublish / Revoke the same
treatment for consistency. Trivial scope.

Files:
- new `frontend/src/components/ui/Toast.tsx` (or extend an existing
  Radix Toast if one exists — check first)
- `frontend/src/pages/Studio.tsx` (Save correction success path)
- `frontend/src/pages/ApiConsole.tsx` (Activate / Unpublish / Revoke)

---

### #5 — Revoke API key has no confirmation

**Direction: Radix AlertDialog confirmation. Copy: "Revoke key
'{name}'? Integrators using this key will start getting 403 immediately."**

One-click destructive action with no recall path is jarring. AlertDialog
adds ~20 lines and matches the rest of the Danger zone semantics.

Files:
- `frontend/src/pages/ApiConsole.tsx` (the Revoke button row)
- check if `frontend/src/components/ui/AlertDialog.tsx` already exists
  (likely yes, used by Unpublish elsewhere)

---

### #6 — First-publish Contract Diff misreports as "breaking"

**Direction: when `prior_published_version_id` is null, replace the
"Activating this version will break existing integrators" warning with
"Initial contract — no prior version to break." and tone the diff
list as informational rather than alarming.**

The diff entries themselves (required_field_added × 3, optional × 1)
are technically correct vs the empty prior, but for an initial publish
they're noise dressed as alarms. The fix is purely client-side:
detect null prior, swap copy and color tone.

Files:
- `frontend/src/pages/ApiConsole.tsx` (Contract diff section)
- `frontend/src/i18n/locales/en.json` (add `contract_diff.initial_*` keys)

Test: `frontend/src/__tests__/api_console.test.tsx`.

---

### #7 — "fields reviewed" vs "field evidence coverage" disagree

**Direction: rename one of them so semantics don't collide.**

Today the EVIDENCE row reads `2 docs · 16 entities · 72 fields
reviewed` *and* `0% with field evidence`. Both are true under their
own definition but they look contradictory in the UI:

- `reviewed_fields` = total fields rendered on docs that received any
  Annotation (overcounts: opening Studio + saving one correction
  promotes every field on the doc).
- `field_evidence_coverage_ratio` = fraction of fields where a
  Prediction's `per_field_evidence` is populated (quote-level).

Suggestion:
- Rename `reviewed_fields` → `annotated_fields` in
  `backend/app/schemas/readiness.py` + `frontend/src/types/readiness.ts`
- Update copy: "**N annotated · M% with field evidence**" or split
  into two rows.

Backend rename touches a public schema field — search for callers
before renaming. May want to add the new name and deprecate the old.

Files:
- `backend/app/schemas/readiness.py`
- `backend/app/services/readiness.py`
- `frontend/src/types/readiness.ts`
- `frontend/src/components/ReadinessPanel.tsx`
- `frontend/src/i18n/locales/en.json` (keys `readiness.evidence_value`,
  `readiness.evidence_coverage`)
- tests: `frontend/src/__tests__/readiness_panel.test.tsx`,
  `backend/tests/test_readiness.py`

---

### #8 — Studio missing real PDF preview

**Direction: NOT in this PR. v1.1 roadmap item per the placeholder
copy. Track here so it doesn't get lost.**

This is the single biggest gap in the software-3.0 loop —
"Real PDF preview lands in v1.1; for now use the entity editor on
the right." Without source-of-truth visible the correction button
becomes "type what you think is right" instead of "fix what the model
got wrong." Acknowledged out-of-scope for this batch; create a
dedicated R8.x or R9 plan.

---

## Suggested commit / PR shape

Three commits in this order, each independently testable:

1. **#1 + #2** (backend response + workspace isolation, includes
   alembic migration if you go the `source` column route). Bigger
   blast radius; do this first while context is fresh.
2. **#3 + #6 + #7** (frontend semantics — Studio affordance, Contract
   Diff initial-publish copy, Readiness rename).
3. **#4 + #5** (Toast + AlertDialog). Smallest, ship-anytime.

Then re-dogfood `docs/local-demo.md` and re-run
`./scripts/release-checklist.sh` (and `EMERGE_E2E=1 ...`) before
opening the PR.

---

## Out of scope here

- Anything not numbered #1–#7 above. Item #8 is explicitly deferred.
- Re-litigating decisions made by the user in the dogfood session.
- The Bayesian-prior visualization redesign (the current "Awaiting
  first verdict" copy from `1ba770e` is the agreed answer).
