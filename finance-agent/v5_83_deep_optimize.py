"""
v5.83 盘后优化: 资金配置重构 + 三层筛选机制 + 性能追踪升级

时间: 2026-05-04 07:30 UTC
背景: 账户现金98.7%闲置，持仓仅1.3%，历史命中率0%，需要重大调整
目标: 资金利用率1.3% → 85%, 命中率0% → ≥60%, 年化收益0.19% → 8-15%

主要改进:
1. 资金配置: 35%防守+40%进攻+15%机动+10%现金 (从当前 35%+0%+0%+65%)
2. 入场筛选: 三层机制 (粗选80只 → 精选20只 → 分配3-5只)
3. 止损止盈: 动态规则替代固定值 (提高持股周期)
4. 性能追踪: 新增5项KPI指标 (推荐成功率/持股周期/资金利用率等)
"""

import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

from config import *
import json
from datetime import datetime

# =================== v5.83 核心优化配置 ===================

# 资金配置模块
CAPITAL_ALLOCATION_V5_83 = {
    'target_allocation': {
        'defensive_positions': 0.35,    # 防守仓位 (蓝筹+强势股, 目标+2-5%年化)
        'offensive_positions': 0.40,    # 进攻仓位 (热点轮动, 目标+15-30%年化)
        'tactical_positions': 0.15,     # 机动仓位 (低位补涨+高分红, 防守反弹)
        'cash_reserve': 0.10,           # 现金储备 (应对突发机会或风险)
    },
    'defensive_sectors': ['消费白马', '金融', '医药'],  # 防守赛道
    'offensive_sectors': ['科技成长', '新能源', '军工'],  # 进攻赛道
    'max_single_position': 0.05,        # 单只最多5% (从15% ↓ 降低风险)
    'min_diversification': 3,           # 最少3只持仓 (避免单一集中)
}

# 三层筛选机制
THREE_LAYER_SELECTION_V5_83 = {
    'enabled': True,
    
    # 第1层：粗选 (高通量筛选，产出80-100只候选)
    'layer_1_coarse': {
        'name': '粗选',
        'targets': {
            'MACD_CROSS': {'min': 0.5, 'threshold': 80},         # MACD金叉或上升 50%以上概率 → 80只
            'RSI_RANGE': {'min': 30, 'max': 70, 'threshold': 100},  # RSI 30-70 → 全选
            'VOLUME_SPIKE': {'multiplier': 1.2, 'threshold': 100},  # 成交量>平均20天*1.2 → 全选
        },
        'expected_output': 80,
        'criteria': [
            'MACD金叉 or MACD上升趋势',
            '大笔买入 ≥2笔 (资金信号)',
            '最近3日成交量 > 平均20日 × 1.2',
        ]
    },
    
    # 第2层：精选 (板块热度+主力意图，产出20-30只推荐)
    'layer_2_refined': {
        'name': '精选',
        'targets': {
            'sector_inflow_pct': 0.03,           # 板块主力净流入占比 ≥3%
            'stock_major_inflow': 50000000,      # 个股超大单净流入 ≥5000万
            'price_position': (0.20, 1.0),       # 最近20日涨幅 20-100% (避免极端高位)
        },
        'expected_output': 25,
        'criteria': [
            '所在板块主力净流入占比 ≥3%',
            '个股超大单净流入 ≥5000万',
            '最近20日涨幅 20-100% (避免极端高位)',
        ]
    },
    
    # 第3层：分配 (分批建仓，控制单只权重，产出3-5只仓位)
    'layer_3_allocation': {
        'name': '分配',
        'first_batch_conditions': {
            'sentiment_threshold': 0.70,         # 情绪>70时: 立即买入
            'allocation_pct': 0.025,             # 首批配置2.5%基金
        },
        'second_batch_conditions': {
            'sentiment_threshold': (0.60, 0.70),  # 情绪60-70时: 等回调3%后买入
            'allocation_pct': 0.025,             # 次批配置2.5%基金
        },
        'expected_output': 5,                   # 分配3-5只仓位
        'total_allocation': 0.075,              # 总配置7.5% (3×2.5%)
        'core_holding_days': 5,                 # 底仓持有至少5个交易日，不频繁止损
        'criteria': [
            '情绪>70时: 立即买入',
            '情绪60-70时: 等回调3%后买入',
            '底仓持有至少5个交易日，不频繁止损',
        ]
    }
}

# 动态止损止盈规则
DYNAMIC_STOP_TAKE_PROFIT_V5_83 = {
    'enabled': True,
    'rules': [
        {
            'name': '快速获利',
            'condition': '进入后3日内涨 ≥8%',
            'action': '止盈50%',
            'rationale': '锁定利润，防止反转'
        },
        {
            'name': '正常持有',
            'condition': '进入后3-10日',
            'action': '持有，目标+15%',
            'rationale': '给予趋势充分时间'
        },
        {
            'name': '技术止损',
            'condition': '跌破进价 -3%',
            'action': '割肉25%',
            'rationale': '快速认亏，保护本金'
        },
        {
            'name': '底部加仓',
            'condition': '跌破进价 -5% 且情绪<50',
            'action': '加仓50%',
            'rationale': '价值区域逆向操作'
        },
        {
            'name': '终极止损',
            'condition': '跌破进价 -8%',
            'action': '全部清空',
            'rationale': '规避系统性风险'
        },
    ],
    'trailing_stop': {
        'enabled': True,
        'peak_retracement_pct': 0.05,   # 从峰值回撤>5%触发
        'lock_ratio': 0.95,             # 锁定95%峰值
        'time_stop_hours': 8,           # 8小时无新高止损
    }
}

# 性能追踪指标 (v5.83新增)
PERFORMANCE_TRACKING_KPI_V5_83 = {
    'enabled': True,
    'kpis': {
        'win_rate': {
            'name': '推荐成功率',
            'formula': '(赢的推荐数 + 平的推荐数×0.5) / 总推荐数',
            'target': 0.60,
            'description': '衡量选股准确度'
        },
        'avg_hold_days': {
            'name': '平均持股周期',
            'formula': '总持股天数 / 总推荐数',
            'target': (7, 15),
            'description': '太短(3-5日)止损频繁，太长(>30日)持有不动'
        },
        'max_single_return': {
            'name': '最大单笔收益',
            'formula': '最大赢利推荐 / 初始投入',
            'target': 0.10,
            'description': '抓住主升浪的能力'
        },
        'capital_utilization_rate': {
            'name': '资金利用率',
            'formula': '(总持仓市值 / 总资产) × 100%',
            'target': 0.85,
            'description': '当前1.3%，目标85%'
        },
        'sharpe_ratio': {
            'name': 'Sharpe比率',
            'formula': '(日均收益 / 日波动) × √252',
            'target': 1.5,
            'description': '风险调整后的收益效率'
        }
    },
    'evaluation_period_days': 30,  # 30天评估周期
    'report_frequency': 'daily',   # 每日输出
}

# 参数调整配置
PARAMETER_ADJUSTMENT_V5_83 = {
    'position_weight_cap': 0.05,          # 单只最多5% (从15% ↓ 降低风险)
    'min_cash_ratio': 0.10,               # 最少保持10%现金 (从25% ↓ 释放更多建仓资金)
    'stop_loss_threshold': -0.08,         # 止损线 -8% (保持，给予容错)
    'trailing_stop_ratio': 0.05,          # 新增: 中途获利保护5% (从峰值)
    'entry_quality_threshold': 45,        # 入场质量45分 (从65↓ 激进但有质量监控)
    'min_position_count': 3,              # 最少持仓3只 (避免单一集中)
    'max_position_count': 8,              # 最多持仓8只 (风险容纳)
}

# =================== 执行函数 ===================

def apply_v5_83_optimization():
    """将v5.83优化配置应用到系统"""
    
    print("\n" + "="*70)
    print("🚀 v5.83 盘后优化启动")
    print("="*70)
    
    # 1. 打印资金配置调整
    print("\n【1】资金配置目标")
    print("-" * 70)
    target_alloc = CAPITAL_ALLOCATION_V5_83['target_allocation']
    print(f"  防守仓位:  {target_alloc['defensive_positions']*100:.0f}% (蓝筹+稳定性强)")
    print(f"  进攻仓位:  {target_alloc['offensive_positions']*100:.0f}% (热点轮动)")
    print(f"  机动仓位:  {target_alloc['tactical_positions']*100:.0f}% (低位补涨)")
    print(f"  现金储备:  {target_alloc['cash_reserve']*100:.0f}% (应对机会)")
    print(f"\n  防守赛道: {', '.join(CAPITAL_ALLOCATION_V5_83['defensive_sectors'])}")
    print(f"  进攻赛道: {', '.join(CAPITAL_ALLOCATION_V5_83['offensive_sectors'])}")
    print(f"  单只最大: {CAPITAL_ALLOCATION_V5_83['max_single_position']*100:.0f}%")
    
    # 2. 打印三层筛选机制
    print("\n【2】三层筛选机制")
    print("-" * 70)
    for layer_key in ['layer_1_coarse', 'layer_2_refined', 'layer_3_allocation']:
        layer = THREE_LAYER_SELECTION_V5_83[layer_key]
        print(f"\n  {layer['name']}阶段 → 产出{layer['expected_output']}只候选")
        for i, criterion in enumerate(layer['criteria'], 1):
            print(f"    {i}. {criterion}")
    
    # 3. 打印止损止盈规则
    print("\n【3】动态止损止盈规则")
    print("-" * 70)
    for i, rule in enumerate(DYNAMIC_STOP_TAKE_PROFIT_V5_83['rules'], 1):
        print(f"  {i}. {rule['name']}")
        print(f"     触发: {rule['condition']}")
        print(f"     操作: {rule['action']}")
        print(f"     原因: {rule['rationale']}")
    
    # 4. 打印KPI指标
    print("\n【4】性能追踪KPI (v5.83新增)")
    print("-" * 70)
    for kpi_key, kpi_val in PERFORMANCE_TRACKING_KPI_V5_83['kpis'].items():
        target_str = f"{kpi_val['target']*100:.0f}%" if isinstance(kpi_val['target'], float) else f"{kpi_val['target']}"
        print(f"  ✓ {kpi_val['name']}")
        print(f"    目标: {target_str} | {kpi_val['description']}")
    
    # 5. 参数调整
    print("\n【5】系统参数调整")
    print("-" * 70)
    print(f"  单只权重上限:  {PARAMETER_ADJUSTMENT_V5_83['position_weight_cap']*100:.0f}% (从15% ↓)")
    print(f"  最少现金比:   {PARAMETER_ADJUSTMENT_V5_83['min_cash_ratio']*100:.0f}% (从25% ↓)")
    print(f"  止损线:       {PARAMETER_ADJUSTMENT_V5_83['stop_loss_threshold']*100:.0f}%")
    print(f"  入场质量:     {PARAMETER_ADJUSTMENT_V5_83['entry_quality_threshold']}分 (从65↓)")
    print(f"  持仓范围:     {PARAMETER_ADJUSTMENT_V5_83['min_position_count']}-{PARAMETER_ADJUSTMENT_V5_83['max_position_count']}只")
    
    # 6. 立即执行的行动项
    print("\n【6】立即执行的行动项")
    print("-" * 70)
    print("  ① 东方证券(600958)分仓调整")
    print("    - 当前: 1400股 (~¥13,076)")
    print("    - 调整后: 保留800股 (~¥7,472) + 售出600股 (~¥5,604, 获利~¥180)")
    print("    - 用途: 获利+¥180 用于新建仓资金")
    
    print("\n  ② 新增进攻仓位建仓")
    print("    - 找3-5只半导体/军工热点")
    print("    - 初始总配置: 30-40万元 (~40% 总资产)")
    print("    - 分批建仓: 遵循三层筛选机制")
    
    print("\n  ③ 本周目标")
    print("    - 资金利用率: 1.3% → 12-15% (第一周)")
    print("    - 持仓数量: 1只 → 5-8只")
    print("    - 命中率: 0% → ≥50% (目标)")
    
    # 生成性能目标汇总
    print("\n【7】30天性能目标")
    print("-" * 70)
    target_metrics = [
        ('总收益率', '+0.19%', '+8-15%'),
        ('推荐命中率', '0%', '≥60%'),
        ('资金利用率', '1.3%', '≥85%'),
        ('平均单笔收益', '-5.9%', '≥5%'),
        ('持股周期', 'N/A', '7-15天'),
        ('Sharpe比率', 'N/A', '≥1.5'),
    ]
    
    for metric, current, target in target_metrics:
        print(f"  {metric:15} | 当前: {current:10} | 目标: {target:10}")
    
    print("\n" + "="*70)
    print("✅ v5.83 优化配置已加载，等待代码集成和测试")
    print("="*70 + "\n")

def export_v5_83_config():
    """导出v5.83配置为JSON，便于后续集成"""
    config_dict = {
        'version': 'v5.83',
        'timestamp': datetime.now().isoformat(),
        'capital_allocation': CAPITAL_ALLOCATION_V5_83,
        'three_layer_selection': THREE_LAYER_SELECTION_V5_83,
        'stop_loss_take_profit': DYNAMIC_STOP_TAKE_PROFIT_V5_83,
        'performance_tracking': PERFORMANCE_TRACKING_KPI_V5_83,
        'parameters': PARAMETER_ADJUSTMENT_V5_83,
    }
    
    config_path = '/home/nikefd/finance-agent/v5_83_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 配置已导出: {config_path}")
    return config_path

if __name__ == '__main__':
    # 执行优化
    apply_v5_83_optimization()
    
    # 导出配置
    config_path = export_v5_83_config()
    
    print("\n💡 后续集成步骤:")
    print("  1. 编辑 trading_engine.py 更新参数")
    print("  2. 编辑 stock_picker.py 实现三层筛选逻辑")
    print("  3. 编辑 position_manager.py 实现动态止损止盈")
    print("  4. 编辑 performance_tracker.py 添加KPI追踪")
    print("  5. 运行本地回测验证")
    print("  6. Git commit + openclaw-deploy 同步")
    print("  7. 重启 finance-api 服务")
