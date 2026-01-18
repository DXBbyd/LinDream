#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 性能优化模块
"""

import asyncio
import time
import gc
from typing import Dict, Any, Optional, List
from collections import deque
import threading

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics = {
            'message_times': deque(maxlen=max_history),
            'memory_usage': deque(maxlen=max_history),
            'cpu_usage': deque(maxlen=max_history),
            'active_connections': 0,
            'total_messages': 0,
            'error_count': 0
        }
        self.lock = threading.Lock()
    
    def record_message_time(self, duration: float):
        """记录消息处理时间"""
        with self.lock:
            self.metrics['message_times'].append(duration)
            self.metrics['total_messages'] += 1
    
    def record_error(self):
        """记录错误"""
        with self.lock:
            self.metrics['error_count'] += 1
    
    def update_connection_count(self, count: int):
        """更新活跃连接数"""
        with self.lock:
            self.metrics['active_connections'] = count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        with self.lock:
            message_times = list(self.metrics['message_times'])
            
            if not message_times:
                return {
                    'avg_message_time': 0,
                    'max_message_time': 0,
                    'min_message_time': 0,
                    'total_messages': self.metrics['total_messages'],
                    'error_count': self.metrics['error_count'],
                    'active_connections': self.metrics['active_connections'],
                    'error_rate': 0
                }
            
            return {
                'avg_message_time': sum(message_times) / len(message_times),
                'max_message_time': max(message_times),
                'min_message_time': min(message_times),
                'total_messages': self.metrics['total_messages'],
                'error_count': self.metrics['error_count'],
                'active_connections': self.metrics['active_connections'],
                'error_rate': self.metrics['error_count'] / max(1, self.metrics['total_messages'])
            }

class MessageQueue:
    """高性能消息队列"""
    
    def __init__(self, max_size: int = 10000):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.processing = False
        self.processors = []
    
    async def put(self, item: Any):
        """添加消息到队列"""
        try:
            await self.queue.put(item)
        except asyncio.QueueFull:
            # 队列满时，丢弃最旧的消息
            try:
                self.queue.get_nowait()
                await self.queue.put(item)
            except asyncio.QueueEmpty:
                pass
    
    async def get(self) -> Any:
        """从队列获取消息"""
        return await self.queue.get()
    
    def size(self) -> int:
        """获取队列大小"""
        return self.queue.qsize()
    
    async def start_processors(self, processor_func, num_workers: int = 3):
        """启动消息处理器"""
        if self.processing:
            return
        
        self.processing = True
        for i in range(num_workers):
            processor = asyncio.create_task(self._process_messages(processor_func, i))
            self.processors.append(processor)
    
    async def stop_processors(self):
        """停止消息处理器"""
        self.processing = False
        for processor in self.processors:
            processor.cancel()
            try:
                await processor
            except asyncio.CancelledError:
                pass
        self.processors.clear()
    
    async def _process_messages(self, processor_func, worker_id: int):
        """处理消息的工作协程"""
        while self.processing:
            try:
                message = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await processor_func(message, worker_id)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"消息处理器 {worker_id} 出错: {e}")

class ConnectionPool:
    """连接池管理"""
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.connections = {}
        self.connection_times = {}
        self.lock = threading.Lock()
    
    def add_connection(self, connection_id: str, connection: Any):
        """添加连接"""
        with self.lock:
            if len(self.connections) >= self.max_connections:
                # 移除最旧的连接
                oldest_id = min(self.connection_times.keys(), 
                              key=lambda k: self.connection_times[k])
                self.remove_connection(oldest_id)
            
            self.connections[connection_id] = connection
            self.connection_times[connection_id] = time.time()
    
    def remove_connection(self, connection_id: str):
        """移除连接"""
        with self.lock:
            if connection_id in self.connections:
                del self.connections[connection_id]
            if connection_id in self.connection_times:
                del self.connection_times[connection_id]
    
    def get_connection(self, connection_id: str) -> Optional[Any]:
        """获取连接"""
        with self.lock:
            return self.connections.get(connection_id)
    
    def cleanup_old_connections(self, max_age: int = 3600):
        """清理旧连接"""
        current_time = time.time()
        with self.lock:
            old_ids = [
                conn_id for conn_id, conn_time in self.connection_times.items()
                if current_time - conn_time > max_age
            ]
            for conn_id in old_ids:
                self.remove_connection(conn_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        with self.lock:
            return {
                'active_connections': len(self.connections),
                'max_connections': self.max_connections
            }

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.cache_times = {}
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                # 检查是否过期
                if time.time() - self.cache_times[key] < self.ttl:
                    return self.cache[key]
                else:
                    # 过期，删除
                    del self.cache[key]
                    del self.cache_times[key]
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self.lock:
            if len(self.cache) >= self.max_size:
                # 移除最旧的缓存项
                oldest_key = min(self.cache_times.keys(), 
                               key=lambda k: self.cache_times[k])
                del self.cache[oldest_key]
                del self.cache_times[oldest_key]
            
            self.cache[key] = value
            self.cache_times[key] = time.time()
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.cache_times.clear()
    
    def cleanup_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        with self.lock:
            expired_keys = [
                key for key, cache_time in self.cache_times.items()
                if current_time - cache_time >= self.ttl
            ]
            for key in expired_keys:
                del self.cache[key]
                del self.cache_times[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'ttl': self.ttl
            }

async def memory_cleanup():
    """内存清理"""
    gc.collect()

async def performance_monitor_task(monitor: PerformanceMonitor, interval: int = 60):
    """性能监控任务"""
    while True:
        try:
            stats = monitor.get_stats()
            print(f"[性能监控] {stats}")
            
            # 定期清理内存
            await memory_cleanup()
            
            await asyncio.sleep(interval)
        except Exception as e:
            print(f"性能监控任务出错: {e}")
            await asyncio.sleep(interval)