/**
 * 金融Agent UI增强 v5.51
 * - 风险告警面板
 * - 止损/止盈执行看板
 */

// === 风险告警面板 (v5.51) ===
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
