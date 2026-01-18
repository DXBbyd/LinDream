import asyncio
import httpx
import os
import datetime
import sys
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import ConfigManager
from modules.logging import Logger

class MediaHandler:
    """媒体处理器"""
    
    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self.config_manager = config_manager
        self.logger = logger
        self.download_queue = asyncio.Queue()
        self.video_cleanup_tasks = []
        
        # 视频缓存管理
        self.video_cache = []  # 存储视频文件路径，用于LRU清理
        self.max_video_cache_size = config_manager.get("performance", {}).get("max_video_cache_size", 10)
    
    async def handle_media(self, msg: List[Dict[str, Any]], data: Dict[str, Any]) -> List[str]:
        """处理媒体文件，下载到对应的聊天目录"""
        media_files = []
        chat_dir = self._get_chat_dir(data)
        
        for m in msg:
            if m.get("type") in ["image", "video"]:
                url = m.get("data", {}).get("url")
                if url:
                    # 检查URL是否有效
                    if not url.startswith(('http://', 'https://')):
                        self.logger.log_platform_info(f"跳过无效URL: {url}")
                        continue
                        
                    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    ext = ".jpg" if m["type"] == "image" else ".mp4"
                    filename = f"{timestamp}.{ext}"
                    
                    # 下载到聊天目录
                    file_path = os.path.join(chat_dir, filename)
                    await self.download_queue.put((url, m["type"], file_path))
                    media_files.append(filename)
        return media_files

    def _get_chat_dir(self, data: Dict[str, Any]) -> str:
        """获取聊天存储目录"""
        if data.get("message_type") == "group":
            group_name = data.get("group_name", "未知群")
            group_id = data.get("group_id", "未知群号")
            safe_group_name = self._sanitize_filename(group_name)
            chat_dir = os.path.join("data", "files", "group", f"[群聊]{safe_group_name}({group_id})")
        else:
            sender = data.get("sender", {})
            user_name = sender.get("nickname", "未知用户")
            user_id = sender.get("user_id", "未知QQ号")
            safe_user_name = self._sanitize_filename(user_name)
            chat_dir = os.path.join("data", "files", "friend", f"[好友]{safe_user_name}({user_id})")
        
        os.makedirs(chat_dir, exist_ok=True)
        return chat_dir

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名，移除不安全字符"""
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        safe_name = name
        for char in unsafe_chars:
            safe_name = safe_name.replace(char, '_')
        return safe_name

    async def download_file(self, url: str, path: str) -> bool:
        """下载文件"""
        try:
            # 检查URL是否包含协议前缀
            if not url.startswith(('http://', 'https://')):
                self.logger.log_platform_info(f"下载失败: {url}, 错误: URL缺少协议前缀")
                return False
                
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    with open(path, "wb") as f:
                        f.write(response.content)
                    return True
                else:
                    self.logger.log_platform_info(f"下载失败: {url}, HTTP状态码: {response.status_code}")
        except Exception as e:
            self.logger.log_platform_info(f"下载失败: {url}, 错误: {e}")
        return False

    async def schedule_video_cleanup(self, path: str, delay: int = None):
        """安排视频清理任务"""
        # 从配置中获取清理延迟，默认10分钟
        if delay is None:
            delay = self.config_manager.get("performance", {}).get("video_cleanup_delay", 600)
        
        await asyncio.sleep(delay)
        if os.path.exists(path):
            os.remove(path)
            msg = f"[通信信息] 已清理视频: {path}"
            print(msg)
            self.logger.write_log(msg)

    async def download_worker(self):
        """下载工作器"""
        while True:
            url, file_type, file_path = await self.download_queue.get()
            if await self.download_file(url, file_path):
                msg = f"{file_type.capitalize()}已下载: {file_path}" + ("（10分钟后清理）" if file_type == "video" else "")
                self.logger.log_platform_info(msg)
                if file_type == "video":
                    # 添加到视频缓存管理
                    self.video_cache.append(file_path)
                    
                    # 检查是否超过最大缓存数量
                    if len(self.video_cache) > self.max_video_cache_size:
                        # 删除最旧的视频文件
                        oldest_video = self.video_cache.pop(0)
                        if os.path.exists(oldest_video):
                            os.remove(oldest_video)
                            self.logger.log_platform_info(f"视频缓存已满，删除最旧视频: {oldest_video}")
                    
                    # 安排定时清理
                    cleanup_task = asyncio.create_task(self.schedule_video_cleanup(file_path))
                    self.video_cleanup_tasks.append(cleanup_task)
            self.download_queue.task_done()
