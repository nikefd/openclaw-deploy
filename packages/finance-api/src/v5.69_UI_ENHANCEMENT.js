/**
 * v5.69 UI 增强补丁
 * 新增功能：
 * 1. 情绪指标仪表板（新标签页）- 市场情绪、新闻热度、策略动量可视化
 * 2. 回测性能对比面板（新标签页）- v5.68 vs 历史版本性能对标
 * 
 * 集成方式：
 * - 在 finance.html 的 </head> 前添加此脚本标签
 * - 新增 API 端点由 finance-api-server.js 提供
 */

// ==================== 1. 情绪指标仪表板 ====================
async function loadSentimentDashboard() {
  const d = await api('/api/finance/sentiment-dashboard');
  if (!d) return;

  const container = document.getElementById('sentimentDashboard');
  if (!container) return;

  // 情绪评分卡片
  const sentimentColor = d.overall_score >= 70 ? '#2ec4b6' : d.overall_score >= 40 ? '#ffd166' : '#e63946';
  const sentimentLabel = d.overall_score >= 70 ? '乐观' : d.overall_score >= 40 ? '中性' : '悲观';

  let html = `
    <div class="sentiment-cards">
      <div class="sentiment-score-card" style="border-left: 4px solid ${sentimentColor}">
        <div class="card-label">综合情绪评分</div>
        <div class="card-value" style="color: ${sentimentColor}">${d.overall_score}</div>
        <div class="card-desc">${sentimentLabel}</div>
      </div>

      <div class="sentiment-metric">
        <div class="metric-label">新闻情绪</div>
        <div class="metric-value up">${d.news_sentiment > 0 ? '+' : ''}${d.news_sentiment}%</div>
        <div class="metric-bar">
          <div class="bar-fill" style="width: ${Math.max(10, Math.min(90, d.news_sentiment + 50))}%; background: ${d.news_sentiment > 0 ? '#2ec4b6' : '#e63946'};"></div>
        </div>
      </div>

      <div class="sentiment-metric">
        <div class="metric-label">持仓热度</div>
        <div class="metric-value">${d.position_heat}°</div>
        <div class="metric-bar">
          <div class="bar-fill" style="width: ${Math.min(90, d.position_heat / 100 * 90)}%; background: #ffd166;"></div>
        </div>
      </div>

      <div class="sentiment-metric">
        <div class="metric-label">策略动量</div>
        <div class="metric-value" style="color: ${d.strategy_momentum > 0 ? '#2ec4b6' : '#e63946'}">${d.strategy_momentum > 0 ? '+' : ''}${d.strategy_momentum}</div>
        <div class="metric-bar">
          <div class="bar-fill" style="width: ${Math.max(10, Math.min(90, d.strategy_momentum * 5 + 50))}%; background: ${d.strategy_momentum > 0 ? '#2ec4b6' : '#e63946'};"></div>
        </div>
      </div>
    </div>

    <div class="sentiment-timeline">
      <h3>近7日情绪走势</h3>
      <canvas id="sentimentTrendChart" style="max-height: 300px;"></canvas>
    </div>

    <div class="sentiment-details">
      <div class="detail-section">
        <h4>热点新闻（${d.top_news?.length || 0}条）</h4>
        <div class="news-list">
          ${(d.top_news || []).slice(0, 5).map(n => `
            <div class="news-item">
              <span class="news-badge" style="background: ${n.sentiment > 0 ? '#2ec4b6' : '#e63946'}">${n.sentiment > 0 ? '利好' : '利空'}</span>
              <span class="news-text">${n.title}</span>
              <span class="news-time">${n.time}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="detail-section">
        <h4>策略执行统计</h4>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-label">今日信号</div>
            <div class="stat-value">${d.today_signals}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">入场数</div>
            <div class="stat-value">${d.entry_count}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">止损数</div>
            <div class="stat-value">${d.stop_loss_count}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">获利数</div>
            <div class="stat-value" style="color: #2ec4b6">${d.profit_count}</div>
          </div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;

  // 绘制情绪趋势图
  if (d.sentiment_trend && d.sentiment_trend.length > 0) {
    const ctx = document.getElementById('sentimentTrendChart');
    if (ctx) {
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: d.sentiment_trend.map(p => p.date),
          datasets: [{
            label: '情绪评分',
            data: d.sentiment_trend.map(p => p.score),
            borderColor: '#4361ee',
            backgroundColor: 'rgba(67, 97, 238, 0.1)',
            tension: 0.3,
            fill: true,
            pointRadius: 4,
            pointBackgroundColor: '#4361ee'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              min: 0, max: 100,
              grid: { color: '#e5e5ea' },
              ticks: { font: { size: 11 } }
            }
          }
        }
      });
    }
  }
}

// ==================== 2. 回测性能对比面板 ====================
async function loadBacktestComparison() {
  const d = await api('/api/finance/backtest-comparison');
  if (!d) return;

  const container = document.getElementById('backtestComparison');
  if (!container) return;

  const compareMetrics = [
    { key: 'total_return_pct', label: '总收益率', fmt: v => v.toFixed(2) + '%' },
    { key: 'max_drawdown', label: '最大回撤', fmt: v => v.toFixed(2) + '%' },
    { key: 'sharpe_ratio', label: 'Sharpe比率', fmt: v => v.toFixed(2) },
    { key: 'win_rate', label: '胜率', fmt: v => v.toFixed(1) + '%' },
    { key: 'profit_factor', label: '盈利因子', fmt: v => v.toFixed(2) },
  ];

  let html = `
    <div class="backtest-comparison-table">
      <table>
        <thead>
          <tr>
            <th>版本</th>
            <th>开始日期</th>
            <th>回测周期</th>
            ${compareMetrics.map(m => `<th>${m.label}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
  `;

  (d.results || []).slice(0, 3).forEach((r, idx) => {
    const bgClass = idx === 0 ? ' style="background: rgba(46, 196, 182, 0.05)"' : '';
    html += `
      <tr${bgClass}>
        <td><strong>${r.strategy}</strong>${idx === 0 ? ' <span style="color: #2ec4b6; font-size: 11px;">【当前】</span>' : ''}</td>
        <td>${r.start_date}</td>
        <td>${r.days} 天</td>
    `;
    compareMetrics.forEach(m => {
      const val = r[m.key] || 0;
      const color = m.key === 'max_drawdown' ? (val > 5 ? '#e63946' : val > 3 ? '#ffd166' : '#2ec4b6') 
                  : m.key === 'win_rate' ? (val > 55 ? '#2ec4b6' : val > 45 ? '#ffd166' : '#e63946')
                  : (val > 0 ? '#2ec4b6' : '#e63946');
      html += `<td style="color: ${color}">${m.fmt(val)}</td>`;
    });
    html += '</tr>';
  });

  html += `
        </tbody>
      </table>
    </div>

    <div class="backtest-improvement">
      <h3>v5.68 vs v5.67 改进</h3>
      <div class="improvement-items">
  `;

  (d.improvements || []).forEach(imp => {
    const improvement = imp.current - imp.previous;
    const improvementPct = imp.previous !== 0 ? (improvement / Math.abs(imp.previous) * 100) : 0;
    const isPositive = (imp.key === 'max_drawdown' || imp.key === 'total_days_under_peak') ? improvement < 0 : improvement > 0;
    const color = isPositive ? '#2ec4b6' : '#e63946';

    html += `
      <div class="improvement-item" style="border-left: 3px solid ${color}">
        <div class="imp-label">${imp.label}</div>
        <div class="imp-value">
          <span style="color: ${color}">${improvement > 0 ? '+' : ''}${improvement.toFixed(2)}</span>
          <span style="color: #8a8a9a; font-size: 12px;">(${improvementPct > 0 ? '+' : ''}${improvementPct.toFixed(1)}%)</span>
        </div>
      </div>
    `;
  });

  html += `
      </div>
    </div>

    <div class="backtest-heatmap">
      <h3>月度收益分布</h3>
      <canvas id="backtestReturnsChart" style="max-height: 250px;"></canvas>
    </div>
  `;

  container.innerHTML = html;

  // 月度收益图表
  if (d.monthly_returns && d.monthly_returns.length > 0) {
    const ctx = document.getElementById('backtestReturnsChart');
    if (ctx) {
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: d.monthly_returns.map(m => m.month),
          datasets: [{
            label: '月收益率',
            data: d.monthly_returns.map(m => m.return_pct),
            backgroundColor: d.monthly_returns.map(m => m.return_pct >= 0 ? 'rgba(46, 196, 182, 0.7)' : 'rgba(230, 57, 70, 0.7)'),
            borderRadius: 6
          }]
        },
        options: {
          indexAxis: undefined,
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            y: { grid: { color: '#e5e5ea' }, ticks: { callback: v => v + '%' } }
          }
        }
      });
    }
  }
}

// ==================== 样式 ====================
const sentimentStyles = `
<style>
.sentiment-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.sentiment-score-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.card-label {
  font-size: 12px;
  color: var(--sub);
  margin-bottom: 8px;
}

.card-value {
  font-size: 36px;
  font-weight: 700;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 13px;
  color: var(--sub);
}

.sentiment-metric {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
}

.metric-label {
  font-size: 12px;
  color: var(--sub);
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 8px;
}

.metric-bar {
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.sentiment-timeline {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 24px;
}

.sentiment-timeline h3 {
  font-size: 14px;
  margin-bottom: 16px;
}

.sentiment-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.detail-section {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

.detail-section h4 {
  font-size: 13px;
  margin-bottom: 12px;
  color: var(--sub);
  font-weight: 500;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.news-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.news-item:last-child {
  border-bottom: none;
}

.news-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: white;
  font-weight: 500;
}

.news-text {
  flex: 1;
  color: var(--text);
}

.news-time {
  color: var(--sub);
  font-size: 11px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-item {
  background: var(--hover);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.stat-label {
  font-size: 11px;
  color: var(--sub);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}

/* 回测对比样式 */
.backtest-comparison-table {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 24px;
  overflow-x: auto;
}

.backtest-comparison-table table {
  width: 100%;
  font-size: 13px;
}

.backtest-comparison-table th,
.backtest-comparison-table td {
  padding: 12px 8px;
  text-align: right;
}

.backtest-comparison-table th:first-child,
.backtest-comparison-table td:first-child {
  text-align: left;
}

.backtest-improvement {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 24px;
}

.backtest-improvement h3 {
  font-size: 14px;
  margin-bottom: 16px;
}

.improvement-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.improvement-item {
  background: var(--hover);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  justify-content: space-between;
}

.imp-label {
  font-size: 12px;
  color: var(--sub);
}

.imp-value {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.backtest-heatmap {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

.backtest-heatmap h3 {
  font-size: 14px;
  margin-bottom: 16px;
}

body.dark .backtest-comparison-table th {
  color: #8a8a9a;
}
</style>
`;

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
  if (document.head) {
    document.head.insertAdjacentHTML('beforeend', sentimentStyles);
  }
});

// 导出函数供外部调用
window.loadSentimentDashboard = loadSentimentDashboard;
window.loadBacktestComparison = loadBacktestComparison;
