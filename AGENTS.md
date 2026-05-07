# emerge

Software 3.0 文档 API 平台（v1 只实现 ExtractionProject）。**Slogan**: Documents in. APIs emerge. They get better as you correct them.

- Spec (single source of truth): `docs/superpowers/specs/2026-05-02-overall-design.md`
- 实施 plan: `docs/superpowers/plans/2026-05-03-r{1..8}-*.md` + `2026-05-04-r7_5-productization-release-readiness.md`；按 R1→R2→R3 串行；R4–R7 可并行；R7.5 在 R8 publish/readiness UI 前落
- **R8 当前执行计划**: `docs/superpowers/plans/2026-05-04-r8-productization-mvp.md` (overlay)。原 `2026-05-03-r8-ui.md` 保留为完整 UI 历史参考；overlay 复用其 Tasks 1–6 作为 frontend foundation，并在 R8.0–R8.7 phases 内收敛到 productization MVP（API Console / Readiness / Review Inbox / Field Evidence / Partial Feedback / E2E）。冲突处以 overlay 为准。
- Milestone: M1 = R1+R2+R3 walking skeleton; M2 = R4+R5; M3 = R6; M4 = R7+R7.5+R8

## Collaboration

- 中文叙述、简洁、不要 trailing summary
- 推荐而非菜单 — 给方向 + 主要 trade-off，不要罗列等价选项让用户挑
- manual-confirm: destructive 操作（drop table、force-push、大改 plan、改 spec）先问
- 用户是 Karpathy software-3.0 fluent + label-studio veteran，不需要解释 task/annotation/prediction 分离这种基础概念
- Lab side 不预算 token / $ — 只 `max_turn` 和 `early_stop_no_improvement` 边界 (spec §4.4)
- v1 scoping 默认 cut 而非 add；用户已经 cut full Lab/Prod artefact split、image few-shot、named saved views、project clone；MatchingProject/VerificationProject 只预留同应用 project_type，不在 v1 实现

## Engineering

- Backend: FastAPI + async SQLAlchemy 2.x + aiosqlite + alembic + bcrypt + python-jose + pydantic v2，依赖管理 `uv`
- Frontend: Vite + React 19 + TypeScript + Zustand + react-router 6 + Tailwind v3（CSS-var token system）+ Radix + shadcn-style + Lucide
- 错误响应统一 `{error_code, error_message_en}` envelope (spec §11.1)；前端按 `error_code` 翻译
- 主题: light/dark/system 从 day one，**不允许** Tailwind 直接 color class（`bg-gray-100` 等），只用语义 token (`bg-surface`/`text-fg-primary`/...)
- 测试: `cd backend && uv run pytest -v`；迁移: `uv run alembic upgrade head`
- 单一 schema 真相: `backend/app/schemas/schema_field.py` 的 `SchemaField` pydantic model

## Hard rules (red lines)

- **没有 image few-shot**。任何 prompt 路径都不准注入 example I/O pairs。要"教模型"只能改 `description` / `global_notes` (spec §1)
- **没有 bbox / 区域信息**。Annotation 是 JSON 矫正，不存坐标 (spec §3.2)
- **AutoResearch 永不自动 promote**。output 是候选 ProjectVersion，user 必须显式 activate (spec §5.1)
- **Counterexample 永不进 runtime prompt**。仅作 AutoResearch 回归测试集 (spec §1)
- **Public API 读 Project.published_version_id，不读 active_version_id**：active 是 Lab/editor 当前版本；published 才是生产公开 API 版本。编辑/AutoResearch 激活不得自动影响 public API，必须显式 Activate for API (spec §7.2)
- **不读取/打印/提交 secrets**：不要读取或输出 `backend/.env`、provider key、JWT、API key 明文、token/password；前端示例只使用 `EMERGE_API_KEY` 等占位符。API key 明文只允许在 create-key 响应后的 one-time reveal modal 中短暂存在。

## 仓库布局

```
emerge/
├── backend/                     # 由 R1 Task 1 创建；运行: cd backend && uv run uvicorn app.main:app --reload
├── frontend/                    # 由 R8 Task 1 创建；运行: cd frontend && npm run dev
└── docs/superpowers/{specs,plans}/
```

doc-intel-legacy（`/Users/qinqiang02/colab/codespace/ai/doc-intel/`）是上一代项目，emerge 不导入、不迁移其数据；只作 stack 默认 / UX 反例参考。
