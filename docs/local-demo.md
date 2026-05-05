# Local demo walkthrough

> Documents in. APIs emerge. They get better as you correct them.

A 10-minute scripted walk through the R8 Productization MVP on a fresh laptop.
Mirrors the automated `frontend/e2e/walking_skeleton.spec.ts` — if anything
diverges, the spec is authoritative.

This doc never prints, requests, or assumes any real secret value:
- Provider keys (`GOOGLE_API_KEY`, `OPENAI_API_KEY`) live only in `backend/.env`.
- The freshly-revealed API key is referenced as the placeholder `EMERGE_API_KEY`
  throughout. When you copy it from the one-time reveal modal, paste it into a
  terminal as `export EMERGE_API_KEY=...` for that shell only — do **not** write
  it to a checked-in file.
- JWTs land in browser `localStorage` (`emerge.token`); never paste them into
  any doc, log, ticket, or chat.

---

## 0. Prerequisites

- macOS or Linux, Python 3.11+, Node 20+, `uv` installed (`brew install uv`).
- A provider key: either `GOOGLE_API_KEY` (Gemini) or `OPENAI_API_KEY`. The
  defaults assume Gemini (`gemini-2.0-flash` for runtime extraction,
  `gemini-3.1-pro-preview` for the AutoResearch / judge path).
- If your network needs an outbound proxy for the provider, export
  `https_proxy` / `http_proxy` in the shell that runs the backend (the spec
  found `httpx.ConnectError` failures silent in the DB without proxy env).

```bash
# backend/.env (gitignored). Do not commit.
GOOGLE_API_KEY=...           # placeholder; paste your key here
DEFAULT_PROVIDER=gemini
```

---

## 1. Boot the stack

Three shells. Backend on :8000, frontend on :5173, a third for any curl
checks. Snippets below assume you're at the repo root.

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

Open <http://localhost:5173> → you should land on `/login`.

---

## 2. Register and create the first project

1. **Register** with any email + password (`demo@example.com` /
   `hunter22-local-demo` is fine for a throwaway DB). After register you land
   on `/projects` (empty list).
2. **New project** → choose the `japan_receipt` builtin template
   (non-empty schema; spec §1 walking-path default). Name it anything,
   e.g. `demo-receipts`. Submit → you land on `/projects/:id`, which shows:
   - `API Readiness` panel at the top (blockers visible:
     `active_version_unlocked`, `empty_schema` clears once schema is set,
     `schema_not_lock_candidate` clears once you have stable annotations).
   - `Review Inbox` banner ("0 need review · 0 spot-checks · 0 docs total"
     because the vibe-check pool is empty until extract + judge has run).
   - `Documents` table with empty state.

---

## 3. Upload, extract, and correct

1. **Upload three PDFs.** Two will get corrected; the third stays uncorrected
   so the vibe-check pool (spec §4.1) stays non-empty after lock. Any short
   receipt PDF works; a sample is bundled at
   `frontend/e2e/fixtures/sample.pdf`. After upload each row reads
   `uploaded`.
2. **Re-extract remaining** — top of the table. Rows transition to `extracted`
   over ~10–60 s per doc (cold provider; warm Gemini ~3–5 s/doc). If a row
   sticks at `errored`, check the backend log for `httpx.ConnectError`
   (proxy / DNS) — the prediction's `error_message` may be empty due to
   hygiene-tail item #52.
3. **Open Studio for two docs in sequence.** Click a row → land on
   `/projects/:id/studio/:did`. Pick any one field, change its value (e.g.
   correct an OCR'd shop name), click `Save correction`. The button
   re-disables once the store reloads the doc (annotation override seeded
   back into the input). Repeat for a second doc with a stable field name
   present in both — those two corrections satisfy the lock-status precondition.

---

## 4. Lock the schema

1. Go to `/projects/:id/schema` → form mode.
2. The lock-status helper line should now read "ready to lock" (≥2 saved
   corrections with at least one stable field). If the button is still
   disabled, save a third correction.
3. **Lock** → schema is now an immutable ProjectVersion candidate for
   publishing. The `/projects/:id/review` page's Draft callout disappears
   from this point on (corrected docs leave the vibe-check pool — spec §4.1
   lifecycle).

---

## 5. API Console — Activate, key reveal, public extract

1. Go to `/projects/:id/api-console`.
2. **Production API version** card → set the `api_code` (a URL slug like
   `demo-receipts-v1`) → **Activate for API**. The Production pointer flips
   to your locked version. The Lab pointer is unchanged — that's the spec
   §7.2 invariant.
3. **Create key** → name it (e.g. `default`) → modal pops with the plaintext
   key. Click Copy, ack the "save it in your secrets manager" checkbox, then
   Done. **The plaintext is shown exactly once.** After dismiss/reload only
   the prefix is visible.
4. In a terminal:

   ```bash
   export EMERGE_API_KEY=...    # paste from the modal
   curl -X POST http://localhost:8000/extract/demo-receipts-v1 \
     -H "X-Api-Key: ${EMERGE_API_KEY}" \
     -F "file=@frontend/e2e/fixtures/sample.pdf"
   ```

   Response is the public ExtractResponse: `{request_id, prediction_id,
   project_version_id, output, ...}`. No JSON key contains plaintext key
   material.

---

## 6. Public partial feedback → readiness updates

1. From the curl response above, capture `prediction_id` (the public field
   name; integrators send this back as `request_id` in feedback to
   correlate).
2. Either curl, or use the API Console's **Send test feedback** form (gated
   on having ≥1 key — the form keeps the pasted plaintext in component
   state only, cleared on success and on unmount):

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

   Response includes `counterexample_id`. Reload `/projects/:id` →
   `API Readiness` no longer says "No production feedback yet";
   `regression_health.counterexamples_total ≥ 1`. The panel never shows
   `100%` when `counterexamples_total === 0` — the no-feedback copy is
   the only valid render in that branch (spec §7.4).

---

## 7. Review Inbox — judge run materialises verdicts

`/projects/:id/review` shows three sections:
- **Required review** — docs flagged `down` by the judge (from spec §4 vibe-check).
- **Spot-check** — sampled `up_only` docs the judge agreed with.
- **All** — every doc currently in the vibe-check pool.

Until the judge runs, all three are empty (after lock — see §3 above for
why uncorrected docs stay in the pool). Trigger one judge run:

```bash
JWT="$(node -e 'console.log(JSON.parse(require("fs").readFileSync("/dev/stdin"))["emerge.token"])' < /dev/null)"
# Or just open the browser DevTools console and run:
#   localStorage.getItem("emerge.token")
# Paste the value into JWT here. Do NOT commit it.

curl -X POST http://localhost:8000/api/v1/projects/<project_id>/judge \
  -H "Authorization: Bearer ${JWT}"
```

After the judge returns, reload `/projects/:id/review` → at least the **All**
section is non-empty (the uncorrected 3rd doc); whether **Required review**
or **Spot-check** has rows depends on what the judge said about the
predictions. The handoff records the live behaviour on a parking-receipt
PDF: shop_name → `down` (required review), issue_date / total_amount →
`up` (spot-check candidates).

---

## 8. End-of-walk health check

```bash
./scripts/release-checklist.sh                        # 4 pass, 1 skip (E2E)
EMERGE_E2E=1 ./scripts/release-checklist.sh           # 5 pass — backend on :8000 required
```

The E2E version replays steps 2–7 in headless Chromium (~21 s with warm
Gemini, 60–120 s cold). It does the same thing this doc does, but with
synthetic plaintext keys captured via Playwright's `page.request` — the
spec asserts the plaintext never traverses a logged form input.

---

## 9. Common issues

- **`extracted` rows never appear, error_message empty in DB.** Almost always
  `httpx.ConnectError` — provider unreachable. Restart backend with
  `https_proxy` / `http_proxy` set, or check `GOOGLE_API_KEY`.
- **`POST /extract/{api_code}` returns 403.** The project was unpublished, or
  the `X-Api-Key` doesn't match. Re-publish from the API Console; if the
  key was lost (one-time reveal), revoke and create a new one.
- **API Console "Activate for API" button disabled.** Schema not locked, or
  empty. Check `/projects/:id/schema`.
- **Readiness panel keeps showing "schema_not_lock_candidate".** Need ≥2 saved
  corrections sharing at least one stable field name.
- **`/judge` returns 500.** Production wiring needs `default_model_pro` set
  in `backend/.env` (defaults to `gemini-3.1-pro-preview`) and the same
  provider connectivity as runtime extract. If the model name is stale,
  override it in `.env`.
- **Duplicate `api_code` blocking alembic 0015.** Run
  `cd backend && uv run python ../scripts/check_api_code_uniqueness.py`
  before `alembic upgrade head` — the script prints any offending values.

---

## 10. Reset between demos

```bash
# nuclear reset — wipes the local DB and uploaded files. Confirm path first.
rm backend/data/emerge.db backend/data/uploads/* 2>/dev/null
cd backend && uv run alembic upgrade head
```

The `.env` file is preserved (it's gitignored; not in `data/`).
