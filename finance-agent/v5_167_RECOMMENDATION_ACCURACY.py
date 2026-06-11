"""
v5.167 实盘推荐准确率分析与历史追踪系统
================================================================================
分析历史推荐的实际成功率，识别高置信度推荐组合

核心功能:
  1. 追踪每次推荐的实际表现 (ROI%, 持仓天数, 是否止损)
  2. 分析推荐准确率 (按策略/sector/质量等级)
  3. 构建高置信度推荐特征库
  4. 优化后续选股的参数配置

================================================================================
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

# ============================================================================
# Part 1: 实盘推荐历史追踪
# ============================================================================

class RecommendationHistoryTrackerV167:
    """
    追踪推荐历史 & 实际交易表现
    """
    
    def __init__(self, db_path='data/finance.db'):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """确保表存在"""
        try:
            c = sqlite3.connect(self.db_path)
            
            # 推荐历史表
            c.execute("""
                CREATE TABLE IF NOT EXISTS v5_167_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    symbol TEXT,
                    strategy TEXT,
                    sector TEXT,
                    entry_quality REAL,
                    predicted_return REAL,
                    actual_return REAL,
                    status TEXT,
                    days_held INTEGER,
                    stopped_loss BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS v5_167_accuracy_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT,
                    metric_key TEXT,
                    hit_count INTEGER,
                    total_count INTEGER,
                    accuracy_rate REAL,
                    avg_return REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            c.commit()
            c.close()
            logger.info("✅ 推荐历史表已准备")
        except Exception as e:
            logger.error(f"❌ 表创建失败: {e}")
    
    def record_recommendation(self, 
                            symbol: str,
                            strategy: str,
                            sector: str,
                            entry_quality: float,
                            predicted_return: float) -> int:
        """
        记录一次推荐
        returns: recommendation_id
        """
        try:
            c = sqlite3.connect(self.db_path)
            
            cursor = c.execute("""
                INSERT INTO v5_167_recommendations 
                (date, symbol, strategy, sector, entry_quality, predicted_return, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                symbol,
                strategy,
                sector,
                entry_quality,
                predicted_return,
                'OPEN',
            ))
            
            c.commit()
            rec_id = cursor.lastrowid
            c.close()
            
            return rec_id
        except Exception as e:
            logger.error(f"❌ 记录推荐失败: {e}")
            return -1
    
    def close_recommendation(self,
                            rec_id: int,
                            actual_return: float,
                            days_held: int,
                            stopped_loss: bool = False):
        """
        关闭推荐记录 (交易完成)
        """
        try:
            c = sqlite3.connect(self.db_path)
            
            c.execute("""
                UPDATE v5_167_recommendations
                SET actual_return = ?,
                    days_held = ?,
                    stopped_loss = ?,
                    status = ?,
                    closed_at = ?
                WHERE id = ?
            """, (
                actual_return,
                days_held,
                stopped_loss,
                'CLOSED',
                datetime.now(),
                rec_id,
            ))
            
            c.commit()
            c.close()
            logger.info(f"✅ 推荐 {rec_id} 已关闭 (收益: {actual_return}%)")
        except Exception as e:
            logger.error(f"❌ 关闭推荐失败: {e}")


# ============================================================================
# Part 2: 推荐准确率分析
# ============================================================================

class AccuracyAnalyzerV167:
    """
    多维度分析推荐准确率
    """
    
    def __init__(self, db_path='data/finance.db'):
        self.db_path = db_path
    
    def calculate_hit_rate(self, 
                          min_return_threshold: float = 0.0) -> Dict:
        """
        计算命中率 (实际收益 > 阈值)
        """
        try:
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            
            rows = c.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_return > ? THEN 1 ELSE 0 END) as hits,
                    AVG(actual_return) as avg_return,
                    AVG(predicted_return) as avg_predicted,
                    ROUND(AVG(actual_return - predicted_return), 2) as prediction_error
                FROM v5_167_recommendations
                WHERE status = 'CLOSED'
            """, (min_return_threshold,)).fetchone()
            
            c.close()
            
            if not rows or rows['total'] == 0:
                return {'hit_rate': 0, 'total': 0, 'hits': 0}
            
            return {
                'hit_rate': rows['hits'] / rows['total'] * 100,
                'total': rows['total'],
                'hits': rows['hits'],
                'avg_return': rows['avg_return'],
                'avg_predicted': rows['avg_predicted'],
                'prediction_error': rows['prediction_error'],
            }
        except Exception as e:
            logger.error(f"❌ 计算命中率失败: {e}")
            return {}
    
    def calculate_by_strategy(self) -> Dict[str, Dict]:
        """
        按策略计算准确率
        """
        try:
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            
            rows = c.execute("""
                SELECT 
                    strategy,
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) as hits,
                    AVG(actual_return) as avg_return,
                    MIN(actual_return) as min_return,
                    MAX(actual_return) as max_return
                FROM v5_167_recommendations
                WHERE status = 'CLOSED'
                GROUP BY strategy
                ORDER BY hits DESC
            """).fetchall()
            
            c.close()
            
            result = {}
            for r in rows:
                hit_rate = (r['hits'] / r['total'] * 100) if r['total'] > 0 else 0
                result[r['strategy']] = {
                    'total': r['total'],
                    'hits': r['hits'],
                    'hit_rate': hit_rate,
                    'avg_return': r['avg_return'],
                    'min_return': r['min_return'],
                    'max_return': r['max_return'],
                }
            
            return result
        except Exception as e:
            logger.error(f"❌ 按策略计算失败: {e}")
            return {}
    
    def calculate_by_sector(self) -> Dict[str, Dict]:
        """按sector计算准确率"""
        try:
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            
            rows = c.execute("""
                SELECT 
                    sector,
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) as hits,
                    AVG(actual_return) as avg_return,
                    AVG(CASE WHEN stopped_loss THEN 1 ELSE 0 END) as stop_loss_rate
                FROM v5_167_recommendations
                WHERE status = 'CLOSED'
                GROUP BY sector
                ORDER BY hits DESC
            """).fetchall()
            
            c.close()
            
            result = {}
            for r in rows:
                hit_rate = (r['hits'] / r['total'] * 100) if r['total'] > 0 else 0
                result[r['sector']] = {
                    'total': r['total'],
                    'hits': r['hits'],
                    'hit_rate': hit_rate,
                    'avg_return': r['avg_return'],
                    'stop_loss_rate': r['stop_loss_rate'],
                }
            
            return result
        except Exception as e:
            logger.error(f"❌ 按sector计算失败: {e}")
            return {}
    
    def calculate_by_quality_level(self) -> Dict[str, Dict]:
        """
        按entry_quality等级计算准确率
        """
        try:
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            
            rows = c.execute("""
                SELECT 
                    CASE 
                        WHEN entry_quality >= 80 THEN '优秀(80+)'
                        WHEN entry_quality >= 70 THEN '良好(70-79)'
                        WHEN entry_quality >= 60 THEN '中等(60-69)'
                        ELSE '较弱(<60)'
                    END as quality_level,
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) as hits,
                    AVG(actual_return) as avg_return
                FROM v5_167_recommendations
                WHERE status = 'CLOSED'
                GROUP BY quality_level
                ORDER BY quality_level DESC
            """).fetchall()
            
            c.close()
            
            result = {}
            for r in rows:
                hit_rate = (r['hits'] / r['total'] * 100) if r['total'] > 0 else 0
                result[r['quality_level']] = {
                    'total': r['total'],
                    'hits': r['hits'],
                    'hit_rate': hit_rate,
                    'avg_return': r['avg_return'],
                }
            
            return result
        except Exception as e:
            logger.error(f"❌ 按质量等级计算失败: {e}")
            return {}


# ============================================================================
# Part 3: 高置信度推荐特征库
# ============================================================================

class HighConfidenceProfileV167:
    """
    根据实盘数据构建高置信度推荐特征
    """
    
    def __init__(self, accuracy_analyzer: AccuracyAnalyzerV167):
        self.analyzer = accuracy_analyzer
    
    def identify_best_strategy_sector_combo(self) -> List[Tuple[str, str, float]]:
        """
        识别命中率最高的 (strategy, sector) 组合
        returns: [(strategy, sector, hit_rate), ...]
        """
        try:
            db = sqlite3.connect(self.analyzer.db_path)
            db.row_factory = sqlite3.Row
            
            rows = db.execute("""
                SELECT 
                    strategy,
                    sector,
                    COUNT(*) as total,
                    SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) as hits,
                    ROUND(
                        SUM(CASE WHEN actual_return > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                        2
                    ) as hit_rate
                FROM v5_167_recommendations
                WHERE status = 'CLOSED' AND total >= 5
                GROUP BY strategy, sector
                ORDER BY hit_rate DESC
            """).fetchall()
            
            db.close()
            
            result = []
            for r in rows:
                result.append((r['strategy'], r['sector'], r['hit_rate']))
            
            return result
        except Exception as e:
            logger.error(f"❌ 识别最优组合失败: {e}")
            return []
    
    def get_quality_improvement_opportunity(self) -> Dict:
        """
        识别质量等级的改进空间
        返回: 哪些quality等级应该提升/降低阈值
        """
        by_quality = self.analyzer.calculate_by_quality_level()
        
        opportunity = {}
        for quality, metrics in by_quality.items():
            if metrics['hit_rate'] > 70:
                # 高命中率 → 可以考虑降低此级别的阈值
                opportunity[quality] = {
                    'action': 'LOWER_THRESHOLD',  # 允许更多候选进入此级别
                    'confidence': metrics['hit_rate'],
                    'avg_return': metrics['avg_return'],
                }
            elif metrics['hit_rate'] < 40:
                # 低命中率 → 应该提升阈值
                opportunity[quality] = {
                    'action': 'RAISE_THRESHOLD',
                    'confidence': metrics['hit_rate'],
                    'avg_return': metrics['avg_return'],
                }
        
        return opportunity


# ============================================================================
# Part 4: 推荐系统集成与监控
# ============================================================================

class RecommendationSystemV167:
    """
    完整的推荐系统 - 追踪 + 分析 + 优化
    """
    
    def __init__(self, db_path='data/finance.db'):
        self.tracker = RecommendationHistoryTrackerV167(db_path)
        self.analyzer = AccuracyAnalyzerV167(db_path)
        self.profile = HighConfidenceProfileV167(self.analyzer)
    
    def generate_accuracy_report(self) -> str:
        """生成完整的准确率报告"""
        lines = [
            "\n" + "=" * 80,
            "📊 实盘推荐准确率分析报告 (v5.167)",
            "=" * 80,
        ]
        
        # 整体命中率
        overall = self.analyzer.calculate_hit_rate(min_return_threshold=0.0)
        if overall.get('total', 0) > 0:
            lines.append(f"\n🎯 整体命中率: {overall['hit_rate']:.1f}% "
                        f"({overall['hits']}/{overall['total']})")
            lines.append(f"   平均实际收益: {overall['avg_return']:.2f}%")
            lines.append(f"   平均预测收益: {overall['avg_predicted']:.2f}%")
            lines.append(f"   预测偏差: {overall['prediction_error']:.2f}%")
        else:
            lines.append("\n⚠️  暂无已关闭的推荐记录")
        
        # 按策略
        lines.append("\n📈 按策略分析:")
        by_strategy = self.analyzer.calculate_by_strategy()
        for strategy, metrics in sorted(by_strategy.items(), key=lambda x: x[1]['hit_rate'], reverse=True):
            lines.append(f"  {strategy:35} | 命中率: {metrics['hit_rate']:5.1f}% | "
                        f"平均收益: {metrics['avg_return']:6.2f}%")
        
        # 按Sector
        lines.append("\n🗺️  按Sector分析:")
        by_sector = self.analyzer.calculate_by_sector()
        for sector, metrics in sorted(by_sector.items(), key=lambda x: x[1]['hit_rate'], reverse=True):
            lines.append(f"  {sector:15} | 命中率: {metrics['hit_rate']:5.1f}% | "
                        f"平均收益: {metrics['avg_return']:6.2f}% | 止损率: {metrics['stop_loss_rate']:.1%}")
        
        # 按质量等级
        lines.append("\n⭐ 按质量等级:")
        by_quality = self.analyzer.calculate_by_quality_level()
        for quality, metrics in by_quality.items():
            lines.append(f"  {quality:12} | 命中率: {metrics['hit_rate']:5.1f}% | "
                        f"平均收益: {metrics['avg_return']:6.2f}%")
        
        # 最优组合
        lines.append("\n🏆 最优 (策略, Sector) 组合:")
        combos = self.profile.identify_best_strategy_sector_combo()
        for i, (strategy, sector, hit_rate) in enumerate(combos[:5], 1):
            lines.append(f"  {i}. {strategy:30} × {sector:10} → {hit_rate:.1f}% 命中率")
        
        lines.append("=" * 80 + "\n")
        return "\n".join(lines)
    
    def get_recommendations_for_period(self, days: int = 30) -> List[Dict]:
        """
        获取最近N天的推荐汇总
        """
        try:
            c = sqlite3.connect(self.tracker.db_path)
            c.row_factory = sqlite3.Row
            
            since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            rows = c.execute("""
                SELECT *
                FROM v5_167_recommendations
                WHERE date >= ? AND status = 'CLOSED'
                ORDER BY created_at DESC
            """, (since,)).fetchall()
            
            c.close()
            
            result = []
            for r in rows:
                result.append({
                    'id': r['id'],
                    'date': r['date'],
                    'symbol': r['symbol'],
                    'strategy': r['strategy'],
                    'sector': r['sector'],
                    'entry_quality': r['entry_quality'],
                    'predicted_return': r['predicted_return'],
                    'actual_return': r['actual_return'],
                    'days_held': r['days_held'],
                    'stopped_loss': r['stopped_loss'],
                    'hit': 1 if r['actual_return'] > 0 else 0,
                })
            
            return result
        except Exception as e:
            logger.error(f"❌ 获取推荐列表失败: {e}")
            return []


# ============================================================================
# 模块导出
# ============================================================================

_system_v167 = None

def initialize_recommendation_system(db_path='data/finance.db') -> RecommendationSystemV167:
    """初始化推荐系统"""
    global _system_v167
    _system_v167 = RecommendationSystemV167(db_path)
    return _system_v167

def get_recommendation_system() -> Optional[RecommendationSystemV167]:
    """获取推荐系统实例"""
    return _system_v167

def record_recommendation(symbol: str, strategy: str, sector: str, 
                        entry_quality: float, predicted_return: float) -> int:
    """记录推荐"""
    if _system_v167:
        return _system_v167.tracker.record_recommendation(
            symbol, strategy, sector, entry_quality, predicted_return
        )
    return -1

def close_recommendation(rec_id: int, actual_return: float, 
                       days_held: int, stopped_loss: bool = False):
    """关闭推荐"""
    if _system_v167:
        _system_v167.tracker.close_recommendation(rec_id, actual_return, days_held, stopped_loss)
