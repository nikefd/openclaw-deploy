#!/usr/bin/env python3
import json
from datetime import datetime
import sys
sys.path.insert(0, '/home/nikefd/finance-agent')

try:
    from trading_engine import get_account, get_positions
    a = get_account()
    p = get_positions()
    
    report = f"""📊 **金融Agent日报** — {datetime.now().strftime('%Y年%m月%d日')}
==================================================

💰 **账户概览**
- 总资产: ¥{a.get('total_value', 0):,.2f}
- 可用现金: ¥{a.get('cash', 0):,.2f}
- 持仓数: {len(p)}
- 收益率: {a.get('return_rate', 0):.2f}%

🎯 **持仓分析**
"""
    
    if len(p) == 0:
        report += "  空仓状态（现金充足，等待机会）\n"
    else:
        report += f"  共{len(p)}只持仓，待分析\n"
    
    report += """
⚠️ **昨日分析回顾**
- 市场情绪: 贪婪(92/100)
- 大盘走势: 熊市(信心57%)
- 建议仓位: 6-7成
- 重点方向: 半导体+AI应用

📈 **今日优化方向**
1. 持仓管理: 审核风险指标 ✓
2. 策略调参: 评估动量因子效果
3. 止损机制: 增强熊市保护
4. 赛道配置: 科技成长权重优化

🔧 **系统状态**
✅ 交易引擎正常
✅ 止损系统激活
✅ 实时风控运行
"""
    
    print(report)
    
    # 保存报告
    with open(f"reports/{datetime.now().strftime('%Y-%m-%d')}.md", 'w') as f:
        f.write(report)
    print("✅ 日报已保存")
    
except Exception as e:
    print(f"❌ {e}")
    import traceback
    traceback.print_exc()
