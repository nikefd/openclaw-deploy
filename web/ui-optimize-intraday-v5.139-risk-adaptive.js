/**
 * UI优化 v5.139 - 盤中风险监控增强
 * 新增实时风险评分、贪婪度自适应指示、风控模式激活提示
 * 激活时间: 2026-05-29 03:30 UTC 盤中優化②
 */

(function() {
  'use strict';

  // === 风险评分引擎 (v5.139 Greedy Adaptive) ===
  window.RiskScoreEngine = {
    // 情绪级别判断
    getSentimentLevel: (score) => {
      if (score > 92) return { level: 'extreme_greed', label: '极度贪婪 🔥', color: '#ff6b6b', mode: 'high_risk' };
      if (score >= 85) return { level: 'greed', label: '贪婪', color: '#ff9800', mode: 'cautious' };
      if (score >= 40) return { level: 'normal', label: '中性', color: '#4361ee', mode: 'balanced' };
      if (score >= 20) return { level: 'fear', label: '恐慌', color: '#2ec4b6', mode: 'aggressive' };
      return { level: 'extreme_fear', label: '极度恐慌 ❄️', color: '#00bcd4', mode: 'max_buy' };
    },

    // 综合风险评分 (0-100)
    calcRiskScore: (data) => {
      let score = 50; // 基础分
      const { sentiment = 50, positions = [], account = {}, maxDD = 0 } = data;

      // 情绪因子 (±30分)
      const sentimentLevel = window.RiskScoreEngine.getSentimentLevel(sentiment);
      if (sentimentLevel.level === 'extreme_greed') score += 25;
      else if (sentimentLevel.level === 'greed') score += 15;
      else if (sentimentLevel.level === 'extreme_fear') score -= 25;
      else if (sentimentLevel.level === 'fear') score -= 15;

      // 仓位集中度 (±20分)
      if (positions && positions.length > 0) {
        const posValues = positions.map(p => (p.current_price || 0) * (p.shares || 0));
        const totalPos = posValues.reduce((s, v) => s + v, 0);
        const maxPos = totalPos > 0 ? Math.max(...posValues) / totalPos * 100 : 0;
        if (maxPos > 40) score += 15;
        else if (maxPos > 25) score += 8;
      }

      // 回撤因子 (±15分)
      if (maxDD < -10) score += 20;
      else if (maxDD < -5) score += 10;
      else if (maxDD > 0) score -= 5;

      // 现金占比 (±10分)
      if (account && account.total_value) {
        const cashRatio = (account.cash || 0) / account.total_value * 100;
        if (cashRatio < 10) score += 10; // 满仓风险
        else if (cashRatio > 80) score -= 8; // 现金过多
      }

      return Math.max(0, Math.min(100, score));
    },

    // 风控激活状态
    getControlStatus: (sentiment, riskScore, positions = []) => {
      const level = window.RiskScoreEngine.getSentimentLevel(sentiment);
      const posCount = positions.length;
      
      let status = {
        active: false,
        mode: 'normal',
        alerts: [],
        recommendations: []
      };

      if (level.level === 'extreme_greed') {
        status.active = true;
        status.mode = 'high_risk';
        status.alerts = [
          `⚠️ 贪婪度${sentiment.toFixed(1)}：停止新建仓位`,
          `🔴 启用加速止盈 (5%→25%, 10%→30%, 18%→25%)`,
          `📍 尾随止损紧缩至3% (从4%)`
        ];
        status.recommendations = [
          '持有现有头寸，等待回调',
          '对利润头寸启用分级止盈',
          '警惕高位回调风险'
        ];
      } else if (level.level === 'greed' && riskScore > 70) {
        status.active = true;
        status.mode = 'cautious';
        status.alerts = [
          `⚡ 贪婪行情：谨慎新建仓位`,
          `📊 保持仓位多样化`
        ];
        status.recommendations = [
          '限制单笔新建数量',
          '优先参与小盘高增长'
        ];
      } else if (level.level === 'fear' && riskScore < 30) {
        status.mode = 'aggressive';
        status.recommendations = [
          '恐慌期可积极建仓',
          '关注低估品种'
        ];
      }

      return status;
    },

    // 渲染风险监控面板
    renderRiskPanel: (data) => {
      const { sentiment = 50, account = {}, positions = [], maxDD = 0 } = data;
      
      const riskScore = window.RiskScoreEngine.calcRiskScore({ sentiment, positions, account, maxDD });
      const sentimentLevel = window.RiskScoreEngine.getSentimentLevel(sentiment);
      const controlStatus = window.RiskScoreEngine.getControlStatus(sentiment, riskScore, positions);

      // 风险评分条
      const riskColor = riskScore > 75 ? '#ff6b6b' : riskScore > 50 ? '#ff9800' : '#2ec4b6';
      
      const html = `
        <div style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:24px">
          <h3 style="font-size:14px;color:var(--sub);margin-bottom:20px">⚠️ 风险监控 (v5.139 Adaptive)</h3>
          
          <!-- 情绪 & 风险评分双指示 -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
            <!-- 情绪仪表盘 -->
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">📊 市场情绪</div>
              <div style="position:relative;width:100%;height:80px;display:flex;align-items:center;justify-content:center">
                <canvas id="sentimentGauge" width="120" height="80"></canvas>
              </div>
              <div style="font-size:16px;font-weight:700;color:${sentimentLevel.color};margin-top:8px">${sentimentLevel.label}</div>
              <div style="font-size:12px;color:var(--sub);margin-top:4px">Score: ${sentiment.toFixed(1)}</div>
            </div>

            <!-- 综合风险评分 -->
            <div style="background:var(--hover);border-radius:8px;padding:16px;text-align:center">
              <div style="font-size:12px;color:var(--sub);margin-bottom:8px">⚡ 综合风险评分</div>
              <div style="position:relative;width:100%;height:80px;display:flex;align-items:center;justify-content:center">
                <canvas id="riskScoreGauge" width="120" height="80"></canvas>
              </div>
              <div style="font-size:28px;font-weight:700;color:${riskColor};margin-top:8px">${riskScore.toFixed(0)}</div>
              <div style="font-size:12px;color:var(--sub);margin-top:4px">${riskScore > 75 ? '⚠️ 高风险' : riskScore > 50 ? '⚡ 中风险' : '✅ 低风险'}</div>
            </div>
          </div>

          <!-- 风控激活状态 -->
          ${controlStatus.active ? \`
            <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:16px;margin-bottom:16px">
              <div style="color:#856404;font-weight:600;margin-bottom:8px">🔔 风控模式激活: ${controlStatus.mode.toUpperCase()}</div>
              <ul style="list-style:none;padding:0;margin:0;color:#856404;font-size:12px">
                ${controlStatus.alerts.map(a => \`<li style="padding:4px 0">• \${a}</li>\`).join('')}
              </ul>
            </div>
          \` : ''}

          <!-- 建议 -->
          <div style="background:var(--hover);border-radius:8px;padding:16px">
            <div style="font-size:12px;color:var(--sub);margin-bottom:8px">💡 策略建议</div>
            <ul style="list-style:none;padding:0;margin:0;font-size:12px;color:var(--text)">
              ${controlStatus.recommendations.map(r => \`<li style="padding:4px 0">• \${r}</li>\`).join('')}
            </ul>
          </div>
        </div>
      `;

      return html;
    },

    // 绘制仪表盘
    drawGauges: () => {
      // 情绪仪表盘
      const sentimentCanvas = document.getElementById('sentimentGauge');
      if (sentimentCanvas) {
        const ctx = sentimentCanvas.getContext('2d');
        const sentiment = window.currentSentiment || 50;
        
        // 半圆仪表
        const centerX = sentimentCanvas.width / 2;
        const centerY = sentimentCanvas.height;
        const radius = 50;

        ctx.fillStyle = '#f0f0f5';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
        ctx.fill();

        // 刻度
        const startAngle = Math.PI;
        const endAngle = 2 * Math.PI;
        const angle = startAngle + (sentiment / 100) * (endAngle - startAngle);

        ctx.fillStyle = sentiment > 92 ? '#ff6b6b' : sentiment > 85 ? '#ff9800' : sentiment > 40 ? '#4361ee' : '#2ec4b6';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * 0.7, startAngle, angle);
        ctx.lineTo(centerX, centerY);
        ctx.fill();
      }

      // 风险评分仪表
      const riskCanvas = document.getElementById('riskScoreGauge');
      if (riskCanvas) {
        const ctx = riskCanvas.getContext('2d');
        const riskScore = window.currentRiskScore || 50;

        const centerX = riskCanvas.width / 2;
        const centerY = riskCanvas.height;
        const radius = 50;

        ctx.fillStyle = '#f0f0f5';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
        ctx.fill();

        const startAngle = Math.PI;
        const endAngle = 2 * Math.PI;
        const angle = startAngle + (riskScore / 100) * (endAngle - startAngle);

        ctx.fillStyle = riskScore > 75 ? '#ff6b6b' : riskScore > 50 ? '#ff9800' : '#2ec4b6';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * 0.7, startAngle, angle);
        ctx.lineTo(centerX, centerY);
        ctx.fill();
      }
    }
  };

  // === 全局刷新函数 ===
  window.refreshRiskMonitor = async () => {
    try {
      const res = await fetch('/api/dashboard');
      const data = await res.json();
      
      const panel = document.getElementById('enhanced-risk-panel');
      if (panel) {
        const maxDD = data.max_drawdown || 0;
        window.currentSentiment = data.sentiment?.score || 50;
        window.currentRiskScore = window.RiskScoreEngine.calcRiskScore({
          sentiment: window.currentSentiment,
          positions: data.positions || [],
          account: data.account || {},
          maxDD
        });

        panel.innerHTML = window.RiskScoreEngine.renderRiskPanel({
          sentiment: window.currentSentiment,
          account: data.account || {},
          positions: data.positions || [],
          maxDD
        });

        // 延迟绘制仪表盘
        setTimeout(() => window.RiskScoreEngine.drawGauges(), 100);
      }
    } catch (e) {
      console.error('风险监控刷新失败:', e);
    }
  };

  // === 初始化注入 ===
  document.addEventListener('DOMContentLoaded', () => {
    const riskPanel = document.getElementById('panel-riskmonitor');
    if (riskPanel && !document.getElementById('enhanced-risk-panel')) {
      const div = document.createElement('div');
      div.id = 'enhanced-risk-panel';
      riskPanel.insertBefore(div, riskPanel.firstChild);
      window.refreshRiskMonitor();
    }
  });

})();
