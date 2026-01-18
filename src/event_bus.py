#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 事件总线系统
参考 AstrBot 的事件总线设计，实现完全解耦的事件驱动架构
"""

import asyncio
import time
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class Event:
    """事件基类"""
    event_type: str
    data: Dict[str, Any]
    source: str
    timestamp: float = field(default_factory=lambda: time.time())
    
    def __post_init__(self):
        self._stopped = False
        self._result: Any = None
    
    def stop_propagation(self):
        """停止事件传播"""
        self._stopped = True
    
    def set_result(self, result: Any):
        """设置事件结果"""
        self._result = result
    
    @property
    def is_stopped(self) -> bool:
        return self._stopped
    
    @property
    def result(self) -> Any:
        return self._result


class EventBus:
    """事件总线 - 核心事件分发器
    
    特性:
    - 异步事件处理
    - 事件传播控制
    - 优先级支持
    - 异常隔离
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._priority_listeners: Dict[str, Dict[int, List[Callable]]] = defaultdict(lambda: defaultdict(list))
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        
        # 统计信息
        self._stats = {
            'total_events': 0,
            'total_listeners': 0,
            'errors': 0
        }
    
    def subscribe(self, event_type: str, listener: Callable, priority: int = 0):
        """订阅事件
        
        Args:
            event_type: 事件类型
            listener: 监听器函数
            priority: 优先级，数字越大优先级越高
        """
        with self._lock:
            if priority != 0:
                self._priority_listeners[event_type][priority].append(listener)
            else:
                self._listeners[event_type].append(listener)
            
            self._stats['total_listeners'] += 1
    
    def unsubscribe(self, event_type: str, listener: Callable):
        """取消订阅"""
        with self._lock:
            # 从普通监听器中移除
            if listener in self._listeners[event_type]:
                self._listeners[event_type].remove(listener)
                self._stats['total_listeners'] -= 1
            
            # 从优先级监听器中移除
            for priority_listeners in self._priority_listeners[event_type].values():
                if listener in priority_listeners:
                    priority_listeners.remove(listener)
                    self._stats['total_listeners'] -= 1
    
    async def publish(self, event: Event) -> None:
        """发布事件到队列"""
        try:
            await self._queue.put(event)
            self._stats['total_events'] += 1
        except asyncio.QueueFull:
            print(f"[EventBus] 事件队列已满，丢弃事件: {event.event_type}")
    
    async def publish_sync(self, event: Event) -> Any:
        """同步发布事件并等待结果"""
        await self.publish(event)
        
        # 等待事件被处理
        while event.result is None and not event.is_stopped:
            await asyncio.sleep(0.01)
        
        return event.result
    
    async def start(self):
        """启动事件总线"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_events())
        print("[EventBus] 事件总线已启动")
    
    async def stop(self):
        """停止事件总线"""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        print("[EventBus] 事件总线已停止")
    
    async def _process_events(self):
        """处理队列中的事件"""
        while self._running:
            try:
                # 使用超时避免永久阻塞
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[EventBus] 事件处理出错: {e}")
                self._stats['errors'] += 1
    
    async def _dispatch_event(self, event: Event):
        """分发事件到监听器"""
        # 获取所有监听器（按优先级排序）
        all_listeners = []
        
        # 添加优先级监听器（从高到低）
        with self._lock:
            priorities = sorted(self._priority_listeners[event.event_type].keys(), reverse=True)
            for priority in priorities:
                all_listeners.extend(self._priority_listeners[event.event_type][priority])
            
            # 添加普通监听器
            all_listeners.extend(self._listeners[event.event_type])
        
        # 执行监听器
        for listener in all_listeners:
            if event.is_stopped:
                break
            
            try:
                if asyncio.iscoroutinefunction(listener):
                    result = await listener(event)
                else:
                    result = listener(event)
                
                # 如果监听器返回值，则作为事件结果
                if result is not None:
                    event.set_result(result)
                
            except Exception as e:
                print(f"[EventBus] 监听器 {listener.__name__} 处理事件 {event.event_type} 时出错: {e}")
                self._stats['errors'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            'queue_size': self._queue.qsize(),
            'is_running': self._running
        }
    
    def clear_listeners(self, event_type: Optional[str] = None):
        """清除监听器
        
        Args:
            event_type: 事件类型，如果为 None 则清除所有监听器
        """
        with self._lock:
            if event_type:
                if event_type in self._listeners:
                    self._stats['total_listeners'] -= len(self._listeners[event_type])
                    del self._listeners[event_type]
                
                if event_type in self._priority_listeners:
                    for priority_listeners in self._priority_listeners[event_type].values():
                        self._stats['total_listeners'] -= len(priority_listeners)
                    del self._priority_listeners[event_type]
            else:
                self._stats['total_listeners'] = 0
                self._listeners.clear()
                self._priority_listeners.clear()


# 全局事件总线实例
event_bus = EventBus()