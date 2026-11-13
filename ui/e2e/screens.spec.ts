// Reference screenshots of the key screens (e2e/screens.spec.ts-snapshots/): a change that moves them shows in the
// CI's report. Made on Linux only (fonts differ elsewhere): see docs/architecture.md, "Interface tests".
import { expect, test, type Page } from '@playwright/test';
import { home, newProject, watchServerErrors } from './helpers';

test.skip(process.platform !== 'linux', 'reference screenshots are made on Linux (Playwright image or CI)');

/** What changes from one run or version to the next: hidden from the comparison. */
function changing(page: Page) {
  // the checks panel depends on the computer (Docker, mGBA)
  return [page.locator('.version'), page.locator('.panel.checks'), page.getByText(/fe-maker-e2e|FE Maker Projects/)];
}

async function shot(page: Page, name: string) {
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot(`${name}.png`, { mask: changing(page), fullPage: true });
}

test('key screens', async ({ page }) => {
  const serverErrors = watchServerErrors(page);
  await home(page);
  await shot(page, 'home');

  await newProject(page, 'Captures');
  await shot(page, 'campaign');

  await page.getByRole('tab', { name: 'Chapitres' }).click();
  await shot(page, 'chapter-units');
  await page.getByRole('tab', { name: 'Carte' }).click();
  await shot(page, 'chapter-map');
  await page.getByRole('tab', { name: 'Dialogues' }).click();
  await page.getByRole('button', { name: 'Hello.' }).click();
  await shot(page, 'chapter-dialogue');

  await page.getByRole('tab', { name: 'Personnages' }).click();
  await shot(page, 'character');
  await page.getByRole('tab', { name: 'Classes' }).click();
  await shot(page, 'class');
  await page.getByRole('tab', { name: 'Objets' }).click();
  await shot(page, 'item');

  expect(serverErrors).toEqual([]);
  await home(page);
});
