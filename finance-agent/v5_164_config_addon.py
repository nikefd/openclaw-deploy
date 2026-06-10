# v5.164 配置集成 (2026-06-10 14:00 UTC)
# 晚间深度优化④: 混合策略融合 + 融资缓存 + 动态门槛

V5_164_APPLIED = True

# =================== v5.164 混合策略融合 ===================
HYBRID_STRATEGY_ENABLED = True

# 基础策略权重 (常规模式)
HYBRID_STRATEGY_WEIGHTS = {
    'MACD_RSI': {
        'weight': 0.50,
        'minimum_score': 6,
        'sectors': ['科技成长', '新能源', '电子产品', '半导体', '芯片', '软件服务'],
    },
    'MULTI_FACTOR': {
        'weight': 0.30,
        'minimum_score': 5,
        'sectors': ['消费白马', '医药生物', '食品饮料', '家电', '金融'],
    },
    'MA_CROSS': {
        'weight': 0.20,
        'minimum_score': 4,
        'sectors': ['能源', '化工', '钢铁', '有色金属'],
    }
}

# 融资异变自适应权重 (融资异变时激活)
HYBRID_STRATEGY_WEIGHTS_MARGIN_ANOMALY = {
    'MACD_RSI': 0.30,        # -20%
    'MULTI_FACTOR': 0.50,    # +20% (主策略)
    'MA_CROSS': 0.20
}

# =================== v5.164 融资数据缓存 ===================
MARGIN_CACHE_ENABLED = True
MARGIN_CACHE_TTL = 300          # 5分钟TTL
MARGIN_CACHE_FALLBACK_DAYS = 30 # 历史回溯30天
MARGIN_CACHE_ASYNC_UPDATE = True  # 后台异步更新

# 融资异变检测阈值
MARGIN_ANOMALY_FUSION_DECLINE = -0.20      # 融资下降-20%
MARGIN_ANOMALY_RATIO_THRESHOLD = 0.25      # 融资融券比<25%
MARGIN_ANOMALY_FUSION_UPRISE = 0.15        # 融资上升+15%
MARGIN_ANOMALY_SCORE_THRESHOLD = 0.70      # 异变评分>0.7

# =================== v5.164 动态入场门槛 ===================
DYNAMIC_ENTRY_THRESHOLD_ENABLED = True

# 门槛计算基础 (按7日胜率)
DYNAMIC_THRESHOLD_BY_WINRATE = {
    'high': (0.65, 4.0),        # 胜率>65% → 基础4分 (激进)
    'medium_high': (0.55, 5.0), # 胜率55-65% → 基础5分 (均衡)
    'medium': (0.48, 5.5),      # 胜率48-55% → 基础5.5分
    'low': (0.0, 6.0),          # 胜率<48% → 基础6分 (保守)
}

# 融资异变调整 (-2~0分)
DYNAMIC_THRESHOLD_MARGIN_STRONG_ADJ = -2.0    # 融资异变评分>0.7: -2分
DYNAMIC_THRESHOLD_MARGIN_WEAK_ADJ = -1.0      # 融资异变评分>0.4: -1分

# 情绪调整 (±3分)
DYNAMIC_THRESHOLD_EXTREME_FEAR_ADJ = -3.0     # 情绪<30: -3分 (激进)
DYNAMIC_THRESHOLD_FEAR_ADJ = -1.5             # 情绪<40: -1.5分
DYNAMIC_THRESHOLD_EXTREME_GREED_ADJ = +2.0    # 情绪>92: +2分 (保守)
DYNAMIC_THRESHOLD_GREED_ADJ = +1.0            # 情绪>85: +1分

# 门槛范围限制
DYNAMIC_THRESHOLD_MIN = 3.0   # 最低门槛3分
DYNAMIC_THRESHOLD_MAX = 8.0   # 最高门槛8分

# =================== v5.164 后备配置 (降级) ===================
# 如果动态计算失败，使用静态回退
FALLBACK_TO_STATIC_THRESHOLD = True
FALLBACK_STATIC_THRESHOLD = 6  # v5.163原值

# v5.164 新增: 性能监控
PERFORMANCE_MONITOR_ENABLED = True
PERFORMANCE_LOG_INTERVAL = 60  # 每60秒记录一次

print("✅ v5.164配置已加载")
print(f"   - 混合策略融合: {HYBRID_STRATEGY_ENABLED}")
print(f"   - 融资缓存: {MARGIN_CACHE_ENABLED} (TTL={MARGIN_CACHE_TTL}s)")
print(f"   - 动态门槛: {DYNAMIC_ENTRY_THRESHOLD_ENABLED}")
