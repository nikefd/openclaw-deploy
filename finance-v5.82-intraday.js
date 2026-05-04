// ==================== v5.82 盤中UI增強 - JavaScript邏輯 ====================
// 此脚本处理新的情绪动态面板、绩效统计卡和止损黑名单

async function loadSentimentDynamics() {
  try {
    const data = await fetch('/api/finance/sentiment-dynamics').then(r => r.json());
    if (!data || data.error) {
      document.getElementById('sentimentScore').textContent = '--';
      document.getElementById('sentimentLabel').textContent = 'API错误';
      return;
    }
    
    // 更新情绪评分
    document.getElementById('sentimentScore').textContent = data.current_score || '--';
    
    const score = data.current_score || 50;
    let label = '中性';
    if (score >= 75) label = '極度貪心 ⚠️';
    else if (score >= 65) label = '樂觀 📈';
    else if (score <= 25) label = '極度恐慌 🔴';
    else if (score <= 40) label = '謹慎 ⚠️';
    else if (score <= 60) label = '中性';
    
    document.getElementById('sentimentLabel').textContent = label;
    
    // 更新調整參數
    const params = data.adjust_params || {};
    const paramStr = Object.entries(params)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\\n');
    document.getElementById('emotionAdjustParams').textContent = paramStr || '--';
    
    // 更新執行狀態
    document.getElementById('entrySignals').textContent = (data.today_entries || 0) + ' 筆';
    document.getElementById('stopLossSignals').textContent = (data.today_stop_losses || 0) + ' 筆';
    
    // 顔色編碼
    const scoreEl = document.getElementById('sentimentScore');
    if (score >= 75) {
      scoreEl.style.color = '#e63946'; // 紅色 = 過度樂觀
    } else if (score >= 65) {
      scoreEl.style.color = '#2ec4b6'; // 綠色 = 樂觀
    } else if (score <= 25) {
      scoreEl.style.color = '#e63946'; // 紅色 = 恐慌
    } else if (score <= 40) {
      scoreEl.style.color = '#f4a261'; // 橙色 = 謹慎
    }
  } catch (e) {
    console.error('Sentiment dynamics error:', e);
  }
}

async function loadPerformanceScorecard() {
  try {
    const data = await fetch('/api/finance/performance-stats').then(r => r.json());
    if (!data || data.error) return;
    
    // 績效卡片
    const cards = [
      { label: 'Sharpe倍數', value: (data.sharpe_ratio || 0).toFixed(2), color: data.sharpe_ratio >= 2 ? 'var(--up)' : 'var(--text)' },
      { label: 'Kelly容差', value: (data.kelly_percentage || 0).toFixed(2) + '%', color: 'var(--text)' },
      { label: '入場勝率', value: (data.win_rate || 0).toFixed(1) + '%', color: data.win_rate >= 55 ? 'var(--up)' : data.win_rate >= 45 ? 'var(--text)' : 'var(--down)' }
    ];
    
    const grid = document.getElementById('performanceCardsGrid');
    if (grid) {
      grid.innerHTML = cards.map(c => `
        <div style=\"padding:12px;background:var(--hover);border-radius:8px;text-align:center\">
          <div style=\"font-size:11px;color:var(--sub);margin-bottom:4px\">${c.label}</div>
          <div style=\"font-size:24px;font-weight:700;color:${c.color}\">${c.value}</div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.error('Performance scorecard error:', e);
  }
}

async function loadBacktestComparison() {
  try {
    const data = await fetch('/api/finance/backtest-comparison-v82').then(r => r.json());
    if (!data || data.error) return;
    
    const current = data.current || {};
    const previous = data.previous || {};
    
    const grid = document.getElementById('backtestComparisonGrid');
    if (grid) {
      const returnDiff = (data.improvements?.return_diff || 0).toFixed(2);
      const returnDiffColor = returnDiff >= 0 ? 'color:var(--up)' : 'color:var(--down)';
      
      grid.innerHTML = `
        <div>
          <div style=\"font-size:11px;color:var(--sub);margin-bottom:4px\">總收益率</div>
          <div style=\"font-size:16px;font-weight:700\">${(current.total_return_pct || 0).toFixed(2)}%</div>
          <div style=\"font-size:11px;${returnDiffColor};margin-top:2px\">v5.81: ${(previous.total_return_pct || 0).toFixed(2)}%</div>
        </div>
        <div>
          <div style=\"font-size:11px;color:var(--sub);margin-bottom:4px\">勝率對比</div>
          <div style=\"font-size:16px;font-weight:700\">${(current.win_rate || 0).toFixed(1)}%</div>
          <div style=\"font-size:11px;color:var(--sub);margin-top:2px\">v5.81: ${(previous.win_rate || 0).toFixed(1)}%</div>
        </div>
      `;
    }
  } catch (e) {
    console.error('Backtest comparison error:', e);
  }
}

async function loadStopLossBlacklist() {
  try {
    // 從交易記錄中統計近7天的止損股票
    const trades = await fetch('/api/finance/trades').then(r => r.json());
    if (!trades || !trades.trades) return;
    
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    
    const blacklist = {};
    trades.trades.forEach(t => {
      const tradeDate = new Date(t.trade_date);
      if (tradeDate >= sevenDaysAgo && t.direction === 'SELL' && t.reason && t.reason.includes('止損')) {
        const key = `${t.symbol}|${t.name}`;
        if (!blacklist[key]) {
          blacklist[key] = { symbol: t.symbol, name: t.name, count: 0, lastDate: t.trade_date };
        }
        blacklist[key].count++;
      }
    });
    
    const grid = document.getElementById('stopLossBlacklistGrid');
    if (grid && Object.keys(blacklist).length > 0) {
      grid.innerHTML = Object.entries(blacklist)
        .sort((a, b) => b[1].count - a[1].count)
        .map(([key, item]) => `
          <div style=\"padding:8px;background:var(--hover);border-radius:6px;border-left:3px solid #e63946;text-align:center\">
            <div style=\"font-size:12px;font-weight:600\">${item.symbol}</div>
            <div style=\"font-size:10px;color:var(--sub)\">${item.name}</div>
            <div style=\"font-size:11px;color:#e63946;margin-top:4px;font-weight:600\">${item.count}次止損</div>
          </div>
        `).join('');
      
      // 統計
      const totalStops = Object.values(blacklist).reduce((sum, item) => sum + item.count, 0);
      const statsEl = document.getElementById('blacklistStats');
      if (statsEl) {
        statsEl.textContent = `近7天共${totalStops}次止損，涉及${Object.keys(blacklist).length}只股票`;
      }
    } else if (grid) {
      grid.innerHTML = '<div style=\"grid-column:1/-1;text-align:center;color:var(--sub);padding:12px\">近7天無止損記錄</div>';
    }
  } catch (e) {
    console.error('Stop loss blacklist error:', e);
  }
}

// 在加載儀錶盤時調用
function loadEnhancedPanels() {
  loadSentimentDynamics();
  loadPerformanceScorecard();
  loadBacktestComparison();
  loadStopLossBlacklist();
}

// 定時更新（11:30盤中）
setInterval(() => {
  const now = new Date();
  const hour = now.getHours();
  const min = now.getMinutes();
  // 11:30 ~ 15:00 期間每5分鐘更新一次
  if (hour === 11 || hour === 12 || hour === 13 || hour === 14) {
    loadSentimentDynamics();
  }
}, 5 * 60 * 1000); // 5分鐘

// 頁面載入時執行
if (document.readyState !== 'loading') {
  loadEnhancedPanels();
} else {
  document.addEventListener('DOMContentLoaded', loadEnhancedPanels);
}
