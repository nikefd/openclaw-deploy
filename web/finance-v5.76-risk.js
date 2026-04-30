// v5.76 盤中優化② - 風險監控面板腳本
async function loadRiskMonitor(){
  const d=await api('/api/finance/intraday-optimize');
  if(!d)return;
  
  // 1. 風險摘要卡片
  const summary=d.risk_summary||{};
  const summaryCards=document.getElementById('riskSummaryCards');
  const criticalColor='#e63946', highColor='#ff9f1c', mediumColor='#ffd93d', lowColor='#2ec4b6';
  summaryCards.innerHTML=`
    <div class="card" style="border-left:4px solid ${criticalColor}"><div class="card-label">🔴 關鍵風險</div><div class="card-value" style="color:${criticalColor}">${summary.critical||0}</div></div>
    <div class="card" style="border-left:4px solid ${highColor}"><div class="card-label">🟠 高風險</div><div class="card-value" style="color:${highColor}">${summary.high||0}</div></div>
    <div class="card" style="border-left:4px solid ${mediumColor}"><div class="card-label">🟡 中風險</div><div class="card-value" style="color:${mediumColor}">${summary.medium||0}</div></div>
    <div class="card" style="border-left:4px solid ${lowColor}"><div class="card-label">🟢 低風險</div><div class="card-value" style="color:${lowColor}">${summary.low||0}</div></div>
    <div class="card"><div class="card-label">📊 平均風險</div><div class="card-value" style="font-size:20px">${(summary.avg_risk_score||0).toFixed(0)}</div></div>
  `;
  
  // 2. 持倉風險熱力圖表
  const heatmapTable=document.getElementById('riskHeatmapTable');
  const heatmap=d.position_heatmap||[];
  const riskLevelColor={CRITICAL:'#e63946',HIGH:'#ff9f1c',MEDIUM:'#ffd93d',LOW:'#2ec4b6'};
  heatmapTable.innerHTML=heatmap.map(h=>{
    const riskColor=riskLevelColor[h.risk_level]||'#666';
    const riskIcon={CRITICAL:'🔴',HIGH:'🟠',MEDIUM:'🟡',LOW:'🟢'}[h.risk_level]||'⚪';
    const factorText=h.risk_factors?.slice(0,2).join(' / ')||'無';
    return`<tr style="border-left:4px solid ${riskColor}">
      <td style="font-weight:600">${h.code}</td>
      <td>${h.name}</td>
      <td style="color:${riskColor};font-weight:600">${riskIcon} ${h.risk_level}</td>
      <td style="color:${riskColor};font-weight:600">${h.risk_score}</td>
      <td>${h.holding_days}天</td>
      <td style="color:${h.drawdown_pct<0?'#e63946':'#2ec4b6'}">${h.drawdown_pct.toFixed(1)}%</td>
      <td style="color:${h.pnl_pct>0?'#e63946':'#2ec4b6'}">${h.pnl_pct>0?'+':''}${h.pnl_pct.toFixed(2)}%</td>
      <td style="font-size:11px;color:var(--sub)">${factorText}</td>
    </tr>`;
  }).join('');
  
  // 3. 資金配置建議
  const allocation=d.allocation||{};
  document.getElementById('allocationCash').textContent=allocation.cash_ratio?.toFixed(1)+'%';
  document.getElementById('allocationMode').textContent=`¥${(allocation.cash_amount||0).toLocaleString()}`;
  document.getElementById('allocationModeTag').textContent=allocation.mode||'--';
  document.getElementById('allocationDesc').textContent=allocation.mode_desc||'--';
  
  const suggestions=document.getElementById('allocationSuggestions');
  suggestions.innerHTML=(allocation.suggestions||[]).map(s=>{
    const actionColor=s.action.includes('增配')?'#2ec4b6':s.action.includes('減配')?'#e63946':'#ffd93d';
    return`<div style="background:${actionColor}15;border-left:4px solid ${actionColor};border-radius:8px;padding:12px">
      <div style="font-weight:600;margin-bottom:4px">${s.sector}</div>
      <div style="font-size:12px;color:var(--sub);line-height:1.6">
        <div>現況: ${s.current_pct.toFixed(1)}%</div>
        <div>目標: ${s.target_pct.toFixed(1)}%</div>
        <div style="color:${actionColor};font-weight:600;margin-top:4px">${s.action}</div>
      </div>
    </div>`;
  }).join('');
}
