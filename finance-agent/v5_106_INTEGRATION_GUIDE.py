"""v5.106 集成指南

将v5.106六大改进集成到核心模块
- stock_picker.py: 选股流程
- position_manager.py: 仓位管理
- config.py: 参数配置
- daily_runner.py: 日常监控

"""

import sys

# =================== stock_picker.py 集成指南 ===================

STOCK_PICKER_INTEGRATION = """
# 在stock_picker.py顶部添加导入
from v5_106_DEEP_OPTIMIZE import (
    BacktestDataFusion,
    KellyPositionCalculator,
    SectorMACD参数优化,
    DynamicCashActivation,
    DynamicPositionLimits,
    EnhancedEntryQualityScoring,
    FastPickEngine
)

# 1. 初始化全局对象 (在pick_stocks()之前)
_backtest_fusion = BacktestDataFusion()
_kelly_calc = KellyPositionCalculator(_backtest_fusion)
_fast_pick = FastPickEngine(timeout_sec=0.8)

# 2. 在pick_stocks()中应用改进①: Kelly权重
def pick_stocks(portfolio_value=1_000_000, cash_ratio=0.90):
    '''
    # 获取Kelly调整权重
    best_strategy = _backtest_fusion.get_best_strategy(sector='科技成长')
    if best_strategy:
        kelly_weight = _kelly_calc.get_kelly_adjusted_weight(
            stock_score=75.0,
            win_rate=best_strategy['win_rate'],
            base_weight=1.0
        )
        # 在评分中使用: final_score = base_score * kelly_weight
    '''
    pass

# 3. 在evaluate_technical()中应用改进②: 赛道MACD参数
def evaluate_technical(stock_code, sector):
    '''
    # 获取赛道特定参数
    macd_params = SectorMACD参数优化.get_sector_macd_params(sector)
    rsi_params = SectorMACD参数优化.get_sector_rsi_params(sector)
    
    # 使用差异化参数计算指标
    macd = calculate_macd(price_data, 
                         fast=macd_params['fast'],
                         slow=macd_params['slow'],
                         signal=macd_params['signal'])
    '''
    pass

# 4. 在score_and_rank()中应用改进③: 动态入场门槛
def score_and_rank(candidates, cash_ratio, sentiment_level='normal'):
    '''
    # 获取动态入场门槛
    entry_threshold = DynamicCashActivation.get_dynamic_entry_threshold(
        cash_ratio=cash_ratio,
        sentiment_level=sentiment_level
    )
    
    # 过滤
    qualified = [c for c in candidates if c['entry_quality'] >= entry_threshold]
    '''
    pass

# 5. 在pick_stocks()中应用改进⑤: 6维评分
def enrich_candidates_with_entry_quality(candidates, sector_scores):
    '''
    # 新增机构和Sharpe加分
    for candidate in candidates:
        inst_bonus = EnhancedEntryQualityScoring.get_institution_holding_bonus(
            institution_holding_pct=candidate['institution_pct']
        )
        sharpe_bonus = EnhancedEntryQualityScoring.get_sharpe_history_bonus(
            historical_sharpe=candidate['sharpe_ratio']
        )
        
        candidate['entry_quality_score'] = EnhancedEntryQualityScoring.normalize_score(
            raw_score + inst_bonus + sharpe_bonus
        )
    '''
    pass

# 6. 应用改进⑥: 快速选股
def pick_stocks_fast_v106():
    '''
    results = _fast_pick.pick_stocks_fast(
        get_sentiment_fn=get_market_sentiment,
        get_hot_stocks_fn=get_hot_stocks,
        get_quotes_fn=get_realtime_quotes,
        score_fn=score_and_rank,
        top_n=10
    )
    
    stage_times = _fast_pick.get_stage_times()
    print(f"Stage1: {stage_times.get('stage1', 0):.3f}s")
    print(f"Stage2: {stage_times.get('stage2', 0):.3f}s")
    print(f"Stage3: {stage_times.get('stage3', 0):.3f}s")
    '''
    pass
"""

# =================== position_manager.py 集成指南 ===================

POSITION_MANAGER_INTEGRATION = """
# 在position_manager.py顶部添加导入
from v5_106_DEEP_OPTIMIZE import (
    KellyPositionCalculator,
    DynamicPositionLimits,
    BacktestDataFusion
)

# 1. 初始化
_backtest_fusion = BacktestDataFusion()
_kelly_calc = KellyPositionCalculator(_backtest_fusion)
_dynamic_limits = DynamicPositionLimits()

# 2. 在validate_position_size()中应用改进④
def validate_position_size(stock_code, proposed_size, 
                          current_positions, sentiment_level='normal'):
    '''
    # 获取Kelly-aware的持仓限制
    max_positions = _dynamic_limits.get_max_positions(sentiment_level)
    if len(current_positions) >= max_positions:
        print(f"当前{len(current_positions)}只持仓已达上限{max_positions}")
        return None
    
    # 获取单只仓位上限
    single_limit = _dynamic_limits.get_max_single_position_limit(
        current_position_count=len(current_positions) + 1
    )
    
    # 应用Kelly-aware
    kelly_position = _kelly_calc.get_recommended_position_size(
        sector=get_sector(stock_code)
    )
    kelly_aware_limit = _dynamic_limits.apply_kelly_aware_limit(
        kelly_position=kelly_position,
        sentiment_level=sentiment_level,
        current_count=len(current_positions)
    )
    
    effective_limit = min(kelly_aware_limit, single_limit)
    
    if proposed_size > effective_limit:
        print(f"仓位过大: {proposed_size} > {effective_limit}")
        return effective_limit
    
    return proposed_size
    '''
    pass

# 3. 修改config参数
# 注: MAX_POSITIONS和MAX_SINGLE_POSITION现在由DynamicPositionLimits动态提供
# 可保留作为fallback
MAX_POSITIONS = 8  # fallback
MAX_SINGLE_POSITION = 0.05  # fallback
"""

# =================== config.py 集成指南 ===================

CONFIG_INTEGRATION = """
# 在config.py添加新参数

# v5.106: Kelly动态仓位参数
KELLY_SAFETY_FACTOR = 0.25  # Kelly仓位保守系数

# v5.106: 赛道差异化MACD参数
# 已定义在v5_106_DEEP_OPTIMIZE.py的SectorMACD参数优化类中

# v5.106: 动态现金激活
# 已定义在v5_106_DEEP_OPTIMIZE.py的DynamicCashActivation类中

# v5.106: 6维评分参数
ENTRY_QUALITY_DIMENSIONS_V106 = {
    'trend_alignment': 25,
    'position_advantage': 25,
    'volume_price_confirm': 25,
    'momentum_confirm': 25,
    'institution_holding': 15,
    'sharpe_history': 10
}
ENTRY_QUALITY_MAX_SCORE_V106 = sum(ENTRY_QUALITY_DIMENSIONS_V106.values())  # 125

# v5.106: 快速选股超时
FAST_PICK_TIMEOUT_SEC = 0.8
FAST_PICK_MAX_WORKERS = 4
"""

# =================== daily_runner.py 集成指南 ===================

DAILY_RUNNER_INTEGRATION = """
# 在daily_runner.py中添加监控

def run_evening_deep_optimize():
    '''晚间深度优化 - v5.106'''
    
    from v5_106_DEEP_OPTIMIZE import (
        BacktestDataFusion,
        KellyPositionCalculator
    )
    
    print("\\n[晚间优化] v5.106启动...")
    
    # 获取当前最优策略
    backtest_fusion = BacktestDataFusion()
    best_strategy = backtest_fusion.get_best_strategy()
    
    if best_strategy:
        report = {
            'strategy': best_strategy['strategy'],
            'win_rate': best_strategy['win_rate'] * 100,
            'annual_return': best_strategy['total_return'],
            'sharpe': best_strategy['sharpe_ratio'],
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ 最优策略: {report['strategy']}")
        print(f"   年化: {report['annual_return']:.1f}% | Sharpe: {report['sharpe']:.2f}")
        
        # 计算推荐仓位
        kelly_calc = KellyPositionCalculator(backtest_fusion)
        position_size = kelly_calc.get_recommended_position_size(
            portfolio_value=get_portfolio_value()
        )
        
        print(f"✅ 推荐仓位: ${position_size:,.0f}")
        
        return report
    else:
        print("⚠️  无法获取回测数据")
        return None

# 在daily_runner的main()中调用
if __name__ == '__main__':
    # ... existing code ...
    
    if is_evening_time():
        run_evening_deep_optimize()
"""

# =================== 集成检查清单 ===================

INTEGRATION_CHECKLIST = """
✅ 集成检查清单 (v5.106)

Phase 1: 代码集成
- [ ] 在stock_picker.py导入v5_106_DEEP_OPTIMIZE模块
- [ ] 在position_manager.py导入Kelly和限制类
- [ ] 在config.py添加新参数
- [ ] 在daily_runner.py添加监控函数

Phase 2: 功能集成
- [ ] stock_picker.pick_stocks()应用改进①Kelly权重
- [ ] evaluate_technical()应用改进②赛道MACD参数
- [ ] score_and_rank()应用改进③动态入场门槛
- [ ] validate_position_size()应用改进④Kelly-aware限制
- [ ] enrich_candidates_with_entry_quality()应用改进⑤6维评分
- [ ] pick_stocks()应用改进⑥快速选股引擎

Phase 3: 测试验证
- [ ] 单元测试: Kelly计算准确性
- [ ] 单元测试: 参数融合一致性
- [ ] 集成测试: 选股流程端到端
- [ ] 性能测试: 完成时间 < 0.8s
- [ ] 压力测试: 100只股票并发评分

Phase 4: 部署上线
- [ ] git commit 提交代码
- [ ] 数据库备份
- [ ] 服务重启
- [ ] 监控告警检查
- [ ] 日志验证

Phase 5: 效果追踪
- [ ] 跟踪资金利用率变化 (3.4% → 20-25%)
- [ ] 跟踪日均持仓数变化 (2-3 → 8-12)
- [ ] 跟踪选股速度变化 (< 1.5s → < 0.8s)
- [ ] 跟踪年化收益变化 (10-15% → 17%+)
- [ ] 每周生成报告
"""

# =================== 简化集成示例 ===================

SIMPLIFIED_EXAMPLE = """
# 最小化集成示例 (快速验证)

# 1. stock_picker.py 顶部
from v5_106_DEEP_OPTIMIZE import (
    BacktestDataFusion,
    KellyPositionCalculator,
    SectorMACD参数优化,
    DynamicCashActivation
)

_backtest_fusion = BacktestDataFusion()
_kelly_calc = KellyPositionCalculator(_backtest_fusion)

# 2. 在pick_stocks()中
def pick_stocks(...)
    # 获取Kelly权重
    best_strat = _backtest_fusion.get_best_strategy()
    kelly_weight = _kelly_calc.get_kelly_adjusted_weight(
        stock_score=75, 
        win_rate=best_strat['win_rate']
    )
    
    # 获取动态入场门槛
    entry_threshold = DynamicCashActivation.get_dynamic_entry_threshold(
        cash_ratio=current_cash_ratio,
        sentiment_level='normal'
    )
    
    # 获取赛道参数
    macd_params = SectorMACD参数优化.get_sector_macd_params(sector)
    
    # ... 继续现有逻辑，使用新参数

# 3. position_manager.py 中
from v5_106_DEEP_OPTIMIZE import DynamicPositionLimits

_limits = DynamicPositionLimits()

def validate_position_size(...)
    max_pos = _limits.get_max_positions(sentiment)
    if len(current_positions) >= max_pos:
        return None
    
    single_limit = _limits.get_max_single_position_limit(len(current_positions))
    return min(proposed_size, single_limit)

# 完成! 最小化集成已就绪
"""

def print_integration_guides():
    """打印所有集成指南"""
    print("\n" + "="*80)
    print("v5.106 集成指南")
    print("="*80)
    
    print("\n【stock_picker.py 集成】")
    print(STOCK_PICKER_INTEGRATION)
    
    print("\n【position_manager.py 集成】")
    print(POSITION_MANAGER_INTEGRATION)
    
    print("\n【config.py 集成】")
    print(CONFIG_INTEGRATION)
    
    print("\n【daily_runner.py 集成】")
    print(DAILY_RUNNER_INTEGRATION)
    
    print("\n【集成检查清单】")
    print(INTEGRATION_CHECKLIST)
    
    print("\n【简化集成示例】")
    print(SIMPLIFIED_EXAMPLE)

if __name__ == '__main__':
    print_integration_guides()
