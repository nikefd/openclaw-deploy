# 🔧 侧边栏修复 v3 - 2026-05-08 彻底版

## 核心问题（终于找到了！）

**之前的错误**：
- App.vue 中 `sidebar.setCollapsed(mobile)` 每次 resize 都会重置，导致用户无法手动控制
- AppSidebar.vue 中 `shouldShowCollapsedStyle` 的逻辑对移动端应用了 `collapsed` class
- CSS 中 `.sidebar.collapsed` 在移动端被错误应用，造成无法切换

## 根本修复

### 1️⃣ App.vue - 只在设备类型改变时更新
```typescript
// 关键改动：检测设备类型是否改变，而不是每次都重置
const checkMobile = () => {
  const wasMobile = sidebar.isMobile
  const isMobileNow = window.innerWidth <= 768
  
  if (wasMobile !== isMobileNow) {
    // 设备类型改变了
    sidebar.setIsMobile(isMobileNow)
    
    if (isMobileNow) {
      sidebar.setCollapsed(true)   // 桌面→移动：隐藏
    } else {
      sidebar.setCollapsed(false)  // 移动→桌面：显示
    }
  }
}
```

### 2️⃣ AppSidebar.vue - 分离状态应用
```typescript
// shouldShowCollapsedStyle 只在桌面端应用 collapsed class
const shouldShowCollapsedStyle = computed(() => {
  if (isMobile.value) return false  // 移动端不应用此 class
  return collapsed.value             // 桌面端根据 collapsed 值
})
```

### 3️⃣ AppSidebar.vue - pane 条件简化
```vue
<!-- 只要 collapsed=true 就隐藏内容 -->
<div v-if="!collapsed" class="pane">
```

### 4️⃣ CSS - 让 @media 完全控制移动端
```scss
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    transform: translateX(-100%);     /* 默认隐藏 */
    transition: transform 0.3s ease;
  }
  
  .sidebar:not(.collapsed) {
    transform: translateX(0);         /* collapsed=false → 显示 */
  }
  
  .sidebar.collapsed {
    transform: translateX(-100%);     /* collapsed=true → 隐藏 */
  }
}
```

## 现在应该工作的流程

### 移动端 (375px)
```
1. 打开页面 → 侧边栏隐藏 ✅ (collapsed=true)
2. 点击菜单 ☰ → collapsed 变 false → 侧边栏展开 ✅
3. 点击聊天项 → collapsed 变 true → 侧边栏关闭 ✅
4. 点击背景 → collapsed 变 true → 侧边栏关闭 ✅
5. Resize 到桌面 → collapsed 变 false → 侧边栏显示 ✅
```

### 桌面端 (1920px)
```
1. 打开页面 → 侧边栏展开 ✅ (collapsed=false)
2. 点击 «« 按钮 → collapsed 变 true → 侧边栏折叠到 56px ✅
3. 再点击 »» → collapsed 变 false → 侧边栏展开 ✅
4. Resize 到移动 → collapsed 变 true → 侧边栏隐藏 ✅
```

## 验证清单

- [ ] 在 https://zhangyangbin.com/v2/ 打开浏览器
- [ ] F12 打开开发者工具
- [ ] 切换到手机视图（Ctrl+Shift+M）
- [ ] 刷新页面，侧边栏应该隐藏
- [ ] 点击左上角 ☰，侧边栏应该从左边滑出
- [ ] 点击任意聊天项，侧边栏应该自动关闭
- [ ] 点击侧边栏外的区域，侧边栏应该关闭
- [ ] 把窗口改宽到桌面大小，侧边栏应该自动出现
- [ ] 点击侧边栏顶部的 «« 按钮，应该折叠到 56px

## 代码位置

- ✅ `/home/nikefd/openclaw-deploy/packages/client/src/App.vue` - 修复 checkMobile 逻辑
- ✅ `/home/nikefd/openclaw-deploy/packages/client/src/components/sidebar/AppSidebar.vue` - 修复 shouldShowCollapsedStyle 和 pane 条件
- ✅ `/var/www/chat/v2/` - 已同步编译后的代码

## 问题对比

| 版本 | 问题 | 修复 |
|------|------|------|
| v1 | `collapsed \|\| isMobile` 逻辑陷阱 | ❌ 无法修复 |
| v2 | App.vue 每次 resize 都重置 collapsed | ❌ 导致无法手动控制 |
| v3 | 分离设备检测和用户交互 | ✅ 只在设备类型改变时更新 |

---

👉 **现在测试一下，应该能工作了！** 报告结果 🚀
