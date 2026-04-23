/**
 * 金融Agent UI增强 v5.52
 * - 风险告警面板
 * - 止损/止盈执行看板
 * - 改进①②：现金占比+策略激进度面板 + 绩效统计
 */

// === 改进① 现金占比+策略激进度 (v5.52) ===
async function loadCashProfile() {
  try {
    const data = await api('/api/finance/cash-profile');
    if (!data) return;
    
    document.getElementById('cashRatioVal').textContent = data.cash_ratio + '%';
    document.getElementById('cashAmount').textContent = (data.cash_amount / 10000).toFixed(1) + '万';
    document.getElementById('totalValue').textContent = (data.total_value / 10000).toFixed(1) + '万';
    
    const modeLabel = {
      'aggressive': '🔥 激进',
      'balanced': '⚡ 均衡',
      'conservative': '🛑 保守'
    }[data.strategy_mode] || data.strategy_mode;
    
    document.getElementById('strategyMode').textContent = modeLabel;
    document.getElementById('modeDesc').textContent = data.mode_description || '';
    
    const boostHtml = Object.entries(data.strategy_boost || {})
      .map(([k, v]) => `<div>• ${k}: ${v.toFixed(2)}x</div>`)
      .join('');
    document.getElementById('boostInfo').innerHTML = boostHtml || '--';
  } catch(e) {
    console.error('loadCashProfile', e);
  }
}

// === 改进② 绩效统计 (v5.52) ===
async function loadPerformanceStats() {
  try {
    const data = await api('/api/finance/perf-stats');
    if (!data) return;
    
    // 策略胜率
    const strategyWinRateHtml = Object.entries(data.strategies || {})
      .sort((a, b) => (b[1].win_rate || 0) - (a[1].win_rate || 0))
      .slice(0, 5)
      .map(([name, stats]) => {
        const indicator = stats.effectiveness === 'strong' ? '✅' : stats.effectiveness === 'fair' ? '⚠️' : '❌';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--border)">
          <span>${name}</span>
          <span style="font-weight:600;color:${stats.win_rate >= 50 ? 'var(--up)' : 'var(--down)'};">${indicator} ${stats.win_rate.toFixed(1)}%</span>
        </div>`;
      })
      .join('');
    document.getElementById('strategyWinRate').innerHTML = strategyWinRateHtml || '<div style="color:var(--sub)">--</div>';
    
    // 赛道分布
    const sectorDistHtml = Object.entries(data.sectors || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([sector, count]) => `<div style="background:var(--hover);padding:6px 8px;border-radius:6px;text-align:center">
        <div style="font-size:12px;font-weight:600">${count}笔</div>
        <div style="font-size:10px;color:var(--sub);margin-top:2px">${sector || '未分类'}</div>
      </div>`)
      .join('');
    document.getElementById('sectorDist').innerHTML = sectorDistHtml || '--';
    
    // 入场质量评分
    document.getElementById('entryQualityAvg').textContent = (data.entry_quality_avg || 0).toFixed(1) + '/100';
  } catch(e) {
    console.error('loadPerformanceStats', e);
  }
}

// === 风险告警面板 (v5.51) ===
// === 改进③ 持仓风险热力图 (v5.60) ===
async function loadPositionRiskHeatmap() {
  try {
    const data = await api('/api/finance/position-risk-heatmap');
    if (!data || !data.heatmap) return;
    const grid = document.getElementById('positionRiskGrid');
    if (!grid) return;
    const html = data.heatmap.map(pos => {
      let bgColor = 'rgba(46,196,182,0.1)', borderColor = '#2ec4b6', textColor = '#2ec4b6';
      if (pos.risk_level === 'high') {
        bgColor = 'rgba(230,57,70,0.1)'; borderColor = '#e63946'; textColor = '#e63946';
      } else if (pos.risk_level === 'medium') {
        bgColor = 'rgba(244,162,97,0.1)'; borderColor = '#f4a261'; textColor = '#f4a261';
      }
      return `<div style="background:${bgColor};border:1px solid ${borderColor};border-radius:12px;padding:12px;text-align:center"><div style="font-size:24px;margin-bottom:4px">${pos.risk_icon}</div><div style="font-size:13px;font-weight:600;margin-bottom:2px">${pos.symbol}</div><div style="font-size:11px;color:var(--sub);margin-bottom:6px">${pos.name}</div><div style="font-size:18px;font-weight:700;color:${textColor};margin-bottom:4px">${pos.risk_score}</div><div style="font-size:10px;color:var(--sub);padding-top:6px;border-top:1px solid ${borderColor}33">回撤: ${pos.drawdown}% | 持仓: ${pos.holding_days}d</div></div>`;
    }).join('');
    grid.innerHTML = html;
    document.getElementById('avgRiskScore').textContent = data.avg_risk_score.toFixed(2);
  } catch(e) {
    console.error('loadPositionRiskHeatmap', e);
  }
}

async function loadRiskAlerts(d){
  try{
    const rd=await api('/api/finance/risk-alerts');
    if(!rd||!rd.alerts)return;
    const alerts=rd.alerts||[];
    const grid=document.getElementById('riskAlertGrid');
    if(!grid)return;
    grid.innerHTML=alerts.map(a=>{
      let bgColor='#2ec4b622',textColor='#2ec4b6';
      if(a.level==='high'){bgColor='#e6394622';textColor='#e63946';}
      else if(a.level==='medium'){bgColor='#f4a26122';textColor='#f4a261';}
      const levelIcon=a.level==='high'?'🔴 危险':a.level==='medium'?'🟡 注意':'🟢 正常';
      return`<div style="padding:10px;background:${bgColor};border-radius:8px;text-align:center;border:1px solid ${textColor}33">
        <div style="font-size:11px;color:${textColor};font-weight:600;text-transform:uppercase">${levelIcon}</div>
        <div style="font-size:12px;margin-top:4px;color:var(--text);font-weight:600">${a.label}</div>
        <div style="font-size:11px;color:var(--sub);margin-top:2px">${a.value}</div>
      </div>`;
    }).join('')||'<p style="color:var(--sub);font-size:12px;text-align:center;padding:12px">暂无告警</p>';
  }catch(e){console.error('loadRiskAlerts',e);}
}

// === 止损/止盈执行看板 (v5.51) ===
async function loadStopLossTakeProfitBoard(d){
  try{
    const bd=await api('/api/finance/sl-tp-board');
    if(!bd)return;
    const slEl=document.getElementById('slExecCount');
    const tpEl=document.getElementById('tpExecCount');
    const invalidEl=document.getElementById('invalidSlPct');
    if(!slEl)return;
    slEl.textContent=bd.sl_count||0;
    if(tpEl)tpEl.textContent=bd.tp_count||0;
    if(invalidEl)invalidEl.textContent=(bd.invalid_sl_pct||0)+'%';
    
    const slReasons=bd.sl_reasons||{};
    const tpReasons=bd.tp_reasons||{};
    let gridHtml='';
    
    gridHtml+='<div><div style="font-size:12px;color:var(--sub);margin-bottom:8px;font-weight:600">⛔ 近30天止损原因</div>';
    const slKeys=Object.entries(slReasons).sort((a,b)=>b[1]-a[1]).slice(0,5);
    gridHtml+=slKeys.map(([k,v])=>`<div style="font-size:12px;display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><span>${k}</span><span style="color:var(--down);font-weight:600">${v}次</span></div>`).join('')||'<div style="font-size:12px;color:var(--sub)">暂无</div>';
    gridHtml+='</div>';
    
    gridHtml+='<div><div style="font-size:12px;color:var(--sub);margin-bottom:8px;font-weight:600">✅ 近30天止盈原因</div>';
    const tpKeys=Object.entries(tpReasons).sort((a,b)=>b[1]-a[1]).slice(0,5);
    gridHtml+=tpKeys.map(([k,v])=>`<div style="font-size:12px;display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><span>${k}</span><span style="color:var(--up);font-weight:600">${v}次</span></div>`).join('')||'<div style="font-size:12px;color:var(--sub)">暂无</div>';
    gridHtml+='</div>';
    
    const gridEl=document.getElementById('slTpReasonGrid');
    if(gridEl)gridEl.innerHTML=gridHtml;
  }catch(e){console.error('loadStopLossTakeProfitBoard',e);}
}
