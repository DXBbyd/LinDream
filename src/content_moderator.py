#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinDream - 内容审核系统
参考 AstrBot 的内容审核设计，实现敏感内容过滤
"""

import httpx
import re
from typing import List, Optional, Dict, Any
import asyncio


class ContentModerator:
    """内容审核器
    
    提供关键词过滤和第三方API审核功能
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)
        
        # 关键词黑名单
        self.blacklist_keywords: List[str] = []
        
        # 关键词白名单
        self.whitelist_keywords: List[str] = []
        
        # 正则表达式规则
        self.regex_rules: List[re.Pattern] = []
        
        # 统计信息
        self._stats = {
            'total_checks': 0,
            'blocked_count': 0,
            'filtered_count': 0
        }
    
    def load_blacklist(self, keywords: List[str]):
        """加载黑名单关键词
        
        Args:
            keywords: 关键词列表
        """
        self.blacklist_keywords.extend(keywords)
        print(f"[ContentModerator] 已加载 {len(keywords)} 个黑名单关键词")
    
    def load_whitelist(self, keywords: List[str]):
        """加载白名单关键词
        
        Args:
            keywords: 关键词列表
        """
        self.whitelist_keywords.extend(keywords)
        print(f"[ContentModerator] 已加载 {len(keywords)} 个白名单关键词")
    
    def add_regex_rule(self, pattern: str):
        """添加正则表达式规则
        
        Args:
            pattern: 正则表达式字符串
        """
        try:
            regex = re.compile(pattern)
            self.regex_rules.append(regex)
            print(f"[ContentModerator] 已添加正则规则: {pattern}")
        except re.error as e:
            print(f"[ContentModerator] 无效的正则表达式: {pattern}, 错误: {e}")
    
    async def check_content(self, content: str) -> Dict[str, Any]:
        """检查内容
        
        Args:
            content: 要检查的内容
            
        Returns:
            检查结果字典
        """
        self._stats['total_checks'] += 1
        
        result = {
            'is_safe': True,
            'reason': '',
            'filtered_content': content,
            'blocked_by': None
        }
        
        # 1. 白名单检查
        for keyword in self.whitelist_keywords:
            if keyword in content:
                # 白名单内容直接通过
                return result
        
        # 2. 黑名单关键词检查
        for keyword in self.blacklist_keywords:
            if keyword in content:
                result['is_safe'] = False
                result['reason'] = f"包含敏感词: {keyword}"
                result['blocked_by'] = 'blacklist'
                self._stats['blocked_count'] += 1
                return result
        
        # 3. 正则表达式检查
        for regex in self.regex_rules:
            if regex.search(content):
                result['is_safe'] = False
                result['reason'] = f"匹配违规规则: {regex.pattern}"
                result['blocked_by'] = 'regex'
                self._stats['blocked_count'] += 1
                return result
        
        # 4. 调用百度内容审核 API（如果有 API Key）
        if self.api_key:
            try:
                moderation_result = await self._call_baidu_moderation(content)
                if moderation_result['conclusion'] != '合规':
                    result['is_safe'] = False
                    result['reason'] = moderation_result['data'][0]['msg']
                    result['blocked_by'] = 'baidu_api'
                    self._stats['blocked_count'] += 1
                    return result
            except Exception as e:
                print(f"[ContentModerator] 百度内容审核 API 调用失败: {e}")
        
        return result
    
    def filter_content(self, content: str) -> str:
        """过滤内容
        
        将敏感词替换为星号
        
        Args:
            content: 原始内容
            
        Returns:
            过滤后的内容
        """
        filtered = content
        
        # 替换黑名单关键词
        for keyword in self.blacklist_keywords:
            if keyword in filtered:
                filtered = filtered.replace(keyword, '*' * len(keyword))
                self._stats['filtered_count'] += 1
        
        # 替换正则匹配的内容
        for regex in self.regex_rules:
            matches = regex.finditer(filtered)
            for match in matches:
                start, end = match.span()
                filtered = filtered[:start] + '*' * (end - start) + filtered[end:]
                self._stats['filtered_count'] += 1
        
        return filtered
    
    async def _call_baidu_moderation(self, content: str) -> Dict[str, Any]:
        """调用百度内容审核 API
        
        Args:
            content: 要审核的内容
            
        Returns:
            API 响应结果
        """
        url = "https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined"
        
        params = {
            "access_token": self.api_key,
            "text": content
        }
        
        response = await self.client.post(url, data=params)
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            **self._stats,
            'blacklist_count': len(self.blacklist_keywords),
            'whitelist_count': len(self.whitelist_keywords),
            'regex_rules_count': len(self.regex_rules)
        }
    
    def clear_blacklist(self):
        """清空黑名单"""
        self.blacklist_keywords.clear()
        print("[ContentModerator] 黑名单已清空")
    
    def clear_whitelist(self):
        """清空白名单"""
        self.whitelist_keywords.clear()
        print("[ContentModerator] 白名单已清空")
    
    def clear_regex_rules(self):
        """清空正则规则"""
        self.regex_rules.clear()
        print("[ContentModerator] 正则规则已清空")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# 默认敏感词列表
DEFAULT_BLACKLIST = [
    # 政治敏感词
    '政治敏感词1',
    '政治敏感词2',
    
    # 暴力词汇
    '暴力词汇1',
    '暴力词汇2',
    
    # 色情词汇
    '色情词汇1',
    '色情词汇2',
    
    # 其他敏感词
    # 根据实际需求添加
]

# 默认正则规则
DEFAULT_REGEX_RULES = [
    # 手机号
    r'1[3-9]\d{9}',
    # 身份证号
    r'\d{17}[\dXx]',
    # 邮箱
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
]


def create_default_content_moderator(api_key: Optional[str] = None) -> ContentModerator:
    """创建默认的内容审核器
    
    Args:
        api_key: 百度内容审核 API Key
        
    Returns:
        配置好的内容审核器实例
    """
    moderator = ContentModerator(api_key)
    
    # 加载默认黑名单
    moderator.load_blacklist(DEFAULT_BLACKLIST)
    
    # 加载默认正则规则
    for pattern in DEFAULT_REGEX_RULES:
        moderator.add_regex_rule(pattern)
    
    return moderator


# 全局内容审核器实例
content_moderator = create_default_content_moderator()