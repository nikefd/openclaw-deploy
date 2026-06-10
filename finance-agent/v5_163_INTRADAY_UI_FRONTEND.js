/**
 * v5.163 盤中UI優化② - 前端即時推送面板
 * 目標: 盤中交互 +30% | 風險預警 <5秒 | 入場推送實時展示
 */

(function() {
  'use strict';

  // ============ 實時P&L儀表板 ============
  
  class IntraDayPnLDashboard {
    constructor() {
      this.container = null;
      this.updateInterval = 2000; // 2秒更新
      this.autoRefresh = true;
    }

    init() {
      this.createUI();
      this.startAutoRefresh();
    }

    createUI() {
      const html = `
        <div id="intraday-pnl-v163" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
          <!-- 實時P&L卡片 -->
          <div style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px;">
            <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 16px;">🎯 實時持倉P&L</h3>
            <div id="pnl-positions" style="max-height: 400px; overflow-y: auto;"></div>
          </div>
          
          <!-- 風險儀表板 -->
          <div style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px;">
            <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 16px;">⚠️ 風險警告</h3>
            <div id="risk-alerts" style="max-height: 400px; overflow-y: auto;"></div>
          </div>
          
          <!-- 交易信號 -->
          <div style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; grid-column: 1/-1;">
            <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 16px;">📡 最近交易信號 (5分鐘)</h3>
            <div id="recent-signals" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px;"></div>
          </div>
        </div>
      `;
      
      // 插入到頁面
      const contentDiv = document.querySelector('.content');
      if (contentDiv) {
        contentDiv.insertAdjacentHTML('afterbegin', html);
      }
      
      this.container = document.getElementById('intraday-pnl-v163');
    }

    async refreshData() {
      try {
        const response = await fetch('/api/finance/intraday-ui-v163');
        if (!response.ok) throw new Error('API call failed');
        
        const data = await response.json();
        
        this.renderPnLPositions(data.pnl_dashboard.positions, data.pnl_dashboard.summary);
        this.renderRiskAlerts(data.risk_dashboard);
        this.renderRecentSignals(data.recent_signals);
        
      } catch (e) {
        console.error('[IntraDayPnLDashboard]', e);
      }
    }

    renderPnLPositions(positions, summary) {
      const container = document.getElementById('pnl-positions');
      if (!container) return;
      
      let html = `
        <div style="font-size: 12px; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>總P&L:</span>
            <span style="font-weight: 700; color: ${summary.total_pnl >= 0 ? 'var(--down)' : 'var(--up)'};">${summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl} (${summary.total_pnl_pct >= 0 ? '+' : ''}${summary.total_pnl_pct}%)</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>持倉數:</span>
            <span style="font-weight: 700;">${summary.num_positions}</span>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>資金利用:</span>
            <span style="font-weight: 700;">${summary.utilization_pct}%</span>
          </div>
        </div>
      `;
      
      positions.forEach(pos => {
        const trendIcon = pos.trend === 'up' ? '📈' : '📉';
        const riskColor = {
          'low': '#2ec4b6',
          'medium': '#ffc107',
          'high': '#ff9800',
          'critical': '#e63946'
        }[pos.risk_level] || '#999';
        
        html += `
          <div style="margin-bottom: 12px; padding: 10px; background: var(--hover); border-radius: 6px; border-left: 3px solid ${riskColor};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <div>
                <span style="font-weight: 700; font-size: 13px;">${trendIcon} ${pos.symbol}</span>
                <span style="color: var(--sub); font-size: 11px; margin-left: 8px;">×${pos.shares}股</span>
              </div>
              <span style="font-weight: 700; color: ${pos.pnl > 0 ? 'var(--down)' : 'var(--up)'}; font-size: 12px;">
                ${pos.pnl > 0 ? '+' : ''}${pos.pnl} (${pos.pnl_pct > 0 ? '+' : ''}${pos.pnl_pct}%)
              </span>
            </div>
            <div style="font-size: 11px; color: var(--sub); display: grid; grid-template-columns: 1fr 1fr;">
              <span>成本: ¥${pos.avg_cost}</span>
              <span>現價: ¥${pos.current_price}</span>
            </div>
            <div style="font-size: 11px; color: var(--sub); display: grid; grid-template-columns: 1fr 1fr; margin-top: 4px;">
              <span>持有: ${pos.holding_days}天</span>
              <span>質量: ${pos.entry_quality}分</span>
            </div>
          </div>
        `;
      });
      
      container.innerHTML = html;
    }

    renderRiskAlerts(riskData) {
      const container = document.getElementById('risk-alerts');
      if (!container) return;
      
      if (riskData.alerts.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--sub); padding: 20px;">✅ 暫無風險警告</div>`;
        return;
      }
      
      let html = '';
      riskData.alerts.forEach(alert => {
        const severityColor = {
          'critical': '#e63946',
          'high': '#ff9800',
          'low': '#2ec4b6'
        }[alert.severity] || '#999';
        
        const icon = {
          'critical': '🚨',
          'high': '⚠️',
          'low': '💡'
        }[alert.severity] || '📌';
        
        html += `
          <div style="margin-bottom: 12px; padding: 12px; background: ${severityColor}15; border-left: 3px solid ${severityColor}; border-radius: 6px;">
            <div style="font-weight: 700; color: ${severityColor}; margin-bottom: 4px;">
              ${icon} ${alert.symbol} - ${alert.type}
            </div>
            <div style="font-size: 12px; color: var(--text);">
              ${alert.message}
            </div>
            ${alert.action ? `<div style="margin-top: 8px;"><button onclick="handleStopLoss('${alert.symbol}')" style="padding: 6px 12px; background: ${severityColor}; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px;">🔴 ${alert.action}</button></div>` : ''}
          </div>
        `;
      });
      
      container.innerHTML = html;
    }

    renderRecentSignals(signals) {
      const container = document.getElementById('recent-signals');
      if (!container) return;
      
      if (signals.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--sub); padding: 20px; grid-column: 1/-1;">暫無最近交易信號</div>`;
        return;
      }
      
      let html = '';
      signals.forEach(sig => {
        const isBuy = sig.action === 'BUY';
        const signalColor = isBuy ? '#2ec4b6' : '#e63946';
        const signalIcon = isBuy ? '🟢' : '🔴';
        const statusColor = sig.status === 'OPEN' ? '#ffc107' : '#6c757d';
        
        html += `
          <div style="background: var(--hover); border: 1px solid var(--border); border-radius: 6px; padding: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-weight: 700; color: ${signalColor};">${signalIcon} ${sig.symbol}</span>
              <span style="font-size: 11px; background: ${statusColor}; color: white; padding: 2px 8px; border-radius: 3px;">${sig.status}</span>
            </div>
            <div style="font-size: 12px; color: var(--text); margin-bottom: 4px;">
              <span style="font-weight: 700;">${sig.signal_type}</span> × ${sig.quantity}
            </div>
            <div style="font-size: 11px; color: var(--sub); margin-bottom: 6px;">
              入: ¥${sig.entry_price} ${sig.exit_price ? `出: ¥${sig.exit_price}` : '持倉中'}
            </div>
            <div style="font-size: 12px; color: ${sig.pnl_pct >= 0 ? 'var(--down)' : 'var(--up)'}; font-weight: 700;">
              ${sig.pnl_pct >= 0 ? '+' : ''}${sig.pnl_pct}% (${sig.pnl >= 0 ? '+' : ''}${sig.pnl})
            </div>
          </div>
        `;
      });
      
      container.innerHTML = html;
    }

    startAutoRefresh() {
      this.refreshData();
      setInterval(() => this.refreshData(), this.updateInterval);
    }
  }

  // ============ 回測分析面板 ============
  
  class BacktestAnalyticsPanelV163 {
    constructor() {
      this.container = null;
    }

    init() {
      this.createUI();
      this.refreshData();
    }

    createUI() {
      const html = `
        <div id="backtest-analytics-v163" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
          <!-- 交易頻率分析 -->
          <div style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px;">
            <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 16px;">📊 交易頻率分析</h3>
            <div id="frequency-analysis" style="max-height: 400px; overflow-y: auto;"></div>
          </div>
          
          <!-- 信號持久度 -->
          <div style="background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px;">
            <h3 style="font-size: 14px; color: var(--sub); margin-bottom: 16px;">💪 信號持久度</h3>
            <div id="signal-persistence" style="max-height: 400px; overflow-y: auto;"></div>
          </div>
        </div>
      `;
      
      const analysisTab = document.querySelector('[data-tab="analysis"]');
      if (analysisTab) {
        analysisTab.insertAdjacentHTML('beforeend', html);
      }
      
      this.container = document.getElementById('backtest-analytics-v163');
    }

    async refreshData() {
      try {
        const response = await fetch('/api/finance/backtest-analytics-v163');
        if (!response.ok) throw new Error('API call failed');
        
        const data = await response.json();
        
        this.renderFrequencyAnalysis(data.frequency_analysis);
        this.renderSignalPersistence(data.signal_persistence);
        
      } catch (e) {
        console.error('[BacktestAnalyticsV163]', e);
      }
    }

    renderFrequencyAnalysis(data) {
      const container = document.getElementById('frequency-analysis');
      if (!container) return;
      
      // 日頻率
      let html = '<div style="margin-bottom: 12px;"><strong style="font-size: 12px;">日交易頻率:</strong><br/>';
      data.daily_frequency.slice(0, 10).forEach(d => {
        html += `
          <div style="font-size: 11px; margin: 4px 0; display: flex; justify-content: space-between;">
            <span>${d.date}</span>
            <span>${d.trade_count}筆 | 平均${d.avg_pnl_pct > 0 ? '+' : ''}${d.avg_pnl_pct}% | ${d.win_rate}%勝率</span>
          </div>
        `;
      });
      html += '</div>';
      
      // 信號類型
      html += '<div><strong style="font-size: 12px;">信號類型表現:</strong><br/>';
      data.signal_performance.forEach(s => {
        const barLength = (s.win_rate / 100) * 100;
        html += `
          <div style="font-size: 11px; margin: 8px 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>${s.signal_type}</span>
              <span>${s.count}筆 | ${s.avg_pnl_pct > 0 ? '+' : ''}${s.avg_pnl_pct}%</span>
            </div>
            <div style="background: var(--hover); border-radius: 2px; height: 6px; overflow: hidden;">
              <div style="background: ${s.avg_pnl_pct > 0 ? 'var(--down)' : 'var(--up)'}; width: ${barLength}%; height: 100%;"></div>
            </div>
          </div>
        `;
      });
      html += '</div>';
      
      container.innerHTML = html;
    }

    renderSignalPersistence(data) {
      const container = document.getElementById('signal-persistence');
      if (!container) return;
      
      let html = '';
      data.quality_persistence.forEach(q => {
        html += `
          <div style="margin-bottom: 12px; padding: 10px; background: var(--hover); border-radius: 6px;">
            <div style="font-weight: 700; color: ${q.avg_pnl_pct > 0 ? 'var(--down)' : 'var(--up)'}; margin-bottom: 6px;">
              ${q.quality_level}
            </div>
            <div style="font-size: 11px; color: var(--sub); display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
              <span>交易: ${q.total_trades}筆</span>
              <span>勝率: ${q.win_rate}%</span>
              <span>平均: ${q.avg_pnl_pct > 0 ? '+' : ''}${q.avg_pnl_pct}%</span>
              <span>最佳: ¥${q.best_trade}</span>
            </div>
          </div>
        `;
      });
      
      container.innerHTML = html;
    }
  }

  // ============ 初始化 ============
  
  document.addEventListener('DOMContentLoaded', () => {
    // 初始化盤中P&L儀表板
    const pnlDash = new IntraDayPnLDashboard();
    pnlDash.init();
    
    // 初始化回測分析面板
    const backtestDash = new BacktestAnalyticsPanelV163();
    backtestDash.init();
  });

  // 全局函數 - 一鍵止損
  window.handleStopLoss = function(symbol) {
    if (confirm(`確認止損 ${symbol} ?`)) {
      // 調用後端止損API (需要在finance-api-server.js中添加)
      fetch(`/api/finance/execute-stop-loss?symbol=${symbol}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
          alert(`止損執行: ${data.message}`);
          // 刷新數據
          location.reload();
        })
        .catch(e => alert('止損失敗: ' + e.message));
    }
  };

})();
