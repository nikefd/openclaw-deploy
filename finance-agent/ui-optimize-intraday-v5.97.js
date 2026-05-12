/**
 * UI优化 v5.97 - 盘中增强
 * 功能:
 * 1. 现金部署进度条 (96% → 15-20% 目标)
 * 2. Kelly仓位效率实时指标
 * 3. 选股超时保护状态
 * 4. 持仓集中度与推荐
 */

'use strict';

(function() {
  const API = 'http://localhost:7684';
  const CASH_TARGET_MIN = 0.15;
  const CASH_TARGET_MAX = 0.20;
  
  async function updateCashDeploymentProgress() {
    try {
      const res = await fetch(`${API}/dashboard`);
      const data = await res.json();
      
      const account = data.account || {};
      const cash = account.cash || 0;
      const totalValue = account.total_value || 1000000;
      const cashRatio = totalValue > 0 ? cash / totalValue : 0;
      
      // 计算部署进度
      const targetTop = CASH_TARGET_MAX; // 20%
      const targetBot = CASH_TARGET_MIN; // 15%
      
      // 从96.6%到15-20%的进度
      let deployProgress = 0;
      if (cashRatio > targetTop) {
        // 从100% → 20% 是 0% 进度
        deployProgress = Math.max(0, Math.min(100, 
          ((0.966 - cashRatio) / (0.966 - targetTop)) * 100
        ));
      } else {
        // 已在目标范围内
        deployProgress = 100;
      }
      
      const elem = document.getElementById('cashDeploymentProgress');
      if (elem) {
        elem.innerHTML = `
          <div style="margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
              <span style="font-size:12px;color:var(--sub)">💰 现金激进部署进度</span>
              <span style="font-size:13px;font-weight:600">${deployProgress.toFixed(0)}%</span>
            </div>
            <div style="width:100%;height:8px;background:var(--hover);border-radius:4px;overflow:hidden">
              <div style="height:100%;background:linear-gradient(90deg,#2ec4b6,#4361ee);width:${deployProgress}%;transition:width .5s ease"></div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:11px;color:var(--sub)">
              <span>当前: ${(cashRatio*100).toFixed(1)}%</span>
              <span>目标: 15-20%</span>
            </div>
          </div>
        `;
      }
    } catch (e) {
      console.error('[UI-v5.97] Cash deployment update failed:', e.message);
    }
  }
  
  async function updateKellyEfficiency() {
    try {
      const res = await fetch(`${API}/kelly-positions`);
      if (!res.ok) return; // 可能API未实现
      
      const data = await res.json();
      const { fund_utilization, kelly_efficiency } = data;
      
      const elem = document.getElementById('kellyEfficiencyPanel');
      if (elem) {
        const color = kelly_efficiency >= 80 ? '#2ec4b6' : 
                      kelly_efficiency >= 50 ? '#4361ee' : '#ff6b6b';
        
        elem.innerHTML = `
          <div style="text-align:center">
            <div style="font-size:12px;color:var(--sub);margin-bottom:8px">🎲 Kelly仓位效率</div>
            <div style="font-size:28px;font-weight:700;color:${color}">${kelly_efficiency.toFixed(0)}%</div>
            <div style="font-size:11px;color:var(--sub);margin-top:4px">资金利用: ${(fund_utilization).toFixed(1)}%</div>
          </div>
        `;
      }
    } catch (e) {
      // 静默失败，API可能不存在
    }
  }
  
  async function updateStockSelectionStatus() {
    try {
      const res = await fetch(`${API}/selection-status`);
      if (!res.ok) return;
      
      const data = await res.json();
      const { timeout_protected, candidate_pool_size, last_run_seconds } = data;
      
      const elem = document.getElementById('selectionStatusPanel');
      if (elem) {
        const statusText = timeout_protected ? '✅ 防超时启用' : '⚠️ 无保护';
        const statusColor = timeout_protected ? '#2ec4b6' : '#ff9500';
        
        elem.innerHTML = `
          <div style="font-size:12px;color:var(--sub);margin-bottom:8px">🔍 选股状态</div>
          <div style="font-size:13px;font-weight:600;color:${statusColor};margin-bottom:4px">${statusText}</div>
          <div style="font-size:11px;color:var(--sub)">
            <div>候选池: ${candidate_pool_size || 45}只</div>
            <div>最后运行: ${last_run_seconds || 0}s</div>
          </div>
        `;
      }
    } catch (e) {
      // 静默失败
    }
  }
  
  async function updateHoldingConcentration() {
    try {
      const res = await fetch(`${API}/dashboard`);
      const data = await res.json();
      
      const positions = data.positions || [];
      if (positions.length === 0) return;
      
      // 计算持仓集中度
      const totalValue = positions.reduce((s, p) => s + p.current_price * p.shares, 0);
      const concentration = [];
      
      positions.sort((a, b) => (b.current_price * b.shares) - (a.current_price * a.shares));
      positions.slice(0, 3).forEach(p => {
        const pct = totalValue > 0 ? (p.current_price * p.shares / totalValue * 100) : 0;
        concentration.push({ symbol: p.symbol, pct });
      });
      
      const top3Total = concentration.reduce((s, c) => s + c.pct, 0);
      
      const elem = document.getElementById('concentrationPanel');
      if (elem) {
        const healthColor = top3Total > 50 ? '#ff6b6b' : top3Total > 30 ? '#ff9500' : '#2ec4b6';
        
        elem.innerHTML = `
          <div style="font-size:12px;color:var(--sub);margin-bottom:8px">🎯 持仓集中度</div>
          <div style="font-size:20px;font-weight:700;color:${healthColor};margin-bottom:4px">${top3Total.toFixed(1)}%</div>
          <div style="font-size:11px;line-height:1.6;color:var(--sub)">
            ${concentration.slice(0, 3).map(c => `<div>${c.symbol}: ${c.pct.toFixed(1)}%</div>`).join('')}
            <div style="margin-top:4px;color:var(--text);font-size:10px">
              ${top3Total > 50 ? '⚠️ 过度集中' : top3Total > 30 ? '⚠️ 需优化' : '✅ 健康分散'}
            </div>
          </div>
        `;
      }
    } catch (e) {
      console.error('[UI-v5.97] Concentration update failed:', e.message);
    }
  }
  
  // 初始化与自动更新
  function initIntradayOptimization() {
    // 检查目标元素
    const dashboard = document.getElementById('panel-dashboard');
    if (!dashboard) {
      console.log('[UI-v5.97] Dashboard not found, waiting...');
      setTimeout(initIntradayOptimization, 1000);
      return;
    }
    
    // 插入新面板
    const existingWrap = document.getElementById('cashProfileWrap');
    if (existingWrap && !document.getElementById('intradayEnhanceWrap')) {
      const enhanceHtml = `
        <div id="intradayEnhanceWrap" style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:24px">
          <h3 style="font-size:14px;color:var(--sub);margin-bottom:16px;display:flex;align-items:center;gap:8px">⚡ 盘中实时监控 (v5.97)</h3>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:16px">
            <div id="cashDeploymentProgress" style="grid-column:1/-1;padding:12px;background:var(--hover);border-radius:8px"></div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px">
            <div id="kellyEfficiencyPanel" style="padding:12px;background:var(--hover);border-radius:8px;text-align:center;min-height:60px"></div>
            <div id="selectionStatusPanel" style="padding:12px;background:var(--hover);border-radius:8px;min-height:60px"></div>
            <div id="concentrationPanel" style="padding:12px;background:var(--hover);border-radius:8px;min-height:60px"></div>
            <div style="padding:12px;background:var(--hover);border-radius:8px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">📅 更新时间</div>
              <div style="font-size:13px;font-weight:600" id="updateTime">--:--</div>
              <div style="font-size:10px;color:var(--sub);margin-top:4px">每30s刷新</div>
            </div>
          </div>
        </div>
      `;
      
      existingWrap.insertAdjacentHTML('afterend', enhanceHtml);
    }
    
    // 首次更新
    updateCashDeploymentProgress();
    updateKellyEfficiency();
    updateStockSelectionStatus();
    updateHoldingConcentration();
    updateTimeDisplay();
    
    // 定时更新 (30s)
    setInterval(() => {
      updateCashDeploymentProgress();
      updateKellyEfficiency();
      updateStockSelectionStatus();
      updateHoldingConcentration();
      updateTimeDisplay();
    }, 30000);
  }
  
  function updateTimeDisplay() {
    const elem = document.getElementById('updateTime');
    if (elem) {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      elem.textContent = `${hh}:${mm}`;
    }
  }
  
  // 页面加载完成后启动
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIntradayOptimization);
  } else {
    initIntradayOptimization();
  }
})();
