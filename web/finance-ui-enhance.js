// Finance UI 增强 - 持仓详情侧边栏 + 策略贡献热力图
// 版本: v5.55 盘中优化

let posData = [];

// ===== 持仓详情侧边栏 =====
function showPositionSidebar(symbol) {
  const pos = posData?.find(p => p.symbol === symbol);
  if (!pos) return;
  
  const sidebar = document.getElementById('posDetailSidebar') || createPositionSidebar();
  const html = `
    <div class="pos-detail-header">
      <div>
        <div class="pos-detail-title">${pos.name || pos.symbol}</div>
        <div class="pos-detail-subtitle">${pos.symbol}</div>
      </div>
      <button class="pos-detail-close" onclick="closeSidebar()">×</button>
    </div>
    <div class="pos-detail-body">
      <div class="pos-detail-row">
        <div class="pos-detail-label">持仓数量</div>
        <div class="pos-detail-value">${pos.shares} 股</div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">成本均价</div>
        <div class="pos-detail-value">¥${pos.avg_cost?.toFixed(2)}</div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">现价</div>
        <div class="pos-detail-value">¥${pos.current_price?.toFixed(2)}</div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">持仓天数</div>
        <div class="pos-detail-value">${pos.holding_days || '--'} 天</div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">浮盈浮亏</div>
        <div class="pos-detail-value ${pos.pnl_pct >= 0 ? 'up' : 'down'}">
          ${pos.pnl_pct >= 0 ? '+' : ''}${pos.pnl_pct?.toFixed(2) || '--'}% (¥${pos.pnl?.toFixed(0)})
        </div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">历史最高价</div>
        <div class="pos-detail-value">¥${pos.peak_price?.toFixed(2) || '--'}</div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">距高点回撤</div>
        <div class="pos-detail-value ${pos.peak_drawdown < -5 ? 'down' : 'up'}">
          ${pos.peak_drawdown?.toFixed(1) || '--'}%
        </div>
      </div>
      <div class="pos-detail-row">
        <div class="pos-detail-label">追踪止损</div>
        <div class="pos-detail-value">${pos.trailing_stop_active ? '✅ 已激活' : '❌ 未激活'}</div>
      </div>
    </div>
  `;
  
  sidebar.innerHTML = html;
  sidebar.classList.add('show');
}

function createPositionSidebar() {
  const sidebar = document.createElement('div');
  sidebar.id = 'posDetailSidebar';
  sidebar.className = 'pos-detail-sidebar';
  document.body.appendChild(sidebar);
  return sidebar;
}

function closeSidebar() {
  const sidebar = document.querySelector('.pos-detail-sidebar');
  if (sidebar) sidebar.classList.remove('show');
}

// ===== 策略贡献热力图 =====
async function loadStrategyContribution() {
  try {
    const r = await fetch('/api/finance/strategy-contribution');
    const d = await r.json();
    const grid = document.getElementById('strategyGrid');
    
    if (!grid || !d.strategies || d.strategies.length === 0) {
      if (grid) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--sub);padding:40px">暂无策略数据</div>';
      return;
    }
    
    let html = '';
    d.strategies.forEach(s => {
      // 根据盈亏金额判断颜色
      let color = '#4361ee', bgColor = '#e0e7ff';
      
      if (s.total_pnl > 5000) {
        color = '#e63946';
        bgColor = '#ffe0e0';
      } else if (s.total_pnl > 1000) {
        color = '#ff6b6b';
        bgColor = '#ffe5e5';
      } else if (s.total_pnl > 100) {
        color = '#ff9800';
        bgColor = '#fff3e0';
      } else if (s.total_pnl < -5000) {
        color = '#2ec4b6';
        bgColor = '#e0f0ff';
      } else if (s.total_pnl < -1000) {
        color = '#4caf50';
        bgColor = '#e8f5e9';
      }
      
      html += `
        <div class="strategy-tile" style="background:${bgColor};border-left:4px solid ${color}">
          <div class="name">${s.name}</div>
          <div class="value" style="color:${color}">¥${s.total_pnl.toLocaleString()}</div>
          <div style="font-size:11px;color:var(--sub);margin-bottom:4px">
            ${s.trades}笔 | ${s.win_rate}%胜率
          </div>
          <div style="font-size:10px;background:rgba(255,255,255,0.5);padding:2px 4px;border-radius:4px;color:${color}">
            均盈¥${s.avg_win.toLocaleString()} / 均亏¥${s.avg_loss.toLocaleString()}
          </div>
        </div>
      `;
    });
    
    grid.innerHTML = html;
  } catch (e) {
    console.warn('strategy-contribution load error:', e);
  }
}

// 增强持仓表格 - 点击行展开详情
function enhancePositionTable() {
  const table = document.getElementById('posTable');
  if (!table) return;
  
  // 为所有行添加点击事件
  const rows = table.querySelectorAll('tbody tr');
  rows.forEach(row => {
    // 跳过展开的详情行
    if (row.classList.contains('pos-expand-row')) return;
    
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
      const symbol = row.getAttribute('data-symbol');
      if (symbol) showPositionSidebar(symbol);
    });
    
    row.addEventListener('mouseenter', () => {
      if (!row.classList.contains('pos-expand-row')) {
        row.style.background = 'var(--hover)';
      }
    });
    
    row.addEventListener('mouseleave', () => {
      row.style.background = '';
    });
  });
}

// 页面加载时自动初始化
document.addEventListener('DOMContentLoaded', () => {
  // 创建侧边栏容器
  createPositionSidebar();
});

// 集成到现有的refreshAll函数中
const originalRefreshAll = window.refreshAll;
window.refreshAll = async function() {
  if (originalRefreshAll) {
    await originalRefreshAll.call(this);
  }
  
  // 加载策略贡献数据
  loadStrategyContribution();
  
  // 增强持仓表格交互
  enhancePositionTable();
};
