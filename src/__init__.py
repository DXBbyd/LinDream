"""
LinDream 核心模块
包含事件总线、流水线、插件系统等核心组件
"""

from .event_bus import EventBus, Event, event_bus
from .pipeline import Pipeline, PipelineContext, PipelineStage, create_default_pipeline
from .message_origin import MessageOrigin, create_message_origin, parse_message_origin
from .plugin_base import PluginBase, PluginMetadata, PluginContext, PluginManager
from .content_moderator import ContentModerator, content_moderator
from .audit_logger import AuditLogger, AuditEventType, audit_logger

__all__ = [
    'EventBus', 'Event', 'event_bus',
    'Pipeline', 'PipelineContext', 'PipelineStage', 'create_default_pipeline',
    'MessageOrigin', 'create_message_origin', 'parse_message_origin',
    'PluginBase', 'PluginMetadata', 'PluginContext', 'PluginManager',
    'ContentModerator', 'content_moderator',
    'AuditLogger', 'AuditEventType', 'audit_logger'
]