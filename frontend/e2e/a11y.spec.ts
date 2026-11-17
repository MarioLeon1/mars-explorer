import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const NAVCAM = 'NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J'
const PAGES = ['/', '/explorer', `/explorer/${NAVCAM}`, `/perception/${NAVCAM}`, '/terrain', '/replay', '/assistant']

test.describe('Accessibility (axe, WCAG 2.1 A/AA)', () => {
  for (const path of PAGES) {
    test(`no serious or critical violations on ${path}`, async ({ page }) => {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
      const serious = results.violations
        .filter((v) => v.impact === 'serious' || v.impact === 'critical')
        .map((v) => `${v.id} (${v.impact}): ${v.nodes.length} × ${v.nodes[0]?.target.join(' ')} — ${v.help}`)
      expect(serious, serious.join('\n')).toEqual([])
    })
  }
})
