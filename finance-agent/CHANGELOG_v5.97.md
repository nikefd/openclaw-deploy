# v5.97 盘中优化 - 2026-05-12

## 🎯 优化方向: 盘中UI增强 + 实时监控

### 核心改进

#### 1️⃣ 现金部署进度条 (v5.97 UI)
- **功能:** 实时显示现金激进部署的进度 (96.6% → 15-20%)
- **位置:** Dashboard 首屏，新增 "盘中实时监控" 面板
- **指标:**
  - 当前现金占比 vs 目标范围
  - 进度条实时更新 (每30s)
  - 颜色渐变反馈 (绿→蓝)

#### 2️⃣ Kelly仓位效率指标 (实时)
```
API 端点: /kelly-positions (端口 7684)
- fund_utilization: 资金利用率 (%)
- kelly_efficiency: Kelly效率评分 (0-100)
- 目标: 15% Kelly仓位
```

#### 3️⃣ 选股超时保护状态 (新增)
```
API 端点: /selection-status (端口 7684)
- timeout_protected: 防超时启用状态
- candidate_pool_size: 当前候选池大小 (目标45)
- last_run_seconds: 最后一次运行耗时
- 状态指示: ✅ 防超时启用 / ⚠️ 无保护
```

#### 4️⃣ 持仓集中度监控 (新增)
- **指标:** 前3大持仓占总仓位的百分比
- **健康判断:**
  - 🟢 ≤30%: 健康分散
  - 🟡 30-50%: 需要优化
  - 🔴 >50%: 过度集中 (建议调整)

### 技术实现

#### 新增文件
- `/home/nikefd/finance-agent/ui-optimize-intraday-v5.97.js` (8.7KB)
  - 异步加载仪表板实时数据
  - 30秒自动刷新机制
  - 错误处理与降级

#### API更新
- `finance-api-server.js`:
  - `handleSelectionStatus()` - 选股状态查询
  - `handleKellyPositionsV97()` - Kelly效率简化版
  - 路由: `/kelly-positions`, `/selection-status`, `/dashboard`

#### HTML更新
- `/var/www/chat/finance.html`:
  - 加入 `ui-optimize-intraday-v5.97.js` 脚本
  - 自动渲染 "盘中实时监控" 面板

### 数据刷新策略

| 指标 | 刷新频率 | 数据源 |
|------|--------|-------|
| 现金部署进度 | 30s | dashboard API |
| Kelly效率 | 30s | positions表 |
| 选股状态 | 30s | 日志 + reports |
| 持仓集中度 | 30s | positions表 |

### 测试结果

```
✅ API 端点测试:
  GET /dashboard → 200 OK
  现金占比: 96.56%, 总资产: ¥1,001,863

✅ UI 面板测试:
  - 进度条显示: 正常
  - Kelly效率: 可获取
  - 选股保护: 可获取 (需日志)
  - 持仓集中度: 可获取

✅ 自动刷新: 每30s执行一次
```

### 部署清单

- [x] ui-optimize-intraday-v5.97.js 创建
- [x] finance-api-server.js 更新 (新端点)
- [x] finance.html 更新 (新脚本加载)
- [x] 文件复制到 openclaw-deploy
- [x] git 提交与推送
- [x] finance-api 重启

### 预期效果

✅ **盘中可视化增强:**
- 投资者能实时看到资金部署进度
- 持仓集中度一目了然
- 选股系统健康状态可监控
- Kelly仓位效率数字化呈现

✅ **风险管理改进:**
- 及时发现过度集中
- 防超时保护可验证
- 资金利用效率可追踪

✅ **用户体验优化:**
- Dashboard 信息更丰富
- 实时更新无刷新感
- 布局紧凑易阅读

---

**版本:** v5.97  
**时间:** 2026-05-12 03:30 UTC  
**优先级:** P1 (UI增强)  
**兼容:** v5.96 (防超时 + 激进部署) 持续有效
