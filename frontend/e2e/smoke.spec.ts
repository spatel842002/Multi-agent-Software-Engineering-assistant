import { expect, test } from "@playwright/test";

/**
 * End-to-end smoke test for the primary user journey: register, ingest a
 * real repository, get a grounded answer from the repo-Q&A workflow, propose
 * a patch, and reject it. Runs against a real backend + real local Ollama
 * model (via `docker compose up`), not mocks -- see docs/testing.md for how
 * to run this and what it requires.
 */
test("register, ingest a repository, ask a question, and review a patch proposal", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  await page.goto("/register");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /create account/i }).click();

  await expect(page.getByText(/ingest a repository/i)).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: "e2e/screenshots/01-repositories-empty.png", fullPage: true });

  await page.getByLabel(/^name$/i).fill("hello-world");
  await page.getByLabel(/source url/i).fill("https://github.com/octocat/Hello-World.git");
  await page.getByRole("button", { name: /ingest/i }).click();

  await page.getByRole("link", { name: "hello-world" }).click();
  await expect(page.getByText(/^ready$/i)).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: "e2e/screenshots/02-repository-ready.png", fullPage: true });

  await page
    .getByPlaceholder(/how does authentication work/i)
    .fill("What does the README say this repository is for?");
  await page.getByRole("button", { name: /^submit$/i }).click();
  await expect(page.getByText(/prompt repo_qa/i)).toBeVisible({ timeout: 180_000 });
  await page.screenshot({ path: "e2e/screenshots/03-qa-answer.png", fullPage: true });

  await page.getByRole("button", { name: /propose a patch/i }).click();
  await page
    .getByPlaceholder(/describe the change you want made/i)
    .fill("Add one short sentence to README explaining this is a test repository.");
  await page.getByRole("button", { name: /^submit$/i }).click();
  await expect(page.getByRole("link", { name: /review this patch proposal/i })).toBeVisible({
    timeout: 180_000,
  });
  await page.screenshot({ path: "e2e/screenshots/04-patch-proposal-answer.png", fullPage: true });

  await page.getByRole("link", { name: /review this patch proposal/i }).click();
  await expect(page.getByText(/pending approval/i)).toBeVisible();
  await expect(page.getByText(/nothing in this proposal has been applied or executed/i)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/05-patch-proposal-review.png", fullPage: true });

  await page.getByRole("button", { name: /^reject$/i }).click();
  await expect(page.getByText(/^rejected$/i)).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: "e2e/screenshots/06-patch-proposal-rejected.png", fullPage: true });
});
