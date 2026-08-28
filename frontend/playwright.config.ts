import { defineConfig, devices } from "@playwright/test";

// Not run as part of the fast CI frontend job: this exercises the real
// three-workflow pipeline against a real local Ollama model through
// `docker compose up`, which takes minutes per run (see docs/testing.md)
// and needs services CI doesn't provision. Run manually with:
//   npm run test:e2e
export default defineConfig({
  testDir: "./e2e",
  timeout: 5 * 60 * 1000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    screenshot: "on",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
