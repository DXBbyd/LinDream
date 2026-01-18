import asyncio
import websockets
import json
import datetime
import sys
import os
import time
import uuid
from typing import Dict, Any, Optional

# 获取当前文件的目录，并添加到 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from .config import ConfigManager
from .performance import PerformanceMonitor, MessageQueue, ConnectionPool, CacheManager, performance_monitor_task
from .message_handler import MessageHandler
from modules.plugin_system import PluginManager
from modules.rate_limiter import RateLimiter
from modules.logging import Logger
from modules.media_handler import MediaHandler

class BotManager:
    """优化的机器人管理器（集成事件总线）"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.plugin_manager = PluginManager()
        self.rate_limiter = RateLimiter(config_manager)
        self.logger = Logger(config_manager)
        self.message_handler = MessageHandler(config_manager, self.plugin_manager, self.rate_limiter, self.logger)
        self.media_handler = MediaHandler(config_manager, self.logger)
        
        # 性能监控组件
        self.performance_monitor = PerformanceMonitor()
        self.message_queue = MessageQueue(max_size=10000)
        self.connection_pool = ConnectionPool(max_connections=100)
        self.cache_manager = CacheManager(max_size=1000, ttl=3600)
        
        # 机器人状态
        self.bot_id = config_manager.bot_id
        self.running = False
        self.server = None
        self.tasks = []
        
        # 创建必要的目录
        self.create_data_directories()
    
    def create_data_directories(self):
        """创建数据目录"""
        file_base_dir = os.path.join("data", "file")
        files_base_dir = os.path.join("data", "files")
        group_files_dir = os.path.join("data", "files", "group")
        friend_files_dir = os.path.join("data", "files", "friend")
        os.makedirs(file_base_dir, exist_ok=True)
        os.makedirs(files_base_dir, exist_ok=True)
        os.makedirs(group_files_dir, exist_ok=True)
        os.makedirs(friend_files_dir, exist_ok=True)
        os.makedirs("plugin", exist_ok=True)
    
    async def start_server(self):
        """启动WebSocket服务器"""
        self.running = True
        
        # 加载插件
        self.plugin_manager.load_plugins()
        self.plugin_manager.load_patches(self.config_manager.config_data)
        
        # 检查并安装插件依赖
        self.plugin_manager.check_and_install_plugin_dependencies()
        
        # 启动消息处理器
        await self.message_queue.start_processors(self._process_message_from_queue, num_workers=3)
        
        # 启动WebSocket服务器
        host = self.config_manager.get("websocket", {}).get("host", "0.0.0.0")
        port = self.config_manager.get("websocket", {}).get("port", 2048)
        
        print(f"正在启动服务器: ws://{host}:{port}")
        
        self.server = await websockets.serve(
            self.handle_connection,
            host,
            port,
            max_size=10 * 1024 * 1024,  # 10MB 最大消息大小
            max_queue=1000,  # 最大队列大小
            ping_interval=20,  # 心跳间隔
            ping_timeout=10    # 心跳超时
        )
        
        print(f"服务器已在 ws://{host}:{port} 启动")
        
        # 启动后台任务
        self.tasks = [
            asyncio.create_task(self.media_handler.download_worker()),
            asyncio.create_task(self.message_handler.periodic_cleanup()),
            asyncio.create_task(self._cleanup_task()),
            asyncio.create_task(performance_monitor_task(self.performance_monitor, interval=60))
        ]
        
        await self.server.wait_closed()
    
    async def handle_connection(self, connection):
        """处理WebSocket连接"""
        connection_id = str(uuid.uuid4())
        self.connection_pool.add_connection(connection_id, connection)
        self.performance_monitor.update_connection_count(self.connection_pool.get_stats()['active_connections'])
        
        print(f"新连接: {connection.remote_address} (ID: {connection_id})")
        
        try:
            async for message in connection:
                await self.handle_message(connection, message, connection_id)
        except websockets.exceptions.ConnectionClosed:
            print(f"连接已关闭: {connection.remote_address} (ID: {connection_id})")
        except Exception as e:
            print(f"处理连接时出错: {e}")
            self.performance_monitor.record_error()
        finally:
            self.connection_pool.remove_connection(connection_id)
            self.performance_monitor.update_connection_count(self.connection_pool.get_stats()['active_connections'])
    
    async def handle_message(self, websocket, message, connection_id: str):
        """处理接收到的消息"""
        start_time = time.time()
        
        try:
            data = json.loads(message)
            
            # 记录系统事件
            if data.get("post_type") == "meta_event":
                self.logger.log_system_event(data)
                return
            
            # 处理戳一戳事件
            if data.get("post_type") == "notice" and data.get("notice_type") == "notify" and data.get("sub_type") == "poke":
                await self._handle_poke_event(data)
                return
            
            # 处理撤回事件
            if data.get("post_type") == "notice" and data.get("notice_type") == "group_recall":
                await self._handle_recall_event(data)
                return
            
            # 处理其他通知事件
            if data.get("post_type") == "notice":
                await self._handle_notice_event(data)
                return
            
            # 记录消息
            self.logger.log_communication(data)
            
            # 将消息添加到队列而不是直接处理
            await self.message_queue.put({
                'data': data,
                'websocket': websocket,
                'connection_id': connection_id
            })
            
        except json.JSONDecodeError:
            print("接收到了无效的JSON消息")
            self.performance_monitor.record_error()
        except Exception as e:
            print(f"处理消息时出错: {e}")
            self.performance_monitor.record_error()
        finally:
            # 记录处理时间
            duration = time.time() - start_time
            self.performance_monitor.record_message_time(duration)
    
    async def _handle_recall_event(self, data):
        """处理撤回事件"""
        from colorama import Fore, Style
        user_id = data.get('user_id', '未知')
        operator_id = data.get('operator_id', user_id)
        group_id = data.get('group_id', '未知')
        message_id = data.get('message_id', '未知')
        
        # 获取被撤回的消息内容（从消息处理器缓存）
        recalled_message_content = "消息内容不可用"
        
        # 从消息处理器获取缓存的消息内容
        if self.message_handler and hasattr(self.message_handler, 'recall_cache'):
            cached_message = self.message_handler.recall_cache.get(message_id)
            if cached_message:
                recalled_message_content = cached_message.get('message', '消息内容不可用')
        
        # 调用日志记录器记录撤回消息（传入完整的消息内容，包含图片链接）
        self.logger.log_recall(data, message_content=recalled_message_content)
        
        # 检查配置是否启用反撤回功能
        recall_enabled = self.config_manager.config_data.get("features", {}).get("recall_enabled", True)
        if recall_enabled:
            print(f"{Fore.RED}用户 {user_id} 在群 {group_id} 撤回了消息 [{recalled_message_content}] | 操作者: {operator_id}{Style.RESET_ALL}")
        else:
            print(f"{Fore.LIGHTYELLOW_EX}[撤回] {Fore.YELLOW}用户 {user_id} 在群 {group_id} 撤回了消息{Style.RESET_ALL}")

    async def _handle_poke_event(self, data):
        """处理戳一戳事件"""
        from colorama import Fore, Style
        user_id = data.get('user_id', '未知')
        target_id = data.get('target_id', '未知')
        
        # 判断戳的目标
        if str(target_id) == str(self.config_manager.bot_id):
            print(f"{Fore.LIGHTYELLOW_EX}[戳一戳] {Fore.YELLOW}用户 {user_id} 戳了戳机器人{Style.RESET_ALL}")
        else:
            print(f"{Fore.LIGHTYELLOW_EX}[戳一戳] {Fore.YELLOW}用户 {user_id} 戳了戳用户 {target_id}{Style.RESET_ALL}")
        
        # 检查配置是否启用戳一戳回复
        poke_enabled = self.config_manager.config_data.get("features", {}).get("poke_reply_enabled", True)
        if poke_enabled:
            # 如果戳的是机器人，可以考虑回复
            if str(target_id) == str(self.config_manager.bot_id):
                print(f"{Fore.LIGHTCYAN_EX}[戳一戳回复] {Fore.CYAN}机器人被戳{Style.RESET_ALL}")

    async def _handle_notice_event(self, data):
        """处理通知事件"""
        from colorama import Fore, Style
        
        notice_type = data.get("notice_type")
        if notice_type == "group_upload":
            print(f"{Fore.LIGHTBLUE_EX}[群文件上传] {Fore.BLUE}用户 {data.get('user_id', '未知')} 在群 {data.get('group_id', '未知')} 上传了文件{Style.RESET_ALL}")
        elif notice_type == "group_admin":
            sub_type = data.get("sub_type")
            if sub_type == "set":
                print(f"{Fore.LIGHTMAGENTA_EX}[群管设置] {Fore.MAGENTA}用户 {data.get('user_id', '未知')} 被设为群 {data.get('group_id', '未知')} 管理员{Style.RESET_ALL}")
            elif sub_type == "unset":
                print(f"{Fore.LIGHTMAGENTA_EX}[群管取消] {Fore.MAGENTA}用户 {data.get('user_id', '未知')} 被取消群 {data.get('group_id', '未知')} 管理员{Style.RESET_ALL}")
        elif notice_type == "group_decrease":
            sub_type = data.get('sub_type')
            user_id = data.get('user_id', '未知')
            group_id = data.get('group_id', '未知')
            operator_id = data.get('operator_id', user_id)
            
            if sub_type == "leave":
                print(f"{Fore.LIGHTRED_EX}[群成员退出] {Fore.RED}用户 {user_id} 退出了群 {group_id}{Style.RESET_ALL}")
            elif sub_type == "kick":
                print(f"{Fore.LIGHTRED_EX}[群成员被踢] {Fore.RED}用户 {user_id} 被 {operator_id} 踢出群 {group_id}{Style.RESET_ALL}")
            elif sub_type == "kick_me":
                print(f"{Fore.LIGHTRED_EX}[机器人被踢] {Fore.RED}机器人被踢出群 {group_id}{Style.RESET_ALL}")
        elif notice_type == "group_increase":
            sub_type = data.get("sub_type")
            user_id = data.get('user_id', '未知')
            group_id = data.get('group_id', '未知')
            operator_id = data.get('operator_id', user_id)
            
            if sub_type == "approve":
                print(f"{Fore.LIGHTGREEN_EX}[群成员加入] {Fore.GREEN}用户 {user_id} 通过审批加入群 {group_id}{Style.RESET_ALL}")
            elif sub_type == "invite":
                print(f"{Fore.LIGHTGREEN_EX}[群成员邀请] {Fore.GREEN}用户 {user_id} 通过邀请加入群 {group_id}{Style.RESET_ALL}")
        elif notice_type == "friend_add":
            print(f"{Fore.LIGHTCYAN_EX}[好友添加] {Fore.CYAN}用户 {data.get('user_id', '未知')} 添加了机器人为好友{Style.RESET_ALL}")
        elif notice_type == "group_ban":
            sub_type = data.get("sub_type")
            if sub_type == "ban":
                print(f"{Fore.LIGHTRED_EX}[群禁言] {Fore.RED}用户 {data.get('user_id', '未知')} 在群 {data.get('group_id', '未知')} 被禁言{Style.RESET_ALL}")
            elif sub_type == "lift_ban":
                print(f"{Fore.LIGHTGREEN_EX}[群解禁] {Fore.GREEN}用户 {data.get('user_id', '未知')} 在群 {data.get('group_id', '未知')} 被解除禁言{Style.RESET_ALL}")
        elif notice_type == "notify" and data.get("sub_type") == "poke":
            # 戳一戳事件已经在_handle_poke_event中处理了，这里是为了确保不会遗漏
            pass
        else:
            print(f"{Fore.LIGHTWHITE_EX}[通知] {Fore.WHITE}{notice_type} 事件{Style.RESET_ALL}")
            # 根据配置决定是否显示详细信息
            if self.config_manager.config_data.get("features", {}).get("show_detailed_notice", False):
                print(f"  详情: {json.dumps(data, ensure_ascii=False)[:100]}...")

    async def _process_message_from_queue(self, message_item, worker_id: int):
        """从队列处理消息的工作协程"""
        try:
            # 检查消息项是否完整
            if not all(key in message_item for key in ['data', 'websocket']):
                print(f"消息处理器 {worker_id}: 消息数据不完整，跳过处理")
                return
            
            data = message_item['data']
            websocket = message_item['websocket']
            connection_id = message_item.get('connection_id', 'unknown')
            
            # 检查连接是否仍然有效
            if connection_id != 'unknown' and self.connection_pool.get_connection(connection_id) != websocket:
                return  # 连接已关闭，跳过处理
            
            # 处理消息
            await self.message_handler.process_message(websocket, data)
            
        except Exception as e:
            print(f"消息处理器 {worker_id} 出错: {e}")
            self.performance_monitor.record_error()
    
    async def _cleanup_task(self):
        """定期清理任务"""
        while self.running:
            try:
                # 清理速率限制器
                self.rate_limiter.cleanup_expired_trackers()
                
                # 清理连接池
                self.connection_pool.cleanup_old_connections()
                
                # 清理缓存
                self.cache_manager.cleanup_expired()
                
                # 等待5分钟
                await asyncio.sleep(300)
            except Exception as e:
                print(f"清理任务出错: {e}")
                await asyncio.sleep(60)
    
    async def stop_server(self):
        """停止服务器"""
        self.running = False
        print("正在停止服务器...")
        
        # 停止消息处理器
        await self.message_queue.stop_processors()
        
        # 取消所有任务
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 关闭WebSocket服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        print("服务器已停止")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            'performance': self.performance_monitor.get_stats(),
            'rate_limiter': self.rate_limiter.get_stats(),
            'connection_pool': self.connection_pool.get_stats(),
            'cache': self.cache_manager.get_stats(),
            'message_queue': {
                'size': self.message_queue.size(),
                'processing': self.message_queue.processing
            }
        }