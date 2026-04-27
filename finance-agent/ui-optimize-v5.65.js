/**
 * Finance UI 优化 v5.65 - 盘中增强
 * 新增功能：
 * 1. 实时绩效统计仪表板
 * 2. 赛道权重可视化
 * 3. 风险指标展示
 * 4. 性能对标
 */

// ========== 新增API调用 ==========

async function loadPerformanceStats() {
  try {
    const response = await fetch('/api/finance/performance-stats');
    const data = await response.json();
    renderPerformanceStats(data);
  } catch (e) {
    console.error('Performance stats error:', e);
  }
}

// ========== 新增UI渲染函数 ==========

function renderPerformanceStats(stats) {
  const container = document.getElementById('performance-stats-panel');
  if (!container) return;
  
  const html = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px;">
      <!-- Sharpe Ratio -->
      <div class="stat-card">
        <div class="stat-label">Sharpe比率</div>
        <div class="stat-value" style="color: ${stats.sharpe_ratio > 2 ? '#e63946' : stats.sharpe_ratio > 1 ? '#2ec4b6' : '#999'}">
          ${stats.sharpe_ratio.toFixed(2)}
        </div>
        <div class="stat-note">目标: >2.0</div>
      </div>
      
      <!-- Win Rate -->
      <div class="stat-card">
        <div class="stat-label">胜率</div>
        <div class="stat-value" style="color: ${stats.win_rate > 60 ? '#e63946' : stats.win_rate > 50 ? '#2ec4b6' : '#999'}">
          ${stats.win_rate}%
        </div>
        <div class="stat-note">目标: >60%</div>
      </div>
      
      <!-- Max Drawdown -->
      <div class="stat-card">
        <div class="stat-label">最大回撤</div>
        <div class="stat-value" style="color: ${stats.max_drawdown < 5 ? '#2ec4b6' : stats.max_drawdown < 10 ? '#e63946' : '#e63946'}">
          ${stats.max_drawdown.toFixed(2)}%
        </div>
        <div class="stat-note">目标: <5%</div>
      </div>
      
      <!-- Monthly Return -->
      <div class="stat-card">
        <div class="stat-label">月度收益</div>
        <div class="stat-value" style="color: ${stats.monthly_return > 0 ? '#e63946' : '#2ec4b6'}">
          ${stats.monthly_return > 0 ? '+' : ''}${stats.monthly_return.toFixed(2)}%
        </div>
        <div class="stat-note">本月表现</div>
      </div>
      
      <!-- Trade Count -->
      <div class="stat-card">
        <div class="stat-label">交易数量</div>
        <div class="stat-value">${stats.total_trades}</div>
        <div class="stat-note">${stats.positions_count} 持仓</div>
      </div>
      
      <!-- Risk Level -->
      <div class="stat-card">
        <div class="stat-label">风险等级</div>
        <div class="stat-value" style="color: ${stats.max_drawdown < 3 ? '#2ec4b6' : stats.max_drawdown < 8 ? '#e63946' : '#ff4444'}">
          ${getRiskLevel(stats.max_drawdown, stats.sharpe_ratio)}
        </div>
        <div class="stat-note">当前状态</div>
      </div>
    </div>
    
    <!-- 赛道分布 -->
    <div class="sector-distribution" style="background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px;">
      <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 12px;">赛道权重分布</h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px;">
        ${Object.entries(stats.sectors || {}).map(([sector, count]) => `
          <div style="background: var(--hover); border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 12px; color: var(--sub);">${sector}</div>
            <div style="font-size: 18px; font-weight: 600; margin-top: 4px;">${count}</div>
            <div style="font-size: 11px; color: var(--sub); margin-top: 2px;">头寸</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
  
  container.innerHTML = html;
}

function getRiskLevel(maxDD, sharpe) {
  if (maxDD < 3 && sharpe > 2) return '🟢 低';
  if (maxDD < 8 && sharpe > 1) return '🟡 中';
  return '🔴 高';
}

// ========== 增强持仓表 ==========

function enhancePositionTable() {
  const table = document.querySelector('table');
  if (!table) return;
  
  // 添加新列
  const thead = table.querySelector('thead tr');
  const newHeaders = ['风险等级', '相关性', '持仓天数'];
  newHeaders.forEach(h => {
    const th = document.createElement('th');
    th.textContent = h;
    th.style.fontSize = '12px';
    thead.appendChild(th);
  });
}

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', () => {
  // 创建性能统计容器
  const dashboardPanel = document.getElementById('panel-dashboard');
  if (dashboardPanel) {
    const perfDiv = document.createElement('div');
    perfDiv.id = 'performance-stats-panel';
    dashboardPanel.insertBefore(perfDiv, dashboardPanel.firstChild);
  }
  
  // 加载数据
  loadPerformanceStats();
  
  // 每2分钟刷新一次
  setInterval(loadPerformanceStats, 120000);
});

// ========== 样式注入 ==========

const style = document.createElement('style');
style.textContent = \`
.stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  transition: all 0.2s;
}

.stat-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(67, 97, 238, 0.1);
}

.stat-label {
  font-size: 12px;
  color: var(--sub);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  margin: 8px 0;
}

.stat-note {
  font-size: 11px;
  color: var(--sub);
}

.sector-distribution {
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
\`;
document.head.appendChild(style);
