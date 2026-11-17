import { expect, test, type Page } from '@playwright/test'
import { resolve } from 'node:path'

/**
 * Portfolio screenshots with the user's real data: `npm run screenshots` while the app runs
 * (.\scripts\dev.ps1). Output: docs/media/*.png. Not part of the test suite.
 */
const OUT = resolve(import.meta.dirname, '..', '..', 'docs', 'media')
const NAVCAM_2022 = 'NLF_2022_0846455939_237ECM_N0930000NCAM02022_07_195J'

const shot = (page: Page, name: string) => page.screenshot({ path: resolve(OUT, `${name}.png`) })

test.describe.configure({ mode: 'serial' })

test('mission control', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.ds-prov--real_observation').first()).toBeVisible()
  await page.waitForLoadState('networkidle')
  await shot(page, '01-mission-control')
})

test('explorer', async ({ page }) => {
  await page.goto('/explorer?sol=2022')
  await page.waitForLoadState('networkidle')
  await shot(page, '02-explorer')
})

test('perception', async ({ page }) => {
  await page.goto(`/perception/${NAVCAM_2022}`)
  await expect(page.locator('circle.pw__det').first()).toBeAttached({ timeout: 60_000 })
  await page.waitForLoadState('networkidle')
  await shot(page, '03-perception')
})

test('path sketch', async ({ page }) => {
  await page.goto(`/perception/${NAVCAM_2022}`)
  await page.getByRole('tab', { name: 'Path sketch' }).click()
  await page.getByRole('button', { name: 'Set goal (B)' }).click()
  const stage = page.locator('.zv__stage')
  await expect(page.locator('.zv__img').first()).toBeVisible()
  const box = await stage.boundingBox()
  if (!box) throw new Error('viewer not visible')
  await stage.click({ position: { x: box.width * 0.7, y: box.height * 0.4 } })
  await expect(page.getByText('Why this path')).toBeVisible({ timeout: 60_000 })
  await shot(page, '04-path-sketch')
})

test('terrain', async ({ page }) => {
  await page.goto('/terrain')
  await page.getByRole('button', { name: 'Load these drives' }).click()
  await expect(page.getByRole('button', { name: 'Plan routes' })).toBeEnabled({ timeout: 60_000 })
  await page.getByRole('button', { name: 'Plan routes' }).click()
  await expect(page.getByText('Why this route')).toBeVisible({ timeout: 90_000 })
  await page.waitForLoadState('networkidle')
  await shot(page, '05-terrain')
})

test('replay', async ({ page }) => {
  await page.goto('/replay?sol=2024&seq=2024-NAVCAM_LEFT-NCAM00520')
  await expect(page.getByText('RECONSTRUCTED · not a NASA video')).toBeVisible()
  await page.waitForLoadState('networkidle')
  await shot(page, '06-replay')
})

test('assistant', async ({ page }) => {
  await page.goto('/assistant')
  await page.waitForLoadState('networkidle')
  await shot(page, '07-assistant')
})
