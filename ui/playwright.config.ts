// Interface tests (e2e/): FE Maker on the fictional decomp (tests/e2e/serve.py), driven by Chromium.
// Run: npm run e2e (FE_MAKER_PYTHON: the Python with FE Maker's server installed; FE_MAKER_UI_DIST: the interface
// build to serve, default ui/dist). How it works: docs/architecture.md, "Interface tests".
import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.FE_MAKER_E2E_PORT ?? 8790);
const python = process.env.FE_MAKER_PYTHON ?? 'python';

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,               // one server, one open project at a time
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'line',
  timeout: 60_000,
  expect: {
    // Reference screenshots (e2e/*-snapshots/): made on Linux, in Playwright's image (see docs/architecture.md)
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled' },
  },
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${port}`,
    viewport: { width: 1400, height: 900 },
    locale: 'fr-FR',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `"${python}" ../tests/e2e/serve.py --port ${port}`,
    url: `http://127.0.0.1:${port}/api/status`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: 'pipe',
  },
});
