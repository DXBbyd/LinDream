import os
import subprocess
import sys
import importlib.util
from typing import Dict, Any, List
from colorama import init, Fore, Style

# 初始化 colorama
init(autoreset=True)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import ConfigManager
from modules.logging import Logger

class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.loaded_plugins = []
        self.applied_patches = {}
        self.config_manager = None
        self.logger = Logger(ConfigManager())
        self.plugin_dir = "plugin"
        self.plugin_data_dir = "data/plugin_data"
        
        # 确保插件数据目录存在
        os.makedirs(self.plugin_data_dir, exist_ok=True)
    
    def set_config_and_logger(self, config_manager: ConfigManager, logger):
        """设置配置管理器和日志记录器"""
        self.config_manager = config_manager
        self.logger = logger
    
    def get_plugin_data_dir(self, plugin_name: str) -> str:
        """获取插件数据目录"""
        plugin_data_path = os.path.join(self.plugin_data_dir, f"{plugin_name}_data")
        os.makedirs(plugin_data_path, exist_ok=True)
        return plugin_data_path
    
    def check_and_install_plugin_dependencies(self):
        """检查并安装插件依赖"""
        self.logger.log_platform_info("开始检查插件依赖...")
        
        # 遍历插件目录
        if not os.path.exists(self.plugin_dir):
            self.logger.log_platform_info("插件目录不存在，跳过依赖检查")
            return
        
        for plugin_name in os.listdir(self.plugin_dir):
            plugin_path = os.path.join(self.plugin_dir, plugin_name)
            if os.path.isdir(plugin_path):
                requirements_file = os.path.join(plugin_path, "requirements.txt")
                if os.path.exists(requirements_file):
                    self.logger.log_platform_info(f"正在检查插件 {plugin_name} 的依赖...")
                    
                    # 读取requirements.txt文件
                    try:
                        with open(requirements_file, 'r', encoding='utf-8') as f:
                            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                        
                        if requirements:
                            self.logger.log_platform_info(f"插件 {plugin_name} 需要安装依赖: {', '.join(requirements)}")
                            
                            # 检查是否已安装依赖
                            missing_deps = []
                            for req in requirements:
                                package_name = req.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('~=')[0]
                                try:
                                    __import__(package_name.replace('-', '_'))
                                except ImportError:
                                    try:
                                        import importlib
                                        importlib.import_module(package_name.replace('-', '_'))
                                    except ImportError:
                                        missing_deps.append(req)
                            
                            if missing_deps:
                                self.logger.log_platform_info(f"插件 {plugin_name} 缺少依赖，正在安装: {', '.join(missing_deps)}")
                                try:
                                    # 使用pip安装缺失的依赖
                                    subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_deps)
                                    self.logger.log_platform_info(f"插件 {plugin_name} 依赖安装完成")
                                except subprocess.CalledProcessError as e:
                                    self.logger.log_platform_info(f"插件 {plugin_name} 依赖安装失败: {e}")
                            else:
                                self.logger.log_platform_info(f"插件 {plugin_name} 依赖已全部安装")
                        else:
                            self.logger.log_platform_info(f"插件 {plugin_name} 无额外依赖或依赖文件为空")
                    except Exception as e:
                        self.logger.log_platform_info(f"读取插件 {plugin_name} 依赖文件失败: {e}")
                else:
                    self.logger.log_platform_info(f"插件 {plugin_name} 无 requirements.txt 文件，跳过依赖检查")

    def load_patches(self, config_data: Dict[str, Any]):
        """加载所有补丁"""
        self.applied_patches = {}
        
        patches_dir = "patches"
        if not os.path.exists(patches_dir):
            self.logger.log_platform_info("补丁目录不存在，跳过补丁加载")
            return
        
        # 自动扫描补丁目录下的所有子目录作为补丁
        all_items = os.listdir(patches_dir)
        patch_dirs = [item for item in all_items if os.path.isdir(os.path.join(patches_dir, item))]
        
        if not patch_dirs:
            self.logger.log_platform_info("补丁目录中没有补丁，跳过补丁加载")
            return
        
        # 使用蓝色显示补丁系统加载信息
        self.logger.log_platform_info(f"[补丁系统] 正在加载补丁: {', '.join(patch_dirs)}")
        
        try:
            for patch_name in patch_dirs:
                patch_path = os.path.join(patches_dir, patch_name)
                if os.path.isdir(patch_path):
                    main_file = os.path.join(patch_path, "main.py")
                    if os.path.exists(main_file):
                        try:
                            # 动态导入补丁
                            import importlib.util
                            spec = importlib.util.spec_from_file_location(f"patch_{patch_name}", main_file)
                            patch_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(patch_module)
                            
                            # 检查补丁是否有必要的函数
                            if hasattr(patch_module, 'patch_apply'):
                                # 执行补丁应用函数
                                if hasattr(patch_module, 'patch_apply'):
                                    patch_module.patch_apply()
                                    
                                self.applied_patches[patch_name] = {
                                    'name': patch_name,
                                    'module': patch_module,
                                    'path': patch_path
                                }
                                
                                # 使用紫色显示补丁加载完成信息，与别的消息格式相同
                                self.logger.log_platform_info(f"[补丁系统] 补丁加载完成: {patch_name}")
                            else:
                                self.logger.log_platform_info(f"补丁 {patch_name} 缺少patch_apply函数，跳过加载")
                        except Exception as e:
                            self.logger.log_platform_info(f"加载补丁 {patch_name} 失败: {e}")
                    else:
                        self.logger.log_platform_info(f"补丁 {patch_name} 缺少main.py文件，跳过加载")
                else:
                    self.logger.log_platform_info(f"补丁 {patch_name} 目录不存在，跳过加载")
        except Exception as e:
            self.logger.log_platform_info(f"扫描补丁目录失败: {e}")

    def load_plugins(self):
        """加载所有插件"""
        self.loaded_plugins = []
        
        if not os.path.exists(self.plugin_dir):
            self.logger.log_platform_info("插件目录不存在，跳过插件加载")
            return
        
        try:
            for plugin_name in os.listdir(self.plugin_dir):
                plugin_path = os.path.join(self.plugin_dir, plugin_name)
                if os.path.isdir(plugin_path):
                    main_file = os.path.join(plugin_path, "main.py")
                    if os.path.exists(main_file):
                        try:
                            # 动态导入插件
                            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", main_file)
                            plugin_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(plugin_module)
                            
                            # 检查插件是否有必要的函数
                            if (hasattr(plugin_module, 'on_message') or 
                                hasattr(plugin_module, 'on_load') or 
                                hasattr(plugin_module, 'on_command')):
                                # 获取插件的自定义触发指令
                                plugin_cmd = getattr(plugin_module, 'plugin_cmd', None)
                                
                                # 获取插件数据目录
                                plugin_data_dir = self.get_plugin_data_dir(plugin_name)
                                
                                self.loaded_plugins.append({
                                    'name': plugin_name,
                                    'module': plugin_module,
                                    'path': plugin_path,
                                    'data_dir': plugin_data_dir,
                                    'cmd': plugin_cmd  # 添加插件自定义触发指令
                                })
                                
                                # 设置插件数据目录（如果插件有此方法）
                                if hasattr(plugin_module, 'set_data_dir'):
                                    plugin_module.set_data_dir(plugin_data_dir)
                                
                                # 调用插件加载函数（如果存在）
                                if hasattr(plugin_module, 'on_load'):
                                    plugin_module.on_load()
                                    
                                # 统一格式输出
                                cmd_info = f" (指令: {plugin_cmd})" if plugin_cmd else ""
                                print(f"{Fore.LIGHTCYAN_EX}  ▶ [插件加载] {plugin_name}{cmd_info}{Style.RESET_ALL}")
                            else:
                                print(f"{Fore.LIGHTRED_EX}  ▶ [插件跳过] {plugin_name} - 缺少必要函数{Style.RESET_ALL}")
                        except Exception as e:
                            print(f"{Fore.LIGHTRED_EX}  ▶ [插件失败] {plugin_name} - {e}{Style.RESET_ALL}")
                    else:
                        # 检查是否是多语言插件
                        plugin_config_path = os.path.join(plugin_path, "plugin.json")
                        if os.path.exists(plugin_config_path):
                            try:
                                # 尝试加载多语言插件管理器
                                from multilang_plugin_manager import multilang_plugin_manager
                                if multilang_plugin_manager.load_plugin(plugin_path):
                                    print(f"{Fore.LIGHTCYAN_EX}  ▶ [插件加载] {plugin_name}{Style.RESET_ALL}")
                                else:
                                    print(f"{Fore.LIGHTRED_EX}  ▶ [插件失败] {plugin_name}{Style.RESET_ALL}")
                            except ImportError:
                                print(f"{Fore.LIGHTYELLOW_EX}  ▶ [插件跳过] {plugin_name} - 缺少plugin.json文件{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.LIGHTYELLOW_EX}  ▶ [插件跳过] {plugin_name} - 缺少main.py文件{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}  ▶ [插件错误] 扫描插件目录失败: {e}{Style.RESET_ALL}")
        
        # 为插件帮助系统设置插件列表
        for plugin_info in self.loaded_plugins:
            if plugin_info['name'] == 'plugin_help' and hasattr(plugin_info['module'], 'set_main_plugins'):
                try:
                    plugin_info['module'].set_main_plugins(self.loaded_plugins)
                except Exception as e:
                    print(f"{Fore.LIGHTRED_EX}  ▶ [插件错误] 为插件帮助系统设置插件列表失败: {e}{Style.RESET_ALL}")

    async def handle_plugin_messages(self, websocket, data, bot_id):
        """处理插件消息"""
        # 首先让Python插件检查是否需要处理此消息
        for plugin_info in self.loaded_plugins:
            try:
                plugin_module = plugin_info['module']
                if hasattr(plugin_module, 'on_message'):
                    # 调用插件的消息处理函数
                    # 注意：on_message可能在内部使用asyncio.create_task，需要在事件循环中调用
                    result = plugin_module.on_message(websocket, data, bot_id)
                    # 如果插件返回True，表示消息已被处理
                    if result:
                        # 输出插件处理消息日志，使用不同颜色
                        print(f"{Fore.LIGHTCYAN_EX}[插件处理] {Fore.CYAN}插件 {plugin_info['name']} 处理了消息{Style.RESET_ALL}")
                        return True
            except Exception as e:
                self.logger.log_platform_info(f"Python插件 {plugin_info['name']} 处理消息时出错: {e}")
        
        # 检查并使用多语言插件管理器
        try:
            from multilang_plugin_manager import multilang_plugin_manager
            # 让插件处理消息
            plugins = multilang_plugin_manager.get_plugin_list()
            for plugin in plugins:
                try:
                    plugin_name = plugin['name']
                    if multilang_plugin_manager.handle_message(plugin_name, data):
                        # 输出插件处理消息日志，使用不同颜色
                        print(f"{Fore.LIGHTCYAN_EX}[插件处理] {Fore.CYAN}插件 {plugin_name} 处理了消息{Style.RESET_ALL}")
                        return True  # 插件已处理消息
                except Exception as e:
                    self.logger.log_platform_info(f"插件 {plugin['name']} 处理消息时出错: {e}")
        except ImportError:
            pass  # 如果没有多语言插件管理器，则跳过

        # 检查AstrBot插件桥接补丁
        astrbot_patch = self.applied_patches.get('astrbot_plugin_bridge')
        if astrbot_patch and 'module' in astrbot_patch:
            try:
                astrbot_module = astrbot_patch['module']
                if hasattr(astrbot_module, 'process_message'):
                    # 让AstrBot插件处理消息
                    result = astrbot_module.process_message(websocket, data, bot_id)
                    if result:  # 如果AstrBot插件处理了消息
                        # 输出插件处理消息日志，使用不同颜色
                        print(f"{Fore.LIGHTCYAN_EX}[AstrBot插件处理] {Fore.CYAN}AstrBot插件处理了消息{Style.RESET_ALL}")
                        return True
            except Exception as e:
                self.logger.log_platform_info(f"AstrBot插件桥接补丁处理消息时出错: {e}")

        # 检查是否@机器人并包含插件调用格式（保留旧的插件调用方式作为备选）
        if data.get("message_type") == "group":
            message_content = self._format_message(data.get("message")).strip()
            
            # 检查是否@了机器人
            is_at_bot = False
            for msg_item in data.get("message", []):
                if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(bot_id):
                    is_at_bot = True
                    break
            
            # 如果@了机器人且消息包含插件调用格式
            if is_at_bot and message_content.startswith("plugin/"):
                # 解析插件调用格式: plugin/插件名/指令
                parts = message_content.split("/", 2)
                if len(parts) >= 2:
                    plugin_name = parts[1]
                    
                    # 尝试找到并调用指定Python插件
                    for plugin_info in self.loaded_plugins:
                        if plugin_info['name'] == plugin_name:
                            try:
                                plugin_module = plugin_info['module']
                                if hasattr(plugin_module, 'on_command'):
                                    # 调用插件的命令处理函数
                                    command = parts[2] if len(parts) > 2 else ""
                                    result = plugin_module.on_command(websocket, data, command, bot_id)
                                    if result:
                                        # 输出插件处理命令日志，使用不同颜色
                                        print(f"{Fore.LIGHTCYAN_EX}[插件命令] {Fore.CYAN}插件 {plugin_name} 处理了命令{Style.RESET_ALL}")
                                        return True
                            except Exception as e:
                                self.logger.log_platform_info(f"Python插件 {plugin_name} 处理命令时出错: {e}")
                                return True  # 防止继续处理
                    
                    # 检查并使用多语言插件管理器
                    try:
                        from multilang_plugin_manager import multilang_plugin_manager
                        for plugin in plugins:
                            if plugin['name'] == plugin_name:
                                try:
                                    command = parts[2] if len(parts) > 2 else ""
                                    if multilang_plugin_manager.handle_command(plugin_name, command, data):
                                        # 输出插件处理命令日志，使用不同颜色
                                        print(f"{Fore.LIGHTCYAN_EX}[插件命令] {Fore.CYAN}插件 {plugin_name} 处理了命令{Style.RESET_ALL}")
                                        return True
                                except Exception as e:
                                    self.logger.log_platform_info(f"插件 {plugin_name} 处理命令时出错: {e}")
                                    return True  # 防止继续处理
                    except ImportError:
                        pass  # 如果没有多语言插件管理器，则跳过
        
        return False

    def _format_message(self, msg):
        """内部消息格式化函数"""
        import json
        if isinstance(msg, list):
            parts = []
            for m in msg:
                # 安全检查，确保m是字典
                if not isinstance(m, dict):
                    # 如果m不是字典，直接转换为字符串
                    parts.append(str(m))
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