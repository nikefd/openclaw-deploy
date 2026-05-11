/**
 * v5.77 策略分析UI增强模块
 * ────────────────────────────────────────────
 * 
 * 【功能】
 * 新标签页："📊 策略分析"
 *   • 面板1：最优策略参数展示卡
 *   • 面板2：历史命中率图表 (30/60/90天)
 *   • 面板3：赛道权重对比 (当前 vs 推荐)
 * 
 * 【API端点】
 *   • GET /api/finance/strategy-analysis (回测参数 + 命中率)
 *   • GET /api/finance/accuracy-report (准确率详情)
 *   • GET /api/finance/sector-weights (赛道权重)
 */

// =================== 数据获取函数 ===================

async function loadStrategyAnalysis() {
  console.log('📊 加载策略分析数据...');
  
  try {
    // 获取策略分析数据
    const response = await fetch('/api/finance/strategy-analysis');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    // 渲染面板
    renderOptimalStrategyCard(data.optimal_strategy);
    renderAccuracyChart(data.accuracy_report);
    renderSectorWeightComparison(data.sector_weights);
    
    console.log('✅ 策略分析数据加载完成');
  } catch (error) {
    console.error('❌ 加载策略分析失败:', error);
    showErrorNotification('策略分析数据加载失败: ' + error.message);
  }
}

// =================== 面板1：最优策略参数展示卡 ===================

function renderOptimalStrategyCard(data) {
  const container = document.getElementById('panel-strategy-optimal');
  if (!container) return;
  
  const html = `
    <div class="strategy-card-container">
      <h3>⭐ 最优策略参数 (回测TOP1)</h3>
      
      <div class="strategy-overview">
        <span class="badge-strategy">${data.strategy || 'MACD+RSI'}</span>
        <span class="badge-sector">科技成长</span>
      </div>
      
      <div class="metrics-grid">
        <!-- 左列: 技术参数 -->
        <div class="metric-column">
          <h4>技术参数</h4>
          <div class="metric-item">
            <label>MACD</label>
            <value>${data.macd_fast || 12}, ${data.macd_slow || 26}, ${data.macd_signal || 9}</value>
          </div>
          <div class="metric-item">
            <label>RSI</label>
            <value>${data.rsi_period || 14} (${data.rsi_oversold || 30}-${data.rsi_overbought || 70})</value>
          </div>
          <div class="metric-item">
            <label>止损</label>
            <value class="text-danger">${((data.stop_loss || -0.08) * 100).toFixed(1)}%</value>
          </div>
          <div class="metric-item">
            <label>止盈</label>
            <value class="text-success">${((data.take_profit || 0.20) * 100).toFixed(1)}%</value>
          </div>
        </div>
        
        <!-- 中列: 回测成绩 -->
        <div class="metric-column">
          <h4>回测成绩</h4>
          <div class="metric-item">
            <label>年化收益</label>
            <value class="text-success">${((data.backtest_return || 0.171) * 100).toFixed(1)}%</value>
          </div>
          <div class="metric-item">
            <label>Sharpe比率</label>
            <value class="text-info">${(data.backtest_sharpe || 2.35).toFixed(2)}</value>
          </div>
          <div class="metric-item">
            <label>胜率</label>
            <value class="text-success">${((data.backtest_winrate || 0.60) * 100).toFixed(0)}%</value>
          </div>
          <div class="metric-item">
            <label>最大回撤</label>
            <value class="text-warning">${((data.backtest_max_dd || 0.0408) * 100).toFixed(1)}%</value>
          </div>
        </div>
        
        <!-- 右列: 应用赛道 -->
        <div class="metric-column">
          <h4>应用赛道</h4>
          <div class="sectors-list">
            ${(data.apply_sectors || []).map(s => `<span class="badge-sector-small">${s}</span>`).join('')}
          </div>
        </div>
      </div>
    </div>
    
    <style>
      .strategy-card-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
      }
      
      .strategy-card-container h3 {
        margin: 0 0 16px 0;
        font-size: 18px;
        font-weight: 600;
      }
      
      .strategy-overview {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
        flex-wrap: wrap;
      }
      
      .badge-strategy {
        background: rgba(255,255,255,0.3);
        padding: 6px 12px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
      }
      
      .badge-sector {
        background: rgba(255,255,255,0.2);
        padding: 6px 12px;
        border-radius: 16px;
        font-size: 12px;
      }
      
      .metrics-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
      }
      
      .metric-column h4 {
        margin: 0 0 12px 0;
        font-size: 13px;
        font-weight: 600;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      .metric-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 8px;
      }
      
      .metric-item label {
        font-size: 12px;
        opacity: 0.9;
      }
      
      .metric-item value {
        font-size: 14px;
        font-weight: 600;
        text-align: right;
      }
      
      .text-success { color: #10b981; }
      .text-danger { color: #ef4444; }
      .text-warning { color: #f59e0b; }
      .text-info { color: #3b82f6; }
      
      .sectors-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      
      .badge-sector-small {
        background: rgba(255,255,255,0.15);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
      }
      
      @media (max-width: 1024px) {
        .metrics-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }
      
      @media (max-width: 640px) {
        .metrics-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
  `;
  
  container.innerHTML = html;
}

// =================== 面板2：历史命中率图表 ===================

function renderAccuracyChart(data) {
  const container = document.getElementById('panel-accuracy-chart');
  if (!container) return;
  
  // 准备数据 (30/60/90天)
  const periods = data.periods || {};
  const periods30 = periods[30] || {};
  const periods60 = periods[60] || {};
  const periods90 = periods[90] || {};
  
  const chartData = {
    labels: ['30天', '60天', '90天'],
    datasets: [
      {
        label: '命中率',
        data: [
          (periods30.hit_rate_pct || 0),
          (periods60.hit_rate_pct || 0),
          (periods90.hit_rate_pct || 0),
        ],
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 6,
        pointBackgroundColor: '#10b981',
      },
      {
        label: '盈利率',
        data: [
          (periods30.win_rate_pct || 0),
          (periods60.win_rate_pct || 0),
          (periods90.win_rate_pct || 0),
        ],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 6,
        pointBackgroundColor: '#3b82f6',
      },
    ]
  };
  
  const html = `
    <div class="accuracy-chart-container">
      <h3>📈 历史命中率趋势</h3>
      <div class="chart-wrapper">
        <canvas id="accuracyLineChart" style="height: 300px;"></canvas>
      </div>
      
      <div class="accuracy-stats">
        <div class="stat-card">
          <h4>最近30天</h4>
          <div class="stat-item">
            <label>命中率</label>
            <value class="text-success">${(periods30.hit_rate_pct || 0).toFixed(1)}%</value>
          </div>
          <div class="stat-item">
            <label>样本</label>
            <value>${periods30.sample_size || 0}条</value>
          </div>
          <div class="stat-item">
            <label>平均收益</label>
            <value class="text-success">${(periods30.avg_return_pct || 0).toFixed(2)}%</value>
          </div>
        </div>
        
        <div class="stat-card">
          <h4>最近60天</h4>
          <div class="stat-item">
            <label>命中率</label>
            <value class="text-success">${(periods60.hit_rate_pct || 0).toFixed(1)}%</value>
          </div>
          <div class="stat-item">
            <label>样本</label>
            <value>${periods60.sample_size || 0}条</value>
          </div>
          <div class="stat-item">
            <label>平均收益</label>
            <value class="text-success">${(periods60.avg_return_pct || 0).toFixed(2)}%</value>
          </div>
        </div>
        
        <div class="stat-card">
          <h4>最近90天</h4>
          <div class="stat-item">
            <label>命中率</label>
            <value class="text-success">${(periods90.hit_rate_pct || 0).toFixed(1)}%</value>
          </div>
          <div class="stat-item">
            <label>样本</label>
            <value>${periods90.sample_size || 0}条</value>
          </div>
          <div class="stat-item">
            <label>平均收益</label>
            <value class="text-success">${(periods90.avg_return_pct || 0).toFixed(2)}%</value>
          </div>
        </div>
      </div>
    </div>
    
    <style>
      .accuracy-chart-container {
        background: white;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }
      
      .accuracy-chart-container h3 {
        margin: 0 0 20px 0;
        font-size: 16px;
        font-weight: 600;
      }
      
      .chart-wrapper {
        margin-bottom: 20px;
        position: relative;
        height: 300px;
      }
      
      .accuracy-stats {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
      }
      
      .stat-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
      }
      
      .stat-card h4 {
        margin: 0 0 12px 0;
        font-size: 13px;
        font-weight: 600;
        color: #6b7280;
      }
      
      .stat-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #e5e7eb;
      }
      
      .stat-item:last-child {
        border-bottom: none;
      }
      
      .stat-item label {
        font-size: 12px;
        color: #6b7280;
      }
      
      .stat-item value {
        font-size: 14px;
        font-weight: 600;
      }
      
      @media (max-width: 1024px) {
        .accuracy-stats {
          grid-template-columns: 1fr;
        }
      }
    </style>
  `;
  
  container.innerHTML = html;
  
  // 创建图表
  setTimeout(() => {
    if (typeof Chart !== 'undefined') {
      const ctx = document.getElementById('accuracyLineChart');
      if (ctx) {
        new Chart(ctx, {
          type: 'line',
          data: chartData,
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'top',
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                max: 100,
                ticks: {
                  callback: function(value) {
                    return value + '%';
                  }
                }
              }
            }
          }
        });
      }
    }
  }, 100);
}

// =================== 面板3：赛道权重对比 ===================

function renderSectorWeightComparison(data) {
  const container = document.getElementById('panel-sector-weights');
  if (!container) return;
  
  const currentWeights = data.current_weights || {};
  const recommendedWeights = data.recommended_weights || {};
  
  // 获取所有赛道
  const allSectors = new Set([
    ...Object.keys(currentWeights),
    ...Object.keys(recommendedWeights)
  ]);
  
  const sectors = Array.from(allSectors).sort();
  
  // 准备柱状图数据
  const chartData = {
    labels: sectors,
    datasets: [
      {
        label: '当前权重',
        data: sectors.map(s => currentWeights[s] || 0),
        backgroundColor: '#93c5fd',
        borderRadius: 4,
      },
      {
        label: '推荐权重',
        data: sectors.map(s => recommendedWeights[s] || 0),
        backgroundColor: '#fbbf24',
        borderRadius: 4,
      }
    ]
  };
  
  const html = `
    <div class="sector-weight-container">
      <h3>⚖️ 赛道权重对比 (当前 vs 推荐)</h3>
      
      <div class="chart-wrapper-bar">
        <canvas id="sectorWeightChart" style="height: 300px;"></canvas>
      </div>
      
      <div class="weight-table">
        <table>
          <thead>
            <tr>
              <th>赛道</th>
              <th>当前权重</th>
              <th>推荐权重</th>
              <th>差异</th>
              <th>建议</th>
            </tr>
          </thead>
          <tbody>
            ${sectors.map(s => {
              const current = currentWeights[s] || 0;
              const recommended = recommendedWeights[s] || 0;
              const diff = recommended - current;
              let advice = '';
              if (diff > 0.3) advice = '⬆️ 增加配置';
              else if (diff < -0.3) advice = '⬇️ 减少配置';
              else advice = '➡️ 维持不变';
              
              return `
                <tr>
                  <td>${s}</td>
                  <td>${current.toFixed(2)}x</td>
                  <td>${recommended.toFixed(2)}x</td>
                  <td class="${diff > 0 ? 'text-success' : 'text-danger'}">${diff > 0 ? '+' : ''}${diff.toFixed(2)}x</td>
                  <td>${advice}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
    
    <style>
      .sector-weight-container {
        background: white;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }
      
      .sector-weight-container h3 {
        margin: 0 0 20px 0;
        font-size: 16px;
        font-weight: 600;
      }
      
      .chart-wrapper-bar {
        margin-bottom: 24px;
        position: relative;
        height: 300px;
      }
      
      .weight-table {
        overflow-x: auto;
      }
      
      .weight-table table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      
      .weight-table th {
        background: #f3f4f6;
        padding: 12px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid #e5e7eb;
      }
      
      .weight-table td {
        padding: 12px;
        border-bottom: 1px solid #e5e7eb;
      }
      
      .weight-table tr:hover {
        background: #f9fafb;
      }
    </style>
  `;
  
  container.innerHTML = html;
  
  // 创建柱状图
  setTimeout(() => {
    if (typeof Chart !== 'undefined') {
      const ctx = document.getElementById('sectorWeightChart');
      if (ctx) {
        new Chart(ctx, {
          type: 'bar',
          data: chartData,
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'top',
              }
            },
            scales: {
              y: {
                beginAtZero: true,
              }
            }
          }
        });
      }
    }
  }, 100);
}

// =================== 初始化函数 ===================

document.addEventListener('DOMContentLoaded', function() {
  // 监听标签页切换到策略分析时加载数据
  const strategyTab = document.querySelector('[data-tab="strategy-analysis"]');
  if (strategyTab) {
    strategyTab.addEventListener('click', loadStrategyAnalysis);
  }
});

// 辅助函数
function showErrorNotification(message) {
  console.error(message);
  // 如果有通知系统，在这里集成
  const notification = document.createElement('div');
  notification.className = 'notification notification-error';
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #ef4444;
    color: white;
    padding: 12px 20px;
    border-radius: 6px;
    z-index: 10000;
    animation: slideIn 0.3s ease-out;
  `;
  document.body.appendChild(notification);
  setTimeout(() => notification.remove(), 5000);
}
