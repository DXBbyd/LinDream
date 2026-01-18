import time
import threading
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple
from src.config import ConfigManager

class RateLimiter:
    """优化的速率限制器"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.message_rate_limit = config_manager.get("performance", {}).get("message_rate_limit", 10)
        self.burst_limit = config_manager.get("performance", {}).get("burst_limit", 20)
        self.cooldown_period = config_manager.get("performance", {}).get("cooldown_period", 5)
        
        # 消息速率跟踪器
        self.message_rate_trackers = defaultdict(lambda: deque(maxlen=self.burst_limit))
        
        # 冷却时间跟踪器
        self.cooldown_trackers = {}
        
        # 用户级别限制
        self.user_limits = {}
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'cooldown_activations': 0
        }
    
    def set_user_limit(self, user_id: str, limit: int):
        """设置特定用户的速率限制"""
        with self.lock:
            self.user_limits[user_id] = limit
    
    def get_user_limit(self, user_id: str) -> int:
        """获取用户的速率限制"""
        return self.user_limits.get(user_id, self.message_rate_limit)
    
    async def check_rate_limit(self, chat_key: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """检查消息速率限制
        
        Returns:
            Tuple[bool, str]: (是否允许, 原因)
        """
        current_time = time.time()
        
        with self.lock:
            self.stats['total_requests'] += 1
            
            # 检查冷却时间
            if chat_key in self.cooldown_trackers:
                if current_time - self.cooldown_trackers[chat_key] < self.cooldown_period:
                    self.stats['blocked_requests'] += 1
                    return False, f"冷却中，请等待 {self.cooldown_period - (current_time - self.cooldown_trackers[chat_key]):.1f} 秒"
                else:
                    # 冷却时间结束，移除记录
                    del self.cooldown_trackers[chat_key]
            
            # 获取用户特定的限制
            user_limit = self.get_user_limit(user_id) if user_id else self.message_rate_limit
            
            # 获取速率跟踪器，调整 maxlen
            rate_tracker = self.message_rate_trackers[chat_key]
            if rate_tracker.maxlen != user_limit:
                # 重新创建具有正确 maxlen 的 deque
                old_tracker = rate_tracker
                rate_tracker = deque(old_tracker, maxlen=user_limit)
                self.message_rate_trackers[chat_key] = rate_tracker
            
            # 清理1秒前的消息记录
            while rate_tracker and current_time - rate_tracker[0] > 1.0:
                rate_tracker.popleft()
            
            # 检查是否超过速率限制
            if len(rate_tracker) >= user_limit:
                # 检查是否超过突发限制
                if len(rate_tracker) >= self.burst_limit:
                    # 激活冷却时间
                    self.cooldown_trackers[chat_key] = current_time
                    self.stats['cooldown_activations'] += 1
                    self.stats['blocked_requests'] += 1
                    return False, f"超过突发限制，冷却 {self.cooldown_period} 秒"
                
                self.stats['blocked_requests'] += 1
                return False, f"超过速率限制 ({user_limit}/秒)"
            
            # 记录这次请求
            rate_tracker.append(current_time)
            return True, "允许"
    
    def cleanup_expired_trackers(self):
        """清理过期的速率跟踪器"""
        current_time = time.time()
        
        with self.lock:
            # 获取需要清理的键
            expired_keys = []
            for chat_key, rate_tracker in self.message_rate_trackers.items():
                # 如果超过60秒没有活动，清理该聊天
                if not rate_tracker or current_time - rate_tracker[-1] > 60:
                    expired_keys.append(chat_key)
            
            # 清理过期的跟踪器
            for key in expired_keys:
                del self.message_rate_trackers[key]
                if key in self.cooldown_trackers:
                    del self.cooldown_trackers[key]
            
            # 清理过期的冷却时间
            cooldown_expired = []
            for chat_key, cooldown_time in self.cooldown_trackers.items():
                if current_time - cooldown_time > self.cooldown_period * 2:
                    cooldown_expired.append(chat_key)
            
            for key in cooldown_expired:
                del self.cooldown_trackers[key]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            total_requests = self.stats['total_requests']
            blocked_requests = self.stats['blocked_requests']
            
            return {
                **self.stats,
                'block_rate': blocked_requests / max(1, total_requests),
                'active_trackers': len(self.message_rate_trackers),
                'active_cooldowns': len(self.cooldown_trackers),
                'user_limits': len(self.user_limits)
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.stats = {
                'total_requests': 0,
                'blocked_requests': 0,
                'cooldown_activations': 0
            }
    
    def get_user_status(self, chat_key: str) -> Dict:
        """获取特定聊天/用户的状态"""
        with self.lock:
            current_time = time.time()
            rate_tracker = self.message_rate_trackers.get(chat_key, deque())
            
            # 清理1秒前的消息记录
            while rate_tracker and current_time - rate_tracker[0] > 1.0:
                rate_tracker.popleft()
            
            cooldown_remaining = 0
            if chat_key in self.cooldown_trackers:
                cooldown_remaining = max(0, self.cooldown_period - (current_time - self.cooldown_trackers[chat_key]))
            
            return {
                'messages_in_last_second': len(rate_tracker),
                'cooldown_remaining': cooldown_remaining,
                'in_cooldown': cooldown_remaining > 0
            }