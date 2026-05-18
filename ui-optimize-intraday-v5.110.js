/**
 * v5.110 盤中UI優化② - 仓位热力图 + 实时情绪 + Sharpe监控
 * 新增功能:
 * 1. 仓位热力图 (持有天数/收益率热力)
 * 2. 实时情绪仪表 + Sharpe/回撤卡片
 * 3. 动态阈值显示 (当前现金占比→推荐阈值)
 * 4. Kelly系数实时监控
 * 5. 绩效统计分级 (按赛道/策略)
 */

// ============================================================================
// 功能①: 仓位热力图增强
// ============================================================================

async function loadPositionHeatmapV110() {
  try {
    const res = await fetch('/api/finance/position-heatmap-v110?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const heatmapPanel = document.getElementById('position-heatmap-panel');
    if (!heatmapPanel) return;

    const { positions = [], metrics = {}, grid_layout = [] } = data;
    const concentration = metrics.concentration_ratio || 0;
    const upCount = metrics.up_count || 0;
    const totalCount = metrics.total_count || 0;
    const upRatio = totalCount > 0 ? (upCount / totalCount * 100) : 0;

    let html = `<div>`;
    
    // 顶部指标卡
    html += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">
      <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
        <div style="font-size:11px;color:var(--sub);margin-bottom:4px">持仓数</div>
        <div style="font-size:20px;font-weight:700;color:var(--accent)">${totalCount}</div>
      </div>
      <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
        <div style="font-size:11px;color:var(--sub);margin-bottom:4px">上涨占比</div>
        <div style="font-size:20px;font-weight:700;color:#4ade80">${upRatio.toFixed(1)}%</div>
        <div style="font-size:10px;color:var(--sub);margin-top:2px">↑${upCount} ↓${totalCount - upCount}</div>
      </div>
      <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
        <div style="font-size:11px;color:var(--sub);margin-bottom:4px">集中度</div>
        <div style="font-size:20px;font-weight:700;color:${concentration > 70 ? '#f87171' : concentration > 50 ? '#fb923c' : '#4ade80'}">${concentration.toFixed(1)}%</div>
      </div>
    </div>`;

    // 热力图格子 (按持有天数和收益率混合)
    if (grid_layout && grid_layout.length > 0) {
      html += `<div style="font-size:12px;color:var(--sub);margin-bottom:8px;font-weight:600">持仓热力分布 (颜色=收益率, 大小=持有天数)</div>`;
      html += `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));gap:6px">`;
      
      grid_layout.forEach(cell => {
        const pnlPct = cell.pnl_pct || 0;
        const holdingDays = cell.holding_days || 0;
        const size = Math.min(Math.max(holdingDays * 1.5, 60), 120);
        
        // 颜色映射 (红=上涨, 蓝=下跌)
        let bgColor = '#4361ee';
        if (pnlPct > 15) bgColor = '#81c784';      // 深绿 (大涨)
        else if (pnlPct > 5) bgColor = '#a5d6a7'; // 浅绿 (小涨)
        else if (pnlPct > 0) bgColor = '#c8e6c9'; // 更浅绿
        else if (pnlPct > -5) bgColor = '#ffd9a3'; // 橙色 (小跌)
        else if (pnlPct > -15) bgColor = '#ffb5a3'; // 粉红
        else bgColor = '#f87171';                   // 红色 (大跌)
        
        html += `<div style="width:${size}px;height:${size}px;background:${bgColor};border:1px solid var(--border);border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:10px;font-weight:600;cursor:pointer;transition:transform 0.15s" title="${cell.symbol}: ${pnlPct > 0 ? '+' : ''}${pnlPct.toFixed(1)}% (持${holdingDays}天)">
          <div style="color:var(--text)">${cell.symbol}</div>
          <div style="color:var(--text);font-size:11px;margin-top:2px">${pnlPct > 0 ? '+' : ''}${pnlPct.toFixed(1)}%</div>
          <div style="color:var(--sub);font-size:9px;margin-top:2px">${holdingDays}d</div>
        </div>`;
      });
      
      html += `</div>`;
    }
    
    heatmapPanel.innerHTML = html;
  } catch (e) {
    console.warn('position-heatmap-v110 error:', e.message);
  }
}

// ============================================================================
// 功能②: 实时情绪仪表 + Sharpe/回撤卡片
// ============================================================================

async function loadSentimentMeterV110() {
  try {
    const res = await fetch('/api/finance/sentiment-meter-v110?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const sentimentPanel = document.getElementById('sentiment-heatmap-panel');
    if (!sentimentPanel) return;

    const {
      sentiment_score = 50,
      sentiment_label = '中性',
      sharpe_ratio = 0,
      max_drawdown = 0,
      win_rate = 0,
      recent_trend = 'neutral'
    } = data;

    let html = `<div>`;
    
    // 情绪仪表盘
    html += `<div style="display:grid;grid-template-columns:150px 1fr;gap:16px;align-items:center;margin-bottom:16px">
      <div style="text-align:center">
        <div style="font-size:11px;color:var(--sub);margin-bottom:8px">市场情绪</div>
        <div style="width:120px;height:120px;margin:0 auto;border-radius:50%;background:conic-gradient(var(--accent) 0deg ${sentiment_score * 3.6}deg, var(--border) ${sentiment_score * 3.6}deg);display:flex;align-items:center;justify-content:center">
          <div style="text-align:center">
            <div style="font-size:32px;font-weight:700;color:var(--text)">${sentiment_score}</div>
            <div style="font-size:11px;color:var(--sub)">分</div>
          </div>
        </div>
        <div style="font-size:12px;font-weight:600;margin-top:8px">${sentiment_label}</div>
        <div style="font-size:10px;color:var(--sub)">趋势:${recent_trend}</div>
      </div>
      <div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div style="padding:12px;background:var(--hover);border-radius:8px">
            <div style="font-size:11px;color:var(--sub);margin-bottom:6px">Sharpe比率</div>
            <div style="font-size:18px;font-weight:700;color:var(--accent)">${sharpe_ratio.toFixed(2)}</div>
            <div style="font-size:10px;color:var(--sub);margin-top:4px">${sharpe_ratio > 1 ? '✓ 优秀' : sharpe_ratio > 0.5 ? '△ 良好' : '✗ 待改善'}</div>
          </div>
          <div style="padding:12px;background:var(--hover);border-radius:8px">
            <div style="font-size:11px;color:var(--sub);margin-bottom:6px">最大回撤</div>
            <div style="font-size:18px;font-weight:700;color:var(--down)">${max_drawdown.toFixed(2)}%</div>
            <div style="font-size:10px;color:var(--sub);margin-top:4px">${Math.abs(max_drawdown) < 5 ? '✓ 低风险' : Math.abs(max_drawdown) < 15 ? '△ 中风险' : '✗ 高风险'}</div>
          </div>
          <div style="padding:12px;background:var(--hover);border-radius:8px;grid-column:1/-1">
            <div style="font-size:11px;color:var(--sub);margin-bottom:6px">胜率</div>
            <div style="font-size:18px;font-weight:700;color:#4ade80">${win_rate.toFixed(1)}%</div>
            <div style="font-size:10px;color:var(--sub);margin-top:4px">${win_rate > 55 ? '✓ 高于平均' : '△ 近期待改善'}</div>
          </div>
        </div>
      </div>
    </div>`;

    sentimentPanel.innerHTML = html;
  } catch (e) {
    console.warn('sentiment-meter-v110 error:', e.message);
  }
}

// ============================================================================
// 功能③: 动态阈值监控 (现金占比→推荐阈值)
// ============================================================================

async function loadThresholdMonitorV110() {
  try {
    const res = await fetch('/api/finance/threshold-monitor-v110?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const cashPanel = document.getElementById('cashProfileWrap');
    if (!cashPanel) return;

    const {
      current_cash_ratio = 0,
      current_cash = 0,
      total_value = 0,
      recommended_cash_ratio = 0.15,
      strategy_mode = 'balanced',
      kelly_multiplier = 1.0,
      position_limit = 10,
      max_single_weight = 0.15
    } = data;

    // 根据现金占比推荐阈值和模式
    let modeLabel = '';
    let modeDesc = '';
    let modeColor = 'var(--accent)';

    if (strategy_mode === 'aggressive') {
      modeLabel = '激进模式';
      modeDesc = '高风险高收益';
      modeColor = '#e63946';
    } else if (strategy_mode === 'conservative') {
      modeLabel = '保守模式';
      modeDesc = '低风险稳定';
      modeColor = '#2ec4b6';
    } else {
      modeLabel = '均衡模式';
      modeDesc = '风险收益均衡';
      modeColor = 'var(--accent)';
    }

    // 计算现金占比状态
    const cashRatioPct = (current_cash_ratio * 100).toFixed(1);
    const recommendPct = (recommended_cash_ratio * 100).toFixed(1);
    const cashStatus = current_cash_ratio > recommended_cash_ratio * 1.2 
      ? '💰 现金充足，可增加投入' 
      : current_cash_ratio < recommended_cash_ratio * 0.8 
      ? '⚠️ 现金紧张，建议减仓' 
      : '✓ 现金配比正常';

    // 更新HTML
    const cashRatioEl = document.getElementById('cashRatioVal');
    const strategyModeEl = document.getElementById('strategyMode');
    const modeDescEl = document.getElementById('modeDesc');
    const boostInfoEl = document.getElementById('boostInfo');

    if (cashRatioEl) {
      cashRatioEl.textContent = `${cashRatioPct}%`;
    }

    if (strategyModeEl) {
      strategyModeEl.textContent = modeLabel;
      strategyModeEl.style.background = modeColor;
    }

    if (modeDescEl) {
      modeDescEl.innerHTML = `${modeDesc}<br><span style="font-size:10px;color:var(--sub)">${cashStatus}</span>`;
    }

    if (boostInfoEl) {
      boostInfoEl.innerHTML = `
        <div style="font-size:11px;margin-bottom:6px"><strong>Kelly系数:</strong> ${kelly_multiplier.toFixed(2)}x</div>
        <div style="font-size:11px;margin-bottom:6px"><strong>推荐现金:</strong> ${recommendPct}% (${(total_value * recommended_cash_ratio / 100).toFixed(0)}元)</div>
        <div style="font-size:11px;margin-bottom:6px"><strong>持仓限制:</strong> ${position_limit}只</div>
        <div style="font-size:11px"><strong>单只上限:</strong> ${(max_single_weight * 100).toFixed(1)}%</div>
      `;
    }
  } catch (e) {
    console.warn('threshold-monitor-v110 error:', e.message);
  }
}

// ============================================================================
// 功能④: Kelly系数实时监控
// ============================================================================

async function loadKellyMonitorV110() {
  try {
    const res = await fetch('/api/finance/kelly-monitor-v110?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const perfIndicatorsWrap = document.getElementById('perfIndicatorsWrap');
    if (!perfIndicatorsWrap) return;

    const {
      kelly_coefficient = 0,
      kelly_status = 'normal',
      win_loss_ratio = 0,
      average_win = 0,
      average_loss = 0,
      win_rate = 0,
      kelly_recommendation = ''
    } = data;

    // 构建Kelly监控面板HTML
    let html = `<div style="background:var(--hover);border-radius:8px;padding:16px;margin-top:12px">
      <div style="font-size:12px;color:var(--sub);margin-bottom:12px;font-weight:600">📊 Kelly系数</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px">
        <div style="padding:10px;background:var(--card);border-radius:6px;text-align:center">
          <div style="font-size:10px;color:var(--sub)">Kelly系数</div>
          <div style="font-size:16px;font-weight:700;color:var(--accent)">${kelly_coefficient.toFixed(3)}</div>
          <div style="font-size:9px;color:var(--sub);margin-top:2px">状态: ${kelly_status}</div>
        </div>
        <div style="padding:10px;background:var(--card);border-radius:6px;text-align:center">
          <div style="font-size:10px;color:var(--sub)">盈亏比</div>
          <div style="font-size:16px;font-weight:700;color:${win_loss_ratio > 1 ? 'var(--up)' : 'var(--down)'}">${win_loss_ratio.toFixed(2)}</div>
          <div style="font-size:9px;color:var(--sub);margin-top:2px">平均盈/亏</div>
        </div>
        <div style="padding:10px;background:var(--card);border-radius:6px;text-align:center">
          <div style="font-size:10px;color:var(--sub)">胜率</div>
          <div style="font-size:16px;font-weight:700;color:#4ade80">${win_rate.toFixed(1)}%</div>
          <div style="font-size:9px;color:var(--sub);margin-top:2px">信号可靠性</div>
        </div>
      </div>
      <div style="padding:8px;background:var(--card);border-radius:6px;font-size:11px;color:var(--text);line-height:1.6">${kelly_recommendation}</div>
    </div>`;

    // 插入到性能指标面板
    const perfWrap = document.getElementById('perfIndicatorsWrap');
    if (perfWrap) {
      const existingKelly = perfWrap.querySelector('[data-kelly-panel]');
      if (existingKelly) {
        existingKelly.innerHTML = html;
      } else {
        const div = document.createElement('div');
        div.setAttribute('data-kelly-panel', '1');
        div.innerHTML = html;
        perfWrap.appendChild(div);
      }
    }
  } catch (e) {
    console.warn('kelly-monitor-v110 error:', e.message);
  }
}

// ============================================================================
// 功能⑤: 绩效统计分级 (按赛道/策略)
// ============================================================================

async function loadPerformanceBreakdownV110() {
  try {
    const res = await fetch('/api/finance/performance-breakdown-v110?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const perfStatsWrap = document.getElementById('perfStatsWrap');
    if (!perfStatsWrap) return;

    const {
      by_sector = {},
      by_strategy = {},
      by_timeframe = {}
    } = data;

    // 按赛道统计
    let html = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:12px">`;
    
    Object.entries(by_sector).forEach(([sector, stats]) => {
      const color = stats.win_rate > 60 ? '#4ade80' : stats.win_rate > 40 ? 'var(--accent)' : 'var(--up)';
      html += `<div style="padding:10px;background:var(--hover);border-radius:6px;border-left:3px solid ${color}">
        <div style="font-size:11px;color:var(--sub);margin-bottom:4px">${sector}</div>
        <div style="font-size:14px;font-weight:700;color:${color}">${stats.win_rate.toFixed(1)}%</div>
        <div style="font-size:10px;color:var(--sub);margin-top:2px">${stats.wins}/${stats.total}</div>
      </div>`;
    });

    html += `</div>`;

    // 按策略统计
    html += `<div style="font-size:12px;color:var(--sub);margin-bottom:8px;font-weight:600">按策略统计</div>`;
    html += `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:12px">`;

    Object.entries(by_strategy).forEach(([strategy, stats]) => {
      const color = stats.avg_return > 2 ? '#4ade80' : stats.avg_return > 0 ? 'var(--accent)' : 'var(--up)';
      html += `<div style="padding:10px;background:var(--hover);border-radius:6px">
        <div style="font-size:10px;color:var(--sub)">🎯 ${strategy}</div>
        <div style="font-size:13px;font-weight:700;color:${color}">${stats.avg_return > 0 ? '+' : ''}${stats.avg_return.toFixed(2)}%</div>
        <div style="font-size:9px;color:var(--sub)">平均收益</div>
      </div>`;
    });

    html += `</div>`;

    // 更新面板
    const strategyWinRateEl = document.getElementById('strategyWinRate');
    if (strategyWinRateEl) {
      const topStrategies = Object.entries(by_strategy)
        .sort((a, b) => b[1].win_rate - a[1].win_rate)
        .slice(0, 5)
        .map(([name, stats]) => `
          <div style="margin-bottom:6px">
            <div style="font-size:11px;color:var(--sub)">${name}</div>
            <div style="font-size:13px;font-weight:600">
              ${stats.win_rate.toFixed(1)}% <span style="font-size:11px;color:var(--sub)">(${stats.wins}/${stats.total})</span>
            </div>
          </div>
        `).join('');
      strategyWinRateEl.innerHTML = topStrategies || '<div style="color:var(--sub)">暂无</div>';
    }
  } catch (e) {
    console.warn('performance-breakdown-v110 error:', e.message);
  }
}

// ============================================================================
// 主初始化函数
// ============================================================================

async function initIntradayUIV110() {
  try {
    await Promise.all([
      loadPositionHeatmapV110(),
      loadSentimentMeterV110(),
      loadThresholdMonitorV110(),
      loadKellyMonitorV110(),
      loadPerformanceBreakdownV110()
    ]);
  } catch (e) {
    console.error('Intraday UI v5.110 init error:', e);
  }
}

// 自动刷新 (每30秒)
function startIntradayAutoRefreshV110() {
  initIntradayUIV110(); // 立即执行
  setInterval(initIntradayUIV110, 30000);
}

// 页面加载时初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startIntradayAutoRefreshV110);
} else {
  startIntradayAutoRefreshV110();
}

// 导出全局函数
window.initIntradayUIV110 = initIntradayUIV110;
