import json
import os
from typing import Dict, Any, List

def format_message(msg) -> str:
    """格式化消息"""
    if isinstance(msg, list):
        parts = []
        for m in msg:
            tp = m.get("type")
            data = m.get("data", {})

            if tp == "text":
                parts.append(data.get("text", ""))
            elif tp == "at":
                parts.append(f"@{data.get('qq','未知')} ")
            elif tp == "reply":
                parts.append(f"[引用:{data.get('id','未知')}]")
            elif tp == "image":
                parts.append(f"[图片] {data.get('url') or data.get('file','')}")
            elif tp == "json":
                try:
                    inner = json.loads(data.get("data","{}"))
                    meta = inner.get("meta", {}).get("contact", {})
                    nickname = meta.get("nickname","")
                    tag = meta.get("tag","")
                    jump = meta.get("jumpUrl","")
                    parts.append(f"[JSON卡片] {nickname} | {tag} | {jump}")
                except:
                    parts.append("[JSON卡片]")
            else:
                parts.append(f"[{tp}]")
        return "".join(parts)
    elif isinstance(msg, dict):
        return json.dumps(msg, ensure_ascii=False)
    else:
        return str(msg)

def sanitize_filename(name: str) -> str:
    """清理文件名，移除不安全字符"""
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    safe_name = name
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    return safe_name

def get_chat_dir(data: Dict[str, Any]) -> str:
    """获取聊天存储目录"""
    if data.get("message_type") == "group":
        group_name = data.get("group_name", "未知群")
        group_id = data.get("group_id", "未知群号")
        safe_group_name = sanitize_filename(group_name)
        chat_dir = os.path.join("data", "file", f"[群聊]{safe_group_name}({group_id})")
    else:
        sender = data.get("sender", {})
        user_name = sender.get("nickname", "未知用户")
        user_id = sender.get("user_id", "未知QQ号")
        safe_user_name = sanitize_filename(user_name)
        chat_dir = os.path.join("data", "file", f"[好友]{safe_user_name}({user_id})")
    
    os.makedirs(chat_dir, exist_ok=True)
    return chat_dir

def get_chat_key(data: Dict[str, Any]) -> str:
    """获取聊天唯一标识"""
    if data.get("message_type") == "group":
        return f"group_{data.get('group_id')}"
    else:
        return f"private_{data.get('sender', {}).get('user_id')}"

def get_user_permission_level(user_id: str, config_data: Dict[str, Any]) -> int:
    """获取用户权限等级"""
    # 检查是否为主人
    owners = config_data.get("owners", [])
    if str(user_id) in owners:
        return 3  # 主人
    
    # 检查是否为管理员
    admins = config_data.get("admins", [])
    if str(user_id) in admins:
        return 2  # 管理员
    
    return 1  # 普通用户

def is_authorized(user_id: str, required_level: int, config_data: Dict[str, Any]) -> bool:
    """检查用户权限"""
    user_level = get_user_permission_level(user_id, config_data)
    return user_level >= required_level
