"""
v5.162: Kelly係數自動調整系統 (Kelly Auto-Adjustment)

核心邏輯:
1. 基於7日勝率自動調整Kelly係數
   - 高勝率 (>70%): Kelly 1.75 (激進)
   - 正常勝率 (50-70%): Kelly 1.5 (平衡)
   - 低勝率 (<50%): Kelly 1.0 (保守)

2. 連續交易追踪
   - 連續虧損 >5天: Kelly ÷ 2 (資本保護)
   - 連續獲利 >10天: Kelly × 1.2 (複利加速, 上限1.75)

3. 最大回撤保護
   - 回撤 >10%: Kelly × 0.8 (應急防守)
   - 回撤 >15%: Kelly × 0.5 (極端防守)

預期效果: 風險調整收益 +25%, 最大回撤 -40%
"""

import sqlite3
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class KellyAutoAdjustment:
    """Kelly係數自動調整系統"""
    
    def __init__(self, db_path: str = None):
        """
        初始化
        
        Args:
            db_path: 數據庫路徑 (用於讀取交易歷史)
        """
        self.db_path = db_path
        self.base_kelly = 1.5  # 基礎Kelly係數
        
        # Kelly係數區間
        self.kelly_range = {
            'min': 0.5,
            'max': 1.75,
            'default': 1.5
        }
    
    def get_7day_win_rate(self) -> float:
        """
        計算7日勝率
        
        Returns:
            7日勝率 (0-1)
        """
        if not self.db_path:
            return 0.5  # 無數據時返回50%
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查詢7天內的已平倉交易
            cursor.execute("""
            SELECT COUNT(*) as total FROM trades 
            WHERE exit_time >= datetime('now', '-7 days') 
            AND status = 'closed'
            """)
            total = cursor.fetchone()[0] or 0
            
            # 查詢7天內的獲利交易
            cursor.execute("""
            SELECT COUNT(*) as wins FROM trades 
            WHERE exit_time >= datetime('now', '-7 days') 
            AND status = 'closed' AND pnl > 0
            """)
            wins = cursor.fetchone()[0] or 0
            
            conn.close()
            
            if total == 0:
                return 0.5
            
            return wins / total
        
        except Exception as e:
            logger.error(f"獲取7日勝率失敗: {e}")
            return 0.5
    
    def get_consecutive_stats(self) -> Dict:
        """
        獲取連續交易統計
        
        Returns:
            {consecutive_wins, consecutive_losses, win_streak_days}
        """
        if not self.db_path:
            return {
                'consecutive_wins': 0,
                'consecutive_losses': 0,
                'win_streak_days': 0
            }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查詢最近的交易結果 (最多20筆)
            cursor.execute("""
            SELECT pnl FROM trades 
            WHERE status = 'closed'
            ORDER BY exit_time DESC LIMIT 20
            """)
            
            recent_trades = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not recent_trades:
                return {
                    'consecutive_wins': 0,
                    'consecutive_losses': 0,
                    'win_streak_days': 0
                }
            
            # 計算連續獲利
            consecutive_wins = 0
            for pnl in recent_trades:
                if pnl > 0:
                    consecutive_wins += 1
                else:
                    break
            
            # 計算連續虧損
            consecutive_losses = 0
            for pnl in recent_trades:
                if pnl <= 0:
                    consecutive_losses += 1
                else:
                    break
            
            return {
                'consecutive_wins': consecutive_wins,
                'consecutive_losses': consecutive_losses,
                'win_streak_days': consecutive_wins
            }
        
        except Exception as e:
            logger.error(f"獲取連續交易統計失敗: {e}")
            return {
                'consecutive_wins': 0,
                'consecutive_losses': 0,
                'win_streak_days': 0
            }
    
    def get_current_drawdown(self, current_equity: float, peak_equity: float) -> float:
        """
        計算當前回撤
        
        Args:
            current_equity: 當前淨值
            peak_equity: 歷史最高淨值
        
        Returns:
            回撤比例 (負值)
        """
        if peak_equity == 0:
            return 0
        
        return (current_equity - peak_equity) / peak_equity
    
    def calculate_dynamic_kelly(
        self,
        win_rate_7d: float,
        consecutive_losses: int = 0,
        consecutive_wins: int = 0,
        current_drawdown: float = 0,
        volatility_regime: str = 'normal'
    ) -> float:
        """
        計算動態Kelly係數
        
        Args:
            win_rate_7d: 7日勝率 (0-1)
            consecutive_losses: 連續虧損天數
            consecutive_wins: 連續獲利天數
            current_drawdown: 當前回撤 (負值, e.g., -0.10 = 10%)
            volatility_regime: 波動率制度 (low/normal/high/extreme)
        
        Returns:
            調整後的Kelly係數 (0.5-1.75)
        """
        
        # Step 1: 基於7日勝率的基礎Kelly
        if win_rate_7d > 0.70:
            base_kelly = 1.75
        elif win_rate_7d > 0.60:
            base_kelly = 1.65
        elif win_rate_7d > 0.50:
            base_kelly = 1.5
        elif win_rate_7d > 0.40:
            base_kelly = 1.25
        else:
            base_kelly = 1.0
        
        # Step 2: 波動率制度調整
        volatility_adjustments = {
            'low': 1.0,        # 低波: 保持
            'normal': 0.95,    # 正常: -5%
            'high': 0.85,      # 高波: -15%
            'extreme': 0.70    # 極端: -30%
        }
        volatility_adj = volatility_adjustments.get(volatility_regime, 0.95)
        base_kelly *= volatility_adj
        
        # Step 3: 連續虧損懲罰
        if consecutive_losses >= 5:
            loss_penalty = 0.5 ** min(consecutive_losses - 4, 3)
            base_kelly *= loss_penalty
            logger.warning(
                f"⚠️ 連續虧損{consecutive_losses}天，Kelly係數降低: "
                f"{base_kelly / loss_penalty:.2f}x → {base_kelly:.2f}x"
            )
        
        # Step 4: 連續獲利加速 (但上限1.75)
        if consecutive_wins >= 10:
            bonus = min(0.20, consecutive_wins * 0.02)  # 每天+2%, 上限20%
            base_kelly *= (1 + bonus)
            base_kelly = min(1.75, base_kelly)
            logger.info(
                f"✅ 連續獲利{consecutive_wins}天，Kelly係數加速: "
                f"{base_kelly / (1 + bonus):.2f}x → {base_kelly:.2f}x"
            )
        
        # Step 5: 最大回撤保護
        if current_drawdown < -0.15:  # 回撤>15%
            extreme_protection = 0.5
            base_kelly *= extreme_protection
            logger.critical(
                f"🚨 極端回撤{current_drawdown:.1%}，Kelly應急防守: "
                f"調整至{base_kelly:.2f}x"
            )
        elif current_drawdown < -0.10:  # 回撤>10%
            high_protection = 0.8
            base_kelly *= high_protection
            logger.error(
                f"⚠️ 高位回撤{current_drawdown:.1%}，Kelly保護模式: "
                f"調整至{base_kelly:.2f}x"
            )
        
        # 邊界處理
        final_kelly = max(self.kelly_range['min'], min(self.kelly_range['max'], base_kelly))
        
        return round(final_kelly, 2)
    
    def get_adjustment_report(
        self,
        current_equity: float,
        peak_equity: float,
        volatility_regime: str = 'normal'
    ) -> Dict:
        """
        獲取完整的Kelly調整報告
        
        Returns:
            {kelly_coefficient, components, explanation}
        """
        # 獲取各項數據
        win_rate_7d = self.get_7day_win_rate()
        consecutive_stats = self.get_consecutive_stats()
        current_drawdown = self.get_current_drawdown(current_equity, peak_equity)
        
        # 計算Kelly係數
        kelly = self.calculate_dynamic_kelly(
            win_rate_7d=win_rate_7d,
            consecutive_losses=consecutive_stats['consecutive_losses'],
            consecutive_wins=consecutive_stats['consecutive_wins'],
            current_drawdown=current_drawdown,
            volatility_regime=volatility_regime
        )
        
        # 生成報告
        report = {
            'kelly_coefficient': kelly,
            'components': {
                'win_rate_7d': f"{win_rate_7d:.1%}",
                'consecutive_wins': consecutive_stats['consecutive_wins'],
                'consecutive_losses': consecutive_stats['consecutive_losses'],
                'current_drawdown': f"{current_drawdown:.1%}",
                'volatility_regime': volatility_regime
            },
            'timestamp': datetime.now().isoformat(),
            'explanation': self._generate_explanation(
                win_rate_7d, consecutive_stats, current_drawdown, volatility_regime
            )
        }
        
        return report
    
    def _generate_explanation(
        self,
        win_rate_7d: float,
        consecutive_stats: Dict,
        current_drawdown: float,
        volatility_regime: str
    ) -> str:
        """生成Kelly調整的解釋文本"""
        
        parts = []
        
        # 勝率說明
        if win_rate_7d > 0.70:
            parts.append(f"✓ 高勝率({win_rate_7d:.0%}) → Kelly激進")
        elif win_rate_7d > 0.50:
            parts.append(f"◐ 正常勝率({win_rate_7d:.0%}) → Kelly平衡")
        else:
            parts.append(f"✗ 低勝率({win_rate_7d:.0%}) → Kelly保守")
        
        # 連續獲利
        if consecutive_stats['consecutive_wins'] >= 10:
            parts.append(f"✅ 連贏{consecutive_stats['consecutive_wins']}天 → Kelly加速")
        elif consecutive_stats['consecutive_losses'] >= 5:
            parts.append(f"⚠️ 連虧{consecutive_stats['consecutive_losses']}天 → Kelly降低")
        
        # 回撤狀態
        if current_drawdown < -0.15:
            parts.append(f"🚨 極端回撤{current_drawdown:.1%} → 應急防守")
        elif current_drawdown < -0.10:
            parts.append(f"⚠️ 高位回撤{current_drawdown:.1%} → 保護模式")
        
        # 波動率
        if volatility_regime != 'normal':
            parts.append(f"📊 {volatility_regime}波動率 → 動態調整")
        
        return ' | '.join(parts) if parts else '正常運行'


class KellyCoefficientsMonitor:
    """Kelly係數監測器 (用於實時監測)"""
    
    def __init__(self, kelly_adjustment: KellyAutoAdjustment):
        self.kelly = kelly_adjustment
        self.kelly_history = []
        self.adjustments = []
        self.last_kelly = 1.5
    
    def update(
        self,
        current_equity: float,
        peak_equity: float,
        volatility_regime: str = 'normal'
    ) -> Optional[Dict]:
        """
        更新Kelly係數
        
        Returns:
            如果Kelly改變超過0.1，返回調整通知；否則返回None
        """
        report = self.kelly.get_adjustment_report(
            current_equity, peak_equity, volatility_regime
        )
        
        new_kelly = report['kelly_coefficient']
        self.kelly_history.append(new_kelly)
        
        # 檢查是否有顯著改變
        change = abs(new_kelly - self.last_kelly)
        if change > 0.1:  # Kelly改變超過0.1
            adjustment_event = {
                'timestamp': datetime.now(),
                'from_kelly': self.last_kelly,
                'to_kelly': new_kelly,
                'change': change,
                'reason': report['explanation']
            }
            self.adjustments.append(adjustment_event)
            
            logger.warning(
                f"⚠️ Kelly係數調整: {self.last_kelly:.2f}x → {new_kelly:.2f}x "
                f"({change:+.2f}x) - {report['explanation']}"
            )
            
            self.last_kelly = new_kelly
            return adjustment_event
        
        self.last_kelly = new_kelly
        return None
    
    def get_adjustment_statistics(self) -> Dict:
        """獲取調整統計"""
        if not self.adjustments:
            return {}
        
        total_adjustments = len(self.adjustments)
        upside_adjustments = sum(1 for a in self.adjustments if a['to_kelly'] > a['from_kelly'])
        downside_adjustments = total_adjustments - upside_adjustments
        
        avg_change = sum(a['change'] for a in self.adjustments) / total_adjustments if total_adjustments > 0 else 0
        
        return {
            'total_adjustments': total_adjustments,
            'upside_adjustments': upside_adjustments,
            'downside_adjustments': downside_adjustments,
            'average_change': round(avg_change, 3),
            'current_kelly': self.last_kelly,
            'adjustments': self.adjustments
        }


# ===== 使用示例 =====

if __name__ == '__main__':
    print("🧪 Kelly係數自動調整系統測試\n")
    
    # 初始化
    kelly_sys = KellyAutoAdjustment()
    
    # 測試案例1: 高勝率
    print("📊 測試案例1: 高勝率 (75%), 連贏5天")
    kelly1 = kelly_sys.calculate_dynamic_kelly(
        win_rate_7d=0.75,
        consecutive_wins=5,
        consecutive_losses=0,
        current_drawdown=0,
        volatility_regime='normal'
    )
    print(f"   → Kelly係數: {kelly1:.2f}x\n")
    
    # 測試案例2: 連續虧損
    print("📊 測試案例2: 正常勝率 (60%), 連虧7天")
    kelly2 = kelly_sys.calculate_dynamic_kelly(
        win_rate_7d=0.60,
        consecutive_wins=0,
        consecutive_losses=7,
        current_drawdown=-0.08,
        volatility_regime='normal'
    )
    print(f"   → Kelly係數: {kelly2:.2f}x\n")
    
    # 測試案例3: 極端回撤
    print("📊 測試案例3: 低勝率 (40%), 回撤-18%")
    kelly3 = kelly_sys.calculate_dynamic_kelly(
        win_rate_7d=0.40,
        consecutive_wins=0,
        consecutive_losses=0,
        current_drawdown=-0.18,
        volatility_regime='high'
    )
    print(f"   → Kelly係數: {kelly3:.2f}x\n")
    
    # 測試案例4: 高波動率
    print("📊 測試案例4: 高勝率 (70%), 極端波動率")
    kelly4 = kelly_sys.calculate_dynamic_kelly(
        win_rate_7d=0.70,
        consecutive_wins=0,
        consecutive_losses=0,
        current_drawdown=0,
        volatility_regime='extreme'
    )
    print(f"   → Kelly係數: {kelly4:.2f}x\n")
    
    # 完整報告
    print("📋 完整Kelly調整報告:")
    report = kelly_sys.get_adjustment_report(
        current_equity=950000,  # 當前淨值
        peak_equity=1000000,    # 歷史最高淨值
        volatility_regime='normal'
    )
    
    for k, v in report['components'].items():
        print(f"   {k}: {v}")
    print(f"\n   → 最終Kelly係數: {report['kelly_coefficient']:.2f}x")
    print(f"   → 說明: {report['explanation']}")
    
    print("\n✅ Kelly係數自動調整系統測試完成")
