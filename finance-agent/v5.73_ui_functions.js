// 持倉散佈圖
async function loadPortfolioScatter(){
  const d=await api('/api/finance/portfolio-scatter');
  if(!d)return;
  document.getElementById('portfolioRiskLevel').textContent=d.risk_level||'-';
  document.getElementById('portfolioRiskLevel').style.color=d.risk_level==='RED'?'#e63946':d.risk_level==='YELLOW'?'#ff9f1c':'#2ec4b6';
  document.getElementById('portfolioHHI').textContent=(d.concentration_metrics?.hhi||0).toFixed(2);
  const warn=document.getElementById('portfolioWarning');
  if(d.warning){warn.style.display='block';warn.innerHTML='<strong>⚠️ '+d.warning+'</strong>';}else{warn.style.display='none';}
  document.getElementById('portfolioRecommendation').textContent=d.recommendation||'持倉結構良好';
  const st=document.getElementById('portfolioSectorTable');
  st.innerHTML=Object.entries(d.sectors||{}).map(([sec,data])=>`<tr><td>${sec}</td><td>¥${fmt(data.market_value)}</td><td>${(data.weight_pct||0).toFixed(1)}%</td><td>${data.position_count}</td></tr>`).join('');
  // 繪製 Bubble Chart
  if(typeof Chart!=='undefined'&&d.bubbles){
    const ctx=document.getElementById('portfolioBubbleChart')?.getContext('2d');
    if(!ctx)return;
    const colorMap={'醫藥':'#ff6b6b','新能源':'#4361ee','主板':'#ffd93d','其他':'#95e1d3'};
    const datasets=Object.entries(d.sectors||{}).map(([sec,data],i)=>({
      label:sec,
      data:d.bubbles.filter(b=>b.sector===sec).map(b=>({x:b.holding_days||0,y:b.pnl_pct||0,r:Math.sqrt(b.market_value)/100||3})),
      backgroundColor:colorMap[sec]||'#95e1d3',
      borderColor:colorMap[sec]||'#95e1d3',
      borderWidth:1,fill:true
    })).filter(ds=>ds.data.length>0);
    if(window.portfolioChart)window.portfolioChart.destroy();
    window.portfolioChart=new Chart(ctx,'bubble',{
      data:{datasets},
      options:{responsive:true,maintainAspectRatio:true,plugins:{legend:{display:true}},scales:{x:{title:{display:true,text:'持倉天數'},min:0},y:{title:{display:true,text:'盈虧%'},beginAtZero:true}}}
    });
  }
}

// 止損執行面板
async function loadStopLossDashboard(){
  const d=await api('/api/finance/stop-loss-dashboard');
  if(!d)return;
  const today=d.today||{};
  document.getElementById('slCount').textContent=today.stop_loss_triggered||0;
  document.getElementById('tpCount').textContent=today.take_profit_triggered||0;
  document.getElementById('posChecked').textContent=today.positions_checked||0;
  document.getElementById('slRatio').textContent=(today.stop_loss_ratio_pct||0).toFixed(1)+'%';
  const details=document.getElementById('slDetails');
  if(today.details&&today.details.length>0){
    details.innerHTML=today.details.map(d=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)">${d}</div>`).join('');
  }else{details.innerHTML='暫無記錄';}
  const recTable=document.getElementById('slRecentTable');
  const recent=d.recent_7days||{};
  if(recent.days&&recent.stats){
    recTable.innerHTML=recent.days.map((day,i)=>{
      const stat=recent.stats[i]||{};
      return`<tr><td>${day}</td><td>${stat.stop_loss||0}</td><td>${stat.take_profit||0}</td><td>${stat.total_checked||0}</td></tr>`;
    }).join('');
  }
}
