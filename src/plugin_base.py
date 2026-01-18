#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 插件基类系统
参考 AstrBot 的插件设计，实现统一的插件开发接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import asyncio


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    description: str
    author: str
    required_permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.required_permissions is None:
            self.required_permissions = []
        if self.dependencies is None:
            self.dependencies = []


class PluginContext:
    """插件上下文
    
    为插件提供运行时环境和API访问
    """
    
    def __init__(self, bot_manager, config_manager, event_bus, websocket=None):
        self.bot_manager = bot_manager
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.websocket = websocket
    
    async def send_message(self, unique_msg_origin: str, message: str) -> bool:
        """发送消息到指定来源
        
        Args:
            unique_msg_origin: 消息源标识符 (格式: platform:message_type:session_id)
            message: 要发送的消息
            
        Returns:
            是否发送成功
        """
        try:
            from core.message_origin import parse_message_origin
            
            # 解析消息源
            origin = parse_message_origin(unique_msg_origin)
            
            # 构建消息数据
            msg_data = {
                "action": "send_group_msg" if origin.is_group() else "send_private_msg",
                "params": {
                    "message": message
                }
            }
            
            # 设置接收者
            if origin.is_group():
                msg_data["params"]["group_id"] = origin.session_id
            else:
                msg_data["params"]["user_id"] = origin.session_id
            
            # 如果有 websocket，发送消息
            if self.websocket:
                import json
                await self.websocket.send(json.dumps(msg_data, ensure_ascii=False))
                return True
            
        except Exception as e:
            print(f"[PluginContext] 发送消息失败: {e}")
        
        return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config_manager.get(key, default)
    
    def set_config(self, key: str, value: Any) -> bool:
        """设置配置
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        try:
            self.config_manager.set(key, value)
            return True
        except Exception as e:
            print(f"[PluginContext] 设置配置失败: {e}")
            return False
    
    def subscribe_event(self, event_type: str, callback, priority: int = 0):
        """订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
            priority: 优先级
        """
        self.event_bus.subscribe(event_type, callback, priority)
    
    def unsubscribe_event(self, event_type: str, callback):
        """取消订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        self.event_bus.unsubscribe(event_type, callback)
    
    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        from core.event_bus import Event
        event = Event(
            event_type=event_type,
            data=data,
            source=f"plugin_{self.__class__.__name__}"
        )
        await self.event_bus.publish(event)


class PluginBase(ABC):
    """插件基类
    
    所有插件都必须继承此类并实现必要的方法
    """
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.metadata: Optional[PluginMetadata] = None
        self._enabled = True
    
    @property
    @abstractmethod
    def plugin_info(self) -> PluginMetadata:
        """插件信息
        
        Returns:
            插件元数据
        """
        pass
    
    async def on_load(self):
        """插件加载时调用
        
        在这里进行插件的初始化工作
        """
        pass
    
    async def on_unload(self):
        """插件卸载时调用
        
        在这里进行插件的清理工作
        """
        pass
    
    async def on_enable(self):
        """插件启用时调用"""
        self._enabled = True
    
    async def on_disable(self):
        """插件禁用时调用"""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """插件是否启用"""
        return self._enabled
    
    async def on_message(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        处理消息
        
        Args:
            message_data: 消息数据
            
        Returns:
            None 表示不处理，返回字符串表示要发送的回复
        """
        return None
    
    async def on_command(self, command: str, context: Dict[str, Any]) -> Optional[str]:
        """
        处理指令
        
        Args:
            command: 指令字符串
            context: 上下文信息
            
        Returns:
            None 表示不处理，返回字符串表示要发送的回复
        """
        return None
    
    async def on_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        处理事件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
        """
        pass


class PluginManager:
    """插件管理器
    
    负责插件的加载、卸载、管理和执行
    """
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_metadata: Dict[str, PluginMetadata] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
    
    def register_plugin(self, plugin: PluginBase):
        """注册插件
        
        Args:
            plugin: 插件实例
        """
        metadata = plugin.plugin_info
        self.plugins[metadata.name] = plugin
        self.plugin_metadata[metadata.name] = metadata
        
        print(f"[PluginManager] 插件已注册: {metadata.name} v{metadata.version}")
    
    async def load_plugin(self, plugin_class, config: Dict[str, Any] = None) -> bool:
        """加载插件
        
        Args:
            plugin_class: 插件类
            config: 插件配置
            
        Returns:
            是否加载成功
        """
        try:
            # 创建插件实例
            plugin = plugin_class(self.context)
            
            # 保存插件配置
            if config:
                self._plugin_configs[plugin.plugin_info.name] = config
                
                # 设置插件配置
                for key, value in config.items():
                    self.context.set_config(f"plugin.{plugin.plugin_info.name}.{key}", value)
            
            # 调用 on_load
            await plugin.on_load()
            
            # 注册插件
            self.register_plugin(plugin)
            
            return True
            
        except Exception as e:
            print(f"[PluginManager] 加载插件失败: {e}")
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否卸载成功
        """
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                await plugin.on_unload()
                
                del self.plugins[plugin_name]
                del self.plugin_metadata[plugin_name]
                
                if plugin_name in self._plugin_configs:
                    del self._plugin_configs[plugin_name]
                
                print(f"[PluginManager] 插件已卸载: {plugin_name}")
                return True
        except Exception as e:
            print(f"[PluginManager] 卸载插件失败: {e}")
        
        return False
    
    async def enable_plugin(self, plugin_name: str) -> bool:
        """启用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否启用成功
        """
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                await plugin.on_enable()
                return True
        except Exception as e:
            print(f"[PluginManager] 启用插件失败: {e}")
        
        return False
    
    async def disable_plugin(self, plugin_name: str) -> bool:
        """禁用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否禁用成功
        """
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                await plugin.on_disable()
                return True
        except Exception as e:
            print(f"[PluginManager] 禁用插件失败: {e}")
        
        return False
    
    async def handle_message(self, message_data: Dict[str, Any]) -> Optional[str]:
        """让所有启用的插件处理消息
        
        Args:
            message_data: 消息数据
            
        Returns:
            第一个插件返回的回复
        """
        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_enabled:
                continue
            
            try:
                result = await plugin.on_message(message_data)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[PluginManager] 插件 {plugin_name} 处理消息时出错: {e}")
        
        return None
    
    async def handle_command(self, command: str, context: Dict[str, Any]) -> Optional[str]:
        """让所有启用的插件处理指令
        
        Args:
            command: 指令字符串
            context: 上下文信息
            
        Returns:
            第一个插件返回的回复
        """
        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_enabled:
                continue
            
            try:
                result = await plugin.on_command(command, context)
                if result is not None:
                    return result
            except Exception as e:
                print(f"[PluginManager] 插件 {plugin_name} 处理指令时出错: {e}")
        
        return None
    
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]):
        """让所有启用的插件处理事件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
        """
        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_enabled:
                continue
            
            try:
                await plugin.on_event(event_type, event_data)
            except Exception as e:
                print(f"[PluginManager] 插件 {plugin_name} 处理事件 {event_type} 时出错: {e}")
    
    def get_plugin_list(self) -> List[PluginMetadata]:
        """获取插件列表
        
        Returns:
            所有插件的元数据列表
        """
        return list(self.plugin_metadata.values())
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """获取插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件实例，如果不存在则返回 None
        """
        return self.plugins.get(plugin_name)
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件配置字典
        """
        return self._plugin_configs.get(plugin_name, {})