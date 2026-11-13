import { expect, type APIRequestContext, type Page } from '@playwright/test';

/** No project open, and the home screen shown. */
export async function home(page: Page) {
  await page.request.post('/api/projects/close');
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Nouveau projet' })).toBeVisible();
}

/** A new project from the home screen, in a new folder of the test server's own projects folder (a test tried again
 * does not meet the folder of its first try). */
export async function newProject(page: Page, name: string) {
  await home(page);
  await page.getByLabel('Nom du jeu').fill(name);
  await page.getByLabel('Auteur').fill('Testeur');
  const folder = page.getByLabel('Dossier (facultatif)');
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  await folder.fill(`${await folder.inputValue()}/${slug}-${Date.now()}`);
  await page.getByRole('button', { name: 'Créer le projet' }).click();
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible();
}

/** A data file of the open project, as the server saved it. */
export async function projectData(request: APIRequestContext, kind: string) {
  const response = await request.get(`/api/project/data/${kind}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/** Fails the test on any server error (5xx) the page met. */
export function watchServerErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('response', (r) => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });
  return errors;
}
