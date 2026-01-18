#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 多功能QQ机器人系统
主程序入口
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from src.app import LinDreamApp

def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        # 显示帮助信息
        show_help()
        return
    
    # 检查配置文件完整性
    if not check_config_integrity():
        print("\n配置文件检查失败，请检查配置后重新启动程序。")
        print("提示: 运行 'python generate_config.py' 来生成配置文件")
        return
    
    # 创建应用实例
    app = LinDreamApp()
    
    try:
        # 运行应用
        asyncio.run(run_app(app))
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

def check_config_integrity():
    """检查配置文件完整性"""
    import json
    import os
    
    print("正在检查配置文件...")
    
    # 检查主配置文件
    config_path = os.path.join("data", "config", "mainconfig.json")
    if not os.path.exists(config_path):
        print("❌ 错误: 主配置文件不存在")
        print(f"   期望位置: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ 错误: 主配置文件格式错误")
        print(f"   {e}")
        return False
    except Exception as e:
        print(f"❌ 错误: 无法读取主配置文件")
        print(f"   {e}")
        return False
    
    # 检查必需的配置项
    required_keys = ['bot_id', 'websocket', 'ai_config']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"❌ 错误: 配置文件缺少必需的配置项: {', '.join(missing_keys)}")
        return False
    
    # 检查 bot_id
    if not config.get('bot_id'):
        print("❌ 错误: 未配置机器人QQ号")
        return False
    
    # 检查 AI 配置
    ai_config = config.get('ai_config', {})
    if not ai_config.get('api_key'):
        print("⚠️  警告: 未配置AI API密钥，AI功能将无法使用")
    
    print("✓ 配置文件检查完成")
    return True

def show_help():
    """显示帮助信息"""
    print("\n" + "="*60)
    print("LinDream 命令行工具")
    print("="*60)
    print("用法: python main.py [选项]")
    print()
    print("选项:")
    print("  --help        显示此帮助信息")
    print()
    print("示例:")
    print("  python main.py              # 启动机器人")
    print("  python generate_config.py   # 生成配置文件")
    print("="*60)

async def run_app(app: LinDreamApp):
    """运行应用程序"""
    try:
        # 运行主应用
        await app.run()
    finally:
        print("\n程序已关闭")

if __name__ == "__main__":
    main()