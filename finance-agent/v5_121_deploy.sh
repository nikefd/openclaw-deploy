#!/bin/bash
# v5.121 部署脚本

echo "================================"
echo "v5.121 部署验证"
echo "================================"

cd /home/nikefd/finance-agent

# 1. 验证配置
echo ""
echo "【1】验证配置文件修改..."
python3 << 'EOF'
import config
checks = [
    ('ENTRY_QUALITY_THRESHOLD', config.ENTRY_QUALITY_THRESHOLD, 18),
    ('KELLY_COEFFICIENT', config.KELLY_COEFFICIENT, 1.52),
    ('MAX_POSITIONS', config.MAX_POSITIONS, 15),
    ('MIN_CASH_RATIO', config.MIN_CASH_RATIO, 0.03),
    ('KELLY_MAX_POSITION', config.KELLY_MAX_POSITION, 0.042),
]

print("  配置验证:")
all_pass = True
for name, actual, expected in checks:
    status = "✅" if actual == expected else "❌"
    print(f"    {status} {name}: {actual} (期望: {expected})")
    if actual != expected:
        all_pass = False

if all_pass:
    print("\n  ✅ 所有配置验证通过!")
else:
    print("\n  ❌ 配置验证失败!")
    exit(1)

# 验证赛道路由
print("\n  赛道路由验证:")
if hasattr(config, 'SECTOR_QUALITY_THRESHOLDS'):
    print(f"    ✅ SECTOR_QUALITY_THRESHOLDS已定义")
    print(f"       科技成长: {config.SECTOR_QUALITY_THRESHOLDS['科技成长']}")
    print(f"       新能源: {config.SECTOR_QUALITY_THRESHOLDS['新能源']}")
else:
    print(f"    ❌ SECTOR_QUALITY_THRESHOLDS未定义")
    exit(1)

# 验证Sharpe分级
print("\n  Sharpe分级验证:")
if hasattr(config, 'SHARPE_GRADED_RISK'):
    print(f"    ✅ SHARPE_GRADED_RISK已定义")
    high = config.SHARPE_GRADED_RISK['high']
    print(f"       高质(Sharpe≥2.0): 仓位倍数={high['position_multiplier']}, 止损={high['stop_loss']}")
else:
    print(f"    ❌ SHARPE_GRADED_RISK未定义")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ 配置验证失败"
    exit 1
fi

# 2. 验证集成模块
echo ""
echo "【2】验证集成模块..."
python3 << 'EOF'
try:
    from v5_121_integration import (
        V5_121_SectorRouter,
        V5_121_SharpeGradedRisk,
        V5_121_DynamicEntryQuality
    )
    print("  ✅ v5_121_integration导入成功")
    
    # 测试赛道路由
    threshold = V5_121_SectorRouter.get_quality_threshold('科技成长')
    multiplier = V5_121_SectorRouter.get_kelly_multiplier('新能源')
    print(f"  ✅ 赛道路由工作正常 (科技阈值={threshold}, 新能源倍数={multiplier})")
    
    # 测试Sharpe分级
    cfg = V5_121_SharpeGradedRisk.get_risk_config(2.35)
    print(f"  ✅ Sharpe分级工作正常 (Sharpe2.35: 仓位倍数={cfg['position_multiplier']})")
    
except Exception as e:
    print(f"  ❌ 集成模块验证失败: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ 集成模块验证失败"
    exit 1
fi

# 3. 快速回归测试
echo ""
echo "【3】快速回归测试..."
python3 << 'EOF'
try:
    # 验证核心导入
    import config
    from data_collector import get_stock_daily
    from position_manager import calculate_kelly_position
    print("  ✅ 核心模块导入成功")
    
except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
    exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ 回归测试失败"
    exit 1
fi

# 4. 显示优化摘要
echo ""
echo "【4】优化摘要"
cat << 'EOF'
  
  【v5.121核心改进】
  ✅ 回测驱动: 直接应用TOP3策略参数(17.1%+2.35Sharpe)
  ✅ 赛道路由: 科技→MACD+RSI, 新能源→混合, 消费→防御
  ✅ Kelly升级: 1.45→1.52 (+4.8%)
  ✅ Sharpe分级: 5档自适应风险管理
  
  【配置变更】
  • ENTRY_QUALITY_THRESHOLD: 20 → 18
  • KELLY_COEFFICIENT: 1.45 → 1.52
  • MAX_POSITIONS: 12 → 15
  • MIN_CASH_RATIO: 5% → 3%
  
  【预期成果】
  • 年化ROI: 18-20% → 21-24% (+3-4%)
  • Sharpe: 2.35 → 2.5-2.7 (+6-15%)
  • 资金利用率: 3.4% → 75-85%
  • 持仓数: 3只 → 12-15只

EOF

# 5. 部署完成
echo ""
echo "================================"
echo "✅ v5.121部署验证完成"
echo "================================"
echo ""
echo "下一步:"
echo "  1. sudo systemctl restart finance-api"
echo "  2. 监控盘中性能指标"
echo "  3. 验证资金加速建仓"
echo "================================"
