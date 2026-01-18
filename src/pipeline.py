#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 流水线处理系统
参考 AstrBot 的流水线架构，将消息处理分解为多个独立的阶段
"""

import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time


@dataclass
class PipelineContext:
    """流水线上下文
    
    在各个阶段之间传递数据和状态
    """
    event_data: Dict[str, Any]
    websocket: Any
    bot_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    _stopped: bool = False
    _error: Optional[Exception] = None
    
    def stop(self):
        """停止流水线执行"""
        self._stopped = True
    
    def set_error(self, error: Exception):
        """设置错误"""
        self._error = error
        self.stop()
    
    @property
    def is_stopped(self) -> bool:
        return self._stopped
    
    @property
    def has_error(self) -> bool:
        return self._error is not None
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置元数据"""
        self.metadata[key] = value


class PipelineStage(ABC):
    """流水线阶段基类
    
    每个阶段负责处理消息的一个特定方面
    """
    
    @property
    @abstractmethod
    def stage_name(self) -> str:
        """阶段名称"""
        pass
    
    @abstractmethod
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """
        处理阶段
        
        使用生成器实现与其他阶段的协作
        通过 yield 可以让其他阶段有机会介入
        """
        pass
    
    def can_skip(self, context: PipelineContext) -> bool:
        """判断是否可以跳过此阶段"""
        return False


class Pipeline:
    """流水线调度器
    
    管理和执行各个处理阶段
    """
    
    def __init__(self):
        self.stages: Dict[str, PipelineStage] = {}
        self.stage_order: List[str] = []
        self._stats = {
            'total_executions': 0,
            'stage_errors': {},
            'execution_times': {}
        }
    
    def add_stage(self, stage: PipelineStage, position: Optional[int] = None):
        """添加阶段
        
        Args:
            stage: 阶段实例
            position: 插入位置，None 表示追加到末尾
        """
        stage_name = stage.stage_name
        self.stages[stage_name] = stage
        
        if position is None:
            self.stage_order.append(stage_name)
        else:
            self.stage_order.insert(position, stage_name)
        
        print(f"[Pipeline] 阶段已添加: {stage_name}")
    
    def remove_stage(self, stage_name: str):
        """移除阶段"""
        if stage_name in self.stages:
            del self.stages[stage_name]
            self.stage_order.remove(stage_name)
            print(f"[Pipeline] 阶段已移除: {stage_name}")
    
    def get_stage(self, stage_name: str) -> Optional[PipelineStage]:
        """获取阶段"""
        return self.stages.get(stage_name)
    
    async def execute(self, context: PipelineContext) -> Dict[str, Any]:
        """执行流水线
        
        Args:
            context: 流水线上下文
            
        Returns:
            执行结果
        """
        self._stats['total_executions'] += 1
        start_time = time.time()
        
        for stage_name in self.stage_order:
            if context.is_stopped:
                break
            
            stage = self.stages.get(stage_name)
            if not stage:
                continue
            
            # 检查是否可以跳过
            if stage.can_skip(context):
                continue
            
            stage_start = time.time()
            
            try:
                # 执行阶段处理
                async for _ in stage.process(context):
                    # 阶段可以 yield 来暂停执行
                    pass
                
                # 记录执行时间
                stage_time = time.time() - stage_start
                if stage_name not in self._stats['execution_times']:
                    self._stats['execution_times'][stage_name] = []
                self._stats['execution_times'][stage_name].append(stage_time)
                
            except Exception as e:
                print(f"[Pipeline] 阶段 {stage_name} 执行失败: {e}")
                context.set_error(e)
                
                # 记录错误
                if stage_name not in self._stats['stage_errors']:
                    self._stats['stage_errors'][stage_name] = 0
                self._stats['stage_errors'][stage_name] += 1
        
        total_time = time.time() - start_time
        return {
            'success': not context.has_error,
            'error': context._error,
            'metadata': context.metadata,
            'execution_time': total_time
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 计算平均执行时间
        avg_times = {}
        for stage_name, times in self._stats['execution_times'].items():
            if times:
                avg_times[stage_name] = sum(times) / len(times)
        
        return {
            'total_executions': self._stats['total_executions'],
            'stage_errors': self._stats['stage_errors'],
            'avg_execution_times': avg_times,
            'stages_count': len(self.stages)
        }


# 预定义的流水线阶段

class PreprocessStage(PipelineStage):
    """预处理阶段
    
    处理语音转文字、图片识别等预处理任务
    """
    
    @property
    def stage_name(self) -> str:
        return "Preprocess"
    
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """预处理消息"""
        data = context.event_data
        
        # 检查是否包含语音
        if self._contains_voice(data):
            try:
                text = await self._voice_to_text(data)
                context.set('voice_text', text)
                print(f"[Preprocess] 语音转文字: {text}")
            except Exception as e:
                print(f"[Preprocess] 语音转文字失败: {e}")
        
        # 检查是否包含图片
        if self._contains_image(data):
            try:
                description = await self._describe_image(data)
                context.set('image_description', description)
                print(f"[Preprocess] 图片识别: {description}")
            except Exception as e:
                print(f"[Preprocess] 图片识别失败: {e}")
        
        yield  # 让其他阶段有机会介入
    
    def _contains_voice(self, data: Dict) -> bool:
        """检查是否包含语音消息"""
        message = data.get('message', [])
        for msg in message:
            if msg.get('type') == 'record':
                return True
        return False
    
    def _contains_image(self, data: Dict) -> bool:
        """检查是否包含图片"""
        message = data.get('message', [])
        for msg in message:
            if msg.get('type') == 'image':
                return True
        return False
    
    async def _voice_to_text(self, data: Dict) -> str:
        """语音转文字"""
        # TODO: 实现实际的语音转文字逻辑
        return "语音内容"
    
    async def _describe_image(self, data: Dict) -> str:
        """图片识别"""
        # TODO: 实现实际的图片识别逻辑
        return "图片描述"


class ContentModerationStage(PipelineStage):
    """内容审核阶段
    
    检查消息内容是否合规
    """
    
    def __init__(self, content_moderator=None):
        super().__init__()
        self.content_moderator = content_moderator
    
    @property
    def stage_name(self) -> str:
        return "ContentModeration"
    
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """内容审核"""
        data = context.event_data
        content = self._extract_content(data)
        
        if not content:
            yield
            return
        
        # 如果有内容审核器，则进行审核
        if self.content_moderator:
            try:
                result = await self.content_moderator.check_content(content)
                
                if not result['is_safe']:
                    context.set('moderation_result', result)
                    context.stop()
                    
                    # 发送警告
                    await self._send_warning(context, result['reason'])
                    print(f"[ContentModeration] 内容审核不通过: {result['reason']}")
                    return
                
                # 过滤内容
                filtered_content = self.content_moderator.filter_content(content)
                context.set('filtered_content', filtered_content)
                
            except Exception as e:
                print(f"[ContentModeration] 内容审核失败: {e}")
        
        yield
    
    def _extract_content(self, data: Dict) -> str:
        """提取文本内容"""
        message = data.get('message', [])
        parts = []
        
        for msg in message:
            if msg.get('type') == 'text':
                parts.append(msg.get('data', {}).get('text', ''))
        
        return ''.join(parts)
    
    async def _send_warning(self, context: PipelineContext, reason: str):
        """发送警告消息"""
        # TODO: 实现发送警告的逻辑
        pass


class CommandStage(PipelineStage):
    """指令扫描阶段
    
    检查并执行指令
    """
    
    def __init__(self, command_prefix: str = '/'):
        super().__init__()
        self.command_prefix = command_prefix
    
    @property
    def stage_name(self) -> str:
        return "Command"
    
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """扫描并执行指令"""
        data = context.event_data
        original_content = self._extract_content(data)
        
        # 检查是否@了机器人
        is_at_bot = False
        for msg_item in data.get("message", []):
            if msg_item.get("type") == "at" and str(msg_item.get("data", {}).get("qq", "")) == str(context.bot_id):
                is_at_bot = True
                break
        
        # 处理消息内容，提取可能的指令
        # 如果被@了，我们需要从消息中提取指令部分
        if is_at_bot:
            # 在@机器人的场景下，处理可能的指令
            # 例如: "@机器人 /help" 或 "@机器人 /help 参数"
            content = original_content.strip()
        else:
            # 没有@机器人，直接使用原始内容
            content = original_content
        
        # 检查是否为指令（直接以/开头 或 @机器人后跟/开头的内容）
        is_command = content and content.startswith(self.command_prefix)
        
        if is_command:
            command = self._parse_command(content)
            
            if command:
                try:
                    result = await self._execute_command(command, context)
                    context.set('command_result', result)
                    context.stop()  # 指令执行后停止流水线
                    
                    print(f"[Command] 指令执行: {command['name']}")
                except Exception as e:
                    print(f"[Command] 指令执行失败: {e}")
                    context.set('command_error', str(e))
        
        yield
    
    def _extract_content(self, data: Dict) -> str:
        """提取文本内容"""
        message = data.get('message', [])
        parts = []
        
        for msg in message:
            if msg.get('type') == 'text':
                parts.append(msg.get('data', {}).get('text', ''))
        
        return ''.join(parts)
    
    def _parse_command(self, content: str) -> Optional[Dict]:
        """解析指令"""
        # 去掉命令前缀并清理空格
        if content.startswith(self.command_prefix):
            content = content[len(self.command_prefix):].strip()
        else:
            # 如果内容不以命令前缀开头，直接返回None
            return None
        
        if not content:
            return None
        
        # 分割指令和参数
        parts = content.split()
        if not parts:
            return None
        
        return {
            'name': parts[0],
            'args': parts[1:] if len(parts) > 1 else []
        }
    
    async def _handle_op_command(self, command: Dict, context: PipelineContext) -> str:
        """处理op指令（设置管理员）"""
        # 检查用户权限
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 获取配置
        config_manager = handler.config_manager
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 3, config_manager.config_data):
            return "权限不足：只有管理员才能执行此操作"
        
        # 获取要设置为管理员的用户ID
        args = command.get('args', [])
        if not args:
            return "用法：/op <用户QQ号>"
        
        target_user_id = args[0]
        if not target_user_id.isdigit():
            return "错误：请输入有效的QQ号"
        
        # 更新配置
        admins = config_manager.config_data.get("admins", [])
        if target_user_id not in admins:
            admins.append(target_user_id)
            config_manager.config_data["admins"] = admins
            
            # 保存配置
            config_manager.save_config()
            
            return f"成功将用户 {target_user_id} 设置为管理员"
        else:
            return f"用户 {target_user_id} 已是管理员"
    
    async def _handle_deop_command(self, command: Dict, context: PipelineContext) -> str:
        """处理deop指令（移除管理员）"""
        # 检查用户权限
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 获取配置
        config_manager = handler.config_manager
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 3, config_manager.config_data):
            return "权限不足：只有管理员才能执行此操作"
        
        # 获取要移除管理员权限的用户ID
        args = command.get('args', [])
        if not args:
            return "用法：/deop <用户QQ号>"
        
        target_user_id = args[0]
        if not target_user_id.isdigit():
            return "错误：请输入有效的QQ号"
        
        # 更新配置
        admins = config_manager.config_data.get("admins", [])
        if target_user_id in admins:
            admins.remove(target_user_id)
            config_manager.config_data["admins"] = admins
            
            # 保存配置
            config_manager.save_config()
            
            return f"成功移除用户 {target_user_id} 的管理员权限"
        else:
            return f"用户 {target_user_id} 不是管理员"
    
    async def _handle_cfg_command(self, command: Dict, context: PipelineContext) -> str:
        """处理cfg指令（设置插件权限）"""
        # 检查用户权限
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 获取配置
        config_manager = handler.config_manager
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 3, config_manager.config_data):
            return "权限不足：只有管理员才能执行此操作"
        
        # 获取参数
        args = command.get('args', [])
        if len(args) < 2:
            return "用法：/cfg <插件名> <参数名> <值>\n例如：/cfg plugin_name enabled true"
        
        plugin_name = args[0]
        param_name = args[1]
        param_value = ' '.join(args[2:]) if len(args) > 2 else args[1]
        
        # 尝试解析参数值
        if param_value.lower() in ['true', 'yes', '1']:
            param_value = True
        elif param_value.lower() in ['false', 'no', '0']:
            param_value = False
        elif param_value.isdigit():
            param_value = int(param_value)
        
        # 更新配置
        plugin_config = config_manager.config_data.get("plugin_config", {})
        if plugin_name not in plugin_config:
            plugin_config[plugin_name] = {}
        plugin_config[plugin_name][param_name] = param_value
        config_manager.config_data["plugin_config"] = plugin_config
        
        # 保存配置
        config_manager.save_config()
        
        return f"成功设置插件 {plugin_name} 的 {param_name} 为 {param_value}"
    
    async def _handle_persona_command(self, command: Dict, context: PipelineContext) -> str:
        """处理persona指令（人格切换）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        args = command.get('args', [])
        
        if not args:
            return "用法：/persona <ls|序号> 或 /persona <人格名称>"

        if args[0] == 'ls' or args[0] == 'list':
            # 列出所有人格
            import os
            persona_dir = os.path.join("data", "personas")
            if not os.path.exists(persona_dir):
                return "人格目录不存在"
            
            persona_files = [f for f in os.listdir(persona_dir) if f.endswith('.txt')]
            if not persona_files:
                return "未找到人格文件"
            
            # 按文件名排序
            persona_files.sort()
            
            result = "可用人格列表：\n"
            for i, file in enumerate(persona_files, 1):
                name = file[:-4]  # 去掉.txt后缀
                result += f"{i}. {name}\n"
            
            return result.strip()
        else:
            # 切换人格
            persona_name = args[0]
            
            # 检查是否是序号
            if persona_name.isdigit():
                import os
                persona_dir = "persona"
                if not os.path.exists(persona_dir):
                    return "人格目录不存在"
                
                persona_files = [f for f in os.listdir(persona_dir) if f.endswith('.txt')]
                if not persona_files:
                    return "未找到人格文件"
                
                # 按文件名排序
                persona_files.sort()
                
                index = int(persona_name) - 1
                if 0 <= index < len(persona_files):
                    persona_name = persona_files[index][:-4]  # 去掉.txt后缀
                else:
                    return f"序号超出范围，共有 {len(persona_files)} 个人格"
            
            # 检查人格文件是否存在
            import os
            persona_path = os.path.join("data", "personas", f"{persona_name}.txt")
            if not os.path.exists(persona_path):
                return f"人格文件不存在: {persona_name}.txt"
            
            # 更新配置
            personas_config = handler.config_manager.config_data.get("personas", {})
            personas_config["default_persona"] = persona_name
            handler.config_manager.config_data["personas"] = personas_config
            
            # 保存配置
            handler.config_manager.save_config()
            
            # 更新当前人格
            handler.current_persona = persona_name
            
            return f"成功切换到人格: {persona_name}"
    
    async def _handle_limit_command(self, command: Dict, context: PipelineContext) -> str:
        """处理limit指令（查看权限等级）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 获取权限等级
        from utils.helpers import get_user_permission_level
        permission_level = get_user_permission_level(str(sender_id), handler.config_manager.config_data)
        
        # 权限等级说明
        level_desc = {1: "普通用户", 2: "管理员", 3: "主人"}
        
        return f"您的权限等级: {permission_level} ({level_desc.get(permission_level, '未知')})"
    
    async def _handle_plugin_command(self, command: Dict, context: PipelineContext) -> str:
        """处理plugin指令（查看已加载插件）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取已加载的插件列表
        loaded_plugins = handler.plugin_manager.loaded_plugins
        if not loaded_plugins:
            return "当前没有加载任何插件"
        
        plugin_list = "已加载插件列表：\n"
        for i, plugin in enumerate(loaded_plugins, 1):
            plugin_name = plugin.get('name', '未知插件')
            plugin_cmd = plugin.get('cmd', '')
            cmd_info = f" (触发指令: {plugin_cmd})" if plugin_cmd else ""
            plugin_list += f"{i}. {plugin_name}{cmd_info}\n"
        
        return plugin_list.strip()
    
    async def _handle_stats_command(self, command: Dict, context: PipelineContext) -> str:
        """处理stats指令（查看统计信息）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取性能统计
        stats = handler.get_performance_stats()
        
        result = "📊 机器人统计信息：\n"
        result += f"• 连接数: {stats['connection_pool']['active_connections']}\n"
        result += f"• 消息队列: {stats['message_queue']['size']} 条\n"
        result += f"• 缓存项: {stats['cache']['size']} 个\n"
        result += f"• 性能评分: {stats['performance']['performance_score']:.2f}\n"
        
        return result.strip()
    
    async def _handle_reset_command(self, command: Dict, context: PipelineContext) -> str:
        """处理reset指令（重载配置和插件）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 2, handler.config_manager.config_data):  # 需要管理员权限
            return "权限不足：只有管理员才能执行此操作"
        
        try:
            # 重新加载配置
            handler.config_manager.load_config()
            
            # 重新加载插件
            handler.plugin_manager.load_plugins()
            
            return "✅ 配置和插件重载成功"
        except Exception as e:
            return f"❌ 重载失败: {str(e)}"
    
    async def _handle_plugin_management_command(self, command: Dict, context: PipelineContext) -> str:
        """处理插件管理指令（load/unload/reload）"""
        handler = context.get('handler')
        if not handler:
            return "系统错误：无法获取处理器"
        
        # 获取发送者ID
        sender = context.event_data.get("sender", {})
        sender_id = sender.get("user_id")
        
        # 检查权限
        from utils.helpers import get_user_permission_level, is_authorized
        if not is_authorized(str(sender_id), 2, handler.config_manager.config_data):  # 需要管理员权限
            return "权限不足：只有管理员才能执行此操作"
        
        command_name = command['name']
        args = command.get('args', [])
        
        if not args:
            return f"用法：/{command_name} <插件名>"
        
        plugin_name = args[0]
        
        try:
            if command_name == 'load':
                # 这里需要实现插件加载逻辑
                # 由于插件加载涉及较复杂的逻辑，这里返回提示信息
                return f"正在加载插件 {plugin_name}..."
            elif command_name == 'unload':
                return f"正在卸载插件 {plugin_name}..."
            elif command_name == 'reload':
                return f"正在重载插件 {plugin_name}..."
            else:
                return "未知插件管理指令"
        except Exception as e:
            return f"插件操作失败: {str(e)}"
    
    async def _execute_command(self, command: Dict, context: PipelineContext) -> Any:
        """执行指令"""
        try:
            command_name = command['name']
            
            # 检查是否是帮助指令
            if command_name == 'help':
                help_text = self._get_help_text()
                context.set('command_result', help_text)
                context.set('command_processed', True)  # 标记指令已处理
                return help_text
            
            # 检查是否是limit指令
            if command_name == 'limit':
                return await self._handle_limit_command(command, context)
            
            # 检查是否是plugin指令
            if command_name == 'plugin':
                return await self._handle_plugin_command(command, context)
            
            # 检查是否是stats指令
            if command_name == 'stats':
                return await self._handle_stats_command(command, context)
            
            # 检查是否是reset指令
            if command_name == 'reset':
                return await self._handle_reset_command(command, context)
            
            # 检查是否是op指令
            if command_name == 'op':
                result = await self._handle_op_command(command, context)
                context.set('command_processed', True)  # 标记指令已处理
                return result
            
            # 检查是否是deop指令
            if command_name == 'deop':
                result = await self._handle_deop_command(command, context)
                context.set('command_processed', True)  # 标记指令已处理
                return result
            
            # 检查是否是cfg指令
            if command_name == 'cfg':
                result = await self._handle_cfg_command(command, context)
                context.set('command_processed', True)  # 标记指令已处理
                return result
            
            # 检查是否是persona指令
            if command_name == 'persona':
                result = await self._handle_persona_command(command, context)
                context.set('command_processed', True)  # 标记指令已处理
                return result
            
            # 检查是否是插件管理指令
            if command_name in ['load', 'unload', 'reload']:
                return await self._handle_plugin_management_command(command, context)
            
            # 检查是否是插件指令（以 / 开头的指令）
            command_args = command['args']
            
            # 尝试让插件系统处理指令
            handler = context.get('handler')
            if handler:
                websocket = context.websocket
                event_data = context.event_data
                bot_id = context.bot_id
                
                plugin_handled = await handler.plugin_manager.handle_plugin_messages(
                    websocket, event_data, bot_id
                )
                
                if plugin_handled:
                    context.set('command_processed', True)  # 标记指令已处理
                    return f"指令 {command_name} 已执行"
                else:
                    context.set('command_processed', True)  # 标记指令已处理
                    return f"未知指令: {command_name}"
            else:
                context.set('command_processed', True)  # 标记指令已处理
                return f"指令处理器不可用"
                
        except Exception as e:
            print(f"[Command] 执行指令时出错: {e}")
            raise
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """🤖 LinDream 帮助信息

基础指令：
/help - 显示此帮助信息
/limit - 查看当前权限等级
/plugin - 显示已加载的插件列表
/persona ls - 列出所有人格
/persona <序号> - 切换人格（使用序号）
/stats - 查看机器人统计信息（新增）
/reset - 重载配置和插件（管理员以上权限）

权限管理指令：
/op <QQ号> - 设置管理员（仅主人可用）
/deop <QQ号> - 移除管理员（仅主人可用）
/cfg <插件名> <参数名> <值> - 设置插件配置（仅管理员可用）

插件管理：
/reload <插件名> - 重新加载指定插件
/unload <插件名> - 卸载指定插件
/load <插件名> - 加载指定插件

AI聊天：
在群聊中@机器人并输入消息
或使用 % 前缀：%你好，请自我介绍

使用方法：
• 直接发送指令，如：/help"""


class LLMRequestStage(PipelineStage):
    """LLM 请求阶段
    
    调用大语言模型生成回复
    """
    
    def __init__(self, llm_client=None):
        super().__init__()
        self.llm_client = llm_client
    
    @property
    def stage_name(self) -> str:
        return "LLMRequest"
    
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """调用 LLM"""
        data = context.event_data
        
        # 如果指令已处理，则跳过LLM请求阶段
        if context.get('command_processed', False):
            print("[LLMRequest] 指令已处理，跳过LLM请求阶段")
            yield
            return
        
        # 如果流水线已被停止（例如指令处理后），则跳过LLM请求阶段
        if context.is_stopped:
            print("[LLMRequest] 流水线已被停止，跳过LLM请求阶段")
            yield
            return
        
        # 检查是否需要调用LLM（@机器人 或 使用 % 前缀）
        should_call_llm = False
        message_content = self._extract_content(data)
        
        # 检查是否@了机器人
        for msg_item in data.get("message", []):
            if (msg_item.get("type") == "at" and 
                str(msg_item.get("data", {}).get("qq", "")) == str(context.bot_id)):
                should_call_llm = True
                break
        
        # 检查是否使用了 % 前缀
        if message_content.startswith("%"):
            should_call_llm = True
        
        # 如果不需要调用LLM，则跳过
        if not should_call_llm:
            print("[LLMRequest] 未被@或使用%前缀，跳过LLM请求阶段")
            yield
            return
        
        # 构建请求（移除%前缀）
        request = self._build_request(context)
        
        if not request:
            yield
            return
        
        try:
            # 调用 LLM
            if self.llm_client:
                response = await self.llm_client.chat(request)
                context.set('llm_response', response)
                print(f"[LLMRequest] LLM 响应: {response[:50]}...")
            else:
                # 不生成模拟响应，直接跳过
                print("[LLMRequest] 未配置LLM客户端，跳过请求")
                yield
                return
            
        except Exception as e:
            print(f"[LLMRequest] LLM 调用失败: {e}")
            context.set('llm_error', str(e))
        
        yield
    
    def _build_request(self, context: PipelineContext) -> Optional[Dict]:
        """构建 LLM 请求"""
        # 使用过滤后的内容
        content = context.get('filtered_content')
        
        if not content:
            content = self._extract_content(context.event_data)
        
        if not content:
            return None
        
        # 如果内容以 % 开头，移除它（这是触发前缀，不是对话内容）
        if content.startswith("%"):
            content = content[1:].strip()
        
        return {
            'messages': [
                {'role': 'user', 'content': content}
            ],
            'model': 'default'
        }
    
    def _extract_content(self, data: Dict) -> str:
        """提取文本内容"""
        message = data.get('message', [])
        parts = []
        
        for msg in message:
            if msg.get('type') == 'text':
                parts.append(msg.get('data', {}).get('text', ''))
        
        return ''.join(parts)


class ResponseStage(PipelineStage):
    """响应发送阶段
    
    发送 LLM 生成的回复
    """
    
    @property
    def stage_name(self) -> str:
        return "Response"
    
    async def process(self, context: PipelineContext) -> AsyncGenerator[None, None]:
        """发送响应"""
        # 如果指令已处理，优先发送指令处理阶段的结果
        if context.get('command_processed', False):
            command_result = context.get('command_result')
            if command_result:
                try:
                    await self._send_response(context.websocket, command_result, context.event_data)
                    print(f"[Response] 指令响应已发送")
                except Exception as e:
                    print(f"[Response] 发送指令响应失败: {e}")
        elif context.get('llm_response'):
            # 否则使用LLM响应
            try:
                await self._send_response(context.websocket, context.get('llm_response'), context.event_data)
                print(f"[Response] LLM响应已发送")
            except Exception as e:
                print(f"[Response] 发送LLM响应失败: {e}")
        
        yield
    
    async def _send_response(self, websocket, message: str, event_data: Dict):
        """发送消息"""
        import json
        
        # 构建消息数据
        msg_data = {
            "action": "send_group_msg" if event_data.get('message_type') == 'group' else "send_private_msg",
            "params": {
                "message": message
            }
        }
        
        # 设置接收者
        if event_data.get('message_type') == 'group':
            msg_data["params"]["group_id"] = event_data.get('group_id')
        else:
            msg_data["params"]["user_id"] = event_data.get('sender', {}).get('user_id')
        
        # 发送消息
        await websocket.send(json.dumps(msg_data, ensure_ascii=False))


def create_default_pipeline(content_moderator=None, llm_client=None) -> Pipeline:
    """创建默认的消息处理流水线
    
    Args:
        content_moderator: 内容审核器
        llm_client: LLM 客户端
        
    Returns:
        配置好的流水线实例
    """
    pipeline = Pipeline()
    
    # 添加阶段
    pipeline.add_stage(PreprocessStage())
    pipeline.add_stage(ContentModerationStage(content_moderator))
    pipeline.add_stage(CommandStage())
    pipeline.add_stage(LLMRequestStage(llm_client))
    pipeline.add_stage(ResponseStage())
    
    return pipeline