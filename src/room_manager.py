#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 聊天会话管理器
管理私聊和群聊会话，支持会话创建、删除、加入、退出等功能
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class Room:
    """聊天会话数据类"""
    room_id: str
    room_type: str  # 'private' 或 'group'
    name: str
    creator_id: str
    created_at: str
    members: List[str]
    is_active: bool = True
    persona: str = "default"  # 人格设置
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Room':
        """从字典创建"""
        # 获取Room类的所有字段名
        import inspect
        room_fields = {f.name for f in inspect.signature(cls).parameters.values()}
        
        # 只保留Room类中存在的字段
        filtered_data = {k: v for k, v in data.items() if k in room_fields}
        
        return cls(**filtered_data)


class RoomManager:
    """聊天会话管理器"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.room_data_file = os.path.join(data_dir, "rooms.json")
        self.memory_dir = os.path.join("data", "room_memories")  # 会话记忆存储目录（固定在data/room_memories）
        
        # 会话数据
        self.rooms: Dict[str, Room] = {}  # room_id -> Room
        self.user_sessions: Dict[str, str] = {}  # user_id -> room_id
        self.group_sessions: Dict[str, str] = {}  # group_id -> room_id
        self.user_previous_private_room: Dict[str, str] = {}  # user_id -> previous_private_room_id
        
        # 确保记忆目录存在
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # 加载会话数据
        self.load_rooms()
    
    def get_memory_file_path(self, room_id: str) -> str:
        """获取会话记忆文件路径"""
        return os.path.join(self.memory_dir, f"{room_id}.json")
    
    def load_room_memory(self, room_id: str) -> List[Dict[str, str]]:
        """加载会话记忆
        
        Args:
            room_id: 会话ID
            
        Returns:
            聊天历史列表
        """
        memory_file = self.get_memory_file_path(room_id)
        
        if not os.path.exists(memory_file):
            return []
        
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                return memory if isinstance(memory, list) else []
        except Exception as e:
            print(f"[RoomManager] 加载会话记忆失败 ({room_id}): {e}")
            return []
    
    def save_room_memory(self, room_id: str, memory: List[Dict[str, str]]):
        """保存会话记忆
        
        Args:
            room_id: 会话ID
            memory: 聊天历史列表
        """
        memory_file = self.get_memory_file_path(room_id)
        
        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RoomManager] 保存会话记忆失败 ({room_id}): {e}")
    
    def clear_room_memory(self, room_id: str):
        """清除会话记忆
        
        Args:
            room_id: 会话ID
        """
        memory_file = self.get_memory_file_path(room_id)
        
        if os.path.exists(memory_file):
            try:
                os.remove(memory_file)
                print(f"[RoomManager] 已清除会话记忆: {room_id}")
            except Exception as e:
                print(f"[RoomManager] 清除会话记忆失败 ({room_id}): {e}")
    
    def append_room_memory(self, room_id: str, message: Dict[str, str]):
        """追加一条消息到会话记忆
        
        Args:
            room_id: 会话ID
            message: 消息字典，格式为 {"role": "user/assistant", "content": "消息内容"}
        """
        memory = self.load_room_memory(room_id)
        memory.append(message)
        self.save_room_memory(room_id, memory)
    
    def load_rooms(self):
        """从文件加载会话数据"""
        try:
            if os.path.exists(self.room_data_file):
                with open(self.room_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 加载会话
                for room_id, room_data in data.get('rooms', {}).items():
                    self.rooms[room_id] = Room.from_dict(room_data)
                
                # 加载用户会话映射
                self.user_sessions = data.get('user_sessions', {})
                self.group_sessions = data.get('group_sessions', {})
                
                print(f"[RoomManager] 已加载 {len(self.rooms)} 个会话")
        except Exception as e:
            print(f"[RoomManager] 加载会话数据失败: {e}")
            self.rooms = {}
            self.user_sessions = {}
            self.group_sessions = {}
    
    def save_rooms(self):
        """保存会话数据到文件"""
        try:
            data = {
                'rooms': {room_id: room.to_dict() for room_id, room in self.rooms.items()},
                'user_sessions': self.user_sessions,
                'group_sessions': self.group_sessions
            }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.room_data_file), exist_ok=True)
            
            with open(self.room_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RoomManager] 保存会话数据失败: {e}")
    
    def create_room(self, room_type: str, name: str, creator_id: str, members: List[str] = None) -> Room:
        """创建新会话
        
        Args:
            room_type: 会话类型 ('private' 或 'group')
            name: 会话名称
            creator_id: 创建者ID
            members: 成员列表（群聊会话需要）
            
        Returns:
            创建的会话对象
        """
        # 生成6位以内的短ID
        import random
        import string
        
        while True:
            # 生成6位随机ID（数字+字母）
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            # 确保ID唯一
            if room_id not in self.rooms:
                break
        
        created_at = datetime.now().isoformat()
        
        if members is None:
            members = [creator_id]
        
        room = Room(
            room_id=room_id,
            room_type=room_type,
            name=name,
            creator_id=creator_id,
            created_at=created_at,
            members=members,
            is_active=True
        )
        
        self.rooms[room_id] = room
        
        # 如果是私聊会话，自动绑定创建者
        if room_type == 'private':
            self.user_sessions[creator_id] = room_id
        
        self.save_rooms()
        return room
    
    def delete_room(self, room_id: str) -> bool:
        """删除会话
        
        Args:
            room_id: 会话ID
            
        Returns:
            是否删除成功
        """
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        
        # 清理用户会话映射
        if room.room_type == 'private':
            # 移除所有绑定到此会话的用户
            users_to_remove = [user_id for user_id, rid in self.user_sessions.items() if rid == room_id]
            for user_id in users_to_remove:
                del self.user_sessions[user_id]
        elif room.room_type == 'group':
            # 移除群组会话映射
            groups_to_remove = [group_id for group_id, rid in self.group_sessions.items() if rid == room_id]
            for group_id in groups_to_remove:
                del self.group_sessions[group_id]
        
        # 删除会话记忆文件
        self.clear_room_memory(room_id)
        
        # 删除会话
        del self.rooms[room_id]
        
        self.save_rooms()
        return True
    
    def get_user_room(self, user_id: str) -> Optional[Room]:
        """获取用户的当前会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户的当前会话，如果没有则返回 None
        """
        room_id = self.user_sessions.get(user_id)
        if room_id and room_id in self.rooms:
            return self.rooms[room_id]
        return None
    
    def get_group_room(self, group_id: str) -> Optional[Room]:
        """获取群组的当前会话
        
        Args:
            group_id: 群组ID
            
        Returns:
            群组的当前会话，如果没有则返回 None
        """
        room_id = self.group_sessions.get(group_id)
        if room_id and room_id in self.rooms:
            return self.rooms[room_id]
        return None
    
    def join_room(self, user_id: str, room_id: str) -> tuple:
        """加入会话
        
        Args:
            user_id: 用户ID
            room_id: 会话ID
            
        Returns:
            (是否成功, 错误信息)
        """
        if room_id not in self.rooms:
            return False, "会话不存在"
        
        room = self.rooms[room_id]
        
        if room.room_type == 'private':
            # 个人会话不能被其他人加入
            return False, "个人会话不能被加入"
        elif room.room_type == 'group':
            # 群聊会话，添加用户到成员列表
            if user_id not in room.members:
                room.members.append(user_id)
            
            # 绑定群组到会话（需要知道是哪个群组）
            # 这里需要从外部传入 group_id，暂时简化处理
            pass
        
        self.save_rooms()
        return True, ""
    
    def leave_room(self, user_id: str, group_id: str = None) -> bool:
        """退出会话
        
        Args:
            user_id: 用户ID
            group_id: 群组ID（可选，用于群聊会话）
            
        Returns:
            是否退出成功
        """
        if group_id:
            # 退出群聊会话
            room_id = self.group_sessions.get(group_id)
            if room_id and room_id in self.rooms:
                room = self.rooms[room_id]
                if user_id in room.members:
                    room.members.remove(user_id)
                    self.save_rooms()
                    return True
        else:
            # 退出私聊会话
            if user_id in self.user_sessions:
                room_id = self.user_sessions[user_id]
                del self.user_sessions[user_id]
                self.save_rooms()
                return True
        
        return False
    
    def list_rooms(self, room_type: str = None) -> List[Room]:
        """列出会话
        
        Args:
            room_type: 会话类型过滤 ('private' 或 'group')，None 表示所有
            
        Returns:
            会话列表
        """
        rooms = list(self.rooms.values())
        
        if room_type:
            rooms = [room for room in rooms if room.room_type == room_type]
        
        return rooms
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """获取会话
        
        Args:
            room_id: 会话ID
            
        Returns:
            会话对象，如果不存在则返回 None
        """
        return self.rooms.get(room_id)
    
    def bind_group_to_room(self, group_id: str, room_id: str) -> bool:
        """绑定群组到会话
        
        Args:
            group_id: 群组ID
            room_id: 会话ID
            
        Returns:
            是否绑定成功
        """
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        if room.room_type != 'group':
            return False
        
        self.group_sessions[group_id] = room_id
        self.save_rooms()
        return True
    
    def get_room_by_id(self, room_id: str) -> Optional[Room]:
        """根据ID获取会话
        
        Args:
            room_id: 会话ID
            
        Returns:
            会话对象，如果不存在则返回 None
        """
        return self.rooms.get(room_id)
    
    def get_active_rooms(self) -> List[Room]:
        """获取所有活跃的会话
        
        Returns:
            活跃会话列表
        """
        return [room for room in self.rooms.values() if room.is_active]
    
    def reset_room_persona(self, room_id: str, default_persona: str = "default") -> bool:
        """重置会话的人格设置为默认人格
        
        Args:
            room_id: 会话ID
            default_persona: 默认人格名称
            
        Returns:
            是否重置成功
        """
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        room.persona = default_persona
        self.save_rooms()
        return True
    
    def switch_to_group_room(self, user_id: str, group_id: str) -> Optional[Room]:
        """切换到群组会话（保存当前私聊会话）
        
        Args:
            user_id: 用户ID
            group_id: 群组ID
            
        Returns:
            切换后的群组会话，如果失败则返回 None
        """
        # 保存当前私聊会话（如果有）
        current_room_id = self.user_sessions.get(user_id)
        if current_room_id:
            current_room = self.rooms.get(current_room_id)
            if current_room and current_room.room_type == 'private':
                # 保存私聊会话ID，以便退出群组后恢复
                self.user_previous_private_room[user_id] = current_room_id
        
        # 切换到群组会话
        room = self.get_group_room(str(group_id))
        if room:
            # 不需要绑定用户到群组会话，因为群组会话通过 group_sessions 管理
            return room
        
        return None
    
    def switch_to_private_room(self, user_id: str) -> Optional[Room]:
        """切换到私聊会话（从群组会话退出时）
        
        Args:
            user_id: 用户ID
            
        Returns:
            切换后的私聊会话，如果失败则返回 None
        """
        # 尝试恢复之前的私聊会话
        previous_room_id = self.user_previous_private_room.get(user_id)
        if previous_room_id and previous_room_id in self.rooms:
            room = self.rooms[previous_room_id]
            if room.room_type == 'private':
                # 恢复私聊会话
                self.user_sessions[user_id] = previous_room_id
                return room
        
        # 如果没有之前的私聊会话，返回当前绑定的私聊会话
        return self.get_user_room(user_id)
    
    def switch_to_new_room(self, user_id: str, new_room: Room, is_from_private_to_group: bool = False) -> Room:
        """切换到新会话（根据需要清理记忆）
        
        Args:
            user_id: 用户ID
            new_room: 新的会话对象
            is_from_private_to_group: 是否从私聊切换到群聊
            
        Returns:
            新的会话对象
        """
        # 如果不是从私聊切换到群聊，且新会话是私聊会话，则需要清理旧私聊会话的记忆
        if not is_from_private_to_group and new_room.room_type == 'private':
            # 获取当前私聊会话
            current_room = self.get_user_room(user_id)
            if current_room and current_room.room_id != new_room.room_id:
                # 清理旧私聊会话的记忆
                self.clear_room_memory(current_room.room_id)
        
        # 更新用户会话映射
        if new_room.room_type == 'private':
            self.user_sessions[user_id] = new_room.room_id
        
        return new_room