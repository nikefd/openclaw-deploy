import { test, expect, devices } from '@playwright/test'

/**
 * Standalone test: verify mobile sidebar drawer behavior on production /v2/.
 * No dev server needed.
 *
 * Generates a fresh oc_session cookie (HMAC) so we can land directly on the chat page.
 */
import crypto from 'crypto'

const COOKIE_SECRET = 'e2014d2b4042fb98de33a5f5cae1abbb8bd8657b74b2bc7cdf2b18e1faa19fd8'
const USER = 'nikefd'
const ORIGIN = 'https://zhangyangbin.com'

function makeSessionCookie() {
  const exp = Date.now() + 24 * 60 * 60 * 1000
  const payload = `${USER}:${exp}`
  const sig = crypto.createHmac('sha256', COOKIE_SECRET).update(payload).digest('hex')
  return `${payload}:${sig}`
}

test.use({
  ...devices['Pixel 5'],
  baseURL: ORIGIN,
  ignoreHTTPSErrors: true,
})

test('mobile sidebar opens when ☰ tapped, closes via backdrop', async ({ context, page }) => {
  // Inject session cookie
  await context.addCookies([
    {
      name: 'oc_session',
      value: makeSessionCookie(),
      domain: 'zhangyangbin.com',
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'Strict',
    },
  ])

  // 1) Land on /v2/
  await page.goto('/v2/', { waitUntil: 'networkidle' })

  // Should see the mobile menu button (only renders when isMobile=true)
  const menuBtn = page.locator('[data-testid="mobile-menu-btn"]')
  await expect(menuBtn).toBeVisible({ timeout: 5000 })

  // 2) Sidebar should start hidden (translateX(-100%))
  const sidebar = page.locator('aside.sidebar')
  await expect(sidebar).toHaveCount(1)
  // Off-screen check via bounding box: x should be < 0
  let box = await sidebar.boundingBox()
  console.log('Initial sidebar bbox:', box)
  expect(box).not.toBeNull()
  // Allow small tolerance, but it should be off-screen left
  expect(box!.x).toBeLessThan(-100)

  // 3) Tap ☰ → sidebar slides in
  await menuBtn.click()
  // Wait for transform transition
  await page.waitForTimeout(500)

  box = await sidebar.boundingBox()
  console.log('After click bbox:', box)
  expect(box).not.toBeNull()
  // x should now be ~0 (visible)
  expect(box!.x).toBeGreaterThanOrEqual(-2)
  expect(box!.x).toBeLessThanOrEqual(2)

  // 4) Backdrop should be visible
  const backdrop = page.locator('.mobile-backdrop')
  await expect(backdrop).toBeVisible()

  // 5) Click backdrop → sidebar hides
  await backdrop.click({ position: { x: 350, y: 400 } })
  await page.waitForTimeout(500)
  box = await sidebar.boundingBox()
  console.log('After backdrop click bbox:', box)
  expect(box!.x).toBeLessThan(-100)
})

test('mobile sidebar reachable + visible diagnostics', async ({ context, page }) => {
  await context.addCookies([
    {
      name: 'oc_session',
      value: makeSessionCookie(),
      domain: 'zhangyangbin.com',
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'Strict',
    },
  ])

  page.on('console', (msg) => console.log(`[browser ${msg.type()}]`, msg.text()))
  page.on('pageerror', (err) => console.log('[pageerror]', err.message))

  await page.goto('/v2/', { waitUntil: 'networkidle' })
  await page.screenshot({ path: 'tests/screenshots/mobile-initial.png', fullPage: true })

  const menuBtn = page.locator('[data-testid="mobile-menu-btn"]')
  await menuBtn.click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: 'tests/screenshots/mobile-after-click.png', fullPage: true })

  // Dump useful state
  const state = await page.evaluate(() => {
    const aside = document.querySelector('aside.sidebar') as HTMLElement | null
    const backdrop = document.querySelector('.mobile-backdrop') as HTMLElement | null
    return {
      innerWidth: window.innerWidth,
      asideExists: !!aside,
      asideClass: aside?.className,
      asideTransform: aside ? getComputedStyle(aside).transform : null,
      asideRect: aside?.getBoundingClientRect().toJSON(),
      backdropExists: !!backdrop,
      backdropDisplay: backdrop ? getComputedStyle(backdrop).display : null,
    }
  })
  console.log('STATE_DUMP:', JSON.stringify(state, null, 2))
})
