import asyncio
import os
from core.config import ConfigManager
from core.bot_manager import BotManager

async def main():
    """主函数"""
    print("正在启动 LinDream QQ 机器人系统...")
    
    # 初始化配置
    config_manager = ConfigManager()
    
    # 初始化机器人管理器
    bot_manager = BotManager(config_manager)
    
    try:
        # 启动服务器
        await bot_manager.start_server()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        await bot_manager.stop_server()
    except Exception as e:
        print(f"服务器运行出错: {e}")
        await bot_manager.stop_server()

if __name__ == "__main__":
    asyncio.run(main())