// v5.107 熱力圖UI優化 (盤前03:30)
// 功能: 多維熱力圖展示 + 即時數據聚合

(function() {
  'use strict';

  /**
   * 構建熱力圖HTML (用於情感/勝率/持倉)
   */
  function renderHeatmapHTML(data, type = 'sentiment') {
    if (!data || !data.heatmap) return '<div class="chart-box" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--sub);">暫無數據</div>';
    
    const { heatmap, distribution, current_score, current_level, trend } = data;
    
    let html = `<div style="margin-bottom: 20px;">`;
    
    // 頂部信息
    html += `<div style="display: grid; grid-template-columns: auto 1fr auto; gap: 16px; margin-bottom: 16px; align-items: center;">`;
    html += `<div style="font-size: 28px; font-weight: 700; color: var(--accent);">${current_score || 0}</div>`;
    html += `<div>`;
    html += `<div style="font-size: 12px; color: var(--sub);">當前評級</div>`;
    html += `<div style="font-size: 14px; font-weight: 600;">${current_level || '中性'}</div>`;
    html += `<div style="font-size: 11px; color: var(--sub); margin-top: 4px;">趨勢: ${trend || '平穩'}</div>`;
    html += `</div>`;
    html += `<div style="text-align: right;">`;
    for (const [label, pct] of Object.entries(distribution || {})) {
      if (pct > 0) {
        html += `<div style="font-size: 11px; color: var(--sub);">${label}: <strong style="color: var(--accent);">${pct}%</strong></div>`;
      }
    }
    html += `</div></div>`;
    
    // 熱力圖格子
    html += `<div class="heatmap-grid" style="max-width: 100%; margin-bottom: 12px;">`;
    heatmap.forEach(cell => {
      const colorLevel = cell.color_level || 0;
      const colors = [
        'var(--border)',     // 0
        '#ffc4c4',           // 1 - 紅色 (恐慌)
        '#ffd9a3',           // 2 - 橙色 (謹慎)
        '#e8f5e9',           // 3 - 綠色 (中性)
        '#b3e5fc',           // 4 - 藍色 (貪婪)
        '#81c784'            // 5 - 深綠 (極貪婪)
      ];
      const bgColor = colors[Math.min(colorLevel, 5)];
      const dateLabel = cell.date ? cell.date.split('-')[2] : '?';
      const tooltipText = `${cell.date}: ${cell.label} (${cell.score})`;
      
      html += `<div class="heatmap-cell" style="background: ${bgColor}; border: 1px solid var(--border);" title="${tooltipText}">`;
      html += `<div class="day">${dateLabel}</div>`;
      html += `<div class="ret">${cell.score}</div>`;
      html += `</div>`;
    });
    html += `</div>`;
    html += `</div>`;
    
    return html;
  }

  /**
   * 渲染勝率熱力圖
   */
  function renderWinrateHeatmapHTML(data) {
    if (!data) return '<div style="color: var(--sub); text-align: center; padding: 20px;">暫無數據</div>';
    
    const { strategies = {}, weekly = [], overall_winrate = 0 } = data;
    
    let html = `<div>`;
    
    // 整體勝率
    html += `<div style="display: grid; grid-template-columns: 1fr auto; gap: 16px; margin-bottom: 16px; align-items: center;">`;
    html += `<div>`;
    html += `<div style="font-size: 12px; color: var(--sub);">整體勝率</div>`;
    html += `<div style="font-size: 24px; font-weight: 700; color: var(--accent);">${overall_winrate.toFixed(1)}%</div>`;
    html += `</div>`;
    html += `<div style="width: 100px; height: 100px; border-radius: 50%; background: conic-gradient(var(--accent) 0deg ${overall_winrate * 3.6}deg, var(--border) ${overall_winrate * 3.6}deg); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600;">${overall_winrate.toFixed(0)}%</div>`;
    html += `</div>`;
    
    // 週期性勝率
    if (weekly.length > 0) {
      html += `<div style="font-size: 12px; color: var(--sub); margin-bottom: 8px; font-weight: 600;">週期勝率</div>`;
      html += `<div style="display: grid; grid-template-columns: repeat(${weekly.length}, 1fr); gap: 8px;">`;
      weekly.forEach(week => {
        const colorLevel = week.color_level || 0;
        const colors = ['#f5f5f5', '#ffc4c4', '#ffd9a3', '#e8f5e9', '#b3e5fc', '#81c784'];
        const bgColor = colors[Math.min(colorLevel, 5)];
        html += `<div style="background: ${bgColor}; border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; font-size: 11px;">`;
        html += `<div style="font-weight: 600;">${week.week}</div>`;
        html += `<div style="font-size: 13px; font-weight: 700; color: var(--text);">${week.winrate.toFixed(1)}%</div>`;
        html += `</div>`;
      });
      html += `</div>`;
    }
    
    html += `</div>`;
    
    return html;
  }

  /**
   * 渲染持倉熱力圖
   */
  function renderPositionHeatmapHTML(data) {
    if (!data) return '<div style="color: var(--sub); text-align: center; padding: 20px;">暫無數據</div>';
    
    const { stocks = {}, pnl_distribution = {}, concentration = 0, total_positions = 0 } = data;
    const stockArray = Object.entries(stocks).map(([symbol, info]) => ({
      symbol,
      ...info
    })).sort((a, b) => b.percentage - a.percentage);
    
    let html = `<div>`;
    
    // 頂部統計
    html += `<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 16px;">`;
    html += `<div style="padding: 12px; background: var(--hover); border-radius: 6px; text-align: center;">`;
    html += `<div style="font-size: 11px; color: var(--sub);">持倉數</div>`;
    html += `<div style="font-size: 20px; font-weight: 700; color: var(--accent);">${total_positions}</div>`;
    html += `</div>`;
    html += `<div style="padding: 12px; background: var(--hover); border-radius: 6px; text-align: center;">`;
    html += `<div style="font-size: 11px; color: var(--sub);">上漲占比</div>`;
    html += `<div style="font-size: 20px; font-weight: 700; color: #4ade80;">${(pnl_distribution.up_ratio || 0).toFixed(1)}%</div>`;
    html += `<div style="font-size: 10px; color: var(--sub); margin-top: 4px;">↑${pnl_distribution.up || 0} ↓${pnl_distribution.down || 0}</div>`;
    html += `</div>`;
    html += `<div style="padding: 12px; background: var(--hover); border-radius: 6px; text-align: center;">`;
    html += `<div style="font-size: 11px; color: var(--sub);">集中度</div>`;
    html += `<div style="font-size: 20px; font-weight: 700; color: ${concentration > 70 ? '#f87171' : concentration > 50 ? '#fb923c' : '#4ade80'};">${concentration.toFixed(1)}%</div>`;
    html += `</div>`;
    html += `</div>`;
    
    // 股票熱力分佈
    if (stockArray.length > 0) {
      html += `<div style="font-size: 12px; color: var(--sub); margin-bottom: 8px; font-weight: 600;">持倉分佈</div>`;
      html += `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px;">`;
      stockArray.forEach(stock => {
        const colorLevel = stock.color_level || 0;
        const colors = ['#f5f5f5', '#ffc4c4', '#ffd9a3', '#e8f5e9', '#b3e5fc', '#81c784'];
        const bgColor = colors[Math.min(colorLevel, 5)];
        html += `<div style="background: ${bgColor}; border: 1px solid var(--border); border-radius: 6px; padding: 10px; font-size: 11px; cursor: pointer;" title="${stock.name}">`;
        html += `<div style="font-weight: 600; font-size: 10px; color: var(--sub);">${stock.symbol}</div>`;
        html += `<div style="font-size: 13px; font-weight: 700; color: var(--text);">${stock.percentage.toFixed(1)}%</div>`;
        html += `<div style="font-size: 10px; color: var(--sub); margin-top: 2px;">${stock.shares}股</div>`;
        html += `</div>`;
      });
      html += `</div>`;
    }
    
    html += `</div>`;
    
    return html;
  }

  /**
   * 加載並顯示所有熱力圖
   */
  async function loadAndRenderHeatmaps() {
    try {
      const response = await fetch('/api/finance/dashboard-aggregate-v107');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const data = await response.json();
      const { sentiment_heatmap, winrate_heatmap, position_heatmap, timestamp } = data;
      
      // 檢查目標容器
      const sentimentPanel = document.getElementById('sentiment-heatmap-panel');
      const winratePanel = document.getElementById('winrate-heatmap-panel');
      const positionPanel = document.getElementById('position-heatmap-panel');
      
      if (sentimentPanel) {
        sentimentPanel.innerHTML = renderHeatmapHTML(sentiment_heatmap, 'sentiment');
      }
      if (winratePanel) {
        winratePanel.innerHTML = renderWinrateHeatmapHTML(winrate_heatmap);
      }
      if (positionPanel) {
        positionPanel.innerHTML = renderPositionHeatmapHTML(position_heatmap);
      }
      
      // 更新時間戳
      const lastUpdateEl = document.getElementById('lastUpdate');
      if (lastUpdateEl && timestamp) {
        const time = new Date(timestamp).toLocaleTimeString('zh-CN');
        lastUpdateEl.textContent = `更新: ${time}`;
      }
    } catch (e) {
      console.error('Heatmap error:', e);
    }
  }

  // 定期刷新 (每30秒)
  setInterval(loadAndRenderHeatmaps, 30000);

  // 立即加載
  setTimeout(loadAndRenderHeatmaps, 500);

  // 導出到全局
  window.loadAndRenderHeatmaps = loadAndRenderHeatmaps;
})();
