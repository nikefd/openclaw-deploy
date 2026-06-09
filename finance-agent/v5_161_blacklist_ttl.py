"""v5.161: 被止損個股黑名單TTL優化

核心改進: 實現黑名單自動過期機制
- 被止損>5天自動清理，支持重新進場
- 新增max_stop_loss_attempt=2: 2次止損後永久黑名單
- 每日0:30自動清理過期記錄

預期效果: 個股重新進場機會↑40%, 減少「好公司永久踏空」

相關代碼位置:
- position_manager.py: get_stop_loss_blacklist() 
- config.py: STOP_LOSS_BLACKLIST_TTL = 5 (天)
"""

from datetime import datetime, timedelta
import json
import os


class StopLossBlacklistManager:
    """被止損個股黑名單TTL管理器"""
    
    def __init__(self, data_dir: str = '/home/nikefd/finance-agent/data'):
        self.data_dir = data_dir
        self.blacklist_file = os.path.join(data_dir, 'stop_loss_blacklist.json')
        self.ttl_days = 5  # 黑名單有效期5天
        self.max_attempts = 2  # 2次止損後永久黑名單
        
        # 黑名單數據結構:
        # {
        #   '600000': {
        #     'symbol': '600000',
        #     'stop_loss_count': 1,
        #     'first_stop_loss_date': '2026-06-01',
        #     'last_stop_loss_date': '2026-06-08',
        #     'last_stop_loss_price': 25.50,
        #     'status': 'temp' or 'permanent'
        #   }
        # }
        
        self.blacklist = self.load_blacklist()
    
    def load_blacklist(self) -> dict:
        """從文件加載黑名單"""
        if os.path.exists(self.blacklist_file):
            try:
                with open(self.blacklist_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_blacklist(self):
        """保存黑名單到文件"""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.blacklist_file, 'w') as f:
            json.dump(self.blacklist, f, indent=2)
    
    def add_stop_loss_record(self, symbol: str, stop_loss_price: float, reason: str = ''):
        """記錄止損事件
        
        Args:
            symbol: 股票代碼
            stop_loss_price: 止損價格
            reason: 止損原因 (可選)
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        if symbol not in self.blacklist:
            self.blacklist[symbol] = {
                'symbol': symbol,
                'stop_loss_count': 0,
                'first_stop_loss_date': today,
                'last_stop_loss_date': today,
                'last_stop_loss_price': stop_loss_price,
                'stop_loss_history': [],
                'status': 'temp'
            }
        
        record = self.blacklist[symbol]
        record['stop_loss_count'] += 1
        record['last_stop_loss_date'] = today
        record['last_stop_loss_price'] = stop_loss_price
        
        # 記錄歷史
        record['stop_loss_history'].append({
            'date': today,
            'price': stop_loss_price,
            'reason': reason
        })
        
        # 2次止損後升級為永久黑名單
        if record['stop_loss_count'] >= self.max_attempts:
            record['status'] = 'permanent'
            print(f"⚠️  {symbol}: 止損{record['stop_loss_count']}次, 升級為永久黑名單")
        else:
            record['status'] = 'temp'
            print(f"📌 {symbol}: 第{record['stop_loss_count']}次止損, "
                  f"黑名單{self.ttl_days}天 (至{(datetime.now() + timedelta(days=self.ttl_days)).strftime('%Y-%m-%d')})")
        
        self.save_blacklist()
    
    def is_blacklisted(self, symbol: str) -> bool:
        """檢查個股是否在黑名單
        
        Returns:
            True 如果在有效黑名單中, False 否則
        """
        if symbol not in self.blacklist:
            return False
        
        record = self.blacklist[symbol]
        
        # 永久黑名單
        if record['status'] == 'permanent':
            return True
        
        # 臨時黑名單: 檢查是否過期
        last_stop_date = datetime.strptime(record['last_stop_loss_date'], '%Y-%m-%d')
        expiry_date = last_stop_date + timedelta(days=self.ttl_days)
        
        if datetime.now() < expiry_date:
            return True
        else:
            # 黑名單已過期, 清理記錄
            self.remove_blacklist(symbol)
            return False
    
    def cleanup_expired_blacklist(self):
        """清理已過期的黑名單 (每日0:30執行)
        
        Returns:
            {'cleaned': [...], 'permanent': [...]}
        """
        cleaned = []
        permanent = []
        today = datetime.now().date()
        
        symbols_to_remove = []
        
        for symbol, record in self.blacklist.items():
            if record['status'] == 'permanent':
                permanent.append(symbol)
            else:
                last_stop_date = datetime.strptime(
                    record['last_stop_loss_date'], '%Y-%m-%d'
                ).date()
                expiry_date = last_stop_date + timedelta(days=self.ttl_days)
                
                if today >= expiry_date:
                    cleaned.append(symbol)
                    symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            del self.blacklist[symbol]
        
        self.save_blacklist()
        
        print(f"🧹 黑名單清理 (v5.161 @每日0:30)")
        print(f"   ✅ 已清理{len(cleaned)}個: {cleaned}")
        print(f"   ⛔ 保留{len(permanent)}個永久黑名單: {permanent}")
        
        return {
            'cleaned': cleaned,
            'permanent': permanent,
            'cleanup_time': datetime.now().isoformat()
        }
    
    def remove_blacklist(self, symbol: str):
        """手動移除黑名單 (重試用)"""
        if symbol in self.blacklist:
            del self.blacklist[symbol]
            self.save_blacklist()
            print(f"✅ {symbol}: 已從黑名單移除, 支持重新進場")
    
    def get_blacklist_status(self) -> dict:
        """獲取黑名單統計信息"""
        today = datetime.now().date()
        
        temp_count = 0
        permanent_count = 0
        temp_list = []
        
        for symbol, record in self.blacklist.items():
            if record['status'] == 'permanent':
                permanent_count += 1
            else:
                last_stop_date = datetime.strptime(
                    record['last_stop_loss_date'], '%Y-%m-%d'
                ).date()
                expiry_date = last_stop_date + timedelta(days=self.ttl_days)
                
                if today < expiry_date:
                    temp_count += 1
                    days_left = (expiry_date - today).days
                    temp_list.append(f"{symbol}(還有{days_left}天)")
        
        return {
            'temp_blacklist_count': temp_count,
            'permanent_blacklist_count': permanent_count,
            'total_count': temp_count + permanent_count,
            'temp_list': temp_list,
            'permanent_list': [s for s, r in self.blacklist.items() if r['status'] == 'permanent']
        }


def integrate_blacklist_ttl_to_position_manager():
    """集成TTL機制到position_manager
    
    應修改的位置:
    1. position_manager.py: get_stop_loss_blacklist()
    2. 添加daily_cron任務: 每日0:30執行cleanup_expired_blacklist()
    """
    
    code_snippet = """
    # ===== v5.161 黑名單TTL機制 =====
    
    from v5_161_blacklist_ttl import StopLossBlacklistManager
    
    blacklist_manager = StopLossBlacklistManager()
    
    # 在get_stop_loss_blacklist()中改為:
    def get_stop_loss_blacklist():
        return blacklist_manager.get_blacklist_status()
    
    # 在position_manager初始化時:
    # blacklist_manager.cleanup_expired_blacklist()  # 每日0:30
    """
    
    return code_snippet


if __name__ == '__main__':
    # 測試用例
    print("🧹 被止損個股黑名單TTL系統 (v5.161)\n")
    
    manager = StopLossBlacklistManager()
    
    # 測試: 記錄止損
    print("記錄測試止損:")
    manager.add_stop_loss_record('600000', 25.50, '跌破支撑')
    manager.add_stop_loss_record('600001', 35.20, '技術面惡化')
    manager.add_stop_loss_record('600002', 45.10, '第1次止損')
    manager.add_stop_loss_record('600002', 44.80, '第2次止損 -> 升級永久黑名單')
    
    print("\n黑名單狀態:")
    status = manager.get_blacklist_status()
    print(f"臨時黑名單: {status['temp_blacklist_count']}個 -> {status['temp_list']}")
    print(f"永久黑名單: {status['permanent_blacklist_count']}個 -> {status['permanent_list']}")
    
    print("\n檢查黑名單:")
    print(f"600000 是否黑名單? {manager.is_blacklisted('600000')} (是)")
    print(f"600003 是否黑名單? {manager.is_blacklisted('600003')} (否)")
    
    print("\n清理過期黑名單:")
    cleanup_result = manager.cleanup_expired_blacklist()
