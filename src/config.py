import json
import os
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config_data: Dict[str, Any] = {}
        self.bot_id = None
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        # 尝试从主配置文件加载
        config_path = os.path.join("data", "config", "mainconfig.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                self.bot_id = self.config_data.get("bot_id")
            except Exception as e:
                print(f"加载主配置文件失败: {e}")
                self.create_default_config()
        else:
            self.create_default_config()
        
        # 从websocket.json文件加载WebSocket配置
        self.load_websocket_config()
        
        # 从admin.txt文件加载管理员列表
        self.load_admins_from_file()
    
    def load_websocket_config(self):
        """从websocket.json文件加载WebSocket配置"""
        ws_config_path = os.path.join("data", "config", "websocket.json")
        
        if os.path.exists(ws_config_path):
            try:
                with open(ws_config_path, 'r', encoding='utf-8') as f:
                    ws_config = json.load(f)
                    # 将websocket配置合并到主配置中
                    if 'websocket' not in self.config_data:
                        self.config_data['websocket'] = {}
                    self.config_data['websocket'].update(ws_config)
            except Exception as e:
                print(f"加载WebSocket配置失败: {e}")
        else:
            # 如果websocket.json不存在，使用默认配置
            if 'websocket' not in self.config_data:
                self.config_data['websocket'] = {
                    "host": "127.0.0.1",
                    "port": 2048,
                    "max_connections": 100
                }
    
    def load_admins_from_file(self):
        """从admin.txt文件加载管理员列表"""
        admin_file_path = os.path.join("data", "other", "admin.txt")
        
        if os.path.exists(admin_file_path):
            try:
                with open(admin_file_path, 'r', encoding='utf-8') as f:
                    admin_lines = f.readlines()
                    # 过滤掉空行和注释行，提取管理员QQ号
                    admins = []
                    for line in admin_lines:
                        line = line.strip()
                        if line and not line.startswith('#') and line.isdigit():
                            admins.append(line)
                self.config_data["admins"] = admins
            except Exception as e:
                print(f"加载管理员列表失败: {e}")
                self.config_data["admins"] = []
        else:
            # 如果admin.txt不存在，初始化为空列表
            self.config_data["admins"] = []
            # 创建空的admin.txt文件
            os.makedirs(os.path.dirname(admin_file_path), exist_ok=True)
            with open(admin_file_path, 'w', encoding='utf-8') as f:
                f.write("")
    
    def create_default_config(self):
        """创建默认配置"""
        print("正在创建默认配置...")
        
        # 获取机器人QQ号
        self.bot_id = input("请输入机器人QQ号: ").strip()
        while not self.bot_id or not self.bot_id.isdigit():
            self.bot_id = input("输入无效，请输入机器人QQ号: ").strip()
        
        # 创建默认配置
        self.config_data = {
            "bot_id": self.bot_id,
            "websocket": {
                "host": "127.0.0.1",
                "port": 2048
            },
            "logging": {
                "level": "INFO",
                "save_type": "all",  # "system", "group", "all"
                "max_files": 101
            },
            "download": {
                "max_workers": 3
            },
            "performance": {
                "max_concurrent_messages": 50,
                "message_rate_limit": 10,
                "task_timeout": 30,
                "max_worker_threads": 10,
                "max_video_cache_size": 10,
                "message_cache_size": 1000,
                "session_history_limit": 20,
                "video_cleanup_delay": 600
            },
            "ai_config": {
                "api_key": "",
                "api_url": "",
                "model_name": "default"
            }
        }
        
        # 保存配置
        config_path = os.path.join("data", "config", "mainconfig.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=2)
        
        # 创建空的admin.txt文件
        admin_file_path = os.path.join("data", "other", "admin.txt")
        os.makedirs(os.path.dirname(admin_file_path), exist_ok=True)
        with open(admin_file_path, 'w', encoding='utf-8') as f:
            f.write("")
    
    def get(self, key: str, default=None):
        """获取配置值"""
        return self.config_data.get(key, default)
    
    def set(self, key: str, value):
        """设置配置值"""
        self.config_data[key] = value
    
    def update_config(self, new_config_data: Dict[str, Any]):
        """更新整个配置数据并保存到文件"""
        self.config_data = new_config_data
        self.bot_id = self.config_data.get("bot_id")
        return self.save_config()
    
    def save_config(self):
        """保存配置到文件"""
        config_path = os.path.join("data", "config", "mainconfig.json")
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False