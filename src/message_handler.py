import asyncio
import json
import datetime
import random
import time
import sys
import os
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional
from colorama import init, Fore, Style

# 初始化 colorama
init(autoreset=True)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .config import ConfigManager
from .room_manager import RoomManager
from modules.plugin_system import PluginManager
from modules.rate_limiter import RateLimiter
from modules.logging import Logger
from modules.media_handler import MediaHandler
import threading
from concurrent.futures import ThreadPoolExecutor

class MessageHandler:
    """消息处理器（集成流水线）"""
    
    def __init__(self, config_manager: ConfigManager, plugin_manager: PluginManager, 
                 rate_limiter: RateLimiter, logger: Logger):
        self.config_manager = config_manager
        self.plugin_manager = plugin_manager
        self.rate_limiter = rate_limiter
        self.logger = logger
        
        # 初始化会话管理器
        self.room_manager = RoomManager(data_dir="data")
        
        # 配置参数
        self.max_concurrent_messages = config_manager.get("performance", {}).get("max_concurrent_messages", 50)
        self.message_rate_limit = config_manager.get("performance", {}).get("message_rate_limit", 10)
        self.task_timeout = config_manager.get("performance", {}).get("task_timeout", 30)
        self.max_worker_threads = config_manager.get("performance", {}).get("max_worker_threads", 10)
        
        # 并发控制变量
        self.message_queues = defaultdict(asyncio.Queue)  # 每个群聊/好友的消息队列
        self.processing_locks = defaultdict(asyncio.Lock)  # 每个群聊的处理锁
        self.active_tasks = set()  # 活跃任务集合
        self.task_semaphore = asyncio.Semaphore(self.max_concurrent_messages)  # 并发消息信号量
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_worker_threads)  # 线程池
        
        # 会话管理
        self.user_sessions = {}  # {user_id: session_data}
        self.group_sessions = {}  # {group_id: session_data}
        self.current_persona = "default"
        
        # 消息缓存
        self.message_cache = {}
        
        # 撤回消息缓存，用于反撤回功能
        self.recall_cache = {}
        
        # 补丁系统
        self.applied_patches = {}
        
        # 自动回复规则和随机回复
        self.auto_reply_rules = {}
        self.random_replies = []
        
        # 加载配置
        self.load_auto_reply_rules()
        self.load_random_replies()
        
        # 加载默认人格
        personas_config = self.config_manager.config_data.get("personas", {})
        default_persona = personas_config.get("default_persona", "default")
        self.current_persona = default_persona.replace(".txt", "")
    
    def load_persona(self, persona_name):
        """加载人格文件内容"""
        import os
        # 移除.txt后缀（如果有的话）
        persona_name = persona_name.replace(".txt", "")
        
        persona_path = os.path.join("data", "personas", f"{persona_name}.txt")
        
        if not os.path.exists(persona_path):
            return f"你是一个友好的助手。"
        
        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                persona_content = f.read().strip()
            
            if not persona_content:
                return f"你是一个友好的助手。"
            
            return persona_content
        except Exception as e:
            self.logger.log_platform_info(f"加载人格文件失败: {e}")
            return f"你是一个友好的助手。"
    
    def get_chat_dir(self, data):
        """获取聊天存储目录"""
        if data.get("message_type") == "group":
            group_name = data.get("group_name", "未知群")
            group_id = data.get("group_id", "未知群号")
            safe_group_name = self.sanitize_filename(group_name)
            chat_dir = os.path.join("data", "file", f"[群聊]{safe_group_name}({group_id})")
        else:
            sender = data.get("sender", {})
            user_name = sender.get("nickname", "未知用户")
            user_id = sender.get("user_id", "未知QQ号")
            safe_user_name = self.sanitize_filename(user_name)
            chat_dir = os.path.join("data", "file", f"[好友]{safe_user_name}({user_id})")
        
        os.makedirs(chat_dir, exist_ok=True)
        return chat_dir

    def sanitize_filename(self, name):
        """清理文件名，移除不安全字符"""
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        safe_name = name
        for char in unsafe_chars:
            safe_name = safe_name.replace(char, '_')
        return safe_name

    def get_chat_key(self, data):
        """获取聊天唯一标识"""
        if data.get("message_type") == "group":
            return f"group_{data.get('group_id')}"
        else:
            return f"private_{data.get('sender', {}).get('user_id')}"

    async def check_rate_limit(self, chat_key):
        """检查消息速率限制 - 使用外部速率限制器"""
        return await self.rate_limiter.check_rate_limit(chat_key)

    async def process_message_with_timeout(self, websocket, data, chat_key):
        """带超时的消息处理"""
        try:
            async with self.task_semaphore:
                # 创建带超时的任务
                task = asyncio.create_task(self.handle_message_with_isolation(websocket, data, chat_key))
                self.active_tasks.add(task)
                
                try:
                    await asyncio.wait_for(task, timeout=self.task_timeout)
                except asyncio.TimeoutError:
                    self.logger.log_platform_info(f"消息处理超时: {chat_key}")
                    task.cancel()
                finally:
                    self.active_tasks.discard(task)
                    
        except Exception as e:
            self.logger.log_platform_info(f"消息处理异常: {e}")

    async def handle_message_with_isolation(self, websocket, data, chat_key):
        """隔离的消息处理"""
        async with self.processing_locks[chat_key]:
            # 检查速率限制
            if not await self.check_rate_limit(chat_key):
                self.logger.log_platform_info(f"消息速率超限: {chat_key}")
                return
            
            # 将消息放入队列等待处理
            await self.message_queues[chat_key].put(data)
            
            # 处理队列中的消息
            while not self.message_queues[chat_key].empty():
                try:
                    msg_data = self.message_queues[chat_key].get_nowait()
                    await self.process_single_message(websocket, msg_data)
                    self.message_queues[chat_key].task_done()
                except asyncio.QueueEmpty:
                    break

    async def process_message(self, websocket, data):
        """处理消息的入口点（供 bot_manager 调用）"""
        try:
            await self.process_single_message(websocket, data)
        except Exception as e:
            self.logger.log_platform_info(f"处理消息时出错: {e}")
            raise

    async def process_single_message(self, websocket, data):
        """处理单条消息（包含完整逻辑）"""
        # 检查并处理伪群友补丁的消息
        if 'pseudo_friend' in self.applied_patches:
            pseudo_friend_module = self.applied_patches['pseudo_friend'].get('module')
            if pseudo_friend_module and hasattr(pseudo_friend_module, 'is_patch_applied'):
                if pseudo_friend_module.is_patch_applied():
                    # 设置WebSocket实例并处理消息
                    if hasattr(pseudo_friend_module, 'set_websocket_instance'):
                        pseudo_friend_module.set_websocket_instance(websocket)
                    if hasattr(pseudo_friend_module, 'process_message'):
                        # 伪群友补丁处理消息
                        processed = await pseudo_friend_module.process_message(websocket, data, self.config_manager.bot_id, self.config_manager.config_data)
                        if processed:
                            # 如果消息已被处理，则跳过后续处理
                            return
        
        # 更新补丁中的机器人状态
        if self.applied_patches and 'web_status' in self.applied_patches:
            try:
                patch_module = self.applied_patches['web_status']['module']
                if hasattr(patch_module, 'update_robot_status'):
                    patch_module.update_robot_status(data)
            except Exception as e:
                self.logger.log_platform_info(f"更新机器人状态失败: {e}")
        
        # 缓存消息用于反撤回功能
        message_id = data.get('message_id')
        if message_id:
            message_content = self.format_message(data.get("message", ""), show_image_url=True)
            self.recall_cache[message_id] = {
                'user_id': data.get('user_id', '未知'),
                'group_id': data.get('group_id', '未知'),
                'message': message_content,
                'time': time.time()
            }
        
        # 处理图片下载
        await self._handle_media_download(data)
        
        # 首先让插件系统检查并处理消息（如打卡插件）
        plugin_handled = await self.plugin_manager.handle_plugin_messages(websocket, data, self.config_manager.bot_id)
        if plugin_handled:
            # 如果插件已处理消息，则跳过后续处理
            return
        
        # 处理指令
        await self.handle_commands(websocket, data)
        
        # 如果指令没有处理（即不是指令），则处理自动回复
        # 注意：这里我们假设指令处理已经完成，如果需要继续处理其他功能，请添加相应逻辑

    async def process_message_event(self, event):
        """处理消息事件（从事件总线接收）"""
        # 检查事件数据是否包含必要字段
        if not all(key in event.data for key in ['message_data', 'websocket']):
            self.logger.log_platform_info(f"事件数据不完整，跳过处理: {event.event_type}")
            return
        
        data = event.data['message_data']
        websocket = event.data['websocket']
        connection_id = event.data.get('connection_id', 'unknown')
        
        # 记录消息
        self.logger.log_communication(data)
        
        # 创建流水线上下文
        context = PipelineContext(
            event_data=data,
            websocket=websocket,
            bot_id=self.config_manager.bot_id,
            metadata={
                'connection_id': connection_id,
                'handler': self
            }
        )
        
        # 执行流水线
        await self.pipeline.execute(context)
        
        # 记录审计日志
        audit_logger.log_event(
            AuditEventType.MESSAGE_RECEIVED,
            data={
                "user_id": data.get('sender', {}).get('user_id'),
                "group_id": data.get('group_id'),
                "content": self.format_message(data.get('message'), show_image_url=False),
                "message_id": data.get('message_id')
            }
        )
    
    async def cleanup_concurrency_resources(self):
        """清理过期的并发控制资源"""
        current_time = time.time()
        
        # 清理过期的速率跟踪器
        expired_keys = []
        for chat_key, rate_tracker in self.message_rate_trackers.items():
            # 如果超过60秒没有活动，清理该聊天
            if rate_tracker and current_time - rate_tracker[-1] > 60:
                expired_keys.append(chat_key)
        
        for key in expired_keys:
            del self.message_rate_trackers[key]
            if key in self.processing_locks:
                del self.processing_locks[key]
            if key in self.message_queues:
                del self.message_queues[key]
        
        # 清理已完成的任务
        completed_tasks = {task for task in self.active_tasks if task.done()}
        self.active_tasks -= completed_tasks

    async def periodic_cleanup(self):
        """定期清理资源"""
        current_time = time.time()
        
        # 清理过期的撤回缓存（保留最近30分钟的消息）
        expired_recall_keys = []
        for msg_id, msg_info in self.recall_cache.items():
            if current_time - msg_info.get('time', 0) > 1800:  # 30分钟
                expired_recall_keys.append(msg_id)
        
        for key in expired_recall_keys:
            del self.recall_cache[key]
        
        # 清理过期的速率跟踪器
        if hasattr(self, 'message_rate_trackers'):
            expired_keys = []
            for chat_key, rate_tracker in self.message_rate_trackers.items():
                # 如果超过60秒没有活动，清理该聊天
                if rate_tracker and current_time - rate_tracker[-1] > 60:
                    expired_keys.append(chat_key)
            
            for key in expired_keys:
                if key in self.message_rate_trackers:
                    del self.message_rate_trackers[key]
                if key in self.processing_locks:
                    del self.processing_locks[key]
                if key in self.message_queues:
                    del self.message_queues[key]
        
        # 清理已完成的任务
        completed_tasks = {task for task in self.active_tasks if task.done()}
        self.active_tasks -= completed_tasks

    def load_auto_reply_rules(self):
        """加载自动回复规则"""
        self.auto_reply_rules = {}
        auto_reply_file = os.path.join("data", "other", "auto.txt")
        
        try:
            if os.path.exists(auto_reply_file):
                with open(auto_reply_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(' ', 1)
                        if len(parts) >= 2:
                            keyword, reply = parts[0], parts[1]
                            self.auto_reply_rules[keyword] = reply
            else:
                # 如果文件不存在，创建默认的auto.txt文件
                os.makedirs(os.path.dirname(auto_reply_file), exist_ok=True)
                with open(auto_reply_file, "w", encoding="utf-8") as f:
                    f.write("# LinDream自动回复规则文件\n")
                    f.write("# 格式：关键词 回复内容\n")
                    f.write("# 每行一条规则，关键词与回复内容之间用空格分隔\n")
                    f.write("# 例：你好 你好呀！有什么可以帮助你的吗？\n")
                    f.write("你好 你好呀！有什么可以帮助你的吗？\n")
                    f.write("晚安 晚安！祝你有个好梦~\n")
                    f.write("早上好 早上好！美好的一天开始了！\n")
                
                self.logger.log_platform_info(f"已创建默认自动回复文件: {auto_reply_file}")
            
            self.logger.log_platform_info(f"已加载 {len(self.auto_reply_rules)} 条自动回复规则")
        except Exception as e:
            self.logger.log_platform_info(f"加载自动回复规则失败: {e}")

    def load_random_replies(self):
        """加载随机回复"""
        self.random_replies = []
        random_reply_file = os.path.join("data", "other", "random.txt")
        
        try:
            if os.path.exists(random_reply_file):
                with open(random_reply_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                self.random_replies = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            else:
                # 如果文件不存在，创建默认的random.txt文件
                os.makedirs(os.path.dirname(random_reply_file), exist_ok=True)
                with open(random_reply_file, "w", encoding="utf-8") as f:
                    f.write("# LinDream随机回复内容\n")
                    f.write("# 每行一条回复内容\n")
                    f.write("今天也是美好的一天呢！\n")
                    f.write("有什么我可以帮你的吗？\n")
                    f.write("哈哈，有趣！\n")
                    f.write("你说得对！\n")
                    f.write("我正在学习中，谢谢你的耐心~\n")
                
                self.logger.log_platform_info(f"已创建默认随机回复文件: {random_reply_file}")
            
            self.logger.log_platform_info(f"已加载 {len(self.random_replies)} 条随机回复")
        except Exception as e:
            self.logger.log_platform_info(f"加载随机回复失败: {e}")

    async def handle_auto_reply(self, websocket, data):
        """处理自动回复"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 防止机器人回复自己的消息
        if str(sender_id) == str(self.config_manager.bot_id):
            return
        
        # 检查是否包含@机器人
        is_at_bot = False
        message_content = self.format_message(data.get("message", ""))
        
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(self.config_manager.bot_id):
                is_at_bot = True
                break
        
        # 检查是否包含自动回复关键词
        matched_reply = None
        matched_keyword = None
        for keyword, reply in self.auto_reply_rules.items():
            if keyword in message_content:
                matched_reply = reply
                matched_keyword = keyword
                break
        
        # 如果匹配到关键词或@机器人，发送回复
        if matched_reply or is_at_bot:
            # 如果是@机器人但没有匹配到关键词，使用随机回复
            if is_at_bot and not matched_reply and self.random_replies:
                matched_reply = random.choice(self.random_replies)
            
            if matched_reply:
                # 输出自动回复触发日志，使用不同颜色
                if matched_keyword:
                    print(f"{Fore.LIGHTYELLOW_EX}[自动回复] {Fore.YELLOW}匹配关键词 '{matched_keyword}' 触发{Style.RESET_ALL}")
                else:
                    print(f"{Fore.LIGHTYELLOW_EX}[自动回复] {Fore.YELLOW}被@触发{Style.RESET_ALL}")
                
                await self.send_message(websocket, matched_reply, 
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)

    async def handle_commands(self, websocket, data):
        """处理指令"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 防止机器人回复自己的消息
        if str(sender_id) == str(self.config_manager.bot_id):
            return
        
        # 检查是否包含@机器人或指令前缀
        message_content = self.format_message(data.get("message", ""))
        
        # 检查是否@了机器人
        is_at_bot = False
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(self.config_manager.bot_id):
                is_at_bot = True
                # 移除@部分，只保留后面的内容
                message_content = message_content.replace(f"@{self.config_manager.bot_id}", "").strip()
                break
        
        # 判断消息类型：群聊还是私聊
        is_private_chat = data.get("message_type") == "private"
        
        # 检查是否包含指令前缀（直接输入以/开头的指令或者@机器人后跟/开头的指令）
        is_command = message_content.startswith("/") or (is_at_bot and message_content.strip().startswith("/"))
        
        if is_command:
            # 提取指令部分
            command_text = message_content.strip()
            if command_text.startswith("/"):
                # 解析指令
                parts = command_text[1:].split(" ", 1)  # 移除/并分割
                command_name = parts[0].lower()
                command_args = parts[1] if len(parts) > 1 else ""
                
                # 根据指令名称执行相应的处理
                if command_name == "help":
                    await self._handle_help_command(websocket, data)
                elif command_name == "op":
                    await self._handle_op_command(websocket, data, command_args)
                elif command_name == "deop":
                    await self._handle_deop_command(websocket, data, command_args)
                elif command_name == "cfg":
                    await self._handle_cfg_command(websocket, data, command_args)
                elif command_name == "persona":
                    await self._handle_persona_command(websocket, data, command_args)
                elif command_name == "limit":
                    await self._handle_limit_command(websocket, data)
                elif command_name == "plugin":
                    await self._handle_plugin_command(websocket, data)
                elif command_name == "stats":
                    await self._handle_stats_command(websocket, data)
                elif command_name == "reset":
                    await self._handle_reset_command(websocket, data)
                elif command_name == "room":
                    await self._handle_room_command(websocket, data, command_args)
                elif command_name in ["load", "unload", "reload"]:
                    await self._handle_plugin_management_command(websocket, data, command_name, command_args)
                else:
                    # 尝试让插件系统处理
                    plugin_handled = await self.plugin_manager.handle_plugin_messages(websocket, data, self.config_manager.bot_id)
                    if not plugin_handled:
                        response = "[未知指令]\n.\n未知指令: {command_name}\n发送 /help 获取帮助".format(command_name=command_name)
                        await self.send_message(websocket, response,
                                              group_id=data.get("group_id"), 
                                              user_id=sender_id)
            else:
                # 如果@了机器人但没有/前缀，发送帮助信息或随机回复
                if is_at_bot:
                    await self.handle_auto_reply(websocket, data)
        elif is_private_chat:
            # 在私聊环境下，直接发送文本也可以触发AI聊天
            await self.handle_ai_chat(websocket, data, message_content)
        else:
            # 不是指令，在群聊中
            should_call_ai = False
            
            # 检查是否@了机器人
            for msg_item in data.get("message", []):
                if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(self.config_manager.bot_id):
                    should_call_ai = True
                    break
            
            # 检查是否使用了 % 前缀
            if message_content.startswith("%"):
                should_call_ai = True
                # 移除%前缀
                message_content = message_content[1:].strip()
            
            if should_call_ai:
                # 调用AI聊天功能
                await self.handle_ai_chat(websocket, data, message_content)
            else:
                # 处理自动回复
                await self.handle_auto_reply(websocket, data)

    async def handle_ai_chat(self, websocket, data, message_content):
        """处理AI聊天请求"""
        sender = data.get("sender", {})
        sender_id = str(sender.get("user_id"))
        group_id = data.get("group_id")
        
        # 确定使用哪个会话
        if group_id:
            # 群聊中，使用群组会话
            room = self.room_manager.get_group_room(str(group_id))
            if not room:
                # 如果群组没有会话，提示用户创建或加入群组会话
                await self.send_message(websocket, "当前群组未绑定会话，请使用 /room group create 创建会话或 /room join <ID> 加入会话",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            # 从私聊切换到群聊时，保存私聊会话（保留记忆）
            self.room_manager.switch_to_group_room(sender_id, str(group_id))
        else:
            # 私聊中，使用个人会话
            room = self.room_manager.get_user_room(sender_id)
            is_new_room = False
            
            # 如果没有个人会话，自动创建个人会话
            if not room:
                room = self.room_manager.create_room(
                    room_type='private',
                    name=f"个人会话_{sender_id}",
                    creator_id=sender_id
                )
                is_new_room = True
                
                # 发送会话创建提示
                await self.send_message(websocket, f"已为您自动创建独立会话\n会话ID: {room.room_id}",
                                      group_id=group_id, 
                                      user_id=sender_id)
        
        # 获取会话的人格设置
        persona_name = room.persona if room.persona else "default"
        
        # 输出AI聊天触发日志，使用不同颜色
        print(f"{Fore.LIGHTGREEN_EX}[AI聊天] {Fore.GREEN}用户 {sender_id} 发起对话 (会话: {room.room_id}, 人格: {persona_name}){Style.RESET_ALL}")
        
        # 检查是否配置了AI参数
        ai_config = self.config_manager.config_data.get("ai_config", {})
        api_key = ai_config.get("api_key")
        api_url = ai_config.get("api_url")
        
        if api_key and api_url:
            # 尝试调用AI服务
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    # 加载会话的人格
                    persona_content = self.load_persona(persona_name)
                    
                    # 加载会话记忆（无限制）
                    chat_history = self.room_manager.load_room_memory(room.room_id)
                    
                    # 构建消息列表，包含系统提示词（人格）和聊天历史
                    messages = [{"role": "system", "content": persona_content}]
                    
                    # 添加所有聊天历史（无限制）
                    if chat_history:
                        messages.extend(chat_history)
                    
                    # 添加当前用户消息
                    messages.append({"role": "user", "content": message_content})
                    
                    payload = {
                        "model": ai_config.get("model_name", "default"),
                        "messages": messages
                    }
                    
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    async with session.post(api_url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            result = await response.json()
                            ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "抱歉，我没有理解您的问题。")
                            
                            # 保存聊天记录到独立文件
                            self.room_manager.append_room_memory(room.room_id, {"role": "user", "content": message_content})
                            self.room_manager.append_room_memory(room.room_id, {"role": "assistant", "content": ai_response})
                        else:
                            ai_response = "AI服务暂时不可用，请稍后再试。"
            except Exception as e:
                ai_response = f"AI服务调用失败: {str(e)}"
        else:
            # 没有配置AI服务，返回提示信息
            ai_response = "AI服务未配置或不可用。"
        
        # 直接发送AI响应，不添加任何前缀
        await self.send_message(websocket, ai_response,
                              group_id=group_id, 
                              user_id=sender_id)

    async def _handle_help_command(self, websocket, data):
        """处理help指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        help_text = """[LinDream 帮助信息]
.
├─ 基础指令:
│  ├─ /help    - 显示帮助
│  ├─ /limit   - 权限等级
│  ├─ /plugin  - 已加载插件
│  ├─ /persona - 人格切换
│  ├─ /stats   - 统计信息
│  └─ /room    - 聊天会话管理
.
├─ 权限管理 (主人):
│  ├─ /op      - 设置管理员
│  ├─ /deop    - 移除管理员
│  └─ /cfg     - 配置插件
.
├─ 插件管理 (管理员):
│  ├─ /load    - 加载插件
│  ├─ /unload  - 卸载插件
│  └─ /reload  - 重载插件
.
├─ AI聊天:
│  ├─ @机器人 - 直接聊天
│  └─ %前缀   - %你好
.
使用方法:
- 直接发送: /help
- @机器人: @LinDream /help"""

        await self.send_message(websocket, help_text,
                              group_id=data.get("group_id"), 
                              user_id=sender_id)

    async def _handle_op_command(self, websocket, data, args):
        """处理op指令（设置管理员）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 3, self.config_manager.config_data):
            await self.send_message(websocket, "权限不足：只有主人才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        if not args:
            await self.send_message(websocket, "[设置管理员]\n.\n用法: /op <用户QQ号>",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        target_user_id = args.split()[0]
        if not target_user_id.isdigit():
            await self.send_message(websocket, "请输入有效的QQ号",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        # 编辑admin.txt文件
        admin_file_path = os.path.join("data", "other", "admin.txt")
        try:
            # 读取现有的管理员列表
            if os.path.exists(admin_file_path):
                with open(admin_file_path, 'r', encoding='utf-8') as f:
                    admin_lines = f.readlines()
                    # 过滤掉空行和注释行，提取管理员QQ号
                    existing_admins = []
                    for line in admin_lines:
                        line = line.strip()
                        if line and not line.startswith('#') and line.isdigit():
                            existing_admins.append(line)
            else:
                existing_admins = []
            
            # 检查目标用户是否已经是管理员
            if target_user_id not in existing_admins:
                # 添加新管理员
                existing_admins.append(target_user_id)
                
                # 保存回admin.txt文件
                with open(admin_file_path, 'w', encoding='utf-8') as f:
                    for admin in existing_admins:
                        f.write(f"{admin}\n")
                
                # 重新加载配置以获取最新的管理员列表
                self.config_manager.load_admins_from_file()
                
                await self.send_message(websocket, f"成功将用户 {target_user_id} 设置为管理员",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
            else:
                await self.send_message(websocket, f"用户 {target_user_id} 已是管理员",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
        except Exception as e:
            await self.send_message(websocket, f"添加管理员失败: {e}",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)

    async def _handle_deop_command(self, websocket, data, args):
        """处理deop指令（移除管理员）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 3, self.config_manager.config_data):
            await self.send_message(websocket, "权限不足：只有主人才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        if not args:
            await self.send_message(websocket, "[移除管理员]\n.\n用法: /deop <用户QQ号>",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        target_user_id = args.split()[0]
        if not target_user_id.isdigit():
            await self.send_message(websocket, "请输入有效的QQ号",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        # 编辑admin.txt文件
        admin_file_path = os.path.join("data", "other", "admin.txt")
        try:
            # 读取现有的管理员列表
            if os.path.exists(admin_file_path):
                with open(admin_file_path, 'r', encoding='utf-8') as f:
                    admin_lines = f.readlines()
                    # 过滤掉空行和注释行，提取管理员QQ号
                    existing_admins = []
                    for line in admin_lines:
                        line = line.strip()
                        if line and not line.startswith('#') and line.isdigit():
                            existing_admins.append(line)
            else:
                existing_admins = []
            
            # 检查目标用户是否是管理员
            if target_user_id in existing_admins:
                # 移除管理员
                existing_admins.remove(target_user_id)
                
                # 保存回admin.txt文件
                with open(admin_file_path, 'w', encoding='utf-8') as f:
                    for admin in existing_admins:
                        f.write(f"{admin}\n")
                
                # 重新加载配置以获取最新的管理员列表
                self.config_manager.load_admins_from_file()
                
                await self.send_message(websocket, f"成功移除用户 {target_user_id} 的管理员权限",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
            else:
                await self.send_message(websocket, f"用户 {target_user_id} 不是管理员",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
        except Exception as e:
            await self.send_message(websocket, f"移除管理员失败: {e}",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)

    async def _handle_cfg_command(self, websocket, data, args):
        """处理cfg指令（设置插件权限）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 2, self.config_manager.config_data):
            await self.send_message(websocket, "权限不足：只有管理员才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        arg_parts = args.split()
        if len(arg_parts) < 2:
            usage_text = "[配置插件]\n.\n用法:\n├─ /cfg <插件名> <参数> <值>\n└─ 例: /cfg welcome enabled true"
            await self.send_message(websocket, usage_text,
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        plugin_name = arg_parts[0]
        param_name = arg_parts[1]
        param_value = ' '.join(arg_parts[2:]) if len(arg_parts) > 2 else arg_parts[1]
        
        # 尝试解析参数值
        if param_value.lower() in ['true', 'yes', '1']:
            param_value = True
        elif param_value.lower() in ['false', 'no', '0']:
            param_value = False
        elif param_value.isdigit():
            param_value = int(param_value)
        
        # 更新配置
        plugin_config = self.config_manager.config_data.get("plugin_config", {})
        if plugin_name not in plugin_config:
            plugin_config[plugin_name] = {}
        plugin_config[plugin_name][param_name] = param_value
        self.config_manager.config_data["plugin_config"] = plugin_config
        
        # 保存配置
        self.config_manager.save_config()
        
        response = f"[配置结果]\n.\n插件: {plugin_name}\n参数: {param_name}\n值: {param_value}"
        await self.send_message(websocket, response,
                              group_id=data.get("group_id"), 
                              user_id=sender_id)

    async def _handle_persona_command(self, websocket, data, args):
        """处理persona指令（人格切换）"""
        sender = data.get("sender", {})
        sender_id = str(sender.get("user_id"))
        group_id = data.get("group_id")
        
        arg_parts = args.split()
        
        if not arg_parts:
            # 直接输入/persona，显示人格列表和帮助
            import os
            persona_dir = os.path.join("data", "personas")
            if not os.path.exists(persona_dir):
                await self.send_message(websocket, "人格目录不存在",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            persona_files = [f for f in os.listdir(persona_dir) if f.endswith('.txt')]
            if not persona_files:
                await self.send_message(websocket, "未找到人格文件",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            # 按文件名排序
            persona_files.sort()
            
            # 获取当前会话的人格
            current_room_persona = "default"
            if group_id:
                room = self.room_manager.get_group_room(str(group_id))
            else:
                room = self.room_manager.get_user_room(sender_id)
            
            if room:
                current_room_persona = room.persona if room.persona else "default"
            
            help_text = "[人格切换帮助]\n.\n├─ 用法:\n│  ├─ /persona ls      - 查看人格列表\n│  ├─ /persona <序号>  - 切换人格(序号)\n│  └─ /persona <名称>  - 切换人格(名称)\n.\n├─ 当前会话人格:\n│  └─ {current_persona}\n.\n├─ 可用人格:\n".format(current_persona=current_room_persona)
            
            for i, file in enumerate(persona_files, 1):
                name = file[:-4]  # 去掉.txt后缀
                if name == current_room_persona:
                    help_text += f"│  └─ {i}. {name} *\n"  # 当前人格标记为*
                else:
                    help_text += f"│  ├─ {i}. {name}\n"
            
            help_text += "\n.\n说明:\n├─ 私聊会话：可随意切换人格，切换时自动清除记忆\n└─ 群组会话：仅创建者可切换人格"
            
            await self.send_message(websocket, help_text,
                                  group_id=group_id, 
                                  user_id=sender_id)
            return

        if arg_parts[0] in ['ls', 'list']:
            # 列出所有人格
            import os
            persona_dir = os.path.join("data", "personas")
            if not os.path.exists(persona_dir):
                await self.send_message(websocket, "人格目录不存在",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            persona_files = [f for f in os.listdir(persona_dir) if f.endswith('.txt')]
            if not persona_files:
                await self.send_message(websocket, "未找到人格文件",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            # 按文件名排序
            persona_files.sort()
            
            # 获取当前会话的人格
            current_room_persona = "default"
            if group_id:
                room = self.room_manager.get_group_room(str(group_id))
            else:
                room = self.room_manager.get_user_room(sender_id)
            
            if room:
                current_room_persona = room.persona if room.persona else "default"
            
            result = "[人格列表]\n."
            for i, file in enumerate(persona_files, 1):
                name = file[:-4]  # 去掉.txt后缀
                if name == current_room_persona:
                    result += f"\n├─ {i}. {name} *"
                else:
                    result += f"\n├─ {i}. {name}"
            
            await self.send_message(websocket, result,
                                  group_id=group_id, 
                                  user_id=sender_id)
        else:
            # 切换人格
            persona_name = arg_parts[0]
            
            # 检查是否是序号
            if persona_name.isdigit():
                import os
                persona_dir = os.path.join("data", "personas")
                if not os.path.exists(persona_dir):
                    await self.send_message(websocket, "人格目录不存在",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
                
                persona_files = [f for f in os.listdir(persona_dir) if f.endswith('.txt')]
                if not persona_files:
                    await self.send_message(websocket, "未找到人格文件",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
                
                # 按文件名排序
                persona_files.sort()
                
                index = int(persona_name) - 1
                if 0 <= index < len(persona_files):
                    persona_name = persona_files[index][:-4]  # 去掉.txt后缀
                else:
                    await self.send_message(websocket, f"序号超出范围 (1-{len(persona_files)})",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
            
            # 检查人格文件是否存在
            import os
            persona_path = os.path.join("data", "personas", f"{persona_name}.txt")
            if not os.path.exists(persona_path):
                await self.send_message(websocket, f"人格文件不存在: {persona_name}.txt",
                                      group_id=group_id, 
                                      user_id=sender_id)
                return
            
            # 获取当前会话
            if group_id:
                room = self.room_manager.get_group_room(str(group_id))
                if not room:
                    await self.send_message(websocket, "当前群组未绑定会话",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
                
                # 群组会话：只有创建者可以切换人格
                if str(sender_id) != room.creator_id:
                    await self.send_message(websocket, "权限不足：只有群组会话的创建者才能切换人格",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
                
                # 切换群组会话人格（不清除记忆）
                room.persona = persona_name
                self.room_manager.save_rooms()
                response = f"成功切换群组会话人格: {persona_name}"
            else:
                # 私聊会话：可以随意切换人格
                room = self.room_manager.get_user_room(sender_id)
                if not room:
                    await self.send_message(websocket, "您当前没有会话，请先发送消息创建会话",
                                          group_id=group_id, 
                                          user_id=sender_id)
                    return
                
                # 切换私聊会话人格（清除记忆）
                room.persona = persona_name
                self.room_manager.save_rooms()
                self.room_manager.clear_room_memory(room.room_id)
                response = f"成功切换私聊会话人格: {persona_name}\n\n(已自动清除会话记忆，避免人格混淆)"
            
            await self.send_message(websocket, response,
                                  group_id=group_id, 
                                  user_id=sender_id)

    async def _handle_limit_command(self, websocket, data):
        """处理limit指令（查看权限等级）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 获取权限等级
        from utils.helpers import get_user_permission_level
        permission_level = get_user_permission_level(str(sender_id), self.config_manager.config_data)
        
        # 权限等级说明
        level_desc = {1: "普通用户", 2: "管理员", 3: "主人"}
        level_name = level_desc.get(permission_level, "未知")
        
        response = f"权限等级: {permission_level} ({level_name})"
        
        await self.send_message(websocket, response,
                              group_id=data.get("group_id"), 
                              user_id=sender_id)

    async def _handle_plugin_command(self, websocket, data):
        """处理plugin指令（查看已加载插件）"""
        # 获取已加载的插件列表
        loaded_plugins = self.plugin_manager.loaded_plugins
        
        plugin_list = "[已加载插件]\n."
        if loaded_plugins:
            for i, plugin in enumerate(loaded_plugins, 1):
                plugin_name = plugin.get('name', '未知插件')
                plugin_cmd = plugin.get('cmd', '')
                if plugin_cmd:
                    plugin_list += f"\n├─ {i}. {plugin_name} | 指令: {plugin_cmd}"
                else:
                    plugin_list += f"\n├─ {i}. {plugin_name}"
        else:
            plugin_list += "\n├─ 暂无已加载插件"
        
        # 检查是否有AstrBot插件桥接补丁并获取其插件列表
        astrbot_patch = self.plugin_manager.applied_patches.get('astrbot_plugin_bridge')
        if astrbot_patch and 'module' in astrbot_patch:
            try:
                astrbot_module = astrbot_patch['module']
                if hasattr(astrbot_module, 'get_astrbot_plugins_menu'):
                    astrbot_menu = astrbot_module.get_astrbot_plugins_menu()
                    if astrbot_menu:  # 如果有AstrBot插件
                        plugin_list += f"\n\n{astrbot_menu}"
            except Exception as e:
                self.logger.log_platform_info(f"获取AstrBot插件列表失败: {e}")
        
        await self.send_message(websocket, plugin_list.strip(),
                              group_id=data.get("group_id"), 
                              user_id=data.get("sender", {}).get("user_id"))

    async def _handle_stats_command(self, websocket, data):
        """处理stats指令（查看统计信息）"""
        # 获取性能统计（这里简化处理，返回基本统计信息）
        result = "[机器人统计]\n.\n├─ 连接数: 1\n├─ 已加载插件: {plugin_count} 个\n├─ 当前人格: {persona}\n└─ 运行状态: 正常".format(
            plugin_count=len(self.plugin_manager.loaded_plugins),
            persona=self.current_persona
        )
        
        await self.send_message(websocket, result,
                              group_id=data.get("group_id"), 
                              user_id=data.get("sender", {}).get("user_id"))

    async def _handle_reset_command(self, websocket, data):
        """处理reset指令（重载配置和插件）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 2, self.config_manager.config_data):  # 需要管理员权限
            await self.send_message(websocket, "权限不足：只有管理员才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        try:
            # 重新加载主配置和相关配置文件
            self.config_manager.load_config()
            
            # 重新加载插件
            self.plugin_manager.load_plugins()
            
            # 重新加载补丁
            self.plugin_manager.load_patches(self.config_manager.config_data)
            
            # 检查并安装插件依赖
            self.plugin_manager.check_and_install_plugin_dependencies()
            
            # 重新加载自动回复规则和随机回复
            self.load_auto_reply_rules()
            self.load_random_replies()
            
            await self.send_message(websocket, "配置和插件重载成功",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
        except Exception as e:
            import traceback
            error_msg = f"重载失败: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)  # 打印到控制台
            await self.send_message(websocket, f"重载失败: {str(e)}",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)

    async def _handle_plugin_management_command(self, websocket, data, command_name, args):
        """处理插件管理指令（load/unload/reload）"""
        # 获取发送者ID
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 2, self.config_manager.config_data):  # 需要管理员权限
            await self.send_message(websocket, "权限不足：只有管理员才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        if not args:
            await self.send_message(websocket, f"用法：/{command_name} <插件名>",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        plugin_name = args.split()[0]
        
        try:
            if command_name == 'load':
                # 这里需要实现插件加载逻辑
                await self.send_message(websocket, f"正在加载插件 {plugin_name}...",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
            elif command_name == 'unload':
                await self.send_message(websocket, f"正在卸载插件 {plugin_name}...",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
            elif command_name == 'reload':
                await self.send_message(websocket, f"正在重载插件 {plugin_name}...",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
            else:
                await self.send_message(websocket, "未知插件管理指令",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
        except Exception as e:
            await self.send_message(websocket, f"插件操作失败: {str(e)}",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)

    def format_message(self, msg, show_image_url=False):
        """格式化消息
        
        Args:
            msg: 消息内容
            show_image_url: 是否显示图片链接（默认为False）
        """
        if isinstance(msg, list):
            parts = []
            for m in msg:
                # 确保m是字典类型，避免错误
                if not isinstance(m, dict):
                    parts.append(str(m))  # 如果m不是字典，直接转换为字符串
                    continue
                
                tp = m.get("type")
                data = m.get("data", {})

                if tp == "text":
                    parts.append(data.get("text", ""))
                elif tp == "at":
                    parts.append(f"@{data.get('qq','未知')} ")
                elif tp == "reply":
                    parts.append(f"[引用:{data.get('id','未知')}]")
                elif tp == "image":
                    if show_image_url:
                        image_url = data.get('url') or data.get('file', '')
                        parts.append(f"[图片] {image_url}")
                    else:
                        parts.append("[图片]")
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
            # 如果msg既不是列表也不是字典，直接返回字符串形式
            return str(msg) if msg is not None else ""
            return str(msg)

    async def _download_image(self, url: str, data: Dict[str, Any] = None):
        """下载图片"""
        try:
            # 检查URL是否有效
            if not url.startswith(('http://', 'https://')):
                self.logger.log_platform_info(f"跳过无效图片URL: {url}")
                return
            
            # 如果没有提供data，无法确定保存路径，跳过
            if not data:
                return
            
            # 获取聊天存储目录
            chat_dir = self.get_chat_dir(data)
            
            # 生成文件名（使用时间戳）
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S_%f")
            filename = f"{timestamp}.jpg"
            file_path = os.path.join(chat_dir, filename)
            
            # 检查文件是否已存在（避免重复下载）
            if os.path.exists(file_path):
                self.logger.log_platform_info(f"图片已存在，跳过下载: {file_path}")
                return
            
            # 下载图片
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    self.logger.log_platform_info(f"图片已下载: {file_path}")
                else:
                    self.logger.log_platform_info(f"图片下载失败: {url}, HTTP状态码: {response.status_code}")
        except Exception as e:
            self.logger.log_platform_info(f"图片下载失败: {url}, 错误: {e}")
    
    async def _handle_media_download(self, data: Dict[str, Any]):
        """处理媒体文件下载（图片、视频）"""
        try:
            message = data.get("message", [])
            if not message:
                return
            
            # 检查消息中是否包含图片或视频
            for msg_item in message:
                if not isinstance(msg_item, dict):
                    continue
                
                msg_type = msg_item.get("type")
                if msg_type not in ["image", "video"]:
                    continue
                
                # 获取URL
                url = msg_item.get("data", {}).get("url") or msg_item.get("data", {}).get("file", "")
                if not url:
                    continue
                
                # 检查URL是否有效
                if not url.startswith(('http://', 'https://')):
                    continue
                
                # 获取聊天存储目录
                chat_dir = self.get_chat_dir(data)
                
                # 生成文件名（使用时间戳）
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S_%f")
                ext = ".jpg" if msg_type == "image" else ".mp4"
                filename = f"{timestamp}{ext}"
                file_path = os.path.join(chat_dir, filename)
                
                # 检查文件是否已存在（避免重复下载）
                if os.path.exists(file_path):
                    continue
                
                # 下载文件
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=30.0)
                    if response.status_code == 200:
                        with open(file_path, "wb") as f:
                            f.write(response.content)
                        self.logger.log_platform_info(f"{'图片' if msg_type == 'image' else '视频'}已下载: {file_path}")
                    else:
                        self.logger.log_platform_info(f"{'图片' if msg_type == 'image' else '视频'}下载失败: {url}, HTTP状态码: {response.status_code}")
        except Exception as e:
            self.logger.log_platform_info(f"媒体文件下载失败: {e}")

    async def send_message(self, websocket, message, group_id=None, user_id=None):
        """发送消息"""
        try:
            msg_data = {
                "action": "send_group_msg" if group_id else "send_private_msg",
                "params": {}
            }
            
            if group_id:
                msg_data["params"]["group_id"] = group_id
            else:
                msg_data["params"]["user_id"] = user_id
                
            msg_data["params"]["message"] = message
            
            await websocket.send(json.dumps(msg_data, ensure_ascii=False))
            
            # 输出发送消息的日志，使用亮蓝色，只显示消息类型
            if group_id:
                print(f"{Fore.LIGHTBLUE_EX}[已发送群消息] {Fore.CYAN}向群 {group_id} 发送消息{Style.RESET_ALL}")
            else:
                print(f"{Fore.LIGHTBLUE_EX}[已发送私聊消息] {Fore.CYAN}向用户 {user_id} 发送消息{Style.RESET_ALL}")
                
            return True
        except Exception as e:
            self.logger.log_platform_info(f"发送消息失败: {e}")
            return False

    async def _handle_room_command(self, websocket, data, args):
        """处理room指令（聊天会话管理）"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 1, self.config_manager.config_data):
            await self.send_message(websocket, "权限不足：需要用户权限才能执行此操作",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        # 解析子指令
        arg_parts = args.strip().split()
        
        if not arg_parts or arg_parts[0] == "":
            # 显示帮助信息
            await self._handle_room_help(websocket, data)
            return
        
        subcommand = arg_parts[0].lower()
        
        if subcommand == "info":
            await self._handle_room_info(websocket, data)
        elif subcommand == "exit":
            await self._handle_room_exit(websocket, data)
        elif subcommand == "new":
            await self._handle_room_new(websocket, data)
        elif subcommand == "group":
            # 处理群组子指令
            if len(arg_parts) >= 2:
                group_subcommand = arg_parts[1].lower()
                group_args = ' '.join(arg_parts[2:]) if len(arg_parts) > 2 else ""
                
                if group_subcommand == "create":
                    await self._handle_room_group_create(websocket, data, group_args)
                elif group_subcommand == "del":
                    await self._handle_room_group_del(websocket, data, group_args)
                elif group_subcommand == "list":
                    await self._handle_room_group_list(websocket, data)
                else:
                    await self.send_message(websocket, f"未知的群组子指令: {group_subcommand}\n发送 /room 查看帮助",
                                          group_id=data.get("group_id"), 
                                          user_id=sender_id)
            else:
                await self.send_message(websocket, "用法: /room group <create|del|list> [参数]",
                                      group_id=data.get("group_id"), 
                                      user_id=sender_id)
        elif subcommand == "join":
            await self._handle_room_join(websocket, data, ' '.join(arg_parts[1:]))
        elif subcommand == "leave":
            await self._handle_room_leave(websocket, data)
        else:
            await self.send_message(websocket, f"未知的子指令: {subcommand}\n发送 /room 查看帮助",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)

    async def _handle_room_help(self, websocket, data):
        """处理 /room 帮助指令"""
        help_text = """[聊天会话管理帮助]
.
├─ 基础指令:
│  ├─ /room info    - 查看当前对话的会话ID
│  ├─ /room exit    - 退出当前聊天会话（删除会话数据）
│  └─ /room new     - 创建新的个人会话（私聊中）或群组会话（群聊中）
.
├─ 群组管理:
│  ├─ /room group create [名称]  - 创建一个群聊会话
│  ├─ /room group del <ID>       - 删除对应ID的群组会话
│  └─ /room group list           - 列出所有已创建的群组会话与ID
.
├─ 会话操作:
│  ├─ /room join <ID>  - 加入对应群组会话
│  └─ /room leave      - 退出当前群组会话
.
说明:
- 个人会话：仅供您自己使用，其他人无法加入，会话ID为6位
- 群组会话：可以创建多个群组会话，任何人都可以加入，会话ID为6位
- 管理员和主人可以直接删除任何群组会话
- 普通用户只能删除自己创建的群组会话"""
        
        await self.send_message(websocket, help_text,
                              group_id=data.get("group_id"), 
                              user_id=data.get("sender", {}).get("user_id"))

    async def _handle_room_info(self, websocket, data):
        """处理 /room info 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        group_id = data.get("group_id")
        
        if group_id:
            # 群聊中，查看群组的会话
            room = self.room_manager.get_group_room(str(group_id))
            if room:
                info_text = f"""[群组会话信息]
.
群组ID: {group_id}
会话ID: {room.room_id}
会话名称: {room.name}
创建者: {room.creator_id}
创建时间: {room.created_at}
成员数量: {len(room.members)}"""
            else:
                info_text = f"[群组会话信息]\n.\n群组ID: {group_id}\n状态: 未加入任何会话"
        else:
            # 私聊中，查看用户的会话
            room = self.room_manager.get_user_room(str(sender_id))
            if room:
                info_text = f"""[私聊会话信息]
.
用户ID: {sender_id}
会话ID: {room.room_id}
会话名称: {room.name}
创建时间: {room.created_at}"""
            else:
                info_text = f"[私聊会话信息]\n.\n用户ID: {sender_id}\n状态: 未创建任何会话"
        
        await self.send_message(websocket, info_text,
                              group_id=group_id, 
                              user_id=sender_id)

    async def _handle_room_exit(self, websocket, data):
        """处理 /room exit 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        group_id = data.get("group_id")
        
        if group_id:
            # 群聊中，退出群组会话
            success = self.room_manager.leave_room(str(sender_id), str(group_id))
            if success:
                response = "已成功退出群组会话"
            else:
                response = "退出群组会话失败：您可能不在任何群组会话中"
        else:
            # 私聊中，删除用户的会话
            room = self.room_manager.get_user_room(str(sender_id))
            if room:
                # 删除会话（会清除聊天记忆和人格设置）
                success = self.room_manager.delete_room(room.room_id)
                if success:
                    response = "已成功退出并删除当前会话\n\n会话的聊天记忆和人格设置已清除"
                else:
                    response = "删除会话失败"
            else:
                response = "您当前没有活跃的会话"
        
        await self.send_message(websocket, response,
                              group_id=group_id, 
                              user_id=sender_id)

    async def _handle_room_new(self, websocket, data):
        """处理 /room new 指令"""
        sender = data.get("sender", {})
        sender_id = str(sender.get("user_id"))
        group_id = data.get("group_id")
        
        # 先检查是否已有个人会话
        existing_room = self.room_manager.get_user_room(sender_id)
        if existing_room:
            # 删除旧会话（会自动清除记忆文件）
            self.room_manager.delete_room(existing_room.room_id)
        
        # 创建新的个人会话
        room = self.room_manager.create_room(
            room_type='private',
            name=f"个人会话_{sender_id}",
            creator_id=sender_id
        )
        
        response = f"已创建新的个人会话\n会话ID: {room.room_id}\n\n旧会话的聊天记忆和人格设置已清除，已恢复默认人格\n注意：个人会话仅供您自己使用，其他人无法加入"
        
        await self.send_message(websocket, response,
                              group_id=group_id, 
                              user_id=sender_id)

    async def _handle_room_group_create(self, websocket, data, args):
        """处理 /room group create 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 解析会话名称
        room_name = args.strip() if args.strip() else f"群组会话_{sender_id}"
        
        # 创建群组会话
        room = self.room_manager.create_room(
            room_type='group',
            name=room_name,
            creator_id=str(sender_id),
            members=[str(sender_id)]
        )
        
        response = f"""[群组会话创建成功]
.
会话ID: {room.room_id}
会话名称: {room.name}
创建者: {sender_id}

提示：使用 /room join {room.room_id} 加入此会话"""
        
        await self.send_message(websocket, response,
                              group_id=data.get("group_id"), 
                              user_id=sender_id)

    async def _handle_room_group_del(self, websocket, data, args):
        """处理 /room group del 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        
        if not args:
            await self.send_message(websocket, "用法: /room group del <会话ID>",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        room_id = args.strip()
        room = self.room_manager.get_room(room_id)
        
        if not room:
            await self.send_message(websocket, f"会话不存在: {room_id}",
                                  group_id=data.get("group_id"), 
                                  user_id=sender_id)
            return
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        permission_level = get_user_permission_level(str(sender_id), self.config_manager.config_data)
        
        # 主人和管理员可以删除任何群组会话
        # 普通用户只能删除自己创建的群组会话
        if permission_level >= 2 or str(sender_id) == room.creator_id:
            success = self.room_manager.delete_room(room_id)
            if success:
                response = f"已成功删除群组会话: {room.name} ({room_id})"
            else:
                response = "删除群组会话失败"
        else:
            response = "权限不足：您只能删除自己创建的群组会话"
        
        await self.send_message(websocket, response,
                              group_id=data.get("group_id"), 
                              user_id=sender_id)

    async def _handle_room_group_list(self, websocket, data):
        """处理 /room group list 指令"""
        # 获取所有群组会话
        group_rooms = self.room_manager.list_rooms(room_type='group')
        
        if not group_rooms:
            response = "[群组会话列表]\n.\n暂无群组会话"
        else:
            response = "[群组会话列表]\n."
            for i, room in enumerate(group_rooms, 1):
                response += f"\n├─ {i}. {room.name}"
                response += f"\n│  ├─ 会话ID: {room.room_id}"
                response += f"\n│  ├─ 创建者: {room.creator_id}"
                response += f"\n│  └─ 成员数: {len(room.members)}"
            
            response += f"\n.\n共 {len(group_rooms)} 个群组会话"
        
        await self.send_message(websocket, response,
                              group_id=data.get("group_id"), 
                              user_id=data.get("sender", {}).get("user_id"))

    async def _handle_room_join(self, websocket, data, args):
        """处理 /room join 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        group_id = data.get("group_id")
        
        if not args:
            await self.send_message(websocket, "用法: /room join <会话ID>",
                                  group_id=group_id, 
                                  user_id=sender_id)
            return
        
        room_id = args.strip()
        room = self.room_manager.get_room(room_id)
        
        if not room:
            await self.send_message(websocket, f"会话不存在: {room_id}",
                                  group_id=group_id, 
                                  user_id=sender_id)
            return
        
        if room.room_type != 'group':
            await self.send_message(websocket, "只能加入群组会话",
                                  group_id=group_id, 
                                  user_id=sender_id)
            return
        
        # 加入会话
        success, error_msg = self.room_manager.join_room(str(sender_id), room_id)
        
        if success:
            # 如果在群聊中，绑定群组到会话
            if group_id:
                self.room_manager.bind_group_to_room(str(group_id), room_id)
                # 保存当前私聊会话（如果有）
                self.room_manager.switch_to_group_room(str(sender_id), str(group_id))
            
            response = f"已成功加入群组会话: {room.name}\n会话ID: {room.room_id}\n\n(您的私聊会话已自动保存，退出群组后将恢复)"
        else:
            response = f"加入会话失败: {error_msg}"
        
        await self.send_message(websocket, response,
                              group_id=group_id, 
                              user_id=sender_id)

    async def _handle_room_leave(self, websocket, data):
        """处理 /room leave 指令"""
        sender = data.get("sender", {})
        sender_id = sender.get("user_id")
        group_id = data.get("group_id")
        
        if not group_id:
            await self.send_message(websocket, "/room leave 指令只能在群聊中使用",
                                  group_id=group_id, 
                                  user_id=sender_id)
            return
        
        # 退出群组会话
        success = self.room_manager.leave_room(str(sender_id), str(group_id))
        
        if success:
            # 自动切换回私聊会话
            private_room = self.room_manager.switch_to_private_room(str(sender_id))
            if private_room:
                response = f"已成功退出当前群组会话\n\n已自动切换回私聊会话: {private_room.name} (ID: {private_room.room_id})"
            else:
                response = "已成功退出当前群组会话"
        else:
            response = "退出群组会话失败：您可能不在任何群组会话中"
        
        await self.send_message(websocket, response,
                              group_id=group_id, 
                              user_id=sender_id)