/**
 * UI Optimization v5.159 - Intraday Dashboard & Real-time Sentiment
 * 盤中優化②: UI體驗改進 (11:30 Intraday Focus)
 * 
 * 改進重點:
 * ① 實時情緒指數仪表盤 (分钟级更新)
 * ② 分鐘級收益曲線 (盤中實時K線)
 * ③ 策略信號分布熱圖 (即時信號強度)
 * ④ 持倉風險等級動態顯示
 * ⑤ 交易執行效率儀表 (成交速度/滑點分析)
 */

(function(global) {
  'use strict';

  const V5_159_Config = {
    refreshInterval: 30000,      // 30s update (盤中11:30 主動刷新)
    sentimentRefresh: 60000,      // 1min sentiment
    chartUpdateThrottle: 5000,    // 5s chart
    maxChartPoints: 240,          // 4小時分鐘級 (240 points)
  };

  // ========== 1️⃣ 實時情緒動態面板 ==========
  function initRealTimeSentimentPanel() {
    const wrap = document.getElementById('sentimentDynamicsWrap');
    if (!wrap) return;

    // 擴展面板：添加實時情緒曲線
    const sentimentChart = document.createElement('div');
    sentimentChart.id = 'sentimentTrendChart';
    sentimentChart.style.cssText = `
      height: 200px;
      margin-top: 12px;
      background: var(--hover);
      border-radius: 8px;
      padding: 12px;
      position: relative;
    `;
    
    // 簡易ASCII迷你圖表
    const chartCanvas = document.createElement('canvas');
    chartCanvas.id = 'sentimentCanvas';
    chartCanvas.width = 350;
    chartCanvas.height = 120;
    chartCanvas.style.cssText = 'max-width:100%; height:auto;';
    sentimentChart.appendChild(chartCanvas);

    wrap.appendChild(sentimentChart);

    // 初始化情緒曲線數據
    window._sentimentHistory = [];
    drawSentimentTrend();
  }

  function updateRealTimeSentiment(sentimentData) {
    const { score = 50, label = '中性' } = sentimentData;
    
    // 記錄歷史
    const now = new Date().toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' });
    window._sentimentHistory = window._sentimentHistory || [];
    window._sentimentHistory.push({ time: now, score, timestamp: Date.now() });
    
    // 保留最多240個數據點 (4小時)
    if (window._sentimentHistory.length > 240) {
      window._sentimentHistory.shift();
    }

    // 更新面板顯示
    const scoreEl = document.getElementById('sentimentScore');
    const labelEl = document.getElementById('sentimentLabel');
    if (scoreEl) scoreEl.textContent = score;
    if (labelEl) {
      labelEl.textContent = label;
      labelEl.style.color = score > 70 ? '#e63946' : score > 40 ? '#6c757d' : '#2ec4b6';
    }

    // 動態參數提示
    updateEmotionAdjustParams(score);

    // 更新圖表
    if (window._sentimentHistory.length % 2 === 0) {
      drawSentimentTrend();
    }
  }

  function drawSentimentTrend() {
    const canvas = document.getElementById('sentimentCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const data = window._sentimentHistory || [];
    if (data.length === 0) return;

    const padding = 30;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    // 清空
    ctx.fillStyle = 'var(--hover)';
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 繪製背景網格
    ctx.strokeStyle = 'rgba(200,200,200,0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding + (height / 5) * i;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(canvas.width - padding, y);
      ctx.stroke();
    }

    // 繪製指標線
    ctx.strokeStyle = 'rgba(100, 150, 200, 0.3)';
    ctx.lineWidth = 1;
    [25, 50, 75].forEach(threshold => {
      const y = padding + height - (height * threshold / 100);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(canvas.width - padding, y);
      ctx.stroke();
      
      ctx.fillStyle = 'rgba(150, 150, 150, 0.5)';
      ctx.font = '10px sans-serif';
      ctx.fillText(threshold, 5, y - 2);
    });

    // 繪製數據曲線
    if (data.length > 1) {
      ctx.strokeStyle = '#4361ee';
      ctx.lineWidth = 2;
      ctx.beginPath();

      data.forEach((point, idx) => {
        const x = padding + (width / (data.length - 1)) * idx;
        const y = padding + height - (height * point.score / 100);
        
        if (idx === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();

      // 繪製數據點
      data.forEach((point, idx) => {
        const x = padding + (width / (data.length - 1)) * idx;
        const y = padding + height - (height * point.score / 100);
        
        ctx.fillStyle = point.score > 70 ? '#e63946' : point.score > 40 ? '#6c757d' : '#2ec4b6';
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // 繪製最新點提示
    if (data.length > 0) {
      const latest = data[data.length - 1];
      const x = canvas.width - padding - 5;
      const y = padding + height - (height * latest.score / 100);
      
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(latest.score, x - 12, y - 8);
    }
  }

  function updateEmotionAdjustParams(score) {
    let macdAdj = 0, rsiAdj = 0, mode = '平衡';
    
    if (score > 92) {
      macdAdj = 15; rsiAdj = -15; mode = '🔴 極度貪婪';
    } else if (score > 85) {
      macdAdj = 8; rsiAdj = -8; mode = '🟥 貪婪';
    } else if (score >= 40) {
      macdAdj = 0; rsiAdj = 0; mode = '🟨 中性';
    } else if (score >= 25) {
      macdAdj = -5; rsiAdj = 8; mode = '🟦 恐慌';
    } else {
      macdAdj = -15; rsiAdj = 25; mode = '🔵 極度恐慌';
    }

    const paramsEl = document.getElementById('emotionAdjustParams');
    if (paramsEl) {
      paramsEl.innerHTML = `
        <div>模式: ${mode}</div>
        <div>MACD: ${macdAdj > 0 ? '+' : ''}${macdAdj}%</div>
        <div>RSI: ${rsiAdj > 0 ? '+' : ''}${rsiAdj}%</div>
      `;
    }
  }

  // ========== 2️⃣ 分鐘級收益曲線 ==========
  function initIntradayReturnsChart() {
    const wrap = document.createElement('div');
    wrap.id = 'intradayReturnsWrap';
    wrap.style.cssText = `
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 24px;
    `;
    
    wrap.innerHTML = `
      <h3 style="font-size:14px;color:var(--sub);margin-bottom:16px;display:flex;align-items:center;gap:8px">
        📈 盤中收益走勢 (1分鐘級)
      </h3>
      <div style="display:grid;grid-template-columns:1fr auto;gap:12px;margin-bottom:12px">
        <div id="intradayStatsRow" style="display:flex;gap:24px;font-size:12px"></div>
        <div style="text-align:right;font-size:11px;color:var(--sub)">
          <div>最後更新: <span id="intradayLastUpdate">--:--</span></div>
        </div>
      </div>
      <canvas id="intradayReturnsCanvas" width="700" height="180" style="max-width:100%;height:auto;"></canvas>
    `;

    const dashboard = document.getElementById('panel-dashboard');
    if (dashboard && dashboard.firstChild) {
      dashboard.insertBefore(wrap, dashboard.firstChild.nextSibling);
    }

    window._intradayReturnsHistory = [];
    startIntradayChartUpdate();
  }

  function startIntradayChartUpdate() {
    // 模擬分鐘級數據更新 (實際應從API獲取)
    setInterval(() => {
      fetchIntradayReturns();
    }, V5_159_Config.chartUpdateThrottle);
  }

  function fetchIntradayReturns() {
    // 調用API獲取當日快照
    fetch('/api/dashboard')
      .then(r => r.json())
      .then(data => {
        const { today_pnl, total_return_pct, account } = data;
        
        window._intradayReturnsHistory = window._intradayReturnsHistory || [];
        window._intradayReturnsHistory.push({
          time: new Date(),
          pnl: today_pnl,
          returnPct: total_return_pct,
          capital: account.total_value
        });

        // 保留4小時內的數據
        const cutoff = Date.now() - 4 * 3600000;
        window._intradayReturnsHistory = window._intradayReturnsHistory.filter(
          p => new Date(p.time).getTime() > cutoff
        );

        if (window._intradayReturnsHistory.length > V5_159_Config.maxChartPoints) {
          window._intradayReturnsHistory.shift();
        }

        updateIntradayChart();
      })
      .catch(err => console.error('[v5.159] fetchIntradayReturns error:', err));
  }

  function updateIntradayChart() {
    const data = window._intradayReturnsHistory || [];
    if (data.length === 0) return;

    // 更新統計
    const latest = data[data.length - 1];
    const earliest = data[0];
    
    const statsRow = document.getElementById('intradayStatsRow');
    if (statsRow && latest) {
      const dayChange = ((latest.returnPct - (earliest.returnPct || 0)) * 100).toFixed(2);
      statsRow.innerHTML = `
        <div>
          <div style="font-size:11px;color:var(--sub)">今日收益</div>
          <div style="font-size:16px;font-weight:600;color:${latest.pnl >= 0 ? '#e63946' : '#2ec4b6'}">${latest.pnl >= 0 ? '+' : ''}${latest.pnl.toFixed(0)}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--sub)">盤中漲幅</div>
          <div style="font-size:16px;font-weight:600;color:${dayChange >= 0 ? '#e63946' : '#2ec4b6'}">${dayChange >= 0 ? '+' : ''}${dayChange}%</div>
        </div>
      `;
    }

    // 更新時間戳
    const lastUpdateEl = document.getElementById('intradayLastUpdate');
    if (lastUpdateEl) {
      lastUpdateEl.textContent = new Date().toLocaleTimeString('zh-CN', { 
        hour12: false, hour: '2-digit', minute: '2-digit' 
      });
    }

    drawIntradayChart(data);
  }

  function drawIntradayChart(data) {
    const canvas = document.getElementById('intradayReturnsCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const padding = 40;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (data.length < 2) return;

    // 計算範圍
    const pnls = data.map(p => p.pnl);
    const minPnl = Math.min(...pnls);
    const maxPnl = Math.max(...pnls, 0);
    const range = Math.max(Math.abs(minPnl), Math.abs(maxPnl), 1000);

    // 繪製網格
    ctx.strokeStyle = 'rgba(200,200,200,0.15)';
    ctx.lineWidth = 1;
    ctx.font = '11px sans-serif';
    ctx.fillStyle = '#999';
    
    for (let i = 0; i <= 4; i++) {
      const y = padding + (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(canvas.width - padding, y);
      ctx.stroke();
      
      const val = (2 - i) * range / 2;
      ctx.textAlign = 'right';
      ctx.fillText((val > 0 ? '+' : '') + val.toFixed(0), padding - 8, y + 4);
    }

    // 繪製零線
    const zeroY = padding + height / 2;
    ctx.strokeStyle = 'rgba(150, 150, 150, 0.5)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    ctx.lineTo(canvas.width - padding, zeroY);
    ctx.stroke();

    // 繪製收益曲線
    ctx.strokeStyle = '#4361ee';
    ctx.lineWidth = 2.5;
    ctx.beginPath();

    data.forEach((point, idx) => {
      const x = padding + (width / (data.length - 1)) * idx;
      const normalizedPnl = point.pnl / range;
      const y = zeroY - height * normalizedPnl / 2;

      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    // 繪製填充
    ctx.fillStyle = 'rgba(67, 97, 238, 0.1)';
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    data.forEach((point, idx) => {
      const x = padding + (width / (data.length - 1)) * idx;
      const normalizedPnl = point.pnl / range;
      const y = zeroY - height * normalizedPnl / 2;
      ctx.lineTo(x, y);
    });
    ctx.lineTo(padding + width, zeroY);
    ctx.fill();

    // 繪製時間標籤
    ctx.fillStyle = '#999';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    [0, Math.floor(data.length / 2), data.length - 1].forEach(idx => {
      const point = data[idx];
      const x = padding + (width / (data.length - 1)) * idx;
      const timeStr = point.time.toLocaleTimeString('zh-CN', { 
        hour12: false, hour: '2-digit', minute: '2-digit' 
      });
      ctx.fillText(timeStr, x, canvas.height - 8);
    });
  }

  // ========== 3️⃣ 持倉風險等級動態 ==========
  function initPositionRiskDynamic() {
    // 在持倉表中添加實時風險指標
    const observer = new MutationObserver(() => {
      updatePositionRiskIndicators();
    });

    const posTable = document.querySelector('table[id*="pos"]');
    if (posTable) {
      observer.observe(posTable, { childList: true, subtree: true });
    }
  }

  function updatePositionRiskIndicators() {
    const rows = document.querySelectorAll('tr[data-symbol]');
    rows.forEach(row => {
      const pnlPctEl = row.querySelector('[data-metric="pnl_pct"]');
      if (!pnlPctEl) return;

      const pnlPct = parseFloat(pnlPctEl.textContent);
      let riskLevel = '🟢 低';
      let riskColor = '#2ec4b6';

      if (pnlPct < -10) {
        riskLevel = '🔴 極危';
        riskColor = '#e63946';
      } else if (pnlPct < -5) {
        riskLevel = '🟠 高';
        riskColor = '#ff9500';
      } else if (pnlPct < -2) {
        riskLevel = '🟡 中';
        riskColor = '#ffc107';
      }

      const riskEl = row.querySelector('[data-metric="risk_level"]');
      if (riskEl) {
        riskEl.innerHTML = `<span style="color:${riskColor};font-weight:600">${riskLevel}</span>`;
      }
    });
  }

  // ========== 4️⃣ 策略信號分布熱圖 ==========
  function initSignalHeatmap() {
    const wrap = document.createElement('div');
    wrap.id = 'signalHeatmapWrap';
    wrap.style.cssText = `
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 24px;
    `;
    
    wrap.innerHTML = `
      <h3 style="font-size:14px;color:var(--sub);margin-bottom:12px;display:flex;align-items:center;gap:8px">
        🔥 策略信號熱圖 (盤中實時)
      </h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;font-size:11px">
        <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
          <div style="color:var(--sub);margin-bottom:4px">MACD買入</div>
          <div style="font-size:20px;font-weight:700;color:#e63946" id="signalMacdBuy">0</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">信號強度: <span id="signalMacdBuyStrength">--</span></div>
        </div>
        <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
          <div style="color:var(--sub);margin-bottom:4px">RSI超賣</div>
          <div style="font-size:20px;font-weight:700;color:#2ec4b6" id="signalRsiOversold">0</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">信號強度: <span id="signalRsiOversoldStrength">--</span></div>
        </div>
        <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
          <div style="color:var(--sub);margin-bottom:4px">止損觸發</div>
          <div style="font-size:20px;font-weight:700;color:#ff9500" id="signalStopLoss">0</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">觸發率: <span id="signalStopLossRate">--</span></div>
        </div>
        <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
          <div style="color:var(--sub);margin-bottom:4px">情緒極值</div>
          <div style="font-size:20px;font-weight:700;color:#8b5cf6" id="signalSentimentExtreme">0</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">信號强度: <span id="signalSentimentExtremStrength">--</span></div>
        </div>
      </div>
    `;

    const dashboard = document.getElementById('panel-dashboard');
    if (dashboard) {
      dashboard.appendChild(wrap);
    }
  }

  function updateSignalHeatmap(signals) {
    const { 
      macdBuy = 0, macdBuyStrength = 0,
      rsiOversold = 0, rsiOversoldStrength = 0,
      stopLoss = 0, stopLossRate = 0,
      sentimentExtreme = 0, sentimentExtremeStrength = 0
    } = signals;

    document.getElementById('signalMacdBuy').textContent = macdBuy;
    document.getElementById('signalMacdBuyStrength').textContent = (macdBuyStrength * 100).toFixed(0) + '%';
    
    document.getElementById('signalRsiOversold').textContent = rsiOversold;
    document.getElementById('signalRsiOversoldStrength').textContent = (rsiOversoldStrength * 100).toFixed(0) + '%';
    
    document.getElementById('signalStopLoss').textContent = stopLoss;
    document.getElementById('signalStopLossRate').textContent = (stopLossRate * 100).toFixed(1) + '%';
    
    document.getElementById('signalSentimentExtreme').textContent = sentimentExtreme;
    document.getElementById('signalSentimentExtremStrength').textContent = (sentimentExtremeStrength * 100).toFixed(0) + '%';
  }

  // ========== 5️⃣ 交易執行效率儀表 ==========
  function initExecutionMetrics() {
    const wrap = document.createElement('div');
    wrap.id = 'executionMetricsWrap';
    wrap.style.cssText = `
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px;
      margin-bottom: 24px;
    `;
    
    wrap.innerHTML = `
      <h3 style="font-size:14px;color:var(--sub);margin-bottom:12px;display:flex;align-items:center;gap:8px">
        ⚡ 交易執行效率
      </h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;font-size:12px">
        <div style="padding:12px;background:var(--hover);border-radius:8px">
          <div style="color:var(--sub);margin-bottom:6px">⏱️ 平均成交速度</div>
          <div style="font-size:18px;font-weight:700" id="avgFillSpeed">0.0ms</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">目標: <50ms</div>
        </div>
        <div style="padding:12px;background:var(--hover);border-radius:8px">
          <div style="color:var(--sub);margin-bottom:6px">📊 平均滑點</div>
          <div style="font-size:18px;font-weight:700" id="avgSlippage">0.0bp</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">目標: <5bp</div>
        </div>
        <div style="padding:12px;background:var(--hover);border-radius:8px">
          <div style="color:var(--sub);margin-bottom:6px">✅ 成交率</div>
          <div style="font-size:18px;font-weight:700;color:#2ec4b6" id="fillRate">99.5%</div>
          <div style="color:var(--sub);font-size:10px;margin-top:4px">盤中: 當前會話</div>
        </div>
      </div>
    `;

    const dashboard = document.getElementById('panel-dashboard');
    if (dashboard) {
      dashboard.appendChild(wrap);
    }
  }

  function updateExecutionMetrics(metrics) {
    const { avgFillSpeed = 0, avgSlippage = 0, fillRate = 99.5 } = metrics;
    
    document.getElementById('avgFillSpeed').textContent = avgFillSpeed.toFixed(1) + 'ms';
    document.getElementById('avgSlippage').textContent = avgSlippage.toFixed(1) + 'bp';
    document.getElementById('fillRate').textContent = fillRate.toFixed(1) + '%';
  }

  // ========== 初始化 & 定期更新 ==========
  function initV5_159() {
    console.log('[v5.159] Initializing Intraday UI Optimization');

    initRealTimeSentimentPanel();
    initIntradayReturnsChart();
    initPositionRiskDynamic();
    initSignalHeatmap();
    initExecutionMetrics();

    // 定期刷新情緒
    setInterval(() => {
      fetch('/api/dashboard')
        .then(r => r.json())
        .then(data => {
          updateRealTimeSentiment(data.sentiment);
        })
        .catch(err => console.error('[v5.159] sentiment fetch error:', err));
    }, V5_159_Config.sentimentRefresh);

    // 定期刷新信號熱圖
    setInterval(() => {
      fetch('/api/intraday-signals')
        .then(r => r.json())
        .then(data => {
          updateSignalHeatmap(data);
        })
        .catch(() => {});
    }, 60000);

    console.log('[v5.159] Initialization complete');
  }

  // 在DOMContentLoaded時啟動
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initV5_159);
  } else {
    initV5_159();
  }

  // 暴露全局API
  global.V5_159 = {
    updateRealTimeSentiment,
    updateSignalHeatmap,
    updateExecutionMetrics,
    updateIntradayChart,
  };

})(window);
