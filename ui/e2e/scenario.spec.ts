// A hack made from start to end through the interface: project, character, map, units, dialogue, then closed and
// opened again (everything still there). Spec, section 4, alpha, automated tests point 2.
import { expect, test } from '@playwright/test';
import { home, newProject, projectData, watchServerErrors } from './helpers';

const CELL = 32;   // a map cell at the default zoom (x2)

test('a project made through the interface is still whole once opened again', async ({ page }) => {
  const serverErrors = watchServerErrors(page);
  const name = 'Scenario';
  await newProject(page, name);

  // A new ally, named
  await page.getByRole('tab', { name: 'Personnages' }).click();
  await page.getByRole('button', { name: '+ Allié' }).click();
  await page.getByRole('textbox', { name: 'Nom', exact: true }).fill('Aurore');
  await expect(page.getByRole('button', { name: 'Aurore' })).toBeVisible();

  // The map: a forest painted at (5, 6)
  await page.getByRole('tab', { name: 'Chapitres' }).click();
  await page.getByRole('tab', { name: 'Carte' }).click();
  await page.getByRole('button', { name: 'Forêt', exact: true }).click();
  await page.locator('canvas').first().click({ position: { x: 5 * CELL + CELL / 2, y: 6 * CELL + CELL / 2 } });
  await expect.poll(async () => (await projectData(page.request, 'maps')).layouts?.FakeMap?.rows?.[6]?.[5]).toBe(2);

  // Units: the hero dragged from (3, 4) to (9, 7)
  await page.getByRole('tab', { name: 'Unités et objectif' }).click();
  const hero = page.getByRole('button', { name: 'Testhero · Testlord Niv. 1', exact: true });
  const map = page.getByRole('application');
  const [from, origin] = [(await hero.boundingBox())!, (await map.boundingBox())!];
  await hero.dragTo(map, { targetPosition: { x: from.x - origin.x + 6 * CELL + CELL / 2,
                                             y: from.y - origin.y + 3 * CELL + CELL / 2 } });
  await expect.poll(async () => {
    const hero = (await projectData(page.request, 'chapters')).unitGroups?.UnitDef_TestChapter?.[0];
    return hero && [hero.endX, hero.endY];
  }).toEqual([9, 7]);

  // The opening's dialogue: a second line
  await page.getByRole('tab', { name: 'Dialogues' }).click();
  await page.getByRole('button', { name: 'Hello.' }).click();
  await page.getByRole('textbox', { name: /Tapez la réplique/ }).fill('Bienvenue au camp.');
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await expect.poll(async () => JSON.stringify((await projectData(page.request, 'dialogues')).messages ?? {}))
    .toContain('Bienvenue au camp.');

  // Closed from the File menu, opened again from the recent projects
  await page.getByRole('button', { name: 'Fichier : projets, options, aide' }).click();
  await page.getByRole('menuitem', { name: 'Fermer le projet' }).click();
  await expect(page.getByRole('heading', { name: 'Nouveau projet' })).toBeVisible();
  await page.getByRole('button', { name: /scenario/i }).first().click();   // the most recent
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible();

  await page.getByRole('tab', { name: 'Personnages' }).click();
  await expect(page.getByRole('button', { name: 'Aurore' })).toBeVisible();
  await page.getByRole('tab', { name: 'Chapitres' }).click();
  await page.getByRole('tab', { name: 'Dialogues' }).click();
  await page.getByRole('button', { name: /Hello\./ }).click();
  await expect.poll(() => page.locator('textarea').evaluateAll((areas) =>
    areas.some((a) => (a as HTMLTextAreaElement).value === 'Bienvenue au camp.'))).toBe(true);
  expect((await projectData(page.request, 'maps')).layouts.FakeMap.rows[6][5]).toBe(2);
  const units = (await projectData(page.request, 'chapters')).unitGroups.UnitDef_TestChapter;
  expect([units[0].endX, units[0].endY]).toEqual([9, 7]);

  expect(serverErrors).toEqual([]);
  await home(page);
});
