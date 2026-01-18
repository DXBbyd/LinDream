#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 消息源标识符系统
参考 AstrBot 的 unique_msg_origin 设计，统一的消息源标识符
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class MessageOrigin:
    """消息源标识符
    
    用于唯一标识一个消息来源，支持主动消息发送
    """
    platform: str      # 平台类型: qq, wechat, telegram
    message_type: str  # 消息类型: group, private, channel
    session_id: str    # 会话 ID (群组ID或用户ID)
    
    def to_string(self) -> str:
        """转换为字符串格式
        
        格式: platform:message_type:session_id
        例如: qq:group:123456789
        """
        return f"{self.platform}:{self.message_type}:{self.session_id}"
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            'platform': self.platform,
            'message_type': self.message_type,
            'session_id': self.session_id
        }
    
    @classmethod
    def from_string(cls, origin_str: str) -> 'MessageOrigin':
        """从字符串解析
        
        Args:
            origin_str: 消息源标识符字符串
            
        Returns:
            MessageOrigin 实例
            
        Raises:
            ValueError: 如果格式不正确
        """
        parts = origin_str.split(':')
        if len(parts) != 3:
            raise ValueError(f"Invalid message origin string: {origin_str}")
        
        return cls(
            platform=parts[0],
            message_type=parts[1],
            session_id=parts[2]
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'MessageOrigin':
        """从字典创建
        
        Args:
            data: 包含 platform, message_type, session_id 的字典
            
        Returns:
            MessageOrigin 实例
        """
        return cls(
            platform=data['platform'],
            message_type=data['message_type'],
            session_id=data['session_id']
        )
    
    def is_group(self) -> bool:
        """是否为群聊消息"""
        return self.message_type == 'group'
    
    def is_private(self) -> bool:
        """是否为私聊消息"""
        return self.message_type == 'private'
    
    def __str__(self) -> str:
        return self.to_string()
    
    def __repr__(self) -> str:
        return f"MessageOrigin({self.to_string()})"


def create_message_origin(platform: str, message_type: str, session_id: str) -> str:
    """创建消息源标识符
    
    Args:
        platform: 平台类型
        message_type: 消息类型
        session_id: 会话 ID
        
    Returns:
        消息源标识符字符串
    """
    origin = MessageOrigin(platform, message_type, session_id)
    return origin.to_string()


def parse_message_origin(origin_str: str) -> MessageOrigin:
    """解析消息源标识符
    
    Args:
        origin_str: 消息源标识符字符串
        
    Returns:
        MessageOrigin 实例
    """
    return MessageOrigin.from_string(origin_str)


def create_qq_group_origin(group_id: str) -> str:
    """创建 QQ 群聊消息源"""
    return create_message_origin('qq', 'group', group_id)


def create_qq_private_origin(user_id: str) -> str:
    """创建 QQ 私聊消息源"""
    return create_message_origin('qq', 'private', user_id)


def extract_message_origin(data: Dict[str, Any]) -> Optional[str]:
    """从消息数据中提取消息源标识符
    
    Args:
        data: 消息数据
        
    Returns:
        消息源标识符字符串，如果无法提取则返回 None
    """
    try:
        platform = data.get('platform', 'qq')
        message_type = data.get('message_type', 'private')
        
        if message_type == 'group':
            session_id = data.get('group_id')
        else:
            session_id = data.get('sender', {}).get('user_id')
        
        if session_id:
            return create_message_origin(platform, message_type, str(session_id))
    except Exception:
        pass
    
    return None