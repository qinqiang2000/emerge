# emerge — Software 3.0 Document API Platform · Overall Design

> **Slogan**: Documents in. APIs emerge. They get better as you correct them.
> **Status**: v1 design
> emerge is a clean-slate project; no data migration from any predecessor.
> v1 implements **ExtractionProject** only; MatchingProject / VerificationProject are future project types in the same application.

## Glossary

| 词 | 含义 | 不是什么 |
|---|---|---|
| **Workspace** | 租户边界，admin 划分。普通用户基本不感知（参考 §8.0）。 | 不是单文档矫正页 |
| **Studio** | 单文档矫正页（per-document correction view）。用户从 Document 列表点行进入。见 §8.2。 | 不是租户边界、也不是整个项目页 |
| **Project** | 一个 API 工作单元。v1 只有 `project_type=extraction`：一个文档类型 + schema + extract API。未来同一应用内可有 `matching` / `verification`。属于某 Workspace。 | 不是 doc 集合（doc 是其子资源），也不是另一个应用 |
| **Project Type** | API 的产品形态：`extraction`（v1 实现）、`matching` / `verification`（future）。决定资产类型、Studio UX、public API output contract。 | 不是 Workspace、不是 Template |
| **Document** | 一份上传的文件（PDF / 图片）。一个 doc 一行 DB 记录。 | 不是 JSON 输出 |
| **Prediction** | 模型对某 Document 的输出。自动生成。 | 不是人审过的版本 |
| **Annotation** (DB 表名) | 用户矫正后的完整 JSON。**不**包含 bbox / span 等位置信息（仅借了 label-studio 的表名）。 | 不是 bbox / 区域标注 |
| **entity** (小写) | JSON 输出 array 里的一个元素（如一张 receipt）。"multi-entity" = 一份 doc 可能含多张。 | 不是 DB 表 |
| **Counterexample** | role=counterexample 的 Annotation：API 调用方事后报错的样本。仅作 AutoResearch 回归测试集。 | 不进 runtime prompt |
| **vibe-check 集合** | Project 内"等待人审"的 Document 子集——见 §4.1 精确定义。 | 不是用户主动维护的列表 |

---

## 0. Why this exists

doc-intel was built as "annotation platform that also publishes APIs". In real use, the annotation-first framing turned out to be the wrong shape: users wanted **a stable document API**. The first concrete API type is structured extraction; later the same mechanism can support document matching / verification. Heavy annotation / prompt-engineering / evaluation machinery was overhead, not value.

emerge restarts the design from a Karpathy software-3.0 lens:

> **The API is not configured. It emerges from the user's first few corrections, and gets better with every subsequent one.**

The user's labour is concentrated where it cannot be eliminated — judging correctness on a small sampled subset, and writing/refining natural-language descriptions. In v1 those are **field descriptions** for extraction; in future project types they become **match rule descriptions** or **policy descriptions**. Corrections feed back as evidence that the platform uses to evolve those descriptions autonomously, with human review before activation.

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


### 1.0 Platform scope & Project Types

emerge 的长期产品抽象不是单一“文档抽取工具”，而是 **AI-native Document API Platform**：

```text
docs + natural-language descriptions + LLM + corrections
→ stable API
→ API gets better over time
```

v1 只实现 `ExtractionProject`。为避免以后把 matching 硬塞进 extraction workflow，v1 数据模型从 day one 预留 `Project.project_type`，但创建接口只接受 `extraction`。

| Project Type | v1? | 核心 description 资产 | Runtime input | API output |
|---|---:|---|---|---|
| `extraction` | ✅ | field descriptions + global_notes | 单份 PDF / 图片 | `entities: array<object>` |
| `matching` | future | match rule descriptions + per-role extraction descriptions | 文档 pair / group（如合同 + 发票 + 付款申请） | `decision` + rule-by-rule `checks` + evidence |
| `verification` | future | policy descriptions | 一份或多份文档 + policy | `pass/fail/needs_review` + reasons + evidence |

关键边界：
- **同一个应用，同一套底层机制**：Workspace、Document storage、ProjectVersion、Corrections、Counterexamples、AutoResearch、Readiness、API Publish、Feedback 可复用。
- **不同 Project Type，不同 UX / output contract**：MatchingProject 未来会有 Case、DocumentRole、MatchRule、rule verdict Studio；不复用 Extraction Studio 的 entity field editor。
- **v1 不实现 matching / verification**：只保留 discriminator、spec 占位和未来计划入口，避免扩大当前 scope。
- **description-as-code 泛化**：extraction 生产 field descriptions；matching 生产 match rule descriptions；verification 生产 policy descriptions。


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

### 2.1 Project creation — Docs + NL hybrid bootstrapping

进入“新建 Project”页面，默认入口不是纯表单，也不只是纯 NL，而是 **sample docs + intent**：

```text
┌─────────────────────────────────────────────────────────────┐
│  Create an Extract API                                      │
│                                                             │
│  1) Drop 3–10 sample documents                              │
│     [ PDF / images drag area ]                              │
│                                                             │
│  2) Describe the API you want                               │
│     “Japanese receipts. I need shop name, total, date,      │
│      and each line item.”                                   │
│                                                             │
│  Or start from:                                             │
│    [ Browse builtin Templates ]    [ Empty Project ]        │
└─────────────────────────────────────────────────────────────┘
```

用户上传少量样本文档 + 输入自然语言需求 → 后端用样本文档和 NL 共同生成：
- schema fields with draft descriptions
- global_notes 草稿
- first predictions on the sample docs
- API response preview

用户看到的第一分钟 magic moment 应该是：**文档进来，API 草稿已经出现**。样本文档只用于 schema / description bootstrapping；**不进入 runtime prompt，也不形成 image few-shot pool**。

底部 escape hatch：
- **Browse builtin Templates** — 资深用户走捷径（已有现成 schema，跳过 Docs+NL bootstrapping）
- **Empty Project** — 完全留白，用户自己拖 doc 后从 zero-shot 起步

创建页可以显示 future project type cards，但 v1 只有 Extract API 可用：
- Extract fields from documents — enabled
- Match documents against each other — disabled / future
- Verify documents against rules — disabled / future

### 2.2 The main loop — batch-first progressive evolution

用户**批量**上传（5–50 份），不是一份一份滴进。流程：

```
1. 用户拖 20 份 PDF → 20 个 Document 行, status=uploaded
2. 系统对全部 20 份跑 zero-shot extraction
   (开放式 prompt + array responseSchema, 不带任何示例)
   → 每份 Document 产出 1 条 Prediction，含草稿 JSON
   → Document 列表呈现，状态徽章逐行显示
3. 用户开 doc#1 → 进 Studio（单文档矫正界面）
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
   → Document 列表按 API Readiness / risk 排序，flagged docs 进入 Review Inbox
8. 用户审 Review Inbox：
   - 👎 字段 → 修正 → inline 生成 description patch proposal（用户 Accept / Edit / Just fix this doc）
   - 👍 抽检 → 确认或更正
   - 修正本身只保存 Annotation；任何 description 变更都必须是显式 proposal 被用户接受，或 AutoResearch candidate version 被用户接受
9. Confidence Loop 后台持续算分 → 项目级 API Readiness 显示在页头
10. Readiness checklist 达标 → "Publish / Activate version for API" 主 CTA 可用
```

Project page 的形态对标 label-studio Data Manager：可筛选、可排序、可批量操作的 Document 列表。点行进 Studio（单文档矫正界面）。

**Named saved views** 不在 v1 范围内。筛选是临时的。

### 2.3 Schema maturity & lock prompt heuristic

Schema lock 不应太早出现。原先“≥ 2 份矫正且字段集合接近”只能说明 schema **可能开始稳定**，不能说明已经适合锁定并发布。

v1 改成 **schema maturity** 提示，而不是过早的硬 lock gate：

| Maturity | Conditions | UI copy / behavior |
|---|---|---|
| `draft` | 少于 3 份 reviewed docs，或字段仍频繁新增/删除 | “Keep reviewing — schema is still moving.” 不提示 lock。 |
| `stabilizing` | ≥ 3 份 reviewed docs；最近 3 份矫正的字段集差异 ≤ 1；共有字段类型一致 | “Schema looks stable. Review risky fields before locking.” 可提示继续 Review Inbox。 |
| `lock_candidate` | ≥ 5 份 reviewed docs 或 ≥ 20 reviewed entities；核心字段都有 field-level evidence；最近 5 份矫正没有 breaking schema change；无 readiness hard blocker | 弹 “Lock schema?”，但展示 evidence coverage / risky fields。 |
| `locked` | 用户显式确认 lock | 后续 predict 使用 responseSchema 硬约束；unlock 会创建新 ProjectVersion。 |

锁定可从 Schema editor 取消。若 API 已发布，unlock / schema edit 只影响 `active_version_id`，不会改变 public API；只有显式 **Activate version for API** 才会改变 `published_version_id`。

### 2.4 Description 进化机制

用户矫正 doc 时产生的"修正信号"如何流入 description？

- **手动**：用户直接在 Schema editor 改 description 文字（最直接）
- **Inline teaching proposal**：用户在 Studio 改某个字段值时，系统基于“错误值 → 正确值 + 当前文档上下文”生成一条 description patch proposal，例如“Use tax-included total, not subtotal”。用户可 `Accept` / `Edit` / `Just fix this doc`。
- **AutoResearch 自动建议**：用户点"Improve descriptions" → researcher 看 counterexamples 和 judge 反馈，提议 description 修改 → 用户审阅是否接受
- **绝不自动应用**：不从矫正后的 JSON 静默反推并写入 description（容易错，违反"description 是显式知识"原则）。LLM 可以提案，但必须以可读 diff 形式被人接受。

这种设计强制 description 始终是**人或 AutoResearch 显式书写**的——保证可读、可审计、可作为 Template 资产复用。

### 2.5 Description Workbench — IDE-grade assistance for description-as-code

如果 `description` 是代码，那么 Schema editor 不能只是 textarea。它应逐步变成 **Description Workbench**：

- **Lint**：发现空 description、含糊词（“appropriate value”）、互相矛盾的字段说明、未解释 enum / required 语义。
- **Evidence panel**：每个字段展示最近 prediction 的 field-level evidence、用户修正记录、counterexample 命中情况。
- **Test against docs**：在右侧选择 3–5 份 docs 快速重跑当前 field description，看 before/after diff。
- **Inline patch diff**：LLM / AutoResearch 只能提出 description patch；用户看到可读 diff 后 Accept / Edit / Reject。
- **Examples as documentation, not few-shot**：examples 可以帮助人理解 schema，也可用于 lint / preview；runtime prompt 仍不注入 image few-shot 或 example I/O pairs。
- **Version-aware editing**：description edit 创建新 ProjectVersion；若 API 已发布，编辑只影响 Lab active version，不影响 public API。

v1 最小实现可以先做 lint + evidence panel + patch diff；完整 IDE 体验可在 R8/R9 继续增强。

---

## 3. Data model

emerge takes the `Document` / `Prediction` / `Annotation` separation from label-studio's task model — it is a clean conceptual fit and proven in practice.

> **关于 `Annotation` 表名**：emerge 借用了 label-studio 的命名传统，但**含义不同**——emerge 的 Annotation 是"用户矫正后的完整 JSON"，**不带任何 bbox / 区域 / span 信息**。可以把 Annotation 简单理解为"人审过的 Prediction"。如果 label-studio 经验让你联想到 bbox 标注，请暂时清空那部分预期。

### 3.1 Database tables

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
  project_type           # extraction | matching | verification; v1 accepts extraction only
  template_id            # nullable; tracks origin if forked from Template
  active_version_id      # FK → ProjectVersion; Lab/editor current version
  published_version_id   # FK → ProjectVersion; nullable; public API serves this version only
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
  per_field_evidence      (JSONB: { entity_idx → field_name → { page?, quote?, rationale?, source_text_hash? } })
                          # field-level evidence, no bbox / coordinates / spans; used for Review Inbox and Description Workbench
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
- `Project.project_type` is `extraction` for all v1 Projects. `matching` / `verification` are reserved values for future project types and must not be accepted by v1 create-project APIs.
- `Project.active_version_id` always points to an existing ProjectVersion of the same Project and represents the Lab/editor current version.
- `Project.published_version_id` is nullable; when set, it points to an existing locked ProjectVersion of the same Project and is the only version public API calls serve.
- ProjectVersion is append-only — there is no archive / delete state in v1.
- `Annotation` 没有数量上限——counterexamples 全留作回归集，矫正记录全留作历史。
- `Annotation.role` 仅允许 `counterexample` 或 `none`，DB CHECK 约束。
- `Template.schema_json` is immutable once a Template version is created. Editing creates a new Template version.
- 不存储 bbox 坐标（模型返回或用户画的都不存）—— v1 设计上没有这个能力。
- `Prediction.per_field_evidence` may store page numbers, short quotes, rationales, and source text hashes, but must not store bbox coordinates or visual regions. This gives users field-level evidence without turning emerge into a visual annotation tool.

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
- **Per-Project score** — average of per-Document scores across the Project's **vibe-check set**.

**Vibe-check set 精确定义**：Project 内的 Document 中，最新一条 Prediction **未被随后的 saved Annotation (role=none) 覆盖**的那批。也就是"模型输出过、但用户还没确认或矫正"的 doc。`role=counterexample` 的 Annotation 不算"覆盖"——它是事后报错入池，不消耗 vibe-check 资格。

具体来源两块：
1. 当前 batch 中尚未被人审的 Documents
2. 通过公开 API 进来的最近 N 次调用（按比例采样，N 可配，default 上限 50 条/Project）

vibe-check 集合是**派生视图**，用户不直接管理；系统按上述定义自动维护。

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

### 4.5 API Readiness — product-facing confidence

The internal score formula remains useful for ranking and AutoResearch, but the UI / publish gate must not collapse trust into one number. Product-facing readiness is a checklist-like summary with three axes:

| Axis | Meaning | Display rule |
|---|---|---|
| **Quality estimate** | judge-calibrated estimate over the current vibe-check set | Show score + CI / observation count. Never show judge precision as a naked number. |
| **Evidence coverage** | how much human review exists | reviewed docs / entities / fields, plus risky fields with low evidence |
| **Regression health** | whether known counterexamples are fixed | show `passed / total`; if total = 0, display `No production feedback yet`, never `100%` |

Example header:

```text
API Readiness
Quality: 86% ± 8%    Evidence: 12 docs / 48 entities reviewed
Regression: 7 / 8 passing    Risky fields: tax_id, currency
```

Publish is gated by readiness checklist, not by a single composite score. The default v1 checklist:
- schema is locked
- at least one non-empty active ProjectVersion exists
- readiness endpoint returns no hard blockers
- if counterexample pool is empty, UI warns `No production feedback yet` but may still allow publish with explicit acknowledgement
- if judge calibration CI is wide or observations are low, UI warns `Low evidence`

The old `score` can remain as backend/internal data, but product surfaces should say **API Readiness**, not “confidence = ready”.


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

## 7. API Publish & Release Safety

### 7.1 Endpoints

The public API is a thin façade over `Project.published_version_id`, not over the Lab/editor `active_version_id`. This is the minimal release-safety layer: users can continue editing / activating candidate versions in the Lab without immediately breaking API consumers.

```text
POST /api/v1/projects/{pid}/publish
  body: { api_code: "japan-receipts", project_version_id?: <id> }
  → validates target version is locked and belongs to the project
  → sets project.api_code if provided / changed
  → sets project.published_version_id = target version
  → sets project.api_published_at
  → returns project state

POST /api/v1/projects/{pid}/unpublish
  → clears api_published_at (api_code remains reserved)
  → public API returns 403 while unpublished

POST /api/v1/projects/{pid}/rollback
  body: { project_version_id: <previous_locked_version_id> }
  → sets project.published_version_id to a previous locked version
  → public API uses it on the next call

GET /api/v1/projects/{pid}/contract-diff?from_version_id=<id>&to_version_id=<id>
  → returns breaking / non-breaking output contract changes

GET /api/v1/projects/{pid}/readiness
  → returns API Readiness summary: quality estimate, evidence coverage, regression health, risky fields, publish blockers/warnings

POST /api/v1/projects/{pid}/api-keys
  body: { name: "default" }
  → returns key in plaintext exactly once: "ek_<8-char-prefix>-<32-char-secret>"

POST /extract/{api_code}                                    (public, no JWT; key-only)
  header: X-Api-Key: ek_…
  body: multipart file
  → 200 OK { entities: [...], project_version: <published_version_id>, prediction_id: <id> }
  → 401 missing/bad key
  → 403 project unpublished
  → 404 api_code unknown
  → 413 file too large
  → 429 rate limited (default 60/min/key, configurable by workspace admin)

POST /extract/{api_code}/feedback                           (public, called by integrators after detecting bad output)
  header: X-Api-Key: ek_…
  body one of:
    { request_id: <prediction_id>, correct_output: [...] }     # full feedback
    {
      request_id: <prediction_id>,
      corrections: [                                           # partial feedback
        { entity_index: 0, field_path: "total", correct_value: 1234, comment?: "tax-included total" },
        { entity_index: 1, field_path: "line_items[2].price", correct_value: 99 }
      ],
      issue_type?: "wrong_value" | "missing_field" | "extra_field" | "wrong_entity_count" | "other"
    }
  → full feedback creates Annotation with role=counterexample, parent_prediction_id=<id>
  → partial feedback creates a feedback issue and, when possible, a patched counterexample Annotation by applying corrections to the original Prediction output
  → 200 OK
  → 401 / 403 / 404 same as above
  → 422 prediction_id does not belong to this api_code or patch path is invalid

# API key validation pattern: ek_<8-char-prefix>-<32-char-secret>.
# Server splits on the first '-' after the prefix marker, looks up by prefix (indexed),
# bcrypt-compares the secret half against key_hash. Constant-time comparison.
```

### 7.2 Published-version semantics

There are two version pointers:

| Pointer | Meaning | Used by |
|---|---|---|
| `active_version_id` | Lab/editor current version. User can set this from version timeline. AutoResearch outputs candidate versions that user may activate for Lab. | Studio, internal re-extract, AutoResearch, schema editor |
| `published_version_id` | Production/public API version. Must be explicitly set by Publish / Activate for API. | `POST /extract/{api_code}` only |

Rules:
- 用户改 schema / global_notes → creates a new ProjectVersion and may update `active_version_id`; public API is unchanged.
- AutoResearch 产出新 ProjectVersion → user may activate it for Lab; public API is unchanged.
- 用户在 Publish / API Console 中点 **Activate version for API** → `published_version_id` changes; next public call uses that version.
- 用户 unpublish → API 返回 403; `api_code` stays reserved; `published_version_id` may remain for later re-publish.
- 用户 rollback → `published_version_id` moves back to a previous locked ProjectVersion.

This is not a full Lab/Prod artefact split. There is still one ProjectVersion timeline and one public endpoint. The only product-safety rule is: **editing does not equal publishing**.

### 7.3 Contract diff

Before activating a version for API, UI must show a contract diff between current `published_version_id` and target version.

Breaking changes:
- field removed
- field renamed (detected as removed + added; UI may display as possible rename if names/types/descriptions are similar)
- type changed
- required tightened (`required=false → true`)
- enum narrowed
- top-level output contract changed (not allowed for ExtractionProject v1)

Non-breaking changes:
- description edited
- global_notes edited
- optional field added
- required loosened (`true → false`)
- enum widened
- examples changed

Publishing with breaking changes is allowed in v1, but requires explicit acknowledgement in the UI. API Console must show current published version and target version.

### 7.4 API Console product surface

After publish, "Publish API" becomes an API Console, not just a key-reveal modal. Minimum v1 console:
- current published version and active Lab version
- readiness summary
- contract preview and contract diff
- curl snippet
- Python / JS snippets (static generated examples are fine)
- API key create/list/revoke
- feedback example
- rollback / unpublish controls

Recent API call logs are valuable future product surfaces, but not required for R7.5 unless cheap. Partial feedback **is** part of the public feedback contract: integrators should not be forced to reconstruct the full `correct_output` when they only know “field X was wrong”.

---

## 8. UI layout & interaction

### 8.0 Workspace 对普通用户透明（来自 label-studio 实际经验）

**Workspace = 租户边界，admin 划分。普通用户基本不感知。**

- 普通用户登录 → 直接落到 "我所属 Workspace 的 Project 列表"，看不到 Workspace 概念
- 用户的 mental model：**"我登进来 → 我的 Project 列表 → 进 Project → Document 列表 → 进 Studio"**
- 仅多 Workspace 成员（少见）顶栏会有 Workspace 切换器
- Admin 用户多一个 "Workspace 管理"页

实施约束：
- 单 Workspace 用户的 URL 不带 workspace_id（如 `/projects/<id>`），路由自动解析其唯一 Workspace
- 多 Workspace 用户 URL 带（如 `/w/<workspace_id>/projects/<id>`），切 Workspace 切 URL
- 后端 API 路径仍带 `workspace_id`（保持显式），前端在请求时自动注入

这映射 label-studio 的真实使用模式：90%+ 用户不知道有 Workspace。

### 8.1 Project page (Review Inbox + Document list view)

The Project page is not only a Data Manager table; it is also the product surface of API Readiness. The top area is a **Review Inbox** that tells the user where human attention has the highest leverage:

```text
Review Inbox
7 need review    2 spot-checks    3 production feedback issues
[Review next]
```

Below the inbox, keep the filterable, sortable table. One row per Document.

Columns (default visible):
- Filename
- Status (uploaded / extracting / extracted / errored)
- Entity count (length of latest Prediction's array output)
- Risk / readiness signal (latest per-doc score + flagged fields; product label is not raw confidence)
- Annotation 状态 (none / counterexample) + 矫正过的标记
- Last modified

Filters (ephemeral, not saved as named views in v1):
- Status、是否已矫正、是否 counterexample、risk/readiness range、entity-count range

Top toolbar:
- "Upload" (drag-and-drop multi-file)
- "Re-extract selected" / "Re-extract all"
- "Run AutoResearch"
- "Schema editor" (opens panel)
- Project-level API Readiness header (quality + evidence + regression, not a naked score)
- "API Console" / "Manage API Keys" / "Activate version for API"

Click a row → enters **Studio** for that Document.

### 8.2 Studio (per-doc correction view, V2-pragmatic 2-column)

> **命名注意**：emerge 里有两个"workspace"概念易混。本节的 **Studio** 是单文档矫正页（per-document editor）。**Workspace** 永远指租户边界（admin 划分，普通用户基本不感知）。整份 spec 此后凡涉及单文档矫正页一律用 Studio。

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
- per-field "report wrong" (sets a flag on the field that informs readiness / risky-field weighting)
- **Evidence** popover: page / quote / rationale from `Prediction.per_field_evidence`; no bbox overlay or visual region selection
- **Teach model** action: opens inline description patch proposal for this field, not a hidden automatic prompt change

Bottom buttons:
- **Schema editor** — 滑出一个 panel，**双模式**（见 §8.4）。这是 emerge 的核心编辑面，所有"教模型"的工作发生在这里。
- **Ask researcher** — chat input。自由文字 "this batch is missing tax field"、"currency should always be ISO code"。提交触发 AutoResearch run，把用户的文字注入 diagnosis prompt。
- **Save correction** — 持久化当前 Annotation, role=none。

### 8.3 Schema editor — 双模式（form + chat）

Schema editor 是 emerge 最 software-3.0 的产品面。提供**两个等价模式**，用户可随时切换：

**Form mode**（精确编辑，默认）：

```
┌─ Schema for "Japan Receipts"  [Locked ▼]  [Switch to Chat ⇄]─┐
│                                                              │
│  • shop_name      string  required                           │
│    ┌──────────────────────────────────────────────────────┐  │
│    │ 店名（look near shop logo / 店舗 marker）         │  │
│    └──────────────────────────────────────────────────────┘  │
│    [+ examples]  [+ enum]                                    │
│                                                              │
│  • total_amount   number  required                           │
│    ┌──────────────────────────────────────────────────────┐  │
│    │ 合計金額（税込）                                  │  │
│    └──────────────────────────────────────────────────────┘  │
│  ...                                                         │
│  [+ add field]                                               │
└──────────────────────────────────────────────────────────────┘
```

**Chat mode**（NL 编辑）：

```
┌─ Schema for "Japan Receipts"  [Locked ▼]  [Switch to Form ⇄]─┐
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ user: 把 currency 字段加上，要求 ISO 4217 三字母     │    │
│  │       代码格式，比如 JPY、USD                        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ system 提议变更：                                   │    │
│  │   + add_field("currency", string, required,         │    │
│  │      description="ISO 4217 three-letter code",     │    │
│  │      enum=["JPY","USD","EUR","CNY"])                │    │
│  │                                                     │    │
│  │   [Diff preview ↓]                                  │    │
│  │   [Accept] [Reject] [Edit further]                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ [textarea] 描述你想改什么...                         │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

Chat mode 实现：

- 用户输入 NL → 后端发给 schema-editor LLM（Workspace 配，default 与 researcher 同模型）
- LLM 必须**只能**调用与 AutoResearch 相同的 action toolkit (§5.2)——这保证了 form mode 和 chat mode 两条路径产出语义完全等价的变更
- 系统渲染 action 列表 + diff 预览给用户审阅
- 用户 Accept → 应用为新 ProjectVersion (source=user_edit, source_metadata 含原 NL prompt)
- 用户 Reject → 不应用，对话继续

两个模式**永远写同一个底层数据结构**——只是 UI 表层不同。任何时刻切换不丢工作。这是 software 3.0 在 schema 编辑层面的彻底落地。

### 8.4 Studio 中刻意不做

- No raw-JSON-tree view (the user never edits raw JSON)
- No bbox overlay (multimodal LLMs are unreliable for this; deferred to v2)
- No three-column "annotate fields" layout (replaced by entity-grouped cards)
- No "next undone document" task queue (Document list filters cover this)
- No "labeling queue" terminology — this is not an annotation product

### 8.5 Product terminology

Product-facing UI should avoid annotation-platform / eval-tool wording unless the user is in an advanced/debug context.

| Internal / technical term | Product-facing term |
|---|---|
| Project with extraction schema | Extract API |
| Confidence score | API Readiness |
| Low-confidence documents | Needs review / Review Inbox |
| Annotation | Correction / Reviewed output |
| Counterexample | Production feedback / Regression case |
| active version | Lab version / Draft version |
| published version | API version / Production API version |
| Schema editor textarea | Description Workbench |
| Publish API modal | API Console |

This naming matters: emerge should feel like an API product that learns from corrections, not a labeling platform with an API bolted on.

---

## 9. v1 scope summary

### In scope

- Workspace + multi-tenant isolation (mirroring label-studio / doc-intel-legacy patterns)
- Project with `project_type=extraction` + Schema Template + 5 builtin Templates
- Document upload (multi-file batch)
- Zero-shot extraction with array `responseSchema` — **prompt 不带任何 image few-shot**
- Schema maturity + lock workflow based on reviewed docs/entities, field-level evidence, and no readiness hard blockers
- Schema editor / Description Workbench with per-field NL descriptions, types, examples, enums, lint, evidence panel, and patch diff
- Counterexample Pool (Annotation `role=counterexample`，仅作 AutoResearch 回归测试)
- Confidence Loop (judge + counterexample regression + human review + Bayesian calibration) plus product-facing API Readiness
- AutoResearch (single Reflexion loop + action toolkit, manual + optional semi-automatic trigger)
- ProjectVersion timeline, manual setting of `active_version_id` for Lab
- API publish bound to explicit `published_version_id` with contract diff / rollback safety
- Feedback endpoint receiving full and partial production feedback from API consumers
- Document list view (Data Manager-style)
- 2-column Studio (per-doc correction view)

### Out of scope (v1)

实施 LLM 警惕这些，不要意外加进来：

- Bbox of any kind (model-returned / user-drawn / hover-highlight)
- Full Lab / Prod artefact split — v1 only adds the minimal `published_version_id` safety pointer; no separate environments, deployments, approval workflows, or artefact registries
- Saved named views on Document list (筛选是临时的)
- Webhooks / push notifications
- Multi-user real-time collaboration / annotation locking
- Project clone
- Project-level statistics dashboard tab
- Comparison view (model A vs model B 并排)
- MatchingProject / VerificationProject implementation（同应用 future project types；v1 只预留 `project_type`）

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Multimodal LLM 多实体识别不稳 | Judge prompt explicitly asks "how many entities?"; UI 支持手动 "add entity" / "delete entity"; entity-count 错误形成 counterexample 喂 AutoResearch |
| Zero-shot draft 太差导致 onboarding 崩溃 | Strong default `system_frame` for open-ended extraction；Docs+NL onboarding（§2.1）让用户先给样本文档和需求，schema + first predictions 一起出现；Template 入口提供高质量起点 |
| Schema lock 后悔 | Schema editor 可随时 unlock；unlock 创建新 ProjectVersion；如果 API 已 publish，active_version 变化不会影响 public API，只有显式 Activate for API 才会改变 `published_version_id` |
| AutoResearch goes rogue | Action toolkit is a whitelist; turn history transparent and human-readable; output is a candidate ProjectVersion never auto-promoted to Lab active version or public published version; max_turn + 3-turn no-improvement early stop |
| Judge calibration cold-start | Beta(8,2) prior gives a sane 80% starting point; UI displays `± CI` so users see the uncertainty; spot-check sampling forces calibration data accumulation |
| Multimodal model returns inconsistent JSON shape pre-lock | `responseSchema` enforced at API level even before user lock (uses derived candidate schema); model output is structurally constrained from call #1 |
| Workspace admin picks bad researcher model | Default = Opus; admins must opt-in to change; if change degrades performance, it shows immediately in turn-history score deltas |
| Single user iterating produces small calibration sample (< 30 obs) | UI shows wide CI explicitly; recommendation to keep batch ≥ 10 docs; `judge_precision_calibrated` defaults to prior mean when CI is too wide |
| User uploads 50+ docs and zero-shot batch overruns | Batch extraction runs as background SSE task with per-document progress events; UI does not block; failures mark per-document `errored` status without aborting batch |
| Public API 被 schema 微调意外破坏 | Public API reads `published_version_id`, not `active_version_id`; contract diff warns on breaking changes; rollback points back to a previous locked ProjectVersion |

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
| 两栏 Studio 布局（doc preview + 字段编辑） | ✅ 整体 layout 照搬 | — |
| 工作流模式（doc list → 进 Studio → 矫正 → 回 list） | ✅ 照搬 | — |
| 视觉风格（颜色 / 字体 / 留白 / 圆角） | ❌ | 现代克制：Tailwind + CSS var token system |
| 控件库 | ❌ 不用 antd | Radix（headless）+ shadcn/ui 风格 |
| 图标 | ❌ 不用 LS 自带 | Lucide 或 Phosphor |
| Brand 色 | ❌ | 单一 accent 色（暂定 emerald-600，可调） |

**为什么不像素级照抄 LS**：
1. LS 视觉一眼像企业标注平台，与 emerge "software 3.0 工具"叙事不匹配
2. LS 基于 antd，与 §11.2 day-one dark theme 兼容性差
3. 我们采用的两个"模式"——**Data Manager 列表**和 **2 栏 doc-editor**——其实都是行业通用模式（GitHub PR view、Cursor、Linear inbox 都长这样），不是 LS 专属。"借模式"≠"借 LS"，只是 LS 是一个具体优秀样本。
4. AI 编码（含 Claude Code）在**现代 Tailwind + Radix + shadcn token 体系**下产出更稳——这是项目实际开发节奏的考量，不是审美偏好

最终风格目标：参考 Linear / Vercel / Cursor 的视觉调性——克制现代、单色调主导、一个 accent，留白宽，圆角小到中等。**完全不向 LS 视觉妥协**。

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
| **R7 — Templates & initial API publish** | Template table + 5 builtin seeders（仅 schema descriptions）; Save-as-Template; initial API publish + key + feedback routing; rate limiting | R3 (parallel to R4) |
| **R7.5 — Productization & Release Readiness** | `project_type=extraction`; `published_version_id`; public API serves published version; contract diff; rollback; API Readiness endpoint; docs alignment before UI | R7 |
| **R8 — UI** | **首要 task：建立 §11 的三层底座**（i18n catalog + `useT` hook、light/dark token system、Radix/shadcn 基础组件）；之后铺 Docs+NL project creation、Review Inbox + Document list、Studio inline teaching proposal、Schema editor、AutoResearch run viewer、API Readiness header、API Console / publish flow | R7.5 for publish/readiness surfaces; R2 onwards for earlier screens |

R1, R2, R3 是串行 foundation。R4–R7 可以双人并行。**R7.5 必须在 R8 publish/readiness UI 前完成**，因为它改变 public API version semantics。R8 跟随每个后端 slice 落地。

writing-plans 可参考的 v1 milestone 结构：
- **M1 Walking skeleton** — R1 + R2 + R3 最小：用户能上传、zero-shot 提取、在 Studio 编辑 JSON、保存矫正。无 judge、无 AutoResearch、无 Templates。
- **M2 Confidence** — R4 + R5：counterexample 路径、judge、calibration、人审队列。项目级 confidence score 可见。
- **M3 Evolution** — R6：AutoResearch run loop、action toolkit（纯文本动作）、turn history。
- **M4 Reuse + ship** — R7 + R7.5 + R8 polish：Templates、release-safe API publish、公开 extract 端点、readiness、反馈回路端到端跑通。

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

Ready for review. Current implementation uses R1–R8 plans plus the post-R7 adjustment plan `R7.5 — Productization & Release Readiness`.
