# emerge — Software 3.0 Document Extraction Platform · Overall Design

> **Date**: 2026-05-02 (rev 2026-05-03 — drop few-shot from runtime prompt entirely)
> **Status**: Draft v1, pending user review
> **Slogan**: Documents in. APIs emerge. They get better as you correct them.
> **Source**: Brainstorming session 2026-05-01 / 02 / 03 (full Q&A trail in conversation)
> **Predecessor relationship**: doc-intel becomes legacy. emerge is a clean-slate project — no data migration, no schema reuse, no enforced compatibility.

> **重大设计决策（2026-05-03）**：runtime prompt **不带 few-shot 示例**。所有"教模型"的知识都进入 schema 的字段 `description` / `examples` / `enum` 文本，以及 `global_notes`。理由：(a) 现代多模态 LLM 跟随结构化文字指引的能力远胜两年前；(b) image-based few-shot 带来 5-10s 额外延迟、2-5x token 成本、image-count 软上限风险；(c) 文字描述完全可读、可审计、可作为 Template 资产无损迁移——是真正的 software 3.0 形态：用自然语言写代码。Counterexamples 仍然保留，但**仅作为 AutoResearch 的回归测试集**，永远不进 prompt。

---

## 0. Why this exists

doc-intel was built as "annotation platform that also publishes APIs". In real use, the annotation-first framing turned out to be the wrong shape: users wanted **a structured extraction API**, and the heavy annotation / prompt-engineering / evaluation machinery was overhead, not value.

emerge restarts the design from a Karpathy software-3.0 lens:

> **The API is not configured. It emerges from the user's first few corrections, and gets better with every subsequent one.**

The user's labour is concentrated where it cannot be eliminated — judging correctness on a small sampled subset, and writing/refining each field's natural-language description — and is fed back as evidence that the platform uses to evolve schema descriptions and global notes autonomously.

---

## 1. Conceptual model

一个 `Project` 拥有四类产物 + 模型配置：

| Artefact | Content | Mutated by |
|---|---|---|
| **Schema** | 结构化字段定义：`[{ name, type, required, description (NL), examples?, enum? }, …]`。`description` 承载领域知识（"以 ISO 4217 货币代码输出"、"查找 'Bill To' / 'Purchaser' 标识"）。支持嵌套 `array<object>`。**这是 emerge 唯一向模型传递知识的地方**——没有 image few-shot。 | User (schema editor) + AutoResearch |
| **Counterexample Pool** | 用户事后报错的 (doc, wrong_output, correct_output) 三元组。**仅作为 AutoResearch 的回归测试集**，永远不进 runtime prompt。无上限。 | User corrections (manual) + feedback API (auto) |
| **Prompt elements** | `system_frame` (fixed), `global_notes` (free-text, cross-field) | User + AutoResearch |
| **Model config** | `model_id` + inference params (temperature, etc.) | User / Workspace admin |

**Runtime prompt 是动态拼出来的**，永远不手写：

```
[ system_frame ]
[ per-field instructions: schema.fields[].description joined as a numbered list,
                          每条若有 examples / enum 也内联进同一段 ]
[ global_notes (if any) ]
+ responseSchema attached as API parameter (hard-constraint top-level array<object>, snake_case English keys)
+ target document (image / PDF) as the user content block
```

注意：**没有 few-shot 段落**。要让模型学会某种规则，唯一的方式是把它写进对应字段的 `description`，或写进 `global_notes`。这强制所有"教模型"的知识都是**可读的文本**——不是埋在示例里的隐式知识。

`system_frame` 是固定 boilerplate（~150 tokens，代码里版本管理，用户不可改）。它声明 agent 的角色、输出契约（顶层 array、snake_case 英文 key、不返回空字段、多实体感知），并指示模型严格遵循后面的 per-field instructions 和 global_notes。

用户的核心创造性劳动是**写每个字段的 `description`**——这才是真正的"代码"。AutoResearch 的核心动作也是改这些 description。

### 1.1 Workspace-level asset: Schema Template

A `Template` is a Workspace-scoped, named, versioned snapshot of `(schema, global_notes, recommended_model)`. **Excludes** counterexamples、calibration data、document binaries——Template 只携带**纯文本知识**（schema descriptions / examples / enum / global_notes），跨 batch、跨 Project 无损迁移。Template 在 emerge 里成为"成熟 prompt 知识"的沉淀单元。

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

This contract is encoded in `system_frame` and the schema enforcement layer. **No dropdown lets the user override.** Style preferences live inside `description` text、`examples`、`enum`，never in UI knobs。

---

## 2. User workflow

### 2.1 Project creation — three entry points

1. **From scratch** → zero schema, full O3 progressive evolution
2. **From Template** → schema copied; jump straight to upload
3. **From NL description** → user types `"I want: shop name, total amount, date, line items (name + qty + price)"` → system parses to schema + `description` placeholders → jump to upload

### 2.2 The main loop — batch-first progressive evolution

用户**批量**上传（5–50 份），不是一份一份滴进。流程：

```
1. 用户拖 20 份 PDF → 20 个 Document 行, status=uploaded
2. 系统对全部 20 份跑 zero-shot extraction
   (开放式 prompt + array responseSchema, 不带任何示例)
   → 每份 Document 产出 1 条 Prediction，含草稿 JSON
   → Document 列表呈现，状态徽章逐行显示
3. 用户开 doc#1 → workspace 矫正界面
   → 编辑 JSON、改字段名、删多余项 → 保存
   → 产生 Annotation, role=none（仅作历史记录，不进 prompt）
   → 系统从这条 Annotation 自动派生 schema 候选 v0：
       - 字段名 / 类型来自 JSON 形状
       - description 字段先填占位文本（如"value derived from receipt; refine description as needed"）
4. 用户在 Schema editor 里把 description 写好
   （这是核心创造劳动——把领域知识写成自然语言）
   → schema 候选 v1
5. 用户开 doc#2 → 系统已经用 schema v1 重跑过它的 Prediction
   → 用户改 → 进一步触发 schema description 的微调
   → 再开 doc#3...
6. 当 schema 字段集稳定（≥ 2 份矫正，字段集 ≤ 1 字段差异，类型匹配）
   → 系统弹"Lock schema?"
   → 用户确认 → 后续 predict 都带 responseSchema 硬约束
7. 用户点 "Re-extract remaining" → 后台重跑其余 17 份
   → Document 列表按 confidence 排序，flagged docs 高亮"需复核"
8. 用户审 flagged items：
   - 👎 字段 → 修正 → 触发 description 改进建议
   - 👍 抽检 → 确认或更正
   - 修正本身只更新 Annotation；description 是否更新由用户决定 / 由 AutoResearch 自动建议
9. Confidence Loop 后台持续算分 → 项目级分数显示在页头
10. 分数过阈值 → "Publish API" 按钮解锁
```

Project page 的形态对标 label-studio Data Manager：可筛选、可排序、可批量操作的 Document 列表。点行进 workspace 矫正。

**Named saved views** 不在 v1 范围内。筛选是临时的。

### 2.3 Schema lock prompt heuristic

系统在以下条件全部满足时弹出 lock 提示：
- 该 Project 至少有 2 条 `role=none` 的 saved Annotation（即用户矫正过 ≥ 2 份），AND
- 这些 Annotation 的 key 集合差异 ≤ 1 个字段（agreement 90%+），AND
- 所有共有字段的推断类型一致

锁定可从 Schema editor 取消——但 API 已发布时取消会有警告。

### 2.4 Description 进化机制

用户矫正 doc 时产生的"修正信号"如何流入 description？

- **手动**：用户直接在 Schema editor 改 description 文字（最直接）
- **AutoResearch 自动建议**：用户点"Improve descriptions" → researcher 看 counterexamples 和 judge 反馈，提议 description 修改 → 用户审阅是否接受
- **绝不**：从矫正后的 JSON 自动反推 description（容易错，违反"description 是显式知识"原则）

这种设计强制 description 始终是**人或 AutoResearch 显式书写**的——保证可读、可审计、可作为 Template 资产复用。

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

ProjectVersion                          # snapshot of (schema + prompt elements + counterexample test set + model)
  id, project_id, parent_version_id, version_number
  schema_snapshot           (JSON: full SchemaField list at this version)
  global_notes_snapshot
  model_id_snapshot
  counterexample_ids        (JSON array of Annotation.id)
                            # references by Annotation id; not deep-copies. Used by AutoResearch as regression test set.
                            # Annotation deletion is soft only (status=cancelled), so references remain resolvable.
  source                    user_edit | auto_research | initial
  source_metadata           (JSON: e.g., AutoResearchRun id, action toolkit invocation log)
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
  role                    (counterexample | none) — enforced via DB CHECK constraint
                          # 'none'           = 用户矫正的标准记录，进入 schema 派生 + description 进化的输入信号
                          # 'counterexample' = 生产 API 调用方报错的样本，仅作 AutoResearch 回归测试集，永不进 prompt
  status                  (draft | saved | cancelled) — soft-delete via status='cancelled'
  notes                   (text, optional user comment)
  created_by, created_at, last_modified_by, last_modified_at

# Counterexample 池是一个查询视图，不是独立表：
#   counterexamples = Annotation WHERE project_id=X AND role='counterexample' AND status='saved'

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
- `Annotation` 没有数量上限——counterexamples 全留作回归集，矫正记录全留作历史。
- `Annotation.role` 仅允许 `counterexample` 或 `none`。anchor / growth 等旧概念已废除，DB CHECK 约束反映这一点。
- `Template.schema_json` is immutable once a Template version is created. Editing creates a new Template version.

### 3.3 What we deliberately don't store (v1)

- **bbox coordinates** (model-returned or user-drawn) — completely deferred to v2
- **Field-level snippet library** — never within v1's design horizon
- **Annotation parent chain** beyond `parent_prediction_id` — no full git-style history graph
- **Anchor / growth / few-shot pool** — 已经从设计中彻底移除（见 §1）。所有"教模型"知识都流入字段 description / examples / enum 文本。

---

## 4. Confidence Loop & Calibration

### 4.1 Two signals, one score

| Signal | Computation | Measures |
|---|---|---|
| **LLM-as-judge** | A judge model (Workspace-configurable, default Opus) inspects (document image, predicted JSON). Returns per-entity per-field verdict ∈ {👍, 👎, uncertain} plus a free-text reason for non-👍 cases. | 当前 prompt + schema 在 vibe-check 文档上的字段正确率 |
| **Counterexample Regression** | 对 Counterexample Pool 里的每条 (doc, correct_output)，用当前 schema 重跑 prediction，与 correct_output 做结构化字段比对。命中率 = 通过的 counterexample 数 / 总数。 | "我之前标错的 case，现在还错不错"——直接的回归健康度 |

**Composite score** (range `[0.0, 1.0]`, 1.0 = 全部字段被人审或 judge 校验过都通过、且全部 counterexample 已修复):

```
score = 0.7 * judge_component + 0.3 * counterexample_regression_score
        # 默认权重，per project 可配
        # 当 counterexample 池为空时，counterexample_regression_score 视为 1.0

judge_component = (Σ verdict_weight) / total_fields
  where verdict_weight per (judge_verdict, human_verdict) pair:
    judge 👍, human (not seen)        → judge_precision_calibrated
    judge 👍, human 👍                → 1.0
    judge 👍, human 👎                → 0.0  (and updates calibration: fp += 1)
    judge 👎/uncertain, human fixed   → 1.0
    judge 👎/uncertain, human skipped → 0.0
    judge 👎/uncertain, human 👎      → 0.0  (calibration: tn += 1)

counterexample_regression_score:
  let CE = { all Annotation rows with role='counterexample' AND status='saved' }
  if |CE| == 0:
    return 1.0
  hits = 0
  for ce in CE:
    pred = run_prediction(ce.document_id, current_schema, current_global_notes)
    if structurally_matches(pred.output, ce.output):
      hits += 1
  return hits / |CE|

# structurally_matches: array length 一致；每对 entity 的字段集一致；每个 field 值
# 走对应类型的等价比较（数字±0.01、字符串 normalize、enum 严格相等、嵌套 array 递归）
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

User actions per item: thumbs-up confirm / thumbs-down + correct / skip。修正动作产生 Annotation `role=none`（普通历史记录，不进 prompt，但参与 schema 派生 + description 改进信号）。Confirmations 更新 calibration 计数。

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

Researcher 不能写任意代码或调外部工具。所有 action 都是改 schema 或 global_notes 文本。从下面挑选：

- `edit_field_description(field_name, new_text)` — **主战场**：精炼某个字段的 NL description。绝大多数 turn 的核心动作。
- `add_field_examples(field_name, examples[])` — 给某字段加正例（文本，进 description 段）
- `add_field(name, type, description, required)` — 扩展 schema
- `remove_field(name)` — 收缩 schema
- `make_optional(name)` / `make_required(name)` — 调整约束
- `edit_global_notes(text)` — 改全局 notes
- `add_field_enum(name, values[])` — 给字段加 `enum` 约束（注入 responseSchema）

注意：toolkit 中**没有任何与 anchor / few-shot pool 相关的 action**。researcher 唯一能动的就是文字。这让每一次动作都可读、可复盘、可作为 Template 资产沉淀。

每个 action 是结构化函数调用（不是自由文本），researcher LLM 通过 JSON tool-use API 发出。新 action 可后续向白名单加，不破坏架构。

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
- Annotation 状态 (none / counterexample) + 矫正过的标记
- Last modified

Filters (ephemeral, not saved as named views in v1):
- Status、是否已矫正、是否 counterexample、confidence range、entity-count range

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
|                                      | [💾 Save correction]|
+--------------------------------------+----------------------+
```

Left: 60–70% width Document Preview. Renders PDFs (page-by-page scroll) and images. Pure viewer in v1: no overlays, no clickable hotspots, no bbox.

Right: entity-grouped field list. Each entity is a card; expandable / collapsible. Each field row supports:
- inline value edit
- field deletion
- per-field "report wrong" (sets a flag on the field that informs Confidence weighting)

Bottom buttons:
- **Schema editor** — slides out a panel. Each field has an editable description (multi-line text)、type dropdown、required toggle、optional examples and enum。Schema lock state visible。"Lock / Unlock" button。**这是 emerge 的核心编辑面**——所有"教模型"的工作发生在这里。
- **Ask researcher** — chat input. 自由文字 "this batch is missing tax field"、"currency should always be ISO code"。提交触发 AutoResearch run，把用户的文字注入 diagnosis prompt。
- **Save correction** — 持久化当前 Annotation, role=none。这是普通保存，所有矫正都进历史。

### 8.3 What's intentionally absent in the workspace view

- No raw-JSON-tree view (the user never edits raw JSON)
- No bbox overlay (multimodal LLMs are unreliable for this; deferred to v2)
- No three-column "annotate fields" layout (replaced by entity-grouped cards)
- No "next undone document" task queue (Document list filters cover this)
- **No "anchor management" / "few-shot pool" widget**—few-shot 概念已不存在（见 §1）

---

## 9. v1 scope summary

### In scope

- Workspace + multi-tenant isolation (mirroring label-studio / doc-intel-legacy patterns)
- Project + Schema Template + 5 builtin Templates
- Document upload (multi-file batch)
- Zero-shot extraction with array `responseSchema` — **prompt 不带任何 image few-shot**
- Schema auto-derivation from user corrections + lock workflow
- Schema editor with per-field NL descriptions, types, examples, enums
- Counterexample Pool (Annotation `role=counterexample`，仅作 AutoResearch 回归测试)
- Confidence Loop (judge + counterexample regression + human review + Bayesian calibration)
- AutoResearch (single Reflexion loop + action toolkit, manual + optional semi-automatic trigger)
- ProjectVersion timeline, manual setting of active_version
- API publish bound to Project's active version
- Feedback endpoint receiving counterexamples from API consumers
- Document list view (Data Manager-style)
- 2-column workspace correction view

### Out of scope (v1)

- **Image few-shot of any kind** (anchor / growth / reference)——决定永久不做（见 §0 重大决策）
- Lab / Prod artefact split (deferred to v2 — but `ProjectVersion` already gives the foundation)
- Manual `Promote to Prod` action (v2)
- Bbox of any kind: model-returned, user-drawn, hover-highlight (v2+)
- Self-consistency confidence signal (judge + counterexample regression 已经足够 v1)
- LOO (leave-one-out) confidence signal — 不再需要（没有 anchor pool 可 LOO）
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
| Zero-shot draft 太差导致 onboarding 崩溃（无 few-shot 兜底） | Strong default `system_frame` for open-ended extraction；Template 入口提供高质量起点；用户矫正第一份后 schema descriptions 立刻被填上 → 第二份起就是有 description 加持的 zero-shot；AutoResearch 在用户矫正信号到位后立刻可触发优化 description |
| 某种文档真的需要 image few-shot 才能搞定（无逃生口） | v1 接受这个限制：Template 沉淀的高质量 description + AutoResearch 优化能覆盖 95%+ 实用场景；剩余 5% 是已知 trade-off。如果生产真撞上，v2 可以加 few-shot back（架构上是增量，不是破坏性） |
| Schema lock is regretted later | Always reversible from Schema editor; lock change creates a new ProjectVersion; user warned if unlock occurs after API publish |
| AutoResearch goes rogue | Action toolkit is a whitelist; turn history transparent and human-readable; output is a candidate ProjectVersion never auto-promoted; max_turn + 3-turn no-improvement early stop |
| Judge calibration cold-start | Beta(8,2) prior gives a sane 80% starting point; UI displays `± CI` so users see the uncertainty; spot-check sampling forces calibration data accumulation |
| Multimodal model returns inconsistent JSON shape pre-lock | `responseSchema` enforced at API level even before user lock (uses derived candidate schema); model output is structurally constrained from call #1 |
| Workspace admin picks bad researcher model | Default = Opus; admins must opt-in to change; if change degrades performance, it shows immediately in turn-history score deltas |
| Single user iterating produces small calibration sample (< 30 obs) | UI shows wide CI explicitly; recommendation to keep batch ≥ 10 docs; `judge_precision_calibrated` defaults to prior mean when CI is too wide |
| User uploads 50+ docs and zero-shot batch overruns | Batch extraction runs as background SSE task with per-document progress events; UI does not block; failures mark per-document `errored` status without aborting batch |

---

## 11. Cross-cutting design constraints

三条横切关注，不是单独的 feature 而是约束所有 slice 的全局规则。**day one 落地**——retrofit 都很贵。

### 11.1 Internationalisation (i18n)

**决定**：框架从 day one i18n-ready，**v1 只 ship 英文**。

| 维度 | 约束 |
|---|---|
| Frontend | 用 `react-i18next`（或同类）。所有用户可见字符串走 `t('namespace.key')`，**禁止 hardcode**。namespace 按页面 / 组件分。 |
| Backend | API 错误响应返回 `{ error_code, error_message_en }`，前端按 `error_code` 翻译。错误消息**不**直接返回给终端用户的字面量。 |
| Date / number / currency | 走 `Intl.*` API，即使 default `en-US` 也用 locale-aware 函数 |
| 默认 + 仅 ship locale (v1) | `en` |
| Catalog 文件 | 仅填 `locales/en.json`，结构上为后续 zh / ja 留位 |

**理由**：doc-intel-legacy 后期才加 i18n，hardcoded 字符串散落各处需要补丁式修复。emerge 拒绝重蹈覆辙——这是经典 cheap-now-expensive-later。成本 ~10% 前端 / <5% 后端代码量；回报：v2 加任何语言 = 翻译 catalog，无代码改动。

### 11.2 Theme: light + dark from day one

**决定**：light / dark / system 三模式从 day one 实现，用 **semantic color tokens + CSS variables**。

| 维度 | 约束 |
|---|---|
| Token 命名 | `bg-surface`、`bg-elevated`、`text-fg-primary`、`text-fg-muted`、`border-default`、`border-strong`、`accent-primary`、`status-success` 等。**禁止**用 Tailwind 直接 color class（`bg-gray-100`、`text-white` 等）。 |
| 实现 | CSS variables：`:root { --bg-surface: white; … }` / `.dark { --bg-surface: #0a0a0a; … }`。Tailwind 配置把 token name 映射到 CSS var。 |
| Switch | 加 `.dark` class 到 `<html>`，用户可选 `light` / `dark` / `system`（跟随 `prefers-color-scheme`），偏好持久化到 localStorage。 |
| 默认 | `system` |
| 第三方 | shadcn/ui 默认就是这套 token 体系，可作为起点（不锁定） |
| QA 要求 | 每个 PR 的截图 / Playwright 验收必须覆盖 light + dark 双模式 |

**理由**：doc-intel-legacy 经历过加 theme 后被迫 revert（参考 commit `c801738 revert(frontend): remove dark/light/system theme switcher`）。教训很清晰：theme retrofit 极难——每个 hardcoded color 都得改；hover/focus/disabled 状态在两个 mode 下各自需要调；颜色对比度问题 case-by-case。day one 多 ~5% 组件开发量，远便宜过事后补丁。

### 11.3 UI style direction

**决定**：**借 label-studio 的 workflow / 信息架构，不照搬它的视觉**。

| 维度 | 跟随 label-studio | 自己重做 |
|---|---|---|
| Data Manager 列表（筛选 / 排序 / 批量动作） | ✅ 信息架构和列模型照搬 | — |
| 两栏 workspace 布局（doc preview + 字段编辑） | ✅ 整体 layout 照搬 | — |
| 工作流模式（doc list → 进 workspace → 矫正 → 回 list） | ✅ 照搬 | — |
| 视觉风格（颜色 / 字体 / 留白 / 圆角） | ❌ | 现代克制：Tailwind + CSS var token system |
| 控件库 | ❌ 不用 antd | Radix（headless）+ shadcn/ui 风格 |
| 图标 | ❌ 不用 LS 自带 | Lucide 或 Phosphor |
| Brand 色 | ❌ | 单一 accent 色（暂定 emerald-600，可调） |

**为什么不像素级照抄 LS**：
1. LS 视觉一眼像企业标注平台，与 emerge "software 3.0 工具"叙事不匹配
2. LS 基于 antd，与 §11.2 day-one dark theme 兼容性差
3. 团队的"熟悉感"靠**操作流程**（信息架构）保证就够，不需要靠 CSS 像素位置——前者帮你 6 个月不变，后者 6 个月后第一次想加新模块就别扭

最终风格目标：参考 Linear / Vercel / Cursor 的视觉调性——克制现代、单色调主导、一个 accent，留白宽，圆角小到中等。

### 11.4 这三点对 R8 的影响

R8 plan 必须在第一个 task 就建立：
- i18n catalog 与 hook（`useT`）
- token system（CSS vars + Tailwind config）
- 基础组件（Button / Input / Card / Table 等）的 light/dark/i18n 三重适配

后续所有 R8 task 在这三层基础上叠。如果中途发现 hardcoded 字符串或颜色，应当作 R8 内部的 bug 处理，立即修。

---

## 12. Implementation slicing — handoff to writing-plans

This document is intentionally a **single overall design** rather than feature-cut sub-specs. The next step (writing-plans) decomposes it into implementable slices. Suggested slicing for the planning agent:

| Slice | Scope | Depends on |
|---|---|---|
| **R1 — Foundation** | User / Workspace / Auth / DB scaffolding (FastAPI + async SQLAlchemy + alembic init) | — |
| **R2 — Project & Document model** | Project, Document, Prediction, Annotation tables; multi-file upload; basic list endpoints | R1 |
| **R3 — Schema & extraction core** | ProjectVersion + schema_snapshot; zero-shot prompt composition (NO few-shot); responseSchema integration with Gemini + OpenAI; schema auto-derivation from corrected Annotations; lock workflow | R2 |
| **R4 — Corrections & Counterexamples** | Annotation `role` (none / counterexample); 矫正保存路径；feedback API（生成 counterexample）；counterexample 列表 API | R3 |
| **R5 — Confidence Loop & Calibration** | Judge integration; counterexample regression computation; JudgeCalibration table + Beta updates; UI surfacing of human review queue | R4 |
| **R6 — AutoResearch** | AutoResearchRun table; Reflexion loop; action toolkit dispatch（仅文本类 action）；turn history rendering; manual + semi-automatic triggers | R5 |
| **R7 — Templates & API publish** | Template table + 5 builtin seeders（仅 schema descriptions）; Save-as-Template; API publish + key + feedback routing; rate limiting | R3 (parallel to R4) |
| **R8 — UI** | **首要 task：建立 §11 的三层底座**（i18n catalog + `useT` hook、light/dark token system、Radix/shadcn 基础组件）；之后才铺 Document list page、Workspace correction view (2-column)、Schema editor panel（核心面）、AutoResearch run viewer、Project page header / publish flow | R2 onwards, in parallel with backend slices |

R1, R2, R3 是串行 foundation。R4–R7 可以双人并行。R8 跟随每个后端 slice 落地。

writing-plans 可参考的 v1 milestone 结构：
- **M1 Walking skeleton** — R1 + R2 + R3 最小：用户能上传、zero-shot 提取、在 workspace 编辑 JSON、保存矫正。无 judge、无 AutoResearch、无 Templates。
- **M2 Confidence** — R4 + R5：counterexample 路径、judge、calibration、人审队列。项目级 confidence score 可见。
- **M3 Evolution** — R6：AutoResearch run loop、action toolkit（纯文本动作）、turn history。
- **M4 Reuse + ship** — R7 + R8 polish：Templates、API publish、公开 extract 端点、反馈回路端到端跑通。

writing-plans is the proper next phase to translate this into per-slice plans with task lists and TDD ordering.

---

## 13. Open questions deferred to writing-plans

These are intentionally not pinned in this design. They will surface naturally during plan-writing and should be resolved there:

1. **Backend stack choice** — FastAPI + async SQLAlchemy + SQLite (matching doc-intel-legacy's stack) is the obvious default; whether to start with PostgreSQL instead for production readiness is a R1 decision.
2. **Frontend stack choice** — Vite + React + TypeScript + Zustand (matching doc-intel-legacy) is the default; need to layer i18n（推荐 `react-i18next`）+ Tailwind 的 CSS-var token 配置 + Radix headless 组件（推荐 shadcn/ui starter）+ Lucide 图标。R8 第一个 task 必须把这些底座搭好——见 §11.4。
3. **Judge / researcher LLM provider integration concrete details** — which SDK calls, which retry semantics, which timeout — handled inside R5 / R6 plans.
4. **PDF rendering library** — react-pdf in doc-intel-legacy works fine; carry forward unless plan reveals reason to change.
5. **Concurrency model for batch extraction** — task queue (Celery? Arq? in-process asyncio.gather?) decided in R3 plan based on expected batch sizes.
6. **Auth implementation detail** — JWT (matching legacy) vs sessions; default JWT.
7. **API rate limiting library** — slowapi vs custom; minor choice in R7.

---

## 14. Naming and identity

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
