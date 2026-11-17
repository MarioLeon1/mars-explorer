import { expect, test, type Page } from '@playwright/test'

// Ids from the captured NASA fixtures used by tests/e2e_seed.py.
const NAVCAM = 'NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J'

/** Fail the test on any uncaught page error (React crashes, bad JSON…). */
function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

test.describe('Mars Explorer end to end', () => {
  test('every module opens from the navigation rail without errors', async ({ page }) => {
    const errors = watchErrors(page)
    await page.goto('/')
    await expect(page.getByText('Not affiliated with or endorsed by NASA/JPL')).toBeVisible()
    for (const path of ['/explorer', '/perception', '/terrain', '/replay', '/assistant', '/']) {
      await page.locator(`nav a[href="${path}"]`).first().click()
      await expect(page).toHaveURL(new RegExp(`${path === '/' ? '/$' : path}`))
      await expect(page.locator('main')).not.toBeEmpty()
    }
    expect(errors).toEqual([])
  })

  test('Mission Control shows real, credited data', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.ds-prov--real_observation').first()).toBeVisible()
    await expect(page.getByText('NASA/JPL-Caltech').first()).toBeVisible()
  })

  test('Explorer image detail keeps provenance and credit', async ({ page }) => {
    await page.goto(`/explorer/${NAVCAM}`)
    await expect(page.locator('.ds-prov--real_observation').first()).toBeVisible()
    await expect(page.getByText('NASA/JPL-Caltech').first()).toBeVisible()
    await expect(page.locator('.zv__img').first()).toBeVisible()
  })

  test('Perception path sketch avoids rock candidates on the image', async ({ page }) => {
    const errors = watchErrors(page)
    await page.goto(`/perception/${NAVCAM}`)
    await page.getByRole('tab', { name: 'Path sketch' }).click()
    await expect(page.getByText('IMAGE-SPACE SKETCH · not a drivable route')).toBeVisible()

    await page.getByRole('button', { name: 'Goal at centre' }).click()
    await expect(page.getByText('Why this path')).toBeVisible()
    await expect(page.locator('polyline.ps__path')).toBeAttached()
    await expect(page.getByText('ALGORITHMIC · IMAGE SPACE')).toBeVisible()

    // A real click on the image moves the goal and re-plans.
    await page.getByRole('button', { name: 'Set goal (B)' }).click()
    const stage = page.locator('.zv__stage')
    const box = await stage.boundingBox()
    if (!box) throw new Error('viewer not visible')
    const before = await page.locator('polyline.ps__path').getAttribute('points')
    await stage.click({ position: { x: box.width * 0.8, y: box.height * 0.3 } })
    await expect.poll(() => page.locator('polyline.ps__path').getAttribute('points')).not.toBe(before)
    expect(errors).toEqual([])
  })

  test('Replay plays a reconstructed sequence, clearly labelled', async ({ page }) => {
    await page.goto('/replay?sol=2024&seq=2024-NAVCAM_LEFT-NCAM00518')
    await expect(page.getByText('RECONSTRUCTED · not a NASA video')).toBeVisible()
    const counter = page.locator('.rp-player__counter')
    await expect(counter).toContainText('1/4')
    await page.getByRole('button', { name: 'Play' }).click()
    await expect(counter).toContainText('2/4', { timeout: 15_000 })
    await expect(page.getByText('Official NASA videos')).toBeVisible()
  })

  test('Terrain explains how to get the elevation model when it is missing', async ({ page }) => {
    await page.goto('/terrain')
    await expect(page.getByText('The orbital elevation model is not downloaded yet')).toBeVisible()
    await expect(page.getByText('uv run mars-terrain fetch')).toBeVisible()
  })

  test('Assistant without a key explains how to enable it', async ({ page }) => {
    await page.goto('/assistant')
    await expect(page.getByText('AI assistant · not configured')).toBeVisible()
    await expect(page.getByText('ANTHROPIC_API_KEY=sk-ant-...')).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Message' })).toHaveCount(0)
  })
})
