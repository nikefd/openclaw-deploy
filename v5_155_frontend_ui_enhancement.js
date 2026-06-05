/**
 * v5.155 - Frontend UI Enhancement
 * 
 * 盤中實時UI優化
 * - Real-time P&L updates via WebSocket
 * - Performance dashboard (Win Rate, Sharpe, Sortino, Max DD)
 * - News sentiment heatmap with color coding
 * - 3-minute auto-refresh
 */

(function() {
    'use strict';

    // ========================================================================
    // I. PERFORMANCE DASHBOARD RENDERER
    // ========================================================================

    const PerformanceDashboard = {
        init() {
            this.container = document.getElementById('performanceDashboard');
            if (!this.container) {
                this.createContainer();
            }
            this.refresh();
        },

        createContainer() {
            const html = `
                <div class="chart-row" id="performanceDashboard">
                    <div class="chart-box">
                        <h3>績效統計</h3>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px;">
                            <div>
                                <div class="card-label">勝率</div>
                                <div class="card-value" id="winRate">--</div>
                                <div style="font-size:12px;color:#6c757d;">%</div>
                            </div>
                            <div>
                                <div class="card-label">盈利因子</div>
                                <div class="card-value" id="profitFactor">--</div>
                            </div>
                            <div>
                                <div class="card-label">Sharpe比率</div>
                                <div class="card-value" id="sharpeRatio" style="font-size:18px;">--</div>
                            </div>
                            <div>
                                <div class="card-label">Sortino比率</div>
                                <div class="card-value" id="sortinoRatio" style="font-size:18px;">--</div>
                            </div>
                            <div style="grid-column:1/-1;">
                                <div class="card-label">最大回撤</div>
                                <div class="card-value down" id="maxDrawdown">--</div>
                                <div style="font-size:12px;color:#6c757d;">%</div>
                            </div>
                        </div>
                    </div>

                    <div class="chart-box">
                        <h3>新聞情緒</h3>
                        <div style="margin-top:12px;" id="sentimentAlerts">
                            <p style="text-align:center;color:#6c757d;">加載中...</p>
                        </div>
                    </div>

                    <div class="chart-box">
                        <h3>情緒熱力圖</h3>
                        <div style="display:grid;grid-template-columns:1fr;gap:6px;margin-top:12px;" id="sentimentHeatmap">
                            <p style="text-align:center;color:#6c757d;font-size:12px;">加載中...</p>
                        </div>
                    </div>
                </div>
            `;
            
            // 插入到content區域
            const content = document.querySelector('.content');
            if (content) {
                content.insertAdjacentHTML('beforeend', html);
            }
            
            this.container = document.getElementById('performanceDashboard');
        },

        refresh() {
            fetch('/api/intraday-stats')
                .then(r => r.json())
                .then(data => this.render(data))
                .catch(e => console.error('[PerformanceDashboard]', e));
        },

        render(data) {
            if (!data || !data.performance) return;

            const perf = data.performance;

            // 更新數值
            document.getElementById('winRate').textContent = 
                perf.win_rate_pct.toFixed(1);
            
            document.getElementById('profitFactor').textContent = 
                perf.profit_factor.toFixed(2);
            
            document.getElementById('sharpeRatio').textContent = 
                perf.sharpe_ratio.toFixed(2);
            
            document.getElementById('sortinoRatio').textContent = 
                perf.sortino_ratio.toFixed(2);
            
            document.getElementById('maxDrawdown').textContent = 
                perf.max_drawdown_pct.toFixed(1);

            // 情緒警報
            if (data.alerts && data.alerts.length > 0) {
                this.renderAlerts(data.alerts);
            }

            // 情緒熱力圖
            if (data.sentiment) {
                this.renderHeatmap(data.sentiment);
            }
        },

        renderAlerts(alerts) {
            const container = document.getElementById('sentimentAlerts');
            
            const html = alerts
                .slice(0, 5)
                .map(alert => `
                    <div style="
                        padding:8px 12px;
                        background:${alert.type === 'bullish' ? '#e8f5e9' : '#ffebee'};
                        border-left:3px solid ${alert.type === 'bullish' ? '#2ec4b6' : '#e63946'};
                        border-radius:4px;
                        font-size:12px;
                        margin-bottom:6px;
                    ">
                        <strong>${alert.symbol}</strong>: ${alert.label} (${alert.score})
                    </div>
                `)
                .join('');
            
            container.innerHTML = html || '<p style="color:#6c757d;font-size:12px;">無警報</p>';
        },

        renderHeatmap(sentiment) {
            const container = document.getElementById('sentimentHeatmap');
            
            const html = Object.entries(sentiment)
                .slice(0, 8)
                .map(([symbol, data]) => `
                    <div style="
                        padding:8px 12px;
                        background:${data.color};
                        color:#fff;
                        border-radius:6px;
                        font-size:12px;
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                    ">
                        <strong>${symbol}</strong>
                        <span>${data.score}</span>
                    </div>
                `)
                .join('');
            
            container.innerHTML = html;
        },
    };


    // ========================================================================
    // II. REALTIME P&L UPDATER (WebSocket simulation with polling)
    // ========================================================================

    const RealtimePLUpdater = {
        updateInterval: 1000,  // 1 second
        
        init() {
            this.startPolling();
        },

        startPolling() {
            setInterval(() => {
                this.updatePositions();
            }, this.updateInterval);
        },

        updatePositions() {
            fetch('/api/dashboard')
                .then(r => r.json())
                .then(data => {
                    if (data.positions) {
                        this.updatePositionTable(data.positions);
                        this.updatePLCard(data);
                    }
                })
                .catch(e => console.error('[RealtimePLUpdater]', e));
        },

        updatePositionTable(positions) {
            // 動態更新持倉表格中的實時P&L和百分比
            positions.forEach(pos => {
                const row = document.querySelector(`tr[data-symbol="${pos.symbol}"]`);
                if (row) {
                    // 更新現價
                    const priceCell = row.querySelector('[data-col="current_price"]');
                    if (priceCell) priceCell.textContent = pos.current_price.toFixed(2);
                    
                    // 更新P&L
                    const pnlCell = row.querySelector('[data-col="pnl"]');
                    if (pnlCell) {
                        pnlCell.textContent = pos.pnl.toFixed(2);
                        pnlCell.classList.toggle('up', pos.pnl > 0);
                        pnlCell.classList.toggle('down', pos.pnl < 0);
                    }
                    
                    // 更新P&L %
                    const pnlPctCell = row.querySelector('[data-col="pnl_pct"]');
                    if (pnlPctCell) {
                        pnlPctCell.textContent = pos.pnl_pct.toFixed(2) + '%';
                        pnlPctCell.classList.toggle('up', pos.pnl_pct > 0);
                        pnlPctCell.classList.toggle('down', pos.pnl_pct < 0);
                    }
                }
            });
        },

        updatePLCard(data) {
            if (!data.today_pnl) return;
            
            const card = document.getElementById('todayPnlCard');
            if (card) {
                card.querySelector('.card-value').textContent = data.today_pnl.toFixed(2);
                card.querySelector('.card-value').classList.toggle('up', data.today_pnl > 0);
                card.querySelector('.card-value').classList.toggle('down', data.today_pnl < 0);
            }
        },
    };


    // ========================================================================
    // III. AUTO-REFRESH MANAGER (3-minute sentiment, 1-second P&L)
    // ========================================================================

    const AutoRefreshManager = {
        sentimentRefreshInterval: 180000,  // 3 minutes
        
        init() {
            // 性能儀表板：3分鐘刷新
            setInterval(() => {
                PerformanceDashboard.refresh();
            }, this.sentimentRefreshInterval);
            
            // 實時P&L：1秒刷新（由RealtimePLUpdater處理）
        },
    };


    // ========================================================================
    // IV. MAIN INITIALIZATION
    // ========================================================================

    window.addEventListener('DOMContentLoaded', () => {
        console.log('[v5.155] Intraday UI Enhancement Starting...');
        
        // 初始化性能儀表板
        PerformanceDashboard.init();
        
        // 初始化實時P&L更新
        RealtimePLUpdater.init();
        
        // 初始化自動刷新
        AutoRefreshManager.init();
        
        console.log('[✅] v5.155 Intraday UI Enhancement Ready');
    });

})();
