/**
 * v5.137 盤中優化② - UI與數據展示增強 (11:30優化)
 * 新增:
 * 1. 實時績效排序面板 (ROI/Sharpe/Drawdown/Winrate)
 * 2. 市場熱力圖儀表板 (板塊分組/情緒指標)
 * 3. 風控警告面板 (持倉集中度/虧損風險)
 */

// 初始化新的UI面板
function initPerformanceRankingV137() {
  const html = `
    <div id="panel-performance-ranking" style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="margin: 0; font-size: 14px; color: var(--sub);">📊 實時績效排序</h3>
        <div style="display: flex; gap: 6px;">
          <button onclick="updatePerformanceRanking('roi')" style="padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px;">ROI ↑↓</button>
          <button onclick="updatePerformanceRanking('sharpe')" style="padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px;">Sharpe ↑↓</button>
          <button onclick="updatePerformanceRanking('drawdown')" style="padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px;">Drawdown ↑↓</button>
          <button onclick="updatePerformanceRanking('winrate')" style="padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px;">勝率 ↑↓</button>
        </div>
      </div>
      <div id="ranking-list" style="max-height: 400px; overflow-y: auto;">
        <div style="text-align: center; color: var(--sub); padding: 20px;">⏳ 載入中...</div>
      </div>
    </div>
  `;
  return html;
}

// 獲取績效排序並渲染
async function updatePerformanceRanking(sortBy = 'roi') {
  try {
    const response = await fetch(`/api/finance/performance-ranking-v137?sort_by=${sortBy}&limit=10`);
    const data = await response.json();
    
    if (data.status !== 'OK' || !data.ranking || data.ranking.length === 0) {
      document.getElementById('ranking-list').innerHTML = '<div style="text-align: center; color: var(--sub); padding: 20px;">無持倉數據</div>';
      return;
    }
    
    let html = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">';
    html += '<thead><tr style="border-bottom: 1px solid var(--border);"><th style="text-align: left; padding: 8px; color: var(--sub);">股票</th><th style="text-align: right; padding: 8px;">ROI%</th><th style="text-align: right; padding: 8px;">Sharpe</th><th style="text-align: right; padding: 8px;">Drawdown%</th></tr></thead>';
    html += '<tbody>';
    
    data.ranking.forEach(stock => {
      const roiColor = stock.roi_pct > 0 ? 'var(--down)' : 'var(--up)';
      html += `<tr style="border-bottom: 1px solid var(--border);">
        <td style="padding: 8px;"><strong>${stock.symbol}</strong><br/><span style="color: var(--sub); font-size: 11px;">${stock.name}</span></td>
        <td style="text-align: right; padding: 8px; color: ${roiColor};">${stock.roi_pct > 0 ? '+' : ''}${stock.roi_pct}%</td>
        <td style="text-align: right; padding: 8px;">${stock.sharpe_approx.toFixed(3)}</td>
        <td style="text-align: right; padding: 8px; color: ${stock.peak_drawdown_pct < 0 ? 'var(--up)' : 'var(--down)'};">${stock.peak_drawdown_pct}%</td>
      </tr>`;
    });
    
    html += '</tbody></table>';
    document.getElementById('ranking-list').innerHTML = html;
  } catch (e) {
    console.error('Performance ranking error:', e);
    document.getElementById('ranking-list').innerHTML = '<div style="text-align: center; color: red; padding: 20px;">❌ 加載失敗</div>';
  }
}

// 初始化市場熱力圖
function initMarketHeatmapV137() {
  const html = `
    <div id="panel-market-heatmap" style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="margin: 0; font-size: 14px; color: var(--sub);">🔥 市場熱力圖</h3>
        <div id="sentiment-indicator" style="display: flex; align-items: center; gap: 6px; background: var(--hover); padding: 6px 12px; border-radius: 6px; font-size: 12px;">
          <span id="sentiment-emoji">😐</span>
          <span id="sentiment-text">中性</span>
        </div>
      </div>
      <div id="heatmap-sectors" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; max-height: 400px; overflow-y: auto;">
        <div style="text-align: center; color: var(--sub); padding: 20px; grid-column: 1 / -1;">⏳ 載入中...</div>
      </div>
    </div>
  `;
  return html;
}

// 獲取市場熱力圖並渲染
async function updateMarketHeatmap() {
  try {
    const response = await fetch('/api/finance/market-heatmap-v137?timeframe=daily&include_sentiment=true');
    const data = await response.json();
    
    if (data.status !== 'OK' || !data.sectors) {
      document.getElementById('heatmap-sectors').innerHTML = '<div style="text-align: center; color: var(--sub); padding: 20px; grid-column: 1 / -1;">無數據</div>';
      return;
    }
    
    // 更新情緒指標
    if (data.sentiment) {
      document.getElementById('sentiment-emoji').textContent = data.sentiment.emoji;
      document.getElementById('sentiment-text').textContent = data.sentiment.level + ' (' + data.sentiment.score.toFixed(1) + '%)';
    }
    
    // 渲染板塊卡片
    let html = '';
    data.sectors.forEach(sector => {
      const heatColor = sector.heat_level === 'HOT' ? '#ff6b6b' : sector.heat_level === 'WARM' ? '#ffa500' : '#808080';
      const perfColor = sector.avg_performance_pct > 0 ? 'var(--down)' : 'var(--up)';
      
      html += `
        <div style="background: ${heatColor}15; border: 2px solid ${heatColor}; border-radius: 8px; padding: 12px; text-align: center; cursor: pointer; transition: all 0.2s;">
          <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">${sector.sector}</div>
          <div style="font-size: 11px; color: var(--sub); margin-bottom: 6px;">${sector.stocks_count}支股票</div>
          <div style="font-size: 16px; font-weight: 700; color: ${perfColor};">${sector.avg_performance_pct > 0 ? '+' : ''}${sector.avg_performance_pct.toFixed(2)}%</div>
          <div style="font-size: 10px; color: var(--sub); margin-top: 4px;">${sector.heat_level}</div>
        </div>
      `;
    });
    
    document.getElementById('heatmap-sectors').innerHTML = html;
  } catch (e) {
    console.error('Market heatmap error:', e);
    document.getElementById('heatmap-sectors').innerHTML = '<div style="text-align: center; color: red; padding: 20px; grid-column: 1 / -1;">❌ 加載失敗</div>';
  }
}

// 初始化風控面板
function initRiskMetricsV137() {
  const html = `
    <div id="panel-risk-metrics" style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; margin-bottom: 16px;">
      <h3 style="margin: 0 0 16px 0; font-size: 14px; color: var(--sub);">⚠️ 盤中風控指標</h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px;" id="risk-metrics-grid">
        <div style="text-align: center; color: var(--sub); padding: 20px; grid-column: 1 / -1;">⏳ 載入中...</div>
      </div>
    </div>
  `;
  return html;
}

// 獲取風控指標並渲染
async function updateRiskMetrics() {
  try {
    const response = await fetch('/api/finance/intraday-risk-v137');
    const data = await response.json();
    
    if (data.status === 'ERROR') {
      document.getElementById('risk-metrics-grid').innerHTML = '<div style="text-align: center; color: var(--sub); padding: 20px; grid-column: 1 / -1;">無持倉</div>';
      return;
    }
    
    const riskColor = data.concentration_risk === 'HIGH' ? 'var(--up)' : data.concentration_risk === 'MEDIUM' ? '#ffa500' : 'var(--down)';
    
    let html = `
      <div style="background: var(--hover); border-radius: 8px; padding: 12px; text-align: center;">
        <div style="font-size: 11px; color: var(--sub); margin-bottom: 4px;">持倉數</div>
        <div style="font-size: 18px; font-weight: 700;">${data.position_count}</div>
      </div>
      <div style="background: var(--hover); border-radius: 8px; padding: 12px; text-align: center;">
        <div style="font-size: 11px; color: var(--sub); margin-bottom: 4px;">虧損持倉</div>
        <div style="font-size: 18px; font-weight: 700; color: ${data.losing_positions > 0 ? 'var(--up)' : 'var(--down)'};">${data.losing_positions}</div>
      </div>
      <div style="background: var(--hover); border-radius: 8px; padding: 12px; text-align: center;">
        <div style="font-size: 11px; color: var(--sub); margin-bottom: 4px;">平均回撤</div>
        <div style="font-size: 18px; font-weight: 700; color: var(--up);">${data.avg_drawdown_pct.toFixed(2)}%</div>
      </div>
      <div style="background: var(--hover); border-radius: 8px; padding: 12px; text-align: center;">
        <div style="font-size: 11px; color: var(--sub); margin-bottom: 4px;">集中度風險</div>
        <div style="font-size: 18px; font-weight: 700; color: ${riskColor};">${data.concentration_risk}</div>
      </div>
    `;
    
    document.getElementById('risk-metrics-grid').innerHTML = html;
  } catch (e) {
    console.error('Risk metrics error:', e);
    document.getElementById('risk-metrics-grid').innerHTML = '<div style="text-align: center; color: red; padding: 20px; grid-column: 1 / -1;">❌ 加載失敗</div>';
  }
}

// 初始化所有面板
function initV137Optimization() {
  // 在UI中查找合適的位置插入新面板
  const tabPanels = document.querySelectorAll('[role="tabpanel"]');
  if (tabPanels.length > 0) {
    const mainPanel = tabPanels[0];
    
    // 插入新面板
    const container = document.createElement('div');
    container.id = 'v137-optimization-container';
    container.innerHTML = initPerformanceRankingV137() + initMarketHeatmapV137() + initRiskMetricsV137();
    mainPanel.insertBefore(container, mainPanel.firstChild);
    
    // 加載數據
    updatePerformanceRanking('roi');
    updateMarketHeatmap();
    updateRiskMetrics();
    
    // 定期更新 (每30秒)
    setInterval(() => {
      updatePerformanceRanking('roi');
      updateMarketHeatmap();
      updateRiskMetrics();
    }, 30000);
  }
}

// 等待DOM加載後初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initV137Optimization);
} else {
  initV137Optimization();
}
