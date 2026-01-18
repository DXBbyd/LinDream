import datetime
import os
import sys
from colorama import init, Fore, Style

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import ConfigManager
from typing import Dict, Any

# 初始化 colorama
init(autoreset=True)

class Logger:
    """日志记录器"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.log_file = os.path.join("data", "logs", "system", "message_log.txt")
        self.all_log_file = os.path.join("data", "logs", "host_alllog.log")
        
        # 确保日志目录存在
        os.makedirs(os.path.join("data", "logs", "system"), exist_ok=True)
        os.makedirs(os.path.join("data", "logs", "group"), exist_ok=True)
        os.makedirs(os.path.join("data", "logs", "friend"), exist_ok=True)
        
        # 创建系统日志文件名（按启动时间）
        self.system_log_name = f"system_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.system_log_file = os.path.join("data", "logs", "system", self.system_log_name)
    
    def now(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def write_log(self, text: str):
        """写入日志文件"""
        # 写入系统日志文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        
        # 写入完整日志文件
        with open(self.all_log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        
        # 写入启动日志文件
        with open(self.system_log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def log_system_event(self, data: Dict[str, Any]):
        """记录系统事件"""
        text = f"[系统消息] {self.now()} | {data.get('meta_event_type')} ({data.get('sub_type','')})"
        print(Fore.LIGHTGREEN_EX + Style.BRIGHT + "  ▶ " + text)
        self.write_log(text)

    def log_platform_info(self, text: str):
        """记录平台信息"""
        msg = f"[平台信息] {self.now()} | {text}"
        print(Fore.LIGHTYELLOW_EX + Style.BRIGHT + "  ▶ " + msg)
        self.write_log(msg)

    def log_communication(self, data: Dict[str, Any], media_files=None, is_bot_message=False):
        """记录通信信息"""
        # 类型检查：确保data是字典类型
        if not isinstance(data, dict):
            self.log_platform_info(f"日志记录错误：data应该是字典类型，但收到的是 {type(data).__name__}: {data}")
            return
        
        # 安全地获取时间戳，如果没有time字段则使用当前时间
        time_value = data.get("time")
        if time_value:
            try:
                t = datetime.datetime.fromtimestamp(time_value).strftime("%H:%M:%S")
            except (ValueError, TypeError):
                # 如果时间戳无效，使用当前时间
                t = datetime.datetime.now().strftime("%H:%M:%S")
        else:
            # 如果没有time字段，使用当前时间
            t = datetime.datetime.now().strftime("%H:%M:%S")
        
        sender = data.get("sender", {})
        user_name = sender.get("nickname", "未知")
        user_id = sender.get("user_id")
        
        # 如果是机器人消息，添加标识
        if is_bot_message:
            user_name = f"[机器人]{user_name}"
        
        # 格式化消息内容（不包含图片和视频的链接）
        msg_text, media_urls = self._format_message(data.get("message"))
        
        if data.get("message_type") == "group":
            group_name = data.get("group_name", "未知群")
            group_id = data.get("group_id")
            msg = f"[通信信息] {t} | 群:{group_name}({group_id}) | 来自:{user_name}({user_id}) | 内容:{msg_text}"
            
            # 根据配置决定是否记录群聊日志
            save_type = self.config_manager.get("logging", {}).get("save_type", "all")
            if save_type in ["group", "all"]:
                # 保存到群聊日志
                log_file = os.path.join("data", "logs", "group", f"{group_name}({group_id}).log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{t}] {user_name}({user_id}): {msg_text}\n")
        else:
            msg = f"[通信信息] {t} | 私聊来自:{user_name}({user_id}) | 内容:{msg_text}"
            
            # 根据配置决定是否记录好友日志
            save_type = self.config_manager.get("logging", {}).get("save_type", "all")
            if save_type in ["friend", "all"]:
                # 保存到好友日志
                log_file = os.path.join("data", "logs", "friend", f"{user_id}.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{t}] {user_name}({user_id}): {msg_text}\n")
        
        # 打印主消息
        print(Fore.LIGHTCYAN_EX + Style.BRIGHT + "  ▶ " + msg)
        self.write_log(msg)
        
        # 不显示媒体文件链接（除非是撤回消息）
        # 单独显示媒体文件链接
        # if media_urls:
        #     for media_type, url in media_urls:
        #         media_msg = f"  ▶ [{media_type}] {url}"
        #         print(Fore.LIGHTMAGENTA_EX + Style.BRIGHT + media_msg)
        #         self.write_log(media_msg)
        
        # 显示下载的文件
        if media_files:
            download_msg = f"  ▶ 下载文件: {', '.join(media_files)}"
            print(Fore.LIGHTGREEN_EX + Style.BRIGHT + download_msg)
            self.write_log(download_msg)
    
    def log_recall(self, data: Dict[str, Any], message_content: str = None):
        """记录反撤回消息
        
        Args:
            data: 撤回消息数据
            message_content: 缓存的消息内容（包含图片链接）
        """
        # 使用传入的消息内容，如果没有则尝试从缓存中获取
        text = message_content if message_content else "[无法获取内容]"
        media_files = []
        
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        operator_id = data.get("operator_id")
        
        # 获取群名称
        group_name = data.get("group_name", f"群:{group_id}")
        if not group_name or group_name == f"群:{group_id}":
            group_name = f"群:{group_id}"
        
        # 获取用户名
        user_name = "未知用户"
        if "sender" in data and data["sender"]:
            user_info = data["sender"]
            user_name = user_info.get("nickname", user_info.get("card", f"用户:{user_id}"))
        else:
            user_name = data.get("user_name", data.get("card", f"用户:{user_id}"))
        
        # 获取操作者名称
        operator_name = "未知操作者"
        if operator_id == self.config_manager.bot_id:
            operator_name = "机器人"
        else:
            operator_name = data.get("operator_name", data.get("operator_card", f"操作者:{operator_id}"))
        
        # 保存反撤回消息到文件
        recall_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recall_content = f"""
=== 反撤回消息 ===
时间: {recall_time}
群聊: {group_name}({group_id})
发送者: {user_name}({user_id})
操作者: {operator_name}({operator_id})
消息内容: {text}
媒体文件: {', '.join(media_files) if media_files else '无'}
==================
"""
        
        # 确保文件目录存在
        os.makedirs("file", exist_ok=True)
        recall_file = os.path.join("file", f"recalled_{group_id}.txt")
        with open(recall_file, "a", encoding="utf-8") as f:
            f.write(recall_content + "\n")
        
        # 不输出日志（由 bot_manager 输出）
        # msg = f"[反撤回] {group_name}({group_id}) | {user_name}({user_id}) | {operator_name}({operator_id}) | 内容:{text}"
        # print(Fore.LIGHTRED_EX + Style.BRIGHT + "  ▶ " + msg)
        # self.write_log(msg)

    def _format_message(self, msg):
        """格式化消息内容，返回(格式化后的消息, 媒体URL列表)"""
        import json
        # 如果msg是None，返回空字符串
        if msg is None:
            return "", []
        
        # 如果msg是字符串，直接返回
        if isinstance(msg, str):
            return msg, []
        
        # 如果msg是字典，转换为JSON字符串
        if isinstance(msg, dict):
            return json.dumps(msg, ensure_ascii=False), []
        
        # 如果msg是列表，处理每个元素
        if isinstance(msg, list):
            parts = []
            media_urls = []  # 存储媒体URL列表
            
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
                    # 只显示[图片]，不显示链接
                    parts.append("[图片]")
                    # 将URL添加到媒体列表
                    url = data.get('url') or data.get('file', '')
                    if url:
                        media_urls.append(("图片", url))
                elif tp == "video":
                    # 只显示[视频]，不显示链接
                    parts.append("[视频]")
                    # 将URL添加到媒体列表
                    url = data.get('url') or data.get('file', '')
                    if url:
                        media_urls.append(("视频", url))
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
            return "".join(parts), media_urls
        elif isinstance(msg, dict):
            return json.dumps(msg, ensure_ascii=False), []
        else:
            return str(msg), []
