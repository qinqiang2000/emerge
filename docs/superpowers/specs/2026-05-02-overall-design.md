# emerge — Software 3.0 Document Extraction Platform · Overall Design

> **Date**: 2026-05-02
> **Status**: Draft v1, pending user review
> **Slogan**: Documents in. APIs emerge. They get better as you correct them.
> **Source**: Brainstorming session 2026-05-01 / 02 (full Q&A trail in conversation)
> **Predecessor relationship**: doc-intel becomes legacy. emerge is a clean-slate project — no data migration, no schema reuse, no enforced compatibility.

---

## 0. Why this exists

doc-intel was built as "annotation platform that also publishes APIs". In real use, the annotation-first framing turned out to be the wrong shape: users wanted **a structured extraction API**, and the heavy annotation / prompt-engineering / evaluation machinery was overhead, not value.

emerge restarts the design from a Karpathy software-3.0 lens:

> **The API is not configured. It emerges from the user's first few corrections, and gets better with every subsequent one.**

The user's labour is concentrated where it cannot be eliminated — judging correctness on a small sampled subset — and is fed back as evidence that the platform uses to evolve schema, prompt, and few-shot autonomously.

---

## 1. Conceptual model

A `Project` in emerge owns four artefacts plus a model configuration:

| Artefact | Content | Mutated by |
|---|---|---|
| **Schema** | Structured field bundle: `[{ name, type, required, description (NL), examples?, enum? }, …]`. `description` carries domain knowledge ("ISO 4217 code…", "look for 'Bill To' / 'Purchaser'…"). Supports nested `array<object>`. | User (schema editor) + AutoResearch |
| **Evidence Pool** | Three role-tagged views over `Annotation` rows: Anchors (≤5), Growth (≤5), Counterexamples (unbounded, never injected into prompt) | User corrections (manual) + feedback API (auto) |
| **Prompt elements** | `system_frame` (fixed), `global_notes` (free-text, cross-field) | User + AutoResearch |
| **Model config** | `model_id` + inference params (temperature, etc.) | User / Workspace admin |

The **runtime prompt is composed**, never hand-written:

```
[ system_frame ]
[ per-field instructions: schema.fields[].description joined as a numbered list ]
[ global_notes (if any) ]
[ few-shot examples: anchors then growth, in pool order ]
+ responseSchema attached as API parameter (hard-constraint top-level array<object>, snake_case English keys)
```

`system_frame` is fixed boilerplate (~150 tokens, version-controlled in code, not user-editable). It declares the agent's role, the output contract (top-level array, snake_case English keys, no nulls, multi-entity-aware), and instructs the model to follow the per-field instructions and few-shot examples that follow.

The user's primary creative act is **writing each field's `description`** — not writing prompts.

### 1.1 Workspace-level asset: Schema Template

A `Template` is a Workspace-scoped, named, versioned snapshot of `(schema, global_notes, recommended_model)`. **Excludes** anchors / growth / counterexamples / calibration data.

- `Template → Project`: **fork semantics** (one-time copy, no auto-sync). Used at Project creation.
- `Project → Template`: **explicit "Save as Template"** action. Promotes the Project's current schema as a new Template (or a new version of an existing one).
- 5 system-builtin Templates ship out of the box: `china_vat`, `us_invoice`, `japan_receipt`, `de_rechnung`, `custom_blank`. Read-only, visible in every Workspace.

### 1.2 Output contract — fixed forever

| Aspect | Value |
|---|---|
| Top-level type | `array` of `object` (multi-entity native — a PDF can contain N receipts) |
| Key language | `snake_case` English, always |
| Key style | Direct names (`shop_name`, `total_amount`, `line_items`) — no abbreviations, no camelCase |
| Nesting | Flat preferred; nest only for natural arrays (line items, addresses) |
| Empty fields | Not returned when model is uncertain (avoids hallucinated nulls) |
| Schema enforcement | Sent to model as `responseSchema` API parameter (hard constraint) once locked |

This contract is encoded in `system_frame` and the schema enforcement layer. **No dropdown lets the user override.** Style preferences live inside anchors and `description` text, never in UI knobs.

---

## 2. User workflow

### 2.1 Project creation — three entry points

1. **From scratch** → zero schema, full O3 progressive evolution
2. **From Template** → schema copied; jump straight to upload
3. **From NL description** → user types `"I want: shop name, total amount, date, line items (name + qty + price)"` → system parses to schema + `description` placeholders → jump to upload

### 2.2 The main loop — batch-first progressive evolution

Users upload **batches** (5–50 docs), not one at a time. The flow:

```
1. User drags 20 PDFs → 20 Document rows, status=uploaded
2. System runs zero-shot extraction on all 20 (open-ended prompt + array responseSchema)
   → Each Document gets a Prediction with draft JSON
   → Document list shows status badges per row
3. User opens doc#1 → workspace correction view
   → Saves corrected JSON as Annotation, role=anchor[0]
   → System derives schema candidate v0 from anchor[0] (auto-extracts field names + types from JSON)
4. User opens doc#2
   → Backend has already re-run prediction using anchor[0] as few-shot
   → User corrects → anchor[1] → schema candidate v1
5. User opens doc#3
   → schema field-set has stabilised → system prompts: "Lock schema?"
   → User confirms → from now on, all predictions use locked schema as responseSchema constraint
6. User clicks "Re-extract remaining" → batch job reruns the other 17 docs with locked schema + anchors
7. Document list now ranks docs by `confidence`; flagged docs are highlighted "needs review"
8. User samples 👎/uncertain items + spot-checks 👍 items → marks as growth (or fixes)
9. Confidence Loop math runs continuously in background → score visible at top of project page
10. Score crosses threshold → "Publish API" button unlocks
```

The Project page is shaped like label-studio's Data Manager: a filterable, sortable Document list with batch actions. Per-doc workspace is one click away.

**Named saved views** are out of scope for v1. Filtering is ephemeral.

### 2.3 Schema lock prompt heuristic

System prompts the user to lock schema when:
- ≥ 2 anchors exist, AND
- Their key sets differ by ≤ 1 field (90%+ agreement), AND
- All field types match across the anchors

Locking is reversible from the schema editor — but discouraged after API has been published from this Project.

---

## 3. Data model

emerge takes the `Document` / `Prediction` / `Annotation` separation from label-studio's task model — it is a clean conceptual fit and proven in practice.

### 3.1 Entities

```text
User
  id, email, password_hash, created_at

Workspace                              # tenant boundary
  id, name, owner_id, created_at

WorkspaceMembership
  id, workspace_id, user_id, role  (owner | admin | member)

Template                                # workspace asset
  id, workspace_id, name, description, version
  schema_json (full SchemaField list, denormalised — Templates are immutable per version)
  global_notes, recommended_model_id
  created_at, created_by, builtin: bool

Project
  id, workspace_id, name, created_at, created_by
  template_id            # nullable; tracks origin if forked from Template
  active_version_id      # FK → ProjectVersion; the version the API serves
  api_code               # nullable until published; uniqueness scoped per workspace
  api_published_at

ProjectVersion                          # snapshot of (schema + prompt elements + evidence pool ids + model)
  id, project_id, parent_version_id, version_number
  schema_snapshot   (JSON: full SchemaField list at this version)
  global_notes_snapshot
  model_id_snapshot
  evidence_pool_snapshot  (JSON: { anchor_ids: [...], growth_ids: [...], counterexample_ids: [...] })
                          # references by Annotation id; not deep-copies. v1 does not replay old versions for prediction;
                          # snapshot is informational (timeline, audit). Annotation deletion is soft only (status=cancelled), so
                          # references remain resolvable for reading.
  source: user_edit | auto_research | initial
  source_metadata    (JSON: e.g., AutoResearchRun id, action toolkit invocation log)
  created_at, created_by

# Schema lives inside ProjectVersion.schema_snapshot (denormalised JSON).
# Reasons: schema is small, always read/written together, snapshot semantics align with versioning.

Document
  id, project_id, filename, file_path, mime_type, page_count, byte_size
  uploaded_at, uploaded_by
  data       (JSONB, flexible: source_url, batch_id, OCR text cache, etc.)
  status     (uploaded | extracting | extracted | errored | archived)

Prediction
  id, document_id, project_version_id    # which schema/prompt was used
  model_id, prompt_hash
  output                  (JSONB: array<object>)
  per_field_confidence    (JSONB: { entity_idx → field_name → judge_verdict })
  tokens_used, latency_ms, cost_estimate, created_at
  status (success | partial | failed)
  error_message  (nullable)

Annotation
  id, document_id, parent_prediction_id  (which Prediction the user edited from)
  output                  (JSONB: corrected array<object>)
  role                    (anchor | growth | counterexample | none) — enforced via DB CHECK constraint
  pinned                  (bool, anchor-only — exempt from FIFO eviction; ignored when role != 'anchor')
  status                  (draft | saved | cancelled) — soft-delete via status='cancelled' instead of row removal
  notes                   (text, optional user comment)
  created_by, created_at, last_modified_by, last_modified_at

# Evidence Pool is a query view, not a separate table:
#   anchors   = Annotation WHERE project_id=X AND role='anchor'  ORDER BY created_at  LIMIT 5 (pinned excluded from cap)
#   growth    = Annotation WHERE project_id=X AND role='growth'  ORDER BY created_at DESC  LIMIT 5
#   counter   = Annotation WHERE project_id=X AND role='counterexample'

JudgeCalibration
  id, project_id, judge_model_version            # UNIQUE(project_id, judge_model_version)
  tp, fp, fn, tn          # confusion matrix, integer counts (judge_verdict × human_verdict)
  alpha, beta             # Beta posterior derived from prior + (tp, fp): alpha = 8 + tp, beta = 2 + fp
  observation_count, last_updated_at

AutoResearchRun
  id, project_id, started_at, completed_at, status (running | completed | failed | early_stopped)
  starting_version_id, output_version_id (nullable on failure)
  judge_model_id, researcher_model_id
  turn_count, max_turn
  turn_history     (JSONB: per-turn { diagnosis, actions, confidence_before, confidence_after, judge_per_field })
  termination_reason (threshold_met | max_turn | no_improvement | manual_stop | error)

ApiKey
  id, project_id, name, prefix, key_hash, created_at, created_by
  last_used_at, deleted_at  (soft delete)
```

### 3.2 Key invariants

- A Project always has at least one ProjectVersion (initial empty version on creation).
- `Project.active_version_id` always points to an existing ProjectVersion of the same Project. ProjectVersion is append-only — there is no archive / delete state in v1.
- `Annotation.role = 'anchor'` count ≤ 5 + pinned count per Project. Insert beyond cap evicts oldest unpinned.
- `Counterexample` Annotations never appear in `evidence_pool_snapshot.anchor_ids` or `growth_ids`.
- `Template.schema_json` is immutable once a Template version is created. Editing creates a new Template version.

### 3.3 What we deliberately don't store (v1)

- **bbox coordinates** (model-returned or user-drawn) — completely deferred to v2
- **Field-level snippet library** — never within v1's design horizon
- **Annotation parent chain** beyond `parent_prediction_id` — no full git-style history graph

---

## 4. Confidence Loop & Calibration

### 4.1 Two signals, one score

| Signal | Computation | Measures |
|---|---|---|
| **LLM-as-judge** | A judge model (Workspace-configurable, default Opus) inspects (document image, predicted JSON). Returns per-entity per-field verdict ∈ {👍, 👎, uncertain} plus a free-text reason for non-👍 cases. | Value correctness |
| **Few-shot LOO fit** | Leave-one-out: pick anchor `i`, predict its document using anchors `{0..N}\{i}` as few-shot, compare structurally to the user's saved JSON. Mismatch ratio per field. | Internal coherence of anchors |

**Composite score** (range `[0.0, 1.0]`, where 1.0 = all fields verified or human-confirmed correct):

```
score = 0.8 * judge_component + 0.2 * loo_component        # default weights, configurable per project

judge_component = (Σ verdict_weight) / total_fields
  where verdict_weight per (judge_verdict, human_verdict) pair:
    judge 👍, human (not seen)        → judge_precision_calibrated
    judge 👍, human 👍                → 1.0
    judge 👍, human 👎                → 0.0  (and updates calibration: fp += 1)
    judge 👎/uncertain, human fixed   → 1.0
    judge 👎/uncertain, human skipped → 0.0
    judge 👎/uncertain, human 👎      → 0.0  (calibration: tn += 1)

loo_component = 1 - mismatch_ratio_across_anchors
```

Score is computed at two granularities:

- **Per-Document score** — same formula restricted to the fields of one Document's latest Prediction. Used to rank / filter on the Document list page.
- **Per-Project score** — average of per-Document scores across the Project's vibe-check set (unannotated docs in the batch + sampled production calls).

Recomputed eagerly on:
- new Annotation saved
- new Prediction generated
- new judge run completed
- new feedback API call

Compute is intentionally not throttled. Lab judge cost is an explicit non-concern; only `max_turn` and human attention bound the work.

### 4.2 Human-in-the-loop sampling

The UI surfaces three groups for human review on the Document list page:

- **Required review**: any Document with one or more 👎/uncertain field verdicts (cap 3 fields shown per doc to avoid fatigue)
- **Spot-check**: 2 randomly sampled Documents from the 👍-only set, asking "judge says these are fine, do you agree?"
- **Optional full review**: a toggle "show all"

User actions per item: thumbs-up confirm / thumbs-down + correct / skip. Corrections become Annotations with `role=growth`. Confirmations update calibration counts.

### 4.3 Bayesian calibration of judge precision

Per `(project, judge_model_version)`:

- Prior: `Beta(α=8, β=2)` ≈ 80% precision (reflects judge as "trustworthy but not perfect")
- Update on each (judge_verdict, human_verdict) observation:
  - judge 👍 + human 👍 → `tp += 1`, derived `α = 8 + tp`
  - judge 👍 + human 👎 → `fp += 1`, derived `β = 2 + fp`
  - judge 👎/uncertain + human 👎 → `tn += 1` (recall side; does not affect α/β)
  - judge 👎/uncertain + human 👍 → `fn += 1` (recall side; does not affect α/β)
- Point estimate: `α / (α + β)`
- 95% CI: from Beta inverse CDF
- Only the precision side (tp, fp → α, β) is used in the score formula. The recall side (fn, tn) drives spot-check sampling intensity but is never composed into the displayed confidence number.

Displayed as: `"Judge precision in this project: 82% ± 6% (28 observations)"` — never as a single number without uncertainty.

The recall side (judge 👎 / 👎̄) feeds a parallel matrix used to decide whether to spot-check more aggressively, but does not enter the score.

### 4.4 Cost stance (Lab side)

Judge calls, researcher calls, and re-prediction calls in the Lab are explicitly **not budgeted**. Termination of any process is bounded by:
- `max_turn` (anti-infinite-loop)
- `early_stop_no_improvement` (efficiency)
- user cancel

No `$` estimates shown to user. No token caps. Production-side API has its own cost path (each call costs the user / their downstream consumer one model call); that is unrelated to Lab evolution work.

---

## 5. AutoResearch — single-architecture Reflexion loop

### 5.1 Loop shape

```
state = (current_project_version, vibe_check_set, counterexample_set)
turn = 0

while turn < max_turn (default 10):
    judge_results = run_judge(state)
    diagnosis = researcher_llm.diagnose(state, judge_results, turn_history)
    actions = researcher_llm.choose_actions(diagnosis, action_toolkit)
    new_state = apply_actions(state, actions)
    new_score = run_confidence_loop(new_state)

    turn_history.append({turn, diagnosis, actions, score_before, score_after, judge_results})

    if new_score > threshold:
        return success(new_state)
    if no_improvement_for(3, turn_history):
        return early_stop(best_state_seen)
    if any(action.failed for action in actions):
        log_error_continue
    state = new_state if new_score > score else state
    turn += 1

return max_turn_reached(best_state_seen)
```

The output is always a new `ProjectVersion` candidate. Never auto-promoted to `active_version_id`. User must explicitly accept via the version timeline UI.

### 5.2 Action toolkit (whitelist)

Researcher cannot write arbitrary code or call external tools. It picks from:

- `edit_field_description(field_name, new_text)` — refine one field's NL description
- `add_field_examples(field_name, examples[])` — add positive examples to a field
- `add_field(name, type, description, required)` — extend schema
- `remove_field(name)` — narrow schema
- `make_optional(name)` — relax constraint
- `make_required(name)` — tighten constraint
- `edit_global_notes(text)` — global instruction edit
- `reorder_few_shot(criterion: 'similarity'|'recency'|'diversity')` — reorder anchor pool
- `swap_anchor(old_annotation_id, new_annotation_id)` — replace one anchor with another from the project's annotation history (researcher selects by id, not by FIFO slot)
- `add_field_enum(name, values[])` — add `enum` constraint to a field

Each action is a structured function call (not free text). The researcher LLM emits these via JSON tool-use API. New actions can be added to the whitelist over time without architectural change.

### 5.3 Triggers

| Trigger | Default | Mechanism |
|---|---|---|
| Manual | always available | Button on Project page: "Run AutoResearch" |
| Semi-automatic | OFF | Workspace setting: "Auto-run after every N counterexamples". Range 1–20. |
| Scheduled | not in v1 | Future: nightly runs, etc. |

When a run is in flight, UI shows a banner and a "Stop" button. Concurrent runs on the same project are blocked.

### 5.4 Researcher LLM configuration

Workspace-level setting: `researcher_model_id`. Default: `claude-opus-4-7`. Admins can pick any model with sufficient JSON tool-use capability. Cost is non-concern (see §4.4).

### 5.5 Reading turn history

Each run produces a transparent log: the diagnosis text per turn, the actions taken, the score delta, and which judge calls fired. UI presents this as a collapsible diff view per turn. Users can read why their schema evolved — the platform never improves silently.

---

## 6. Schema Templates (Workspace asset)

### 6.1 Lifecycle

```
Project (forked from Template T_v3)
  → user iterates → schema diverges from T_v3
  → user clicks "Save as Template"
      → if same name as existing T → creates T_v4 (new version)
      → if different name → creates new T'

Template (T) is read at fork time only. After fork, Project owns its own schema fully. No back-propagation.
```

### 6.2 Builtin Templates (system-provided, read-only)

5 templates ship out of the box, one version each:

- `china_vat` — Chinese VAT invoices
- `us_invoice` — generic US invoices
- `japan_receipt` — Japanese receipts (領収書)
- `de_rechnung` — German invoices (Rechnung)
- `custom_blank` — empty schema, no global notes

Each carries: a populated schema with field descriptions tuned over real usage at doc-intel, a `global_notes` paragraph, and a `recommended_model_id`.

Builtins live as rows in the `Template` table with `builtin=true`. They are visible to every Workspace and never deletable / editable. New Workspaces see them immediately on Project creation.

### 6.3 Save as Template UX

Button on Project page (admin/owner role only). Opens dialog:
- name (preset to Project name; user can change)
- description (optional)
- "create new Template" vs "create new version of `<existing>`" toggle

Confirms → creates Template / Template version. Does not modify the source Project.

---

## 7. API Publish (v1 simplified)

### 7.1 v1 scope: project-bound test API

There is **no separate Lab/Prod artefact concept** in v1. The published API is a thin façade over the Project's current `active_version_id`.

```
POST /api/v1/projects/{pid}/publish
  body: { api_code: "japan-receipts" }
  → sets project.api_code; returns project state

POST /api/v1/projects/{pid}/api-keys
  body: { name: "default" }
  → returns key in plaintext exactly once: "ek_<8-char-prefix>-<32-char-secret>"

POST /extract/{api_code}                                    (public, no JWT; key-only)
  header: X-Api-Key: ek_…
  body: multipart file
  → 200 OK { entities: [...], project_version: <int>, prediction_id: <id> }
  → 401 missing/bad key
  → 403 project unpublished
  → 404 api_code unknown
  → 413 file too large
  → 429 rate limited (default 60/min/key, configurable by workspace admin)

POST /extract/{api_code}/feedback                           (public, called by integrators after detecting bad output)
  header: X-Api-Key: ek_…
  body: { request_id: <prediction_id>, correct_output: [...] }
  → creates Annotation with role=counterexample, parent_prediction_id=<id>
  → 200 OK
  → 401 / 403 / 404 same as above
  → 422 prediction_id does not belong to this api_code

# API key validation pattern: ek_<8-char-prefix>-<32-char-secret>.
# Server splits on the first '-' after the prefix marker, looks up by prefix (indexed),
# bcrypt-compares the secret half against key_hash. Constant-time comparison.
```

### 7.2 What changing the Project does to a published API

Because there is no artefact pinning:
- User edits schema → API now uses new schema **immediately** on next call
- AutoResearch produces v_new, user marks it active → API uses v_new immediately
- User unpublishes → all calls now return 403

This is intentional for v1: it makes the platform single-loop, easy to reason about, and matches how doc-intel currently works for users who are evaluating and publishing in the same project.

### 7.3 v2 extension point (not in scope here, listed for orientation)

v2 will add:
- `ProductionDeployment` table with immutable artefact bundles
- "Promote vN to deployment X" explicit user action
- Multiple deployments per Project pinned to different versions
- Blue-green / rollback semantics
- API keys move from `Project` to `ProductionDeployment`

The v1 schema (`ProjectVersion` already exists) can extend to v2 without breaking changes.

---

## 8. UI layout & interaction

Two top-level surfaces.

### 8.1 Project page (Document list view)

Shape: a filterable, sortable table. One row per Document.

Columns (default visible):
- Filename
- Status (uploaded / extracting / extracted / errored)
- Entity count (length of latest Prediction's array output)
- Confidence (latest, per-doc score from the Confidence Loop)
- Role tags (anchor / growth / counterexample / none)
- Last modified

Filters (ephemeral, not saved as named views in v1):
- Status, role, confidence range, entity-count range

Top toolbar:
- "Upload" (drag-and-drop multi-file)
- "Re-extract selected" / "Re-extract all"
- "Run AutoResearch"
- "Schema editor" (opens panel)
- Project-level confidence score (large display)
- "Publish API" / "Manage API Keys"

Click a row → enters the Workspace correction view for that Document.

### 8.2 Workspace correction view (V2-pragmatic, 2-column)

```
+--------------------------------------+----------------------+
|                                      | Entity 1     [⌃⌄][×]|
|                                      |  shop_name: ABC ✎   |
|       Document Preview               |  total: 1234   ✎    |
|       (full size, scrollable,        |  date: 2026-...     |
|        zoom in/out controls)         |  line_items:        |
|                                      |    [01] Coffee 500  |
|                                      |    [02] Tea  300    |
|                                      |    [+ add item]     |
|                                      |                      |
|                                      | Entity 2     [⌃⌄][+]|
|                                      |  ...                 |
|                                      |                      |
|                                      | [+ add entity]       |
|                                      +----------------------+
|                                      | [📋 Schema editor]  |
|                                      | [💬 Ask researcher] |
|                                      | [Save as Anchor]    |
+--------------------------------------+----------------------+
```

Left: 60–70% width Document Preview. Renders PDFs (page-by-page scroll) and images. Pure viewer in v1: no overlays, no clickable hotspots, no bbox.

Right: entity-grouped field list. Each entity is a card; expandable / collapsible. Each field row supports:
- inline value edit
- field deletion
- per-field "report wrong" (sets a flag on the field that informs Confidence weighting)

Bottom buttons:
- **Schema editor** — slides out a panel. Each field has an editable description (multi-line text), type dropdown, required toggle, optional examples and enum. Schema lock state visible. "Lock / Unlock" button.
- **Ask researcher** — chat input. Free-text "this batch is missing tax field", "currency should always be ISO code". Submitting triggers an AutoResearch run with the user's text injected into the diagnosis prompt.
- **Save as anchor** — persists current Annotation with role=anchor, decrementing the FIFO slot.

### 8.3 What's intentionally absent in the workspace view

- No raw-JSON-tree view (the user never edits raw JSON)
- No bbox overlay (multimodal LLMs are unreliable for this; deferred to v2)
- No three-column "annotate fields" layout (replaced by entity-grouped cards)
- No "next undone document" task queue (Document list filters cover this)

---

## 9. v1 scope summary

### In scope

- Workspace + multi-tenant isolation (mirroring label-studio / doc-intel-legacy patterns)
- Project + Schema Template + 5 builtin Templates
- Document upload (multi-file batch)
- Zero-shot extraction with array `responseSchema`
- Schema auto-derivation from anchors + lock workflow
- Schema editor with per-field NL descriptions, types, examples, enums
- Evidence Pool (anchor / growth / counterexample as Annotation roles)
- Confidence Loop (judge + LOO + human review + Bayesian calibration)
- AutoResearch (single Reflexion loop + action toolkit, manual + optional semi-automatic trigger)
- ProjectVersion timeline, manual setting of active_version
- API publish bound to Project's active version
- Feedback endpoint receiving counterexamples from API consumers
- Document list view (Data Manager-style)
- 2-column workspace correction view

### Out of scope (v1)

- Lab / Prod artefact split (deferred to v2 — but `ProjectVersion` already gives the foundation)
- Manual `Promote to Prod` action (v2)
- Bbox of any kind: model-returned, user-drawn, hover-highlight (v2+)
- Self-consistency confidence signal (judge + LOO is sufficient for v1)
- Counterexamples injected into prompt (decided permanent: never)
- Field-level snippet library across schemas (never planned in this design)
- Saved named views on the Document list (filtering is ephemeral; v2 if demanded)
- Webhooks / completion notifications
- Multi-user real-time collaboration / annotation locking
- Comparison view (model A vs model B side-by-side)
- Project clone (orthogonal to Template; v2 if demanded)
- Project-level statistics dashboard tab
- Migrating any data from doc-intel-legacy

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Multimodal LLM cannot reliably detect multiple entities in one document | Judge prompt explicitly asks "how many entities?"; UI supports manual "add entity" + "delete entity"; counterexamples on entity-count errors fed to AutoResearch |
| Zero-shot draft is so wrong it kills onboarding | Strong default `system_frame` for open-ended extraction; Template entry path provides high-quality starting schema; anchor[0] correction is the worst case but bounded |
| Schema lock is regretted later | Always reversible from Schema editor; lock change creates a new ProjectVersion; user warned if unlock occurs after API publish |
| AutoResearch goes rogue | Action toolkit is a whitelist; turn history transparent and human-readable; output is a candidate ProjectVersion never auto-promoted; max_turn + 3-turn no-improvement early stop |
| Judge calibration cold-start | Beta(8,2) prior gives a sane 80% starting point; UI displays `± CI` so users see the uncertainty; spot-check sampling forces calibration data accumulation |
| Multimodal model returns inconsistent JSON shape pre-lock | `responseSchema` enforced at API level even before user lock (uses derived candidate schema); model output is structurally constrained from call #1 |
| Workspace admin picks bad researcher model | Default = Opus; admins must opt-in to change; if change degrades performance, it shows immediately in turn-history score deltas |
| Single user iterating produces small calibration sample (< 30 obs) | UI shows wide CI explicitly; recommendation to keep batch ≥ 10 docs; `judge_precision_calibrated` defaults to prior mean when CI is too wide |
| User uploads 50+ docs and zero-shot batch overruns | Batch extraction runs as background SSE task with per-document progress events; UI does not block; failures mark per-document `errored` status without aborting batch |

---

## 11. Implementation slicing — handoff to writing-plans

This document is intentionally a **single overall design** rather than feature-cut sub-specs. The next step (writing-plans) decomposes it into implementable slices. Suggested slicing for the planning agent:

| Slice | Scope | Depends on |
|---|---|---|
| **R1 — Foundation** | User / Workspace / Auth / DB scaffolding (FastAPI + async SQLAlchemy + alembic init) | — |
| **R2 — Project & Document model** | Project, Document, Prediction, Annotation tables; multi-file upload; basic list endpoints | R1 |
| **R3 — Schema & extraction core** | ProjectVersion + schema_snapshot; zero-shot prompt composition; responseSchema integration with Gemini + OpenAI; schema auto-derivation from anchors; lock workflow | R2 |
| **R4 — Evidence Pool & corrections** | Annotation roles + FIFO logic; feedback API; counterexample handling | R3 |
| **R5 — Confidence Loop & Calibration** | Judge integration; LOO computation; JudgeCalibration table + Beta updates; UI surfacing of human review queue | R4 |
| **R6 — AutoResearch** | AutoResearchRun table; Reflexion loop; action toolkit dispatch; turn history rendering; manual + semi-automatic triggers | R5 |
| **R7 — Templates & API publish** | Template table + builtin seeders; Save-as-Template; API publish + key + feedback routing; rate limiting | R3 (parallel to R4) |
| **R8 — UI** | Document list page; Workspace correction view (2-column); Schema editor panel; AutoResearch run viewer; Project page header / publish flow | R2 onwards, in parallel with backend slices |

R1, R2, R3 are sequential foundations. R4–R7 can be parallelised across two engineers. R8 lands per backend slice as it stabilises.

A reasonable v1 milestone structure for writing-plans to consider:
- **M1 Walking skeleton** — R1 + R2 + R3 minimal: user can upload, extract zero-shot, edit JSON in workspace, save anchor. No judge, no AutoResearch, no Templates yet.
- **M2 Confidence** — R4 + R5: pool roles, judge, LOO, calibration, human review queue. Project-level confidence score visible.
- **M3 Evolution** — R6: AutoResearch run loop, action toolkit, turn history.
- **M4 Reuse + ship** — R7 + R8 polish: Templates, API publish, public extraction endpoint, feedback loop end-to-end.

writing-plans is the proper next phase to translate this into per-slice plans with task lists and TDD ordering.

---

## 12. Open questions deferred to writing-plans

These are intentionally not pinned in this design. They will surface naturally during plan-writing and should be resolved there:

1. **Backend stack choice** — FastAPI + async SQLAlchemy + SQLite (matching doc-intel-legacy's stack) is the obvious default; whether to start with PostgreSQL instead for production readiness is a R1 decision.
2. **Frontend stack choice** — Vite + React + TypeScript + Zustand (matching doc-intel-legacy) is again the default; alternatives are a R8 decision and probably not worth deviating.
3. **Judge / researcher LLM provider integration concrete details** — which SDK calls, which retry semantics, which timeout — handled inside R5 / R6 plans.
4. **PDF rendering library** — react-pdf in doc-intel-legacy works fine; carry forward unless plan reveals reason to change.
5. **Concurrency model for batch extraction** — task queue (Celery? Arq? in-process asyncio.gather?) decided in R3 plan based on expected batch sizes.
6. **Auth implementation detail** — JWT (matching legacy) vs sessions; default JWT.
7. **API rate limiting library** — slowapi vs custom; minor choice in R7.

---

## 13. Naming and identity

- **Project name**: `emerge`
- **Slogan**: Documents in. APIs emerge. They get better as you correct them.
- **CLI / package / repo names**: all `emerge`
- **API key prefix**: `ek_` (emerge key)
- **Public extract route**: `POST /extract/{api_code}` (no version prefix; mirrors stable consumer-facing path)
- **Internal API route**: `/api/v1/...`

Choice rationale: "emerge" carries both software-3.0 emergence semantics (the API is not built — it appears from interactions) and evolutionary semantics (gradual revelation, organic growth from corrections). 6 letters, 2 syllables, internationally pronounceable, no major naming collisions in the AI / dev-tools space.

---

## End of design

Ready for review. The natural next phase is `writing-plans` to slice this into R1–R8 plans with concrete task lists.
