# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: mobile-sidebar.spec.ts >> mobile sidebar reachable + visible diagnostics
- Location: tests/mobile-sidebar.spec.ts:83:5

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('[data-testid="mobile-menu-btn"]')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - button "☰" [ref=e4] [cursor=pointer]
  - complementary [ref=e5]:
    - generic [ref=e6]:
      - generic [ref=e8]: 🐶
      - button "»" [ref=e9] [cursor=pointer]
    - generic [ref=e10]:
      - button "💬" [ref=e11] [cursor=pointer]
      - button "🧠" [ref=e12] [cursor=pointer]
      - button "🛠️" [ref=e13] [cursor=pointer]
    - generic [ref=e15]:
      - button "🌓" [ref=e16] [cursor=pointer]:
        - generic [ref=e17]: 🌓
      - button "🚪" [ref=e18] [cursor=pointer]:
        - generic [ref=e19]: 🚪
  - main [ref=e20]:
    - generic [ref=e22]:
      - heading "开始一段新的对话" [level=2] [ref=e23]
      - paragraph [ref=e24]: 左侧选择历史对话，或点击「+ 新建 chat」。
    - button "🟧 Claude Opus 4.7 ▾" [ref=e27] [cursor=pointer]:
      - generic [ref=e28]: 🟧
      - generic [ref=e29]: Claude Opus 4.7
      - generic [ref=e30]: ▾
```

# Test source

```ts
  3   | /**
  4   |  * Standalone test: verify mobile sidebar drawer behavior on production /v2/.
  5   |  * No dev server needed.
  6   |  *
  7   |  * Generates a fresh oc_session cookie (HMAC) so we can land directly on the chat page.
  8   |  */
  9   | import crypto from 'crypto'
  10  | 
  11  | const COOKIE_SECRET = 'e2014d2b4042fb98de33a5f5cae1abbb8bd8657b74b2bc7cdf2b18e1faa19fd8'
  12  | const USER = 'nikefd'
  13  | const ORIGIN = 'https://zhangyangbin.com'
  14  | 
  15  | function makeSessionCookie() {
  16  |   const exp = Date.now() + 24 * 60 * 60 * 1000
  17  |   const payload = `${USER}:${exp}`
  18  |   const sig = crypto.createHmac('sha256', COOKIE_SECRET).update(payload).digest('hex')
  19  |   return `${payload}:${sig}`
  20  | }
  21  | 
  22  | test.use({
  23  |   ...devices['Pixel 5'],
  24  |   baseURL: ORIGIN,
  25  |   ignoreHTTPSErrors: true,
  26  | })
  27  | 
  28  | test('mobile sidebar opens when ☰ tapped, closes via backdrop', async ({ context, page }) => {
  29  |   // Inject session cookie
  30  |   await context.addCookies([
  31  |     {
  32  |       name: 'oc_session',
  33  |       value: makeSessionCookie(),
  34  |       domain: 'zhangyangbin.com',
  35  |       path: '/',
  36  |       httpOnly: true,
  37  |       secure: true,
  38  |       sameSite: 'Strict',
  39  |     },
  40  |   ])
  41  | 
  42  |   // 1) Land on /v2/
  43  |   await page.goto('/v2/', { waitUntil: 'networkidle' })
  44  | 
  45  |   // Should see the mobile menu button (only renders when isMobile=true)
  46  |   const menuBtn = page.locator('[data-testid="mobile-menu-btn"]')
  47  |   await expect(menuBtn).toBeVisible({ timeout: 5000 })
  48  | 
  49  |   // 2) Sidebar should start hidden (translateX(-100%))
  50  |   const sidebar = page.locator('aside.sidebar')
  51  |   await expect(sidebar).toHaveCount(1)
  52  |   // Off-screen check via bounding box: x should be < 0
  53  |   let box = await sidebar.boundingBox()
  54  |   console.log('Initial sidebar bbox:', box)
  55  |   expect(box).not.toBeNull()
  56  |   // Allow small tolerance, but it should be off-screen left
  57  |   expect(box!.x).toBeLessThan(-100)
  58  | 
  59  |   // 3) Tap ☰ → sidebar slides in
  60  |   await menuBtn.click()
  61  |   // Wait for transform transition
  62  |   await page.waitForTimeout(500)
  63  | 
  64  |   box = await sidebar.boundingBox()
  65  |   console.log('After click bbox:', box)
  66  |   expect(box).not.toBeNull()
  67  |   // x should now be ~0 (visible)
  68  |   expect(box!.x).toBeGreaterThanOrEqual(-2)
  69  |   expect(box!.x).toBeLessThanOrEqual(2)
  70  | 
  71  |   // 4) Backdrop should be visible
  72  |   const backdrop = page.locator('.mobile-backdrop')
  73  |   await expect(backdrop).toBeVisible()
  74  | 
  75  |   // 5) Click backdrop → sidebar hides
  76  |   await backdrop.click({ position: { x: 350, y: 400 } })
  77  |   await page.waitForTimeout(500)
  78  |   box = await sidebar.boundingBox()
  79  |   console.log('After backdrop click bbox:', box)
  80  |   expect(box!.x).toBeLessThan(-100)
  81  | })
  82  | 
  83  | test('mobile sidebar reachable + visible diagnostics', async ({ context, page }) => {
  84  |   await context.addCookies([
  85  |     {
  86  |       name: 'oc_session',
  87  |       value: makeSessionCookie(),
  88  |       domain: 'zhangyangbin.com',
  89  |       path: '/',
  90  |       httpOnly: true,
  91  |       secure: true,
  92  |       sameSite: 'Strict',
  93  |     },
  94  |   ])
  95  | 
  96  |   page.on('console', (msg) => console.log(`[browser ${msg.type()}]`, msg.text()))
  97  |   page.on('pageerror', (err) => console.log('[pageerror]', err.message))
  98  | 
  99  |   await page.goto('/v2/', { waitUntil: 'networkidle' })
  100 |   await page.screenshot({ path: 'tests/screenshots/mobile-initial.png', fullPage: true })
  101 | 
  102 |   const menuBtn = page.locator('[data-testid="mobile-menu-btn"]')
> 103 |   await menuBtn.click()
      |                 ^ Error: locator.click: Test timeout of 30000ms exceeded.
  104 |   await page.waitForTimeout(600)
  105 |   await page.screenshot({ path: 'tests/screenshots/mobile-after-click.png', fullPage: true })
  106 | 
  107 |   // Dump useful state
  108 |   const state = await page.evaluate(() => {
  109 |     const aside = document.querySelector('aside.sidebar') as HTMLElement | null
  110 |     const backdrop = document.querySelector('.mobile-backdrop') as HTMLElement | null
  111 |     return {
  112 |       innerWidth: window.innerWidth,
  113 |       asideExists: !!aside,
  114 |       asideClass: aside?.className,
  115 |       asideTransform: aside ? getComputedStyle(aside).transform : null,
  116 |       asideRect: aside?.getBoundingClientRect().toJSON(),
  117 |       backdropExists: !!backdrop,
  118 |       backdropDisplay: backdrop ? getComputedStyle(backdrop).display : null,
  119 |     }
  120 |   })
  121 |   console.log('STATE_DUMP:', JSON.stringify(state, null, 2))
  122 | })
  123 | 
```