#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 应用程序核心类
"""

import asyncio
import signal
import sys
import os
import datetime
from colorama import init, Fore, Style

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from .config import ConfigManager
from .bot_manager import BotManager

# 初始化 colorama
init(autoreset=True)

class LinDreamApp:
    """LinDream 应用程序主类"""
    
    def __init__(self):
        self.config_manager = None
        self.bot_manager = None
        self.running = False
    
    def print_startup_banner(self):
        """打印启动横幅"""
        banner = r"""
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                             _     _                                          ║
    ║                            | |   | |                                         ║
    ║                            | |__ | | __ _ _ __   __ _  ___                   ║
    ║                            | '_ \| |/ _` | '_ \ / _` |/ _ \                  ║
    ║                            | |_) | | (_| | | | | (_| | (_) |                 ║
    ║                            |_.__/|_|\__,_|_| |_|\__, |\___/                  ║
    ║                                                   __/ |                      ║
    ║                                                  |___/                       ║
    ║                         LinDream - 多功能QQ机器人系统                        ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """
        print(Fore.CYAN + Style.BRIGHT + banner)
        print(Fore.YELLOW + Style.BRIGHT + "    启动时间: " + self.now())
        print(Fore.LIGHTYELLOW_EX + "    " + "="*60)

    def now(self):
        """获取当前时间字符串"""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def print_config_summary(self):
        """打印配置摘要"""
        config = self.config_manager.config_data
        print(Fore.LIGHTGREEN_EX + Style.BRIGHT + "\n    [配置摘要]")
        print(Fore.LIGHTGREEN_EX + f"    机器人QQ: {Fore.WHITE}{self.config_manager.bot_id}")
        print(Fore.LIGHTGREEN_EX + f"    WebSocket地址: {Fore.WHITE}{config.get('websocket', {}).get('host', '127.0.0.1')}:{config.get('websocket', {}).get('port', 2048)}")
        print(Fore.LIGHTGREEN_EX + f"    并发控制: {Fore.WHITE}最大并发:{config.get('performance', {}).get('max_concurrent_messages', 50)}, 速率限制:{config.get('performance', {}).get('message_rate_limit', 10)}/秒")

    def print_startup_info(self):
        """打印启动信息"""
        config = self.config_manager.config_data
        print(Fore.LIGHTYELLOW_EX + "    " + "="*60)
        print(Fore.LIGHTBLUE_EX + Style.BRIGHT + "    系统信息:")
        print(Fore.LIGHTBLUE_EX + f"    服务器地址: {Fore.WHITE}ws://{config.get('websocket', {}).get('host', '0.0.0.0')}:{config.get('websocket', {}).get('port', 2048)}")
        print(Fore.LIGHTBLUE_EX + f"    当前工作目录: {Fore.WHITE}{os.getcwd()}")
        print(Fore.LIGHTBLUE_EX + f"    Python版本: {Fore.WHITE}{'.'.join(map(str, __import__('sys').version_info[:3]))}")
        print(Fore.LIGHTBLUE_EX + Style.BRIGHT + "\n    [状态] 系统初始化完成，等待连接...")
        print(Fore.LIGHTYELLOW_EX + "    " + "="*60 + "\n")

    async def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler():
            print("\n正在关闭 LinDream...")
            self.running = False
            if self.bot_manager:
                print("资源清理完成")
        
        # 添加信号处理器
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

    async def run(self):
        """运行应用程序"""
        print("正在启动 LinDream QQ 机器人系统...")
        
        # 打印启动横幅
        self.print_startup_banner()
        
        # 初始化配置
        self.config_manager = ConfigManager()
        
        # 打印配置摘要
        self.print_config_summary()
        
        # 初始化机器人管理器
        self.bot_manager = BotManager(self.config_manager)
        
        # 打印启动信息
        self.print_startup_info()
        
        self.running = True
        
        try:
            # 启动服务器
            await self.bot_manager.start_server()
        except KeyboardInterrupt:
            print("\n正在关闭服务器...")
        except Exception as e:
            print(f"服务器运行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.bot_manager:
                await self.bot_manager.stop_server()
            print("LinDream 已关闭")