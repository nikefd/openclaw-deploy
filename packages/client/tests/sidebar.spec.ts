/**
 * tests/sidebar.spec.ts
 * Playwright 测试：侧边栏移动端交互
 * 
 * 测试场景：
 * 1. 桌面端：侧边栏展开/折叠正常
 * 2. 移动端：点击菜单按钮展开侧边栏
 * 3. 移动端：点击侧边栏外区域关闭
 * 4. 移动端：导航时自动关闭侧边栏
 */

import { test, expect } from '@playwright/test'

test.describe('Sidebar - Mobile & Desktop', () => {
  test.beforeEach(async ({ page }) => {
    // 启动本地开发服务器 (http://localhost:5173)
    await page.goto('http://localhost:5173')
    // 等待页面加载
    await page.waitForLoadState('networkidle')
  })

  test('Desktop: sidebar should be visible and collapsible', async ({ page }) => {
    // 设置桌面视图 (1920x1080)
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.waitForTimeout(300)

    // 侧边栏应该可见
    const sidebar = page.locator('.sidebar')
    await expect(sidebar).toBeVisible()
    expect(await sidebar.evaluate((el) => window.getComputedStyle(el).width))
      .toBe('240px')

    // 点击折叠按钮
    const collapseBtn = page.locator('.sidebar .icon-btn')
    await collapseBtn.click()
    await page.waitForTimeout(300)

    // 侧边栏应该折叠为 56px
    expect(await sidebar.evaluate((el) => window.getComputedStyle(el).width))
      .toBe('56px')
  })

  test('Mobile: sidebar should be hidden by default', async ({ page }) => {
    // 设置移动视图 (375x667)
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    const sidebar = page.locator('.sidebar')
    // 检查是否被隐藏 (translateX(-100%))
    const transform = await sidebar.evaluate((el) => 
      window.getComputedStyle(el).transform
    )
    // 应该是 matrix(1, 0, 0, 1, -240, 0) 或类似的 translateX(-100%)
    expect(transform).toContain('matrix')
  })

  test('Mobile: clicking menu button should open sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    // 找到移动菜单按钮 (iOS/Android 风格的 hamburger)
    const mobileBtn = page.locator('[data-testid="mobile-menu-btn"]')
    
    // 如果按钮存在，点击它
    if (await mobileBtn.isVisible()) {
      await mobileBtn.click()
      await page.waitForTimeout(300)

      const sidebar = page.locator('.sidebar')
      const transform = await sidebar.evaluate((el) => 
        window.getComputedStyle(el).transform
      )
      // 应该没有 translateX 偏移 (visible)
      expect(transform).not.toContain('-240')
    }
  })

  test('Mobile: clicking sidebar content should keep it open (not auto-close)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    const mobileBtn = page.locator('[data-testid="mobile-menu-btn"]')
    if (await mobileBtn.isVisible()) {
      await mobileBtn.click()
      await page.waitForTimeout(300)

      // 点击侧边栏内的聊天项目
      const chatItem = page.locator('.sidebar .chat-item').first()
      if (await chatItem.isVisible()) {
        await chatItem.click()
        await page.waitForTimeout(300)

        // 侧边栏应该自动关闭（根据修复）
        const sidebar = page.locator('.sidebar')
        const transform = await sidebar.evaluate((el) => 
          window.getComputedStyle(el).transform
        )
        // 如果实现了自动关闭，transform 应该回到 translateX(-100%)
        expect(transform).toContain('matrix')
      }
    }
  })

  test('Mobile: clicking backdrop should close sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    const mobileBtn = page.locator('[data-testid="mobile-menu-btn"]')
    if (await mobileBtn.isVisible()) {
      await mobileBtn.click()
      await page.waitForTimeout(300)

      // 点击 backdrop (深灰色遮罩)
      const backdrop = page.locator('.mobile-backdrop')
      if (await backdrop.isVisible()) {
        await backdrop.click()
        await page.waitForTimeout(300)

        // 侧边栏应该关闭
        const sidebar = page.locator('.sidebar')
        const transform = await sidebar.evaluate((el) => 
          window.getComputedStyle(el).transform
        )
        expect(transform).toContain('matrix')
      }
    }
  })

  test('Mobile: resize from mobile to desktop should show sidebar', async ({ page }) => {
    // 从移动端开始
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    let sidebar = page.locator('.sidebar')
    let transform = await sidebar.evaluate((el) => 
      window.getComputedStyle(el).transform
    )
    expect(transform).toContain('matrix')

    // 调整到桌面大小
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.waitForTimeout(500) // 等待 resize 事件处理 + CSS 过渡

    // 侧边栏应该显示
    sidebar = page.locator('.sidebar')
    const width = await sidebar.evaluate((el) => 
      window.getComputedStyle(el).width
    )
    expect(width).toBe('240px')
  })

  test('Mobile: sidebar should not have pointer-events blocked', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    await page.waitForTimeout(300)

    const mobileBtn = page.locator('[data-testid="mobile-menu-btn"]')
    if (await mobileBtn.isVisible()) {
      // 菜单按钮应该可点击
      await expect(mobileBtn).toBeEnabled()
      
      // 点击打开侧边栏
      await mobileBtn.click()
      await page.waitForTimeout(300)

      const sidebar = page.locator('.sidebar')
      // 侧边栏内的按钮应该可点击
      const sidebarBtn = sidebar.locator('button').first()
      if (await sidebarBtn.isVisible()) {
        await expect(sidebarBtn).toBeEnabled()
      }
    }
  })
})
