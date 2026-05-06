import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_PDF = path.join(HERE, "fixtures", "sample.pdf");

const E2E_ENABLED = process.env.EMERGE_E2E === "1";

test.describe("walking skeleton", () => {
  test.skip(
    !E2E_ENABLED,
    "Live-backend walking skeleton — set EMERGE_E2E=1 (requires running backend with provider key).",
  );

  test("register → extract → lock → publish → feedback → readiness → review", async ({
    page,
  }) => {
    test.setTimeout(8 * 60_000);

    const stamp = Date.now();
    const email = `e2e-walking-${stamp}@e.com`;
    const password = "hunter22-walking-skeleton";

    // 1. Register a fresh user → land on /projects.
    await page.goto("/register");
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/projects$/);

    // 2. Create project from the japan_receipt builtin → land on /projects/:id.
    await page.getByRole("button", { name: /new project/i }).click();
    await expect(page).toHaveURL(/\/projects\/new$/);
    await page.locator("#project-name").fill(`walk-${stamp}`);
    await page.locator("button", { hasText: "japan_receipt" }).click();
    await page.waitForURL(/\/projects\/(\d+)$/);
    const projectIdMatch = page.url().match(/\/projects\/(\d+)$/);
    expect(projectIdMatch).not.toBeNull();
    const projectId = Number(projectIdMatch![1]);

    // ReadinessPanel + Review Inbox banner mount above the Documents heading.
    await expect(page.getByTestId("readiness-panel")).toBeVisible();
    await expect(page.getByTestId("review-inbox-banner")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Documents" }),
    ).toBeVisible();

    // Empty state initially.
    await expect(page.getByText(/No documents yet/i)).toBeVisible();

    // 3. Upload sample.pdf three times. Two corrections satisfy lock-status;
    //    the third doc stays uncorrected so it remains in the vibe-check pool
    //    (spec §4.1: vibe-check excludes docs covered by saved annotations),
    //    giving the review-queue's `all` section at least one row to assert
    //    on without needing /judge to run.
    const fileInput = page.getByTestId("document-upload-input");
    await fileInput.setInputFiles([SAMPLE_PDF, SAMPLE_PDF, SAMPLE_PDF]);
    // Header row + 3 data rows.
    await expect(page.getByRole("row")).toHaveCount(4, { timeout: 15_000 });
    await expect(page.getByText("uploaded").first()).toBeVisible();

    // 4. Trigger extract; allow generous timeout for cold provider call.
    await page.getByRole("button", { name: /re-extract remaining/i }).click();
    await expect(page.getByText("extracted").first()).toBeVisible({
      timeout: 5 * 60_000,
    });
    await expect(page.getByText("extracted")).toHaveCount(3, {
      timeout: 5 * 60_000,
    });

    // Capture JWT for backend-side calls; never log it.
    const jwt = await page.evaluate(() =>
      localStorage.getItem("emerge.token"),
    );
    expect(jwt, "JWT must be persisted after register").toBeTruthy();
    const authHeaders = { Authorization: `Bearer ${jwt}` };

    // List documents to learn the two doc ids and their prediction ids.
    const docsResp = await page.request.get(
      `/api/v1/projects/${projectId}/documents`,
      { headers: authHeaders },
    );
    expect(docsResp.status()).toBe(200);
    const docs = (await docsResp.json()) as { id: number; status: string }[];
    expect(docs.length).toBeGreaterThanOrEqual(3);

    // Pick the first field name from each doc's prediction so the Studio
    // edit targets a real field rather than guessing the schema layout.
    async function predictionFor(docId: number): Promise<{
      id: number;
      firstField: string;
    }> {
      const detail = await page.request.get(
        `/api/v1/projects/${projectId}/documents/${docId}`,
        { headers: authHeaders },
      );
      expect(detail.status()).toBe(200);
      const body = (await detail.json()) as {
        latest_prediction: { id: number; output: Record<string, unknown>[] } | null;
      };
      expect(body.latest_prediction, "doc must have a prediction").not.toBeNull();
      const entity = body.latest_prediction!.output[0];
      expect(entity, "prediction must have at least one entity").toBeTruthy();
      const firstField = Object.keys(entity)[0];
      expect(firstField, "entity must have at least one field").toBeTruthy();
      return { id: body.latest_prediction!.id, firstField };
    }

    const doc1 = docs[0];
    const doc2 = docs[1];
    const pred1 = await predictionFor(doc1.id);
    const pred2 = await predictionFor(doc2.id);

    // 5. Studio edit → save → re-open → annotation override visible. Twice.
    async function saveCorrection(
      docId: number,
      fieldName: string,
      newValue: string,
    ): Promise<void> {
      await page.goto(`/projects/${projectId}/studio/${docId}`);
      await expect(page).toHaveURL(
        new RegExp(`/projects/${projectId}/studio/${docId}$`),
      );
      // The field-row Input is aria-labelledby the field-name span — its
      // accessible name is exactly the field name. Scope by role so we
      // skip sibling buttons (e.g. FlagFieldMenu's "Report issue for {x}"
      // trigger uses an aria-label that substring-matches the field name
      // and would otherwise be the first hit for getByLabel).
      const fieldInput = page
        .getByRole("textbox", { name: fieldName, exact: true })
        .first();
      await expect(fieldInput).toBeVisible({ timeout: 30_000 });
      await fieldInput.fill(newValue);
      const saveButton = page.getByRole("button", { name: /save correction/i });
      await expect(saveButton).toBeEnabled();
      await saveButton.click();
      // After save, the store reloads the doc → draft is reseeded with the
      // new annotation → dirty flips false → button disables again. Use
      // re-disable as the completion signal.
      await expect(saveButton).toBeDisabled({ timeout: 30_000 });
      // Confirm the annotation override seeded back into the input value.
      await expect(fieldInput).toHaveValue(newValue);
    }

    await saveCorrection(doc1.id, pred1.firstField, `e2e-${stamp}-doc1`);
    await saveCorrection(doc2.id, pred2.firstField, `e2e-${stamp}-doc2`);

    // 6. Lock the schema.
    await page.goto(`/projects/${projectId}/schema`);
    const lockBtn = page.getByRole("button", { name: /lock schema/i });
    await expect(lockBtn).toBeEnabled({ timeout: 15_000 });
    await lockBtn.click();
    await expect(
      page.getByRole("button", { name: /unlock/i }),
    ).toBeVisible({ timeout: 15_000 });

    // 7. API Console: Activate-for-API.
    await page.goto(`/projects/${projectId}/api-console`);
    const apiCode = `walk-${stamp}`;
    const codeInput = page.getByLabel("API code to activate with");
    await codeInput.fill(apiCode);
    await page.getByRole("button", { name: /activate for api/i }).click();
    // The "Published" badge in the page header signals publish completed.
    await expect(
      page.getByText("Published", { exact: true }).first(),
    ).toBeVisible({ timeout: 15_000 });

    // 8. Create API key → one-time reveal modal.
    await page.getByRole("button", { name: /create key/i }).click();
    const plaintextLocator = page.getByLabel("API key plaintext");
    await expect(plaintextLocator).toBeVisible({ timeout: 10_000 });
    const plaintextKey = (await plaintextLocator.textContent())?.trim() ?? "";
    expect(
      plaintextKey.startsWith("ek_"),
      "Revealed key must start with ek_ prefix",
    ).toBe(true);
    // Acknowledge → dismiss.
    await page.getByLabel("I have copied this key").check();
    await page.getByRole("button", { name: /^done$/i }).click();
    await expect(plaintextLocator).toBeHidden({ timeout: 5_000 });

    // 9. Send public partial feedback with the freshly-revealed plaintext key
    //    + a known prediction_id from step 4. Use page.request directly so the
    //    plaintext key never traverses a logged form input.
    const feedbackResp = await page.request.post(
      `/extract/${apiCode}/feedback`,
      {
        headers: { "X-Api-Key": plaintextKey },
        data: {
          request_id: pred1.id,
          corrections: [
            {
              entity_index: 0,
              field_path: pred1.firstField,
              correct_value: `e2e-public-${stamp}`,
            },
          ],
          issue_type: "wrong_value",
        },
      },
    );
    expect(
      feedbackResp.status(),
      "feedback endpoint must accept the request",
    ).toBe(200);
    const feedbackBody = (await feedbackResp.json()) as {
      counterexample_id: number;
    };
    expect(typeof feedbackBody.counterexample_id).toBe("number");

    // 10. Trigger judge so per_field_confidence verdicts materialise on the
    //     uncorrected doc. After schema lock, vibe-check pool only contains
    //     uncorrected predictions (gap-#51 strict mode), so judge_predictions
    //     should be exactly 1 (the 3rd doc) — Gemini Pro returns verdicts
    //     that flow into review-queue.required_review or .spot_check below.
    const judgeResp = await page.request.post(
      `/api/v1/projects/${projectId}/judge`,
      { headers: authHeaders },
    );
    expect(
      judgeResp.status(),
      "judge endpoint must succeed now that GeminiJudgeProvider is wired",
    ).toBe(200);
    const judgeBody = (await judgeResp.json()) as {
      judged_predictions: number[];
      failed_predictions: number[];
    };
    expect(
      judgeBody.judged_predictions.length,
      "at least one prediction (the uncorrected doc) must be judged",
    ).toBeGreaterThanOrEqual(1);

    // 11. ReadinessPanel reflects counterexamples_total ≥ 1 — verify via API
    //     (deterministic) and via UI (the "no production feedback" callout
    //     must not render).
    const readinessResp = await page.request.get(
      `/api/v1/projects/${projectId}/readiness`,
      { headers: authHeaders },
    );
    expect(readinessResp.status()).toBe(200);
    const readiness = (await readinessResp.json()) as {
      regression_health: { counterexamples_total: number };
    };
    expect(
      readiness.regression_health?.counterexamples_total ?? 0,
    ).toBeGreaterThanOrEqual(1);

    await page.goto(`/projects/${projectId}`);
    await expect(page.getByTestId("readiness-panel")).toBeVisible();
    await expect(page.getByTestId("readiness-no-feedback")).toHaveCount(0);

    // 12. /projects/:id/review has at least one section non-empty.
    await page.goto(`/projects/${projectId}/review`);
    await expect(
      page.getByRole("heading", { name: /review queue/i }),
    ).toBeVisible();
    const reviewRows = page.locator('[data-testid^="review-row-"]');
    await expect(reviewRows.first()).toBeVisible({ timeout: 30_000 });
  });
});
