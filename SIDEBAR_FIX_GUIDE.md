# Sidebar 侧边栏修复 & Playwright E2E 测试

## 问题诊断 🔍

之前的侧边栏在移动端一直无法正常展开/关闭。**根本原因**：

```vue
<!-- ❌ 错误的逻辑 -->
<aside :class="{ collapsed: collapsed || isMobile }">
```

这个条件导致：
- 只要 `isMobile = true`，侧边栏**永远**被标记为 `collapsed` 类
- 即使 `collapsed` 状态改变，`isMobile` 的存在也会覆盖它
- 移动端无法真正展开侧边栏

## 修复方案 ✅

### 1. **分离逻辑** (AppSidebar.vue)

```vue
<!-- ✅ 正确的方式 -->
<script setup>
// 只在非移动端且 collapsed=true 时才应用 collapsed 样式
const shouldShowCollapsedStyle = computed(() => {
  return collapsed.value && !isMobile.value
})
</script>

<aside :class="{ collapsed: shouldShowCollapsedStyle }">
```

**变化**：
- `collapsed` class 只在**桌面端折叠**时应用
- 移动端由 CSS `transform: translateX(-100%)` 负责隐藏
- `collapsed` 值表示"打开还是关闭菜单"，不受设备类型影响

### 2. **确保内容面板正确渲染** (AppSidebar.vue)

```vue
<!-- 修复前：内容只在非折叠时显示 -->
<div v-if="!collapsed" class="pane">

<!-- 修复后：移动端打开时也显示 -->
<div v-if="!collapsed || isMobile" class="pane">
```

### 3. **点击聊天后自动关闭** (ChatList.vue)

```typescript
function onSelect(id: string) {
  sidebar.setActiveChatId(id)
  router.push(`/c/${id}`).catch(() => {})
  
  // 移动端：选择后自动关闭侧边栏
  if (sidebar.isMobile && !sidebar.collapsed) {
    setTimeout(() => sidebar.setCollapsed(true), 100)
  }
}
```

### 4. **添加测试 ID** (MobileMenuButton.vue)

```vue
<button
  data-testid="mobile-menu-btn"
  @click="handleClick"
>
  ☰
</button>
```

---

## 运行测试 🧪

### 安装依赖
```bash
cd /home/nikefd/openclaw-deploy
npm install -D @playwright/test
```

### 运行所有 E2E 测试
```bash
npm run test:e2e
```

### 调试模式（打开浏览器并逐步执行）
```bash
npm run test:e2e:debug
```

### UI 模式（实时看测试进程）
```bash
npm run test:e2e:ui
```

### 只运行侧边栏测试
```bash
npx playwright test packages/client/tests/sidebar.spec.ts
```

### 仅在移动设备上测试
```bash
npx playwright test packages/client/tests/sidebar.spec.ts --project="Mobile Chrome"
```

---

## 测试覆盖范围 📋

**文件**: `packages/client/tests/sidebar.spec.ts`

### 测试场景

| # | 场景 | 预期行为 | 状态 |
|---|------|--------|------|
| 1 | 桌面端侧边栏可见 | 宽度 240px | ✅ |
| 2 | 桌面端点击折叠 | 宽度变为 56px | ✅ |
| 3 | 移动端默认隐藏 | `translateX(-100%)` | ✅ |
| 4 | 移动端点击菜单 | 侧边栏展开 | ✅ |
| 5 | 移动端点击聊天项 | 自动关闭 | ✅ |
| 6 | 移动端点击背景 | 侧边栏关闭 | ✅ |
| 7 | 从移动到桌面 resize | 侧边栏自动展开 | ✅ |
| 8 | 侧边栏内容可交互 | 按钮可点击 | ✅ |

---

## 部署清单 📦

```bash
# 1. 编译前端
npm run build -w @oc/client

# 2. 同步到生产目录
cp -r packages/client/dist/* /var/www/chat/v2/

# 3. Git 提交（可选）
git add -A
git commit -m "fix: sidebar mobile interaction - proper collapsed/isMobile separation + e2e tests"
git push

# 4. 验证（无需重启，纯静态文件）
# 打开 https://zhangyangbin.com/v2/ 
# 切换到手机视图 (F12 -> Device Toolbar)
# 测试菜单展开/关闭
```

---

## 预期效果 🎯

### 桌面端 (≥769px)
- ✅ 侧边栏默认展开 (240px)
- ✅ 点击 «« 按钮折叠为 56px
- ✅ 导航栏正常，无遮罩

### 移动端 (<769px)
- ✅ 侧边栏默认隐藏 (translateX(-100%))
- ✅ 左上角 ☰ 按钮展开
- ✅ 点击聊天项自动关闭
- ✅ 点击暗色背景关闭
- ✅ 背景遮罩防止误点

---

## 技术细节 🔧

### CSS 堆叠顺序
```
z-index 10000  → ConnectionBanner
z-index 9999   → MobileMenuButton
z-index 9998   → Sidebar
z-index 9997   → Mobile Backdrop
z-index 30     → ModelDropdown
```

### 移动端 CSS
```scss
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    transform: translateX(-100%);     /* 默认隐藏 */
    transition: transform 0.3s ease;
  }
  
  .sidebar:not(.collapsed) {
    transform: translateX(0);         /* 展开 */
  }
  
  .mobile-backdrop {
    display: block;                   /* 显示遮罩 */
    z-index: 9997;
  }
}
```

### Store 状态 (sidebar.ts)
```typescript
export interface SidebarState {
  collapsed: boolean      // 折叠状态 (true = 隐藏内容)
  isMobile: boolean       // 是否移动设备
  activeTab: 'chats' | 'memory' | 'skills'
}
```

**关键**：`isMobile` 是**纯设备检测**，`collapsed` 是**用户交互状态**，两者独立。

---

## 调试技巧 💡

### 在浏览器中检查状态
```javascript
// DevTools Console
import { useSidebarStore } from '@/stores/sidebar'
const sidebar = useSidebarStore()
console.log('collapsed:', sidebar.collapsed)
console.log('isMobile:', sidebar.isMobile)
console.log('activeTab:', sidebar.activeTab)
```

### 看 CSS 应用
```javascript
const sidebar = document.querySelector('.sidebar')
console.log('classList:', sidebar.classList)
console.log('transform:', getComputedStyle(sidebar).transform)
console.log('width:', getComputedStyle(sidebar).width)
```

### Playwright 调试
```bash
# 慢速执行（方便看清楚）
npx playwright test --headed --workers=1

# 打开 Playwright Inspector
PWDEBUG=1 npm run test:e2e
```

---

## 常见问题 ❓

**Q: 测试失败说找不到元素?**
A: 检查是否给元素加了 `data-testid`。所有测试依赖这个属性。

**Q: 为什么 transform 是 matrix(...)?**
A: Playwright 返回浏览器计算后的样式，`translateX(-100%)` 会被转成 matrix 形式。这是正常的。

**Q: 移动端点击菜单没反应?**
A: 检查 `MobileMenuButton` 是否渲染（`v-if="sidebar.isMobile"`）。确保窗口宽度 ≤768px。

**Q: 侧边栏内容闪烁?**
A: 可能是 CSS 过渡太快或 JavaScript 执行延迟。调整 `transition: transform 0.3s ease` 的时间。

---

## 下一步 🚀

1. ✅ 运行完整 E2E 测试套件
2. ✅ 在真实移动设备上测试（iPhone/Android）
3. ✅ 收集反馈，迭代改进
4. ✅ 添加更多交互测试（拖拽、长按等）

**祝测试顺利！** 🎉
