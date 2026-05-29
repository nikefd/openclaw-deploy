/**
 * UI优化 v5.139 - 盤中绩效统计增强
 * 新增高级绩效分析面板：夏普率、胜率、收益分布、风险调整收益
 * 激活时间: 2026-05-29 03:30 UTC 盤中優化②
 */

(function() {
  'use strict';

  // === 绩效统计增强 (v5.139) ===
  window.PerformanceEnhanced = {
    // 计算夏普率
    calcSharpe: (returns, riskFreeRate = 0.02) => {
      if (!returns || returns.length < 2) return 0;
      const mean = returns.reduce((s, r) => s + r, 0) / returns.length;
      const variance = returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / returns.length;
      const stdDev = Math.sqrt(variance);
      if (stdDev === 0) return 0;
      const annualized = Math.sqrt(252); // 交易日数
      return ((mean * 252 - riskFreeRate) / (stdDev * annualized)) || 0;
    },

    // 计算胜率
    calcWinRate: (trades) => {
      if (!trades || trades.length === 0) return 0;
      const wins = trades.filter(t => t.pnl && t.pnl > 0).length;
      return (wins / trades.length * 100).toFixed(2);
    },

    // 计算盈亏比
    calcProfitFactor: (trades) => {
      if (!trades || trades.length === 0) return 0;
      const profits = trades.filter(t => t.pnl > 0).reduce((s, t) => s + (t.pnl || 0), 0);
      const losses = Math.abs(trades.filter(t => t.pnl < 0).reduce((s, t) => s + (t.pnl || 0), 0));
      if (losses === 0) return profits > 0 ? 999 : 0;
      return (profits / losses).toFixed(2);
    },

    // 计算最大连胜/连败
    calcStreaks: (trades) => {
      if (!trades || trades.length === 0) return { maxWin: 0, maxLoss: 0 };
      let maxWin = 0, maxLoss = 0, currentWin = 0, currentLoss = 0;
      trades.forEach(t => {
        if (t.pnl > 0) {
          currentWin++;
          currentLoss = 0;
          maxWin = Math.max(maxWin, currentWin);
        } else if (t.pnl < 0) {
          currentLoss++;
          currentWin = 0;
          maxLoss = Math.max(maxLoss, currentLoss);
        }
      });
      return { maxWin, maxLoss };
    },

    // 计算回撤恢复时间
    calcDrawdownRecovery: (snapshots) => {
      if (!snapshots || snapshots.length < 2) return { maxDD: 0, recoveryDays: 0 };
      let peak = snapshots[0].total_value;
      let maxDD = 0, maxDDDate = null, recoveryDays = 0;
      
      for (let i = 0; i < snapshots.length; i++) {
        const current = snapshots[i].total_value;
        if (current > peak) peak = current;
        
        const dd = (current - peak) / peak * 100;
        if (dd < maxDD) {
          maxDD = dd;
          maxDDDate = i;
        }
      }

      // 计算恢复时间
      if (maxDDDate !== null && maxDDDate > 0) {
        for (let i = maxDDDate; i >= 0; i--) {
          if (snapshots[i].total_value >= peak) {
            recoveryDays = maxDDDate - i;
            break;
          }
        }
      }

      return { maxDD: maxDD.toFixed(2), recoveryDays };
    },

    // 计算收益分布
    calcReturnDistribution: (trades) => {
      if (!trades || trades.length === 0) return { bins: [], freq: [] };
      
      const pnls = trades.filter(t => t.pnl !== undefined).map(t => t.pnl_pct || 0);
      if (pnls.length === 0) return { bins: [], freq: [] };

      const min = Math.floor(Math.min(...pnls) / 5) * 5;
      const max = Math.ceil(Math.max(...pnls) / 5) * 5;
      const bins = [];
      const freq = [];

      for (let i = min; i <= max; i += 5) {
        bins.push(`${i}%~${i+5}%`);
        const count = pnls.filter(p => p >= i && p < i + 5).length;
        freq.push(count);
      }

      return { bins, freq };
    },

    // 构建增强绩效面板 HTML
    renderPerformancePanel: (data) => {
      const {
        trades = [],
        snapshots = [],
        account = {},
        positions = []
      } = data;

      const winRate = window.PerformanceEnhanced.calcWinRate(trades);
      const profitFactor = window.PerformanceEnhanced.calcProfitFactor(trades);
      const streaks = window.PerformanceEnhanced.calcStreaks(trades);
      const recovery = window.PerformanceEnhanced.calcDrawdownRecovery(snapshots);
      const distribution = window.PerformanceEnhanced.calcReturnDistribution(trades);

      // 夏普率计算 (用每日收益)
      let dailyReturns = [];
      if (snapshots.length >= 2) {
        for (let i = snapshots.length - 1; i > 0; i--) {
          const ret = (snapshots[i-1].total_value - snapshots[i].total_value) / snapshots[i].total_value;
          dailyReturns.push(ret);
        }
      }
      const sharpe = window.PerformanceEnhanced.calcSharpe(dailyReturns);

      const html = `
        <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:24px">
          <h3 style="font-size:14px;color:var(--sub);margin-bottom:20px">📊 高级绩效分析 (v5.139)</h3>
          
          <!-- 核心指标卡片 -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:24px">
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">夏普率</div>
              <div style="font-size:28px;font-weight:700;color:var(--accent)">${sharpe.toFixed(2)}</div>
              <div style="font-size:11px;color:var(--sub);margin-top:4px">风险调整收益</div>
            </div>
            
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">胜率</div>
              <div style="font-size:28px;font-weight:700;color:#2ec4b6">${winRate}%</div>
              <div style="font-size:11px;color:var(--sub);margin-top:4px">${trades.length}笔交易</div>
            </div>
            
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">盈亏比</div>
              <div style="font-size:28px;font-weight:700;color:#e63946">${profitFactor}</div>
              <div style="font-size:11px;color:var(--sub);margin-top:4px">平均盈利/亏损</div>
            </div>
            
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">最大回撤</div>
              <div style="font-size:28px;font-weight:700;color:#ff6b6b">${recovery.maxDD}%</div>
              <div style="font-size:11px;color:var(--sub);margin-top:4px">恢复用时${recovery.recoveryDays}天</div>
            </div>
          </div>

          <!-- 连胜/连败 -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">最大连胜</div>
              <div style="font-size:24px;font-weight:700;color:var(--down)">${streaks.maxWin}笔</div>
            </div>
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">最大连败</div>
              <div style="font-size:24px;font-weight:700;color:var(--up)">${streaks.maxLoss}笔</div>
            </div>
          </div>

          <!-- 收益分布直方图 -->
          <div style="background:var(--hover);border-radius:8px;padding:16px">
            <div style="font-size:12px;color:var(--sub);margin-bottom:12px">📈 单笔收益分布</div>
            <div style="display:flex;align-items:flex-end;gap:4px;height:120px">
              ${distribution.freq.map((f, i) => {
                const maxFreq = Math.max(...distribution.freq, 1);
                const height = (f / maxFreq * 100);
                const isPositive = i > distribution.freq.length / 2;
                const color = isPositive ? '#2ec4b6' : '#ff6b6b';
                return \`<div style="flex:1;background:\${color};border-radius:4px;height:\${height}%;min-height:2px;position:relative" title="\${distribution.bins[i]}: \${f}笔"></div>\`;
              }).join('')}
            </div>
            <div style="font-size:11px;color:var(--sub);margin-top:8px;text-align:center">
              ${distribution.bins.length > 0 ? distribution.bins[0] + ' ~ ' + distribution.bins[distribution.bins.length - 1] : '暂无数据'}
            </div>
          </div>
        </div>
      `;

      return html;
    }
  };

  // === 页面加载后注入 ===
  document.addEventListener('DOMContentLoaded', () => {
    // 如果存在performance面板，自动注入增强内容
    const perfPanel = document.getElementById('panel-performance');
    if (perfPanel && !document.getElementById('enhanced-perf-panel')) {
      const div = document.createElement('div');
      div.id = 'enhanced-perf-panel';
      perfPanel.insertBefore(div, perfPanel.firstChild);
    }
  });

  // === 全局函数：刷新绩效数据 ===
  window.refreshPerformanceEnhanced = async () => {
    try {
      const res = await fetch('/api/dashboard');
      const data = await res.json();
      
      // 获取所有交易
      const tradesRes = await fetch('/api/trades');
      const tradesData = await tradesRes.json();
      
      // 获取快照
      const metricsRes = await fetch('/api/metrics');
      const metricsData = await metricsRes.json();

      const panel = document.getElementById('enhanced-perf-panel');
      if (panel) {
        panel.innerHTML = window.PerformanceEnhanced.renderPerformancePanel({
          trades: tradesData.trades || [],
          snapshots: metricsData.snapshots || [],
          account: data.account || {},
          positions: data.positions || []
        });
      }
    } catch (e) {
      console.error('绩效刷新失败:', e);
    }
  };

})();
