/**
 * v5.128 盤中UI優化② - 實時情感熱力圖 + 信號質量評分 + 入場質量看板
 * 11:30 盤中優化版本
 */

async function loadIntradayAggregateV128() {
  try {
    const resp = await fetch('/api/finance/intraday-aggregate-v128');
    const data = await resp.json();
    
    if (!data.error) {
      renderSentimentHeatmapV128(data.sentiment_heatmap || {});
      renderSignalQualityV128(data.signal_quality || {});
      renderEntryQualityV128(data.entry_quality || {});
      updateQuickMetricsV128(data.quick_metrics || {});
    }
  } catch (e) {
    console.error('loadIntradayAggregateV128 error:', e);
  }
}

function renderSentimentHeatmapV128(data) {
  const heatmap = data.heatmap || [];
  const chartBox = document.getElementById('sentimentHeatmapChart');
  
  if (!chartBox) return;
  
  chartBox.innerHTML = heatmap.map((item, idx) => {
    const bgColor = item.color || '#ffd166';
    const brightness = [
      { color: '#e63946', brightness: 'rgba(230, 57, 70, 0.7)' },
      { color: '#f4a261', brightness: 'rgba(244, 162, 97, 0.7)' },
      { color: '#ffd166', brightness: 'rgba(255, 209, 102, 0.7)' },
      { color: '#2ec4b6', brightness: 'rgba(46, 196, 182, 0.7)' }
    ].find(x => x.color === item.color) || { brightness: bgColor };
    
    return `
      <div style="
        padding:12px;
        background:${brightness.brightness};
        border:1px solid ${bgColor};
        border-radius:8px;
        text-align:center;
        cursor:pointer;
        transition:transform 0.2s;
      " onclick="this.style.transform='scale(1.05)';setTimeout(()=>this.style.transform='scale(1)',200)">
        <div style="font-size:12px;color:#fff;margin-bottom:4px;font-weight:600">${item.date}</div>
        <div style="font-size:24px;font-weight:700;color:#fff">${item.score}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.9);margin-top:4px">${item.label}</div>
        <div style="font-size:13px;margin-top:2px">${item.trend_icon}</div>
        <div style="font-size:10px;color:rgba(255,255,255,0.8);margin-top:2px">${item.trend}</div>
      </div>
    `;
  }).join('');
  
  // 更新分布統計
  const distBox = document.getElementById('sentimentDist');
  if (distBox && data.distribution) {
    distBox.innerHTML = Object.entries(data.distribution).map(([label, count]) => `
      <div style="padding:8px;background:var(--hover);border-radius:6px;text-align:center">
        <div style="font-size:11px;color:var(--sub);margin-bottom:2px">${label}</div>
        <div style="font-size:16px;font-weight:700">${count}</div>
      </div>
    `).join('');
  }
}

function renderSignalQualityV128(data) {
  // MACD質量
  const macdQualityEl = document.getElementById('macdQuality');
  if (macdQualityEl) {
    const macd = data.macd || {};
    macdQualityEl.textContent = macd.avg_strength ? Math.round(macd.avg_strength * 10) : '--';
    const macdDetail = document.getElementById('macdDetail');
    if (macdDetail) {
      macdDetail.textContent = `${macd.total || 0}筆 信號`;
    }
  }
  
  // RSI質量
  const rsiQualityEl = document.getElementById('rsiQuality');
  if (rsiQualityEl) {
    const rsi = data.rsi || {};
    rsiQualityEl.textContent = rsi.avg_strength ? Math.round(rsi.avg_strength * 10) : '--';
    const rsiDetail = document.getElementById('rsiDetail');
    if (rsiDetail) {
      rsiDetail.textContent = `${rsi.total || 0}筆 信號`;
    }
  }
  
  // 綜合評分
  const combinedEl = document.getElementById('combinedQuality');
  if (combinedEl) {
    combinedEl.textContent = Math.round(data.combined_quality || 0);
    const levelEl = document.getElementById('qualityLevel');
    if (levelEl) {
      levelEl.textContent = data.quality_level || '一般';
    }
  }
  
  // 最近信號質量
  const recentBox = document.getElementById('recentSignalsBox');
  if (recentBox) {
    const allSignals = [
      ...(data.macd?.recent || []).map(s => ({ ...s, type: 'MACD' })),
      ...(data.rsi?.recent || []).map(s => ({ ...s, type: 'RSI' }))
    ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8);
    
    recentBox.innerHTML = allSignals.length ? allSignals.map(sig => `
      <div style="padding:6px;border-bottom:1px solid rgba(0,0,0,0.1);display:flex;justify-content:space-between">
        <span style="color:var(--text)">${sig.type}</span>
        <span style="font-weight:600;color:var(--accent)">${sig.date.slice(5, 16)}</span>
        <span style="color:${sig.quality_score >= 70 ? '#e63946' : sig.quality_score >= 50 ? '#f4a261' : '#2ec4b6'};font-weight:600">
          ${sig.quality_score}分
        </span>
      </div>
    `).join('') : '<div style="color:var(--sub);text-align:center;padding:12px">暫無數據</div>';
  }
}

function renderEntryQualityV128(data) {
  const cardsBox = document.getElementById('entryQualityCards');
  if (!cardsBox) return;
  
  const stats = [
    { label: '優質 (≥80分)', value: data.distribution?.excellent || 0, color: '#e63946' },
    { label: '良好 (70-79分)', value: data.distribution?.good || 0, color: '#f4a261' },
    { label: '中等 (60-69分)', value: data.distribution?.fair || 0, color: '#ffd166' },
    { label: '較弱 (<60分)', value: data.distribution?.poor || 0, color: '#2ec4b6' },
  ];
  
  cardsBox.innerHTML = stats.map(stat => `
    <div style="
      padding:12px;
      background:rgba(${stat.color.startsWith('#e63946') ? '230,57,70' : stat.color.startsWith('#f4a261') ? '244,162,97' : stat.color.startsWith('#ffd166') ? '255,209,102' : '46,196,182'},0.1);
      border:2px solid ${stat.color};
      border-radius:8px;
      text-align:center;
    ">
      <div style="font-size:11px;color:var(--sub);margin-bottom:4px">${stat.label}</div>
      <div style="font-size:24px;font-weight:700;color:${stat.color}">${stat.value}</div>
    </div>
  `).join('');
  
  // 評分分布條形圖
  const distBox = document.getElementById('scoreDistribution');
  if (distBox && data.score_ranges) {
    const maxCount = Math.max(...Object.values(data.score_ranges));
    distBox.innerHTML = Object.entries(data.score_ranges).map(([range, count]) => {
      const width = maxCount > 0 ? (count / maxCount * 100) : 0;
      return `
        <div style="flex:1;min-width:60px">
          <div style="font-size:10px;color:var(--sub);margin-bottom:4px">${range}</div>
          <div style="
            height:20px;
            background:var(--accent);
            border-radius:4px;
            position:relative;
            width:${width}%;
            min-width:4px;
          " title="${count}筆"></div>
          <div style="font-size:9px;color:var(--text);margin-top:2px;text-align:center">${count}</div>
        </div>
      `;
    }).join('');
  }
}

function updateQuickMetricsV128(data) {
  // 更新儀表盤快速指標
  if (data.today_pnl !== undefined) {
    const todayPnlEl = document.getElementById('perfMaxGain');
    if (todayPnlEl) {
      todayPnlEl.textContent = `${data.today_pnl >= 0 ? '+' : ''}¥${data.today_pnl}`;
      todayPnlEl.style.color = data.today_pnl >= 0 ? 'var(--up)' : 'var(--down)';
    }
  }
  
  if (data.cash_ratio !== undefined) {
    const cashEl = document.getElementById('cashRatioVal');
    if (cashEl) cashEl.textContent = `${data.cash_ratio}%`;
  }
  
  if (data.sentiment_score !== undefined) {
    const sentimentEl = document.getElementById('sentimentScore');
    if (sentimentEl) sentimentEl.textContent = data.sentiment_score;
  }
}

// 分別加載各數據（向後相容）
async function loadSentimentHeatmapV128() {
  try {
    const resp = await fetch('/api/finance/intraday-aggregate-v128');
    const data = await resp.json();
    if (data.sentiment_heatmap) renderSentimentHeatmapV128(data.sentiment_heatmap);
  } catch (e) {
    console.error('loadSentimentHeatmapV128 error:', e);
  }
}

async function loadSignalQualityV128() {
  try {
    const resp = await fetch('/api/finance/intraday-aggregate-v128');
    const data = await resp.json();
    if (data.signal_quality) renderSignalQualityV128(data.signal_quality);
  } catch (e) {
    console.error('loadSignalQualityV128 error:', e);
  }
}

async function loadEntryQualityV128() {
  try {
    const resp = await fetch('/api/finance/intraday-aggregate-v128');
    const data = await resp.json();
    if (data.entry_quality) renderEntryQualityV128(data.entry_quality);
  } catch (e) {
    console.error('loadEntryQualityV128 error:', e);
  }
}

// 頁面加載時自動刷新一次
document.addEventListener('DOMContentLoaded', () => {
  // 延遲200ms確保頁面已加載
  setTimeout(() => {
    loadIntradayAggregateV128();
    // 每30秒自動刷新一次
    setInterval(loadIntradayAggregateV128, 30000);
  }, 200);
});
