# 本地演示流程

> 文档进入，API 随之出现。你纠正得越多，它们会变得越好。

一份 10 分钟的脚本化演示，面向一台全新的笔记本，展示 R8 Productization MVP。
内容与自动化测试 `frontend/e2e/walking_skeleton.spec.ts` 保持一致。如果有任何不一致，
以测试用例为准。

这份文档不会打印、请求或假定任何真实密钥值：
- 提供方密钥（`GOOGLE_API_KEY`、`OPENAI_API_KEY`）只保存在 `backend/.env` 中。
- 新生成并首次揭示的 API key 在全文中统一用占位符 `EMERGE_API_KEY` 表示。
  你从一次性揭示弹窗中复制出来后，只在当前终端里执行
  `export EMERGE_API_KEY=...`，不要写入任何已提交文件。
- JWT 会落到浏览器的 `localStorage`（`emerge.token`）里；不要把它们贴到
  任何文档、日志、工单或聊天中。

---

## 0. 前置条件

- macOS 或 Linux，Python 3.11+，Node 20+，已安装 `uv`（`brew install uv`）。
- 一个提供方密钥：`GOOGLE_API_KEY`（Gemini）或 `OPENAI_API_KEY` 二选一。
  默认假设使用 Gemini；运行时抽取以及 AutoResearch / judge 路径会使用
  `backend/app/settings.py` 中配置的 `default_model_gemini` 和 `default_model_pro`
  （按模型层级拆分，参见 `CLAUDE.md` 中的模型层级拆分记忆说明）。
- 如果你的网络访问提供方需要出站代理，请在运行后端的 shell 中导出
  `https_proxy` / `http_proxy`（测试发现，如果没有代理环境变量，`httpx.ConnectError`
  会静默地留在数据库里）。

```bash
# backend/.env（已被 gitignore）。不要提交。
GOOGLE_API_KEY=...           # 占位符；把你的 key 粘贴到这里
DEFAULT_PROVIDER=gemini
```

---

## 1. 启动整套服务

需要三个 shell。后端运行在 :8000，前端运行在 :5173，第三个 shell 用来执行
任意 curl 检查。下面的命令默认你位于仓库根目录。

```bash
# shell 1 — backend
cd backend
uv sync --extra dev
mkdir -p data
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# shell 2 — frontend
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，你应该会进入 `/login`。

---

## 2. 注册并创建第一个项目

1. **注册** 任意邮箱 + 密码（`demo@example.com` / `hunter22-local-demo`
   适合临时数据库）。注册后会进入 `/projects`（空列表）。
2. **New project** → 选择内置模板 `japan_receipt`
   （非空 schema；对应 spec §1 的默认演示路径）。名字随意，比如 `demo-receipts`。
   提交后会进入 `/projects/:id`，页面上会显示：
   - 顶部的 `API Readiness` 面板（可见阻塞项：
     `active_version_unlocked`，`empty_schema` 在 schema 设置后清除，
     `schema_not_lock_candidate` 在你拿到稳定标注后清除）。
   - `Review Inbox` 横幅（显示“0 need review · 0 spot-checks · 0 docs total”
     ，因为在 extract + judge 跑完之前，vibe-check 池是空的）。
   - `Documents` 表格为空状态。

---

## 3. 上传、抽取并纠正

1. **上传三个 PDF。** 其中两个会被纠正；第三个保持未纠正，这样在 lock 之后
   vibe-check 池（spec §4.1）仍然非空。任意短收据 PDF 都可以；示例文件在
   `frontend/e2e/fixtures/sample.pdf`。上传后每一行都显示 `uploaded`。
2. **Re-extract remaining** — 表格顶部按钮。每个文档会在约 10–60 秒内切换到
   `extracted`（冷启动提供方；Gemini 热身后大约 3–5 秒/文档）。
   如果某一行卡在 `errored`，检查后端日志里是否有 `httpx.ConnectError`
   （代理 / DNS 问题）——由于 hygiene-tail item #52，prediction 的 `error_message`
   可能为空。
3. **依次为两个文档打开 Studio。** 点击某一行 → 进入 `/projects/:id/studio/:did`。
   任选一个字段，修改它的值（例如纠正 OCR 识别错的店名），点击
   `Save correction`。当 store 重新加载文档后，这个按钮会再次变为不可用
   （annotation override 会被重新灌入输入框）。对第二个文档重复一遍，
   选一个两个文档里都存在的稳定字段名——这两次纠正满足 lock 状态的前置条件。

---

## 4. 锁定 schema

1. 进入 `/projects/:id/schema` → form mode。
2. lock-status 辅助行此时应显示 “ready to lock”
   （至少 2 次已保存纠正，且至少有一个稳定字段）。
   如果按钮仍然禁用，再保存第三次纠正。
3. **Lock** → schema 现在变成可发布的不可变 ProjectVersion 候选。
   从这里开始，`/projects/:id/review` 页面的 Draft callout 会消失
   （已纠正的文档会离开 vibe-check 池——见 spec §4.1 生命周期）。

---

## 5. API Console — 激活、密钥揭示、公开抽取

1. 进入 `/projects/:id/api-console`。
2. **Production API version** 卡片 → 设置 `api_code`
   （类似 `demo-receipts-v1` 的 URL slug）→ **Activate for API**。
   Production 指针会切换到你锁定后的版本。Lab 指针保持不变——这是 spec §7.2 的不变量。
3. **Create key** → 输入名称（例如 `default`）→ 弹窗会显示明文 key。
   点击 Copy，勾选“save it in your secrets manager”，然后点 Done。
   **明文只显示一次。** 弹窗关闭或页面重载后，只能看到前缀。
4. 在终端中执行：

   ```bash
   export EMERGE_API_KEY=...    # 从弹窗里粘贴
   curl -X POST http://localhost:8000/extract/demo-receipts-v1 \
     -H "X-Api-Key: ${EMERGE_API_KEY}" \
     -F "file=@frontend/e2e/fixtures/sample.pdf"
   ```

   返回的是公开的 ExtractResponse：
   `{request_id, prediction_id, project_version_id, output, ...}`。
   任何 JSON 字段都不包含明文 key 材料。

---

## 6. 公开的部分反馈 → readiness 更新

1. 从上面的 curl 响应里取出 `prediction_id`
   （公开字段名；集成方会把它作为 `request_id` 回传到反馈里做关联）。
2. 可以直接 curl，也可以用 API Console 里的 **Send test feedback** 表单
   （要求至少有 1 个 key；表单会把粘贴的明文仅保留在组件状态中，
   成功后以及组件卸载时都会清空）：

   ```bash
   curl -X POST http://localhost:8000/extract/demo-receipts-v1/feedback \
     -H "X-Api-Key: ${EMERGE_API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "request_id": <prediction_id>,
       "corrections": [
         {"entity_index": 0, "field_path": "shop_name",
          "correct_value": "Corrected Shop Name"}
       ],
       "issue_type": "wrong_value",
       "notes": "OCR misread the kanji"
     }'
   ```

   响应会包含 `counterexample_id`。刷新 `/projects/:id` →
   `API Readiness` 不再显示 “No production feedback yet”；
   `regression_health.counterexamples_total ≥ 1`。
   当 `counterexamples_total === 0` 时，面板绝不会显示 `100%`——
   “no-feedback” 文案是该分支唯一合法的渲染结果（spec §7.4）。

---

## 7. Review Inbox — judge 运行后产生 verdict

`/projects/:id/review` 会显示三个区块：
- **Required review** — 被 judge 标记为 `down` 的文档（来自 spec §4 的 vibe-check）。
- **Spot-check** — judge 认可的、被抽样为 `up_only` 的文档。
- **All** — 当前 vibe-check 池中的所有文档。

在 judge 运行之前，这三个区块都为空（lock 之后——为什么未纠正的文档仍留在池里，
见上面的 §3）。先从终端触发一次 judge run：

1. 在浏览器里打开 DevTools → Console，运行
   `copy(localStorage.getItem("emerge.token"))`
   （这会把 JWT 复制到剪贴板，而不会打印出来）。
2. 把它粘贴到一个 shell 变量里，然后执行 curl。**不要**把 `JWT` 提交到任何文件。

```bash
JWT=...   # 从剪贴板粘贴
curl -X POST http://localhost:8000/api/v1/projects/<project_id>/judge \
  -H "Authorization: Bearer ${JWT}"
```

judge 返回后，刷新 `/projects/:id/review` →
至少 **All** 区块会非空（未纠正的第 3 个文档）；至于 **Required review**
还是 **Spot-check** 是否有行，取决于 judge 对这些 prediction 的判断。
演示交接记录里，停车收据 PDF 上的实际行为是：shop_name → `down`
（required review），issue_date / total_amount → `up`
（spot-check 候选）。

---

## 8. 演示结束健康检查

```bash
./scripts/release-checklist.sh                        # 4 pass, 1 skip（E2E）
EMERGE_E2E=1 ./scripts/release-checklist.sh           # 5 pass — 需要后端运行在 :8000
```

E2E 版本会在 headless Chromium 中重放步骤 2–7
（Gemini 热启动时约 21 秒，冷启动时 60–120 秒）。
它做的事情和这份文档完全一样，但使用的是 Playwright 的
`page.request` 捕获的 synthetic plaintext keys——spec 断言明文不会经过任何
已记录的表单输入。

---

## 9. 常见问题

- **`extracted` 行一直不出现，DB 里 `error_message` 为空。**
  大概率是 `httpx.ConnectError` —— 提供方不可达。
  带上 `https_proxy` / `http_proxy` 重启后端，或者检查 `GOOGLE_API_KEY`。
- **`POST /extract/{api_code}` 返回 403。**
  项目没有发布，或者 `X-Api-Key` 不匹配。重新到 API Console 发布一次；
  如果 key 丢了（一次性揭示），就撤销并创建一个新的。
- **API Console 的 “Activate for API” 按钮禁用。**
  schema 还没有锁定，或者是空的。检查 `/projects/:id/schema`。
- **Readiness 面板一直显示 “schema_not_lock_candidate”。**
  需要至少 2 次已保存纠正，并且这些纠正共享至少一个稳定字段名。
- **`/judge` 返回 500。**
  生产侧接线需要在 `backend/.env` 中设置 `default_model_pro`
  （默认值是 `gemini-3.1-pro-preview`），并且需要与运行时 extract 相同的提供方连通性。
  如果模型名已经过期，就在 `.env` 里覆盖它。
- **重复的 `api_code` 阻塞 alembic 0015。**
  先执行
  `cd backend && uv run python ../scripts/check_api_code_uniqueness.py`
  再运行 `alembic upgrade head`——脚本会打印所有冲突值。

---

## 10. 演示之间的重置

```bash
# 核弹级重置 — 删除本地数据库和上传文件。先确认路径。
rm backend/data/emerge.db backend/data/uploads/* 2>/dev/null
cd backend && uv run alembic upgrade head
```

`.env` 文件会保留（它在 gitignore 中；不在 `data/` 里）。
