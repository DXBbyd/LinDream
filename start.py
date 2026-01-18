#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream 配置文件生成向导
引导用户生成配置文件
"""

import json
import os
import sys
from datetime import datetime


class ConfigGenerator:
    """配置生成器"""
    
    def __init__(self):
        self.config_data = {}
        self.config_dir = os.path.join("data", "config")
    
    def print_header(self):
        """打印标题"""
        print("\n" + "="*60)
        print("LinDream 配置文件生成向导")
        print("="*60)
        print()
    
    def print_step(self, step: int, title: str):
        """打印步骤标题"""
        print(f"\n[{step}] {title}")
        print("-" * 60)
    
    def get_input(self, prompt: str, default: str = None, required: bool = True) -> str:
        """获取用户输入"""
        if default:
            prompt = f"{prompt} [默认: {default}]: "
        else:
            prompt = f"{prompt}: "
        
        while True:
            value = input(prompt).strip()
            
            if not value:
                if default:
                    return default
                elif not required:
                    return ""
                else:
                    print("此项为必填项，请输入。")
                    continue
            
            return value
    
    def get_boolean_input(self, prompt: str, default: bool = True) -> bool:
        """获取布尔输入"""
        default_str = "Y/n" if default else "y/N"
        while True:
            value = input(f"{prompt} [{default_str}]: ").strip().lower()
            if not value:
                return default
            if value in ['y', 'yes', '是']:
                return True
            if value in ['n', 'no', '否']:
                return False
            print("请输入 Y/yes/是 或 N/no/否")
    
    def get_integer_input(self, prompt: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
        """获取整数输入"""
        while True:
            if default is not None:
                value_str = input(f"{prompt} [默认: {default}]: ").strip()
            else:
                value_str = input(f"{prompt}: ").strip()
            
            if not value_str:
                if default is not None:
                    return default
                print("此项为必填项，请输入。")
                continue
            
            try:
                value = int(value_str)
                if min_val is not None and value < min_val:
                    print(f"值不能小于 {min_val}")
                    continue
                if max_val is not None and value > max_val:
                    print(f"值不能大于 {max_val}")
                    continue
                return value
            except ValueError:
                print("请输入有效的整数。")
    
    def step_bot_config(self):
        """步骤1: 机器人基本配置"""
        self.print_step(1, "机器人基本配置")
        
        bot_id = self.get_input("请输入机器人QQ号", required=True)
        while not bot_id.isdigit():
            print("QQ号必须为数字")
            bot_id = self.get_input("请输入机器人QQ号", required=True)
        
        self.config_data["bot_id"] = bot_id
        print(f"✓ 机器人QQ号: {bot_id}")
    
    def step_websocket_config(self):
        """步骤2: WebSocket配置"""
        self.print_step(2, "WebSocket配置")
        
        host = self.get_input("WebSocket服务器地址", default="127.0.0.1")
        port = self.get_integer_input("WebSocket服务器端口", default=2048, min_val=1, max_val=65535)
        max_connections = self.get_integer_input("最大连接数", default=100, min_val=1)
        
        self.config_data["websocket"] = {
            "host": host,
            "port": port,
            "max_connections": max_connections
        }
        print(f"✓ WebSocket配置: {host}:{port} (最大连接: {max_connections})")
    
    def step_logging_config(self):
        """步骤3: 日志配置"""
        self.print_step(3, "日志配置")
        
        level = self.get_input("日志级别 (DEBUG/INFO/WARNING/ERROR)", default="INFO")
        max_files = self.get_integer_input("最大日志文件数量", default=101, min_val=1)
        
        self.config_data["logging"] = {
            "level": level,
            "max_files": max_files,
            "formats": {
                "system": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "friend": "%(asctime)s - %(message)s",
                "group": "%(asctime)s - %(message)s"
            }
        }
        print(f"✓ 日志配置: {level} 级别, 最多 {max_files} 个文件")
    
    def step_download_config(self):
        """步骤4: 下载配置"""
        self.print_step(4, "下载配置")
        
        max_workers = self.get_integer_input("最大下载线程数", default=3, min_val=1, max_val=10)
        
        self.config_data["download"] = {
            "max_workers": max_workers
        }
        print(f"✓ 下载配置: 最多 {max_workers} 个线程")
    
    def step_performance_config(self):
        """步骤5: 性能配置"""
        self.print_step(5, "性能配置")
        
        self.config_data["performance"] = {
            "max_concurrent_messages": self.get_integer_input("最大并发消息数", default=50, min_val=1),
            "message_rate_limit": self.get_integer_input("消息速率限制 (每秒)", default=10, min_val=1),
            "task_timeout": self.get_integer_input("任务超时时间 (秒)", default=30, min_val=1),
            "max_worker_threads": self.get_integer_input("最大工作线程数", default=10, min_val=1),
            "max_video_cache_size": self.get_integer_input("最大视频缓存数量", default=10, min_val=0),
            "message_cache_size": self.get_integer_input("消息缓存大小", default=1000, min_val=1),
            "session_history_limit": self.get_integer_input("会话历史限制", default=20, min_val=0),
            "video_cleanup_delay": self.get_integer_input("视频清理延迟 (秒)", default=600, min_val=0)
        }
        print("✓ 性能配置已设置")
    
    def step_ai_config(self):
        """步骤6: AI配置"""
        self.print_step(6, "AI配置")
        
        enable_ai = self.get_boolean_input("是否启用AI功能", default=False)
        
        if enable_ai:
            api_key = self.get_input("AI API密钥", required=False)
            api_url = self.get_input("AI API地址", required=False)
            model_name = self.get_input("模型名称", default="default")
        else:
            api_key = ""
            api_url = ""
            model_name = "default"
        
        self.config_data["ai_config"] = {
            "api_key": api_key,
            "api_url": api_url,
            "model_name": model_name
        }
        print(f"✓ AI配置: {'已启用' if enable_ai and api_key else '未启用'}")
    
    def step_owners_config(self):
        """步骤7: 主人配置"""
        self.print_step(7, "主人配置")
        
        print("主人拥有最高权限（等级3），可以执行所有操作包括设置管理员。")
        
        owners = []
        add_owner = True
        
        while add_owner:
            owner_qq = self.get_input("请输入主人QQ号 (留空结束)", required=False)
            if not owner_qq:
                break
            if not owner_qq.isdigit():
                print("QQ号必须为数字")
                continue
            owners.append(owner_qq)
            add_owner = self.get_boolean_input("是否继续添加主人", default=False)
        
        if not owners:
            print("⚠️  警告: 未配置主人，将无法执行高级管理操作")
        
        self.config_data["owners"] = owners
        print(f"✓ 主人配置: {len(owners)} 个主人")
    
    def save_main_config(self):
        """保存主配置文件"""
        config_file = os.path.join(self.config_dir, "mainconfig.json")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 主配置文件已保存: {config_file}")
    
    def create_websocket_config(self):
        """创建WebSocket配置文件"""
        ws_config_file = os.path.join(self.config_dir, "websocket.json")
        ws_config = {
            "host": self.config_data["websocket"]["host"],
            "port": self.config_data["websocket"]["port"],
            "max_connections": self.config_data["websocket"]["max_connections"]
        }
        
        with open(ws_config_file, 'w', encoding='utf-8') as f:
            json.dump(ws_config, f, ensure_ascii=False, indent=2)
        
        print(f"✓ WebSocket配置文件已保存: {ws_config_file}")
    
    def create_log_config(self):
        """创建日志配置文件"""
        log_config_file = os.path.join(self.config_dir, "log.json")
        log_config = self.config_data["logging"]
        
        with open(log_config_file, 'w', encoding='utf-8') as f:
            json.dump(log_config, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 日志配置文件已保存: {log_config_file}")
    
    def create_runtime_status_config(self):
        """创建运行状态配置文件"""
        runtime_config_file = os.path.join(self.config_dir, "runtime_status.json")
        runtime_config = {
            "last_shutdown": datetime.now().isoformat(),
            "system_status": "normal"
        }
        
        with open(runtime_config_file, 'w', encoding='utf-8') as f:
            json.dump(runtime_config, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 运行状态配置文件已保存: {runtime_config_file}")
    
    def create_security_hash_config(self):
        """创建安全哈希配置文件（空配置）"""
        security_config_file = os.path.join(self.config_dir, "security_hash.json")
        security_config = {
            "password_hash": "",
            "created_at": datetime.now().isoformat()
        }
        
        with open(security_config_file, 'w', encoding='utf-8') as f:
            json.dump(security_config, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 安全哈希配置文件已保存: {security_config_file}")
    
    def complete_missing_config(self, config_path: str, missing_keys: list):
        """补全缺少的配置项"""
        # 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("\n" + "="*60)
        print("补全配置项")
        print("="*60)
        
        # 补全缺少的配置项
        for key in missing_keys:
            key_name = key.split(' (')[0]  # 移除括号中的说明
            
            if key_name == 'bot_id':
                print(f"\n[补全] 机器人QQ号")
                bot_id = self.get_input("请输入机器人QQ号", required=True)
                while not bot_id.isdigit():
                    print("QQ号必须为数字")
                    bot_id = self.get_input("请输入机器人QQ号", required=True)
                config["bot_id"] = bot_id
                print(f"✓ 机器人QQ号: {bot_id}")
            
            elif key_name == 'websocket':
                print(f"\n[补全] WebSocket配置")
                host = self.get_input("WebSocket服务器地址", default="127.0.0.1")
                port = self.get_integer_input("WebSocket服务器端口", default=2048, min_val=1, max_val=65535)
                max_connections = self.get_integer_input("最大连接数", default=100, min_val=1)
                
                config["websocket"] = {
                    "host": host,
                    "port": port,
                    "max_connections": max_connections
                }
                print(f"✓ WebSocket配置: {host}:{port} (最大连接: {max_connections})")
            
            elif key_name == 'ai_config':
                print(f"\n[补全] AI配置")
                enable_ai = self.get_boolean_input("是否启用AI功能", default=False)
                
                if enable_ai:
                    api_key = self.get_input("AI API密钥", required=False)
                    api_url = self.get_input("AI API地址", required=False)
                    model_name = self.get_input("模型名称", default="default")
                else:
                    api_key = ""
                    api_url = ""
                    model_name = "default"
                
                config["ai_config"] = {
                    "api_key": api_key,
                    "api_url": api_url,
                    "model_name": model_name
                }
                print(f"✓ AI配置: {'已启用' if enable_ai and api_key else '未启用'}")
            
            elif key_name == 'owners':
                print(f"\n[补全] 主人配置")
                print("主人拥有最高权限（等级3），可以执行所有操作包括设置管理员。")
                
                owners = []
                add_owner = True
                
                while add_owner:
                    owner_qq = self.get_input("请输入主人QQ号 (留空结束)", required=False)
                    if not owner_qq:
                        break
                    if not owner_qq.isdigit():
                        print("QQ号必须为数字")
                        continue
                    owners.append(owner_qq)
                    add_owner = self.get_boolean_input("是否继续添加主人", default=False)
                
                if not owners:
                    print("⚠️  警告: 未配置主人，将无法执行高级管理操作")
                
                config["owners"] = owners
                print(f"✓ 主人配置: {len(owners)} 个主人")
        
        # 保存更新后的配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print("\n" + "="*60)
        print("配置补全完成！")
        print("="*60)
        print(f"\n配置文件已更新: {config_path}")
    
    def run(self):
        """运行配置生成向导"""
        self.print_header()
        
        print("本向导将引导您完成LinDream的配置文件生成。")
        print("请根据提示输入相应的配置信息。")
        print("\n按回车键继续...")
        input()
        
        # 执行各个配置步骤
        self.step_bot_config()
        self.step_websocket_config()
        self.step_logging_config()
        self.step_download_config()
        self.step_performance_config()
        self.step_ai_config()
        self.step_owners_config()
        
        # 保存所有配置文件
        self.save_main_config()
        self.create_websocket_config()
        self.create_log_config()
        self.create_runtime_status_config()
        self.create_security_hash_config()
        
        # 显示总结
        print("\n" + "="*60)
        print("配置完成！")
        print("="*60)
        print("\n已创建的配置文件:")
        print(f"  - {os.path.join(self.config_dir, 'mainconfig.json')}")
        print(f"  - {os.path.join(self.config_dir, 'websocket.json')}")
        print(f"  - {os.path.join(self.config_dir, 'log.json')}")
        print(f"  - {os.path.join(self.config_dir, 'runtime_status.json')}")
        print(f"  - {os.path.join(self.config_dir, 'security_hash.json')}")
        print("\n下一步:")
        print("  1. 检查并修改配置文件中的API密钥等敏感信息")
        print("  2. 运行 'python main.py' 启动机器人")
        print("="*60)
        print()


def main():
    """主函数"""
    generator = ConfigGenerator()
    
    # 确保配置目录存在
    os.makedirs(generator.config_dir, exist_ok=True)
    
    # 检查是否是第一次启动
    config_files = {
        "mainconfig.json": os.path.join(generator.config_dir, "mainconfig.json"),
        "websocket.json": os.path.join(generator.config_dir, "websocket.json"),
        "log.json": os.path.join(generator.config_dir, "log.json"),
        "runtime_status.json": os.path.join(generator.config_dir, "runtime_status.json"),
        "security_hash.json": os.path.join(generator.config_dir, "security_hash.json")
    }
    
    # 检查所有配置文件是否存在
    existing_files = []
    missing_files = []
    invalid_files = []
    
    for file_name, file_path in config_files.items():
        if os.path.exists(file_path):
            # 检查文件是否可以读取
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                existing_files.append(file_name)
            except json.JSONDecodeError as e:
                invalid_files.append((file_name, f"JSON语法错误: {e}"))
            except Exception as e:
                invalid_files.append((file_name, f"读取错误: {e}"))
        else:
            missing_files.append(file_name)
    
    # 如果是第一次启动（所有文件都不存在）
    if not existing_files and not invalid_files:
        print("检测到首次启动，正在初始化配置...")
        print()
        try:
            generator.run()
        except KeyboardInterrupt:
            print("\n\n配置生成已被用户中断。")
            sys.exit(1)
        except Exception as e:
            print(f"\n配置生成过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        return
    
    # 如果有配置文件，进行检查
    print("="*60)
    print("配置文件检查")
    print("="*60)
    
    # 显示检查结果
    if existing_files:
        print(f"\n✓ 存在的配置文件 ({len(existing_files)}):")
        for file_name in existing_files:
            print(f"  - {file_name}")
    
    if missing_files:
        print(f"\n✗ 缺失的配置文件 ({len(missing_files)}):")
        for file_name in missing_files:
            print(f"  - {file_name}")
    
    if invalid_files:
        print(f"\n⚠️  无效的配置文件 ({len(invalid_files)}):")
        for file_name, reason in invalid_files:
            print(f"  - {file_name}: {reason}")
    
    # 检查主配置文件的完整性
    main_config_path = config_files["mainconfig.json"]
    missing_keys = []
    
    if os.path.exists(main_config_path):
        try:
            with open(main_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 检查必需的配置项
            required_keys = ['bot_id', 'websocket', 'ai_config', 'owners']
            for key in required_keys:
                if key not in config:
                    missing_keys.append(key)
                elif key == 'bot_id' and not config.get('bot_id'):
                    missing_keys.append(f"{key} (值为空)")
                elif key == 'owners' and not config.get('owners'):
                    missing_keys.append(f"{key} (值为空)")
            
            if missing_keys:
                print(f"\n✗ 主配置文件缺少配置项:")
                for key in missing_keys:
                    print(f"  - {key}")
            else:
                print(f"\n✓ 主配置文件配置项完整")
        except Exception as e:
            print(f"\n✗ 无法检查主配置文件: {e}")
    
    # 根据检查结果决定下一步
    print("\n" + "="*60)
    
    if missing_files or invalid_files or missing_keys:
        print("检测到配置问题，需要修复。")
        print("\n选项:")
        
        if missing_files or invalid_files:
            print("  1. 重新生成所有配置文件（将覆盖现有配置）")
        
        if missing_keys:
            print("  2. 补全缺少的配置项（保留现有配置）")
        
        print("  3. 退出")
        
        choice = input("\n请选择: ").strip()
        
        if choice == '1' and (missing_files or invalid_files):
            print("\n正在重新生成配置文件...")
            try:
                generator.run()
            except KeyboardInterrupt:
                print("\n\n配置生成已被用户中断。")
                sys.exit(1)
            except Exception as e:
                print(f"\n配置生成过程中发生错误: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        elif choice == '2' and missing_keys:
            print("\n正在补全缺少的配置项...")
            try:
                generator.complete_missing_config(main_config_path, missing_keys)
            except KeyboardInterrupt:
                print("\n\n配置补全已被用户中断。")
                sys.exit(1)
            except Exception as e:
                print(f"\n配置补全过程中发生错误: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        else:
            print("已取消配置生成。")
            return
    else:
        print("✓ 所有配置文件检查通过！")
        print("\n提示: 如需重新配置，请删除 data/config 目录后再次运行此脚本")
        return


if __name__ == "__main__":
    main()