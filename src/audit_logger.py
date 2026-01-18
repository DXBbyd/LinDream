#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 审计日志系统
参考 AstrBot 的审计日志设计，记录所有敏感操作
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from threading import Lock


class AuditEventType(Enum):
    """审计事件类型"""
    # 消息相关
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    MESSAGE_BLOCKED = "message_blocked"
    
    # 指令相关
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    
    # 插件相关
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"
    PLUGIN_ENABLED = "plugin_enabled"
    PLUGIN_DISABLED = "plugin_disabled"
    PLUGIN_ERROR = "plugin_error"
    
    # 配置相关
    CONFIG_CHANGED = "config_changed"
    CONFIG_LOADED = "config_loaded"
    
    # 权限相关
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ACCESS_DENIED = "access_denied"
    
    # 安全相关
    SECURITY_ALERT = "security_alert"
    CONTENT_MODERATION_BLOCKED = "content_moderation_blocked"
    
    # 系统相关
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"


class AuditLogger:
    """审计日志记录器
    
    记录所有敏感操作和系统事件
    """
    
    def __init__(self, log_file: str = "data/logs/audit.log"):
        self.log_file = log_file
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100
        self._lock = Lock()
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 统计信息
        self._stats = {
            'total_events': 0,
            'events_by_type': {}
        }
    
    def log_event(self, event_type: AuditEventType, data: Dict[str, Any], user_id: Optional[str] = None):
        """记录审计事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            user_id: 用户 ID（可选）
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type.value,
            "data": data,
            "user_id": user_id
        }
        
        with self._lock:
            self.buffer.append(event)
            self._stats['total_events'] += 1
            
            # 更新类型统计
            type_name = event_type.value
            if type_name not in self._stats['events_by_type']:
                self._stats['events_by_type'][type_name] = 0
            self._stats['events_by_type'][type_name] += 1
            
            # 缓冲区满时写入文件
            if len(self.buffer) >= self.buffer_size:
                self._flush()
    
    def _flush(self):
        """刷新缓冲区到文件"""
        if not self.buffer:
            return
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                for event in self.buffer:
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
            
            self.buffer.clear()
        except Exception as e:
            print(f"[AuditLogger] 写入审计日志失败: {e}")
    
    def flush(self):
        """手动刷新缓冲区"""
        with self._lock:
            self._flush()
    
    def query_events(self, 
                    event_type: Optional[AuditEventType] = None,
                    user_id: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """查询审计事件
        
        Args:
            event_type: 事件类型筛选
            user_id: 用户 ID 筛选
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            事件列表
        """
        events = []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(events) >= limit:
                        break
                    
                    try:
                        event = json.loads(line.strip())
                        
                        # 过滤事件类型
                        if event_type and event['event_type'] != event_type.value:
                            continue
                        
                        # 过滤用户 ID
                        if user_id and event.get('user_id') != user_id:
                            continue
                        
                        # 过滤时间范围
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if start_time and event_time < start_time:
                            continue
                        if end_time and event_time > end_time:
                            continue
                        
                        events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except FileNotFoundError:
            pass
        
        # 同时检查缓冲区
        with self._lock:
            for event in self.buffer:
                if len(events) >= limit:
                    break
                
                # 应用相同的过滤条件
                if event_type and event['event_type'] != event_type.value:
                    continue
                if user_id and event.get('user_id') != user_id:
                    continue
                
                event_time = datetime.fromisoformat(event['timestamp'])
                if start_time and event_time < start_time:
                    continue
                if end_time and event_time > end_time:
                    continue
                
                events.append(event)
        
        return events
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                'total_events': self._stats['total_events'],
                'events_by_type': self._stats['events_by_type'].copy(),
                'buffer_size': len(self.buffer),
                'log_file': self.log_file
            }
    
    def clear_old_logs(self, days: int = 30):
        """清理旧日志
        
        Args:
            days: 保留天数
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        
        try:
            # 读取所有日志
            all_events = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time >= cutoff_time:
                            all_events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue
            
            # 重写日志文件
            with open(self.log_file, 'w', encoding='utf-8') as f:
                for event in all_events:
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
            
            print(f"[AuditLogger] 已清理 {days} 天前的旧日志")
            
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[AuditLogger] 清理旧日志失败: {e}")


# 便捷函数
def log_message_received(data: Dict[str, Any], user_id: Optional[str] = None):
    """记录消息接收事件"""
    audit_logger.log_event(
        AuditEventType.MESSAGE_RECEIVED,
        data={
            "message_type": data.get('message_type'),
            "group_id": data.get('group_id'),
            "sender_id": data.get('sender', {}).get('user_id'),
            "content": data.get('content', '')[:100]  # 只记录前100个字符
        },
        user_id=user_id
    )


def log_message_sent(target: str, content: str, user_id: Optional[str] = None):
    """记录消息发送事件"""
    audit_logger.log_event(
        AuditEventType.MESSAGE_SENT,
        data={
            "target": target,
            "content": content[:100]  # 只记录前100个字符
        },
        user_id=user_id
    )


def log_command_executed(command: str, args: List[str], user_id: Optional[str] = None):
    """记录指令执行事件"""
    audit_logger.log_event(
        AuditEventType.COMMAND_EXECUTED,
        data={
            "command": command,
            "args": args
        },
        user_id=user_id
    )


def log_config_changed(key: str, old_value: Any, new_value: Any, user_id: Optional[str] = None):
    """记录配置变更事件"""
    audit_logger.log_event(
        AuditEventType.CONFIG_CHANGED,
        data={
            "key": key,
            "old_value": str(old_value),
            "new_value": str(new_value)
        },
        user_id=user_id
    )


def log_security_alert(alert_type: str, details: str, user_id: Optional[str] = None):
    """记录安全警告事件"""
    audit_logger.log_event(
        AuditEventType.SECURITY_ALERT,
        data={
            "alert_type": alert_type,
            "details": details
        },
        user_id=user_id
    )


def log_access_denied(operation: str, user_id: str):
    """记录访问拒绝事件"""
    audit_logger.log_event(
        AuditEventType.ACCESS_DENIED,
        data={
            "operation": operation
        },
        user_id=user_id
    )


# 全局审计日志记录器实例
audit_logger = AuditLogger()
