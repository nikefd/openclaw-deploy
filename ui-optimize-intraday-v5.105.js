/**
 * v5.105 盤中UI優化③ - 實時情緒+績效統計+信號質量
 * 新增API集成：sentiment-dynamics-v102, performance-stats-v102, signal-quality-v102
 */

async function loadSentimentDynamicsV105() {
  try {
    const res = await fetch('/api/finance/sentiment-dynamics-v102?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const scoreEl = document.getElementById('sentimentScore');
    const labelEl = document.getElementById('sentimentLabel');
    const paramsEl = document.getElementById('emotionAdjustParams');
    const entrySigEl = document.getElementById('entrySignals');
    const slSigEl = document.getElementById('stopLossSignals');

    if (scoreEl) {
      scoreEl.textContent = data.sentiment_score || '--';
      const score = data.sentiment_score || 50;
      let color = '#6c757d';
      if (score >= 80) color = '#e63946';
      else if (score >= 65) color = '#f4a261';
      else if (score >= 45) color = '#4361ee';
      else if (score >= 30) color = '#ffd166';
      else color = '#2ec4b6';
      scoreEl.style.color = color;
    }

    if (labelEl) {
      labelEl.textContent = `${data.sentiment_trend_icon || ''} ${data.sentiment_label || '中性'}`;
    }

    if (paramsEl) {
      const p = data.emotion_adjust_params || {};
      paramsEl.innerHTML = `
        <div>Kelly: <strong style="color:var(--accent)">${p.kelly_boost_multiplier || 0}x</strong></div>
        <div>現金: <strong style="color:var(--accent)">${Math.round((p.cash_activation_ratio || 0) * 100)}%</strong></div>
        <div>持倉: <strong style="color:var(--accent)">${p.max_holding_count || 0}只</strong></div>
        <div style="font-size:11px;color:var(--sub);margin-top:4px">${p.entry_intensity || '--'}</div>
      `;
    }

    if (entrySigEl) entrySigEl.textContent = data.entry_signals || 0;
    if (slSigEl) slSigEl.textContent = data.stop_loss_signals || 0;
  } catch (e) {
    console.warn('sentiment-dynamics-v102 error:', e.message);
  }
}

async function loadPerformanceStatsV105() {
  try {
    const res = await fetch('/api/finance/performance-stats-v102?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    // 策略胜率排行
    const winRateEl = document.getElementById('strategyWinRate');
    if (winRateEl) {
      const strategies = data.strategy_win_rate || [];
      winRateEl.innerHTML = strategies.map(s => `
        <div style="margin-bottom:6px">
          <div style="font-size:11px;color:var(--sub)">${s.strategy}</div>
          <div style="font-size:13px;font-weight:600">
            ${s.win_rate}% <span style="font-size:11px;color:var(--sub)">(${s.wins}/${s.total})</span>
          </div>
        </div>
      `).join('') || '<div style="color:var(--sub)">暫無</div>';
    }

    // 賽道分佈
    const sectorEl = document.getElementById('sectorDist');
    if (sectorEl) {
      const sectors = data.sector_distribution || {};
      sectorEl.innerHTML = Object.entries(sectors).map(([name, count]) => `
        <div style="padding:6px;background:var(--hover);border-radius:6px;text-align:center">
          <div style="font-size:11px;color:var(--sub)">${name}</div>
          <div style="font-size:14px;font-weight:700">${count}</div>
        </div>
      `).join('') || '<div style="color:var(--sub);grid-column:1/-1">暫無</div>';
    }

    // 入場質量評分
    const qualityEl = document.getElementById('entryQualityAvg');
    if (qualityEl) {
      const score = data.entry_quality_avg || 0;
      const color = score >= 75 ? 'var(--up)' : score >= 50 ? 'var(--accent)' : 'var(--sub)';
      qualityEl.innerHTML = `<div style="font-size:14px;font-weight:600;color:${color}">${score.toFixed(1)}/100</div>`;
    }
  } catch (e) {
    console.warn('performance-stats-v102 error:', e.message);
  }
}

async function loadSignalQualityV105() {
  try {
    const res = await fetch('/api/finance/signal-quality-v102?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    // MACD
    const macdTotalEl = document.getElementById('macdTotal');
    const macdQualityEl = document.getElementById('macdQualityAvg');
    const macdRecentEl = document.getElementById('macdRecent');

    if (macdTotalEl) macdTotalEl.textContent = data.macd?.total || 0;
    if (macdQualityEl) {
      const score = data.macd?.quality_score || 0;
      macdQualityEl.textContent = Math.round(score);
    }
    if (macdRecentEl) {
      const pnl = data.macd?.avg_pnl || 0;
      macdRecentEl.textContent = `${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%`;
    }

    // RSI
    const rsiTotalEl = document.getElementById('rsiTotal');
    const rsiQualityEl = document.getElementById('rsiQualityAvg');
    const rsiRecentEl = document.getElementById('rsiRecent');

    if (rsiTotalEl) rsiTotalEl.textContent = data.rsi?.total || 0;
    if (rsiQualityEl) {
      const score = data.rsi?.quality_score || 0;
      rsiQualityEl.textContent = Math.round(score);
    }
    if (rsiRecentEl) {
      const pnl = data.rsi?.avg_pnl || 0;
      rsiRecentEl.textContent = `${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%`;
    }

    // Combined
    const combinedEl = document.getElementById('combinedQuality');
    if (combinedEl) {
      const score = data.combined_quality || 0;
      combinedEl.textContent = Math.round(score);
    }
  } catch (e) {
    console.warn('signal-quality-v102 error:', e.message);
  }
}

async function loadIntradayPerformanceV105() {
  try {
    const res = await fetch('/api/finance/intraday-performance-v102?_t=' + Date.now());
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    // 胜率
    const wrEl = document.getElementById('perfWinRate');
    if (wrEl) wrEl.textContent = `${data.win_rate || 0}%`;

    // 平均持倉日
    const hdEl = document.getElementById('perfAvgHoldDays');
    if (hdEl) hdEl.textContent = `${data.avg_holding_days || 0}天`;

    // 最大盈利/虧損
    const maxGainEl = document.getElementById('perfMaxGain');
    const maxLossEl = document.getElementById('perfMaxLoss');

    if (maxGainEl) {
      const gain = data.max_gain || 0;
      maxGainEl.innerHTML = `¥${(gain / 100).toFixed(0)}`;
    }
    if (maxLossEl) {
      const loss = data.max_loss || 0;
      maxLossEl.innerHTML = `¥${(loss / 100).toFixed(0)}`;
    }

    // 交易統計
    const totalEl = document.getElementById('perfTotalTrades');
    const winEl = document.getElementById('perfWinTrades');
    const lossEl = document.getElementById('perfLossTrades');

    if (totalEl) totalEl.textContent = data.total_trades || 0;
    if (winEl) winEl.textContent = data.win_trades || 0;
    if (lossEl) lossEl.textContent = data.loss_trades || 0;
  } catch (e) {
    console.warn('intraday-performance-v102 error:', e.message);
  }
}

// 自動刷新（每30秒）
function startIntradayAutoRefresh() {
  const refreshInterval = 30000; // 30秒
  
  const doRefresh = () => {
    Promise.all([
      loadSentimentDynamicsV105(),
      loadPerformanceStatsV105(),
      loadSignalQualityV105(),
      loadIntradayPerformanceV105(),
    ]).catch(e => console.warn('Intraday refresh error:', e.message));
  };

  doRefresh(); // 立即執行
  setInterval(doRefresh, refreshInterval);
}

// 頁面加載時初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startIntradayAutoRefresh);
} else {
  startIntradayAutoRefresh();
}
