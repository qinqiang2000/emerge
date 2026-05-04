import { expect, test } from "@playwright/test";

test("register → land on projects", async ({ page }) => {
  await page.goto("/register");
  await page.fill('input[type="email"]', `e2e-${Date.now()}@e.com`);
  await page.fill('input[type="password"]', "hunter22");
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/projects/);
});
