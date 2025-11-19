#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.59)
简化、可导入的最小实现，修复语法和缺失导入，保留扩展点。
"""

from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
import re
import json
import asyncio
import aiohttp
import logging
import traceback

# 兼容旧代码里使用的别名
_re = re

# 引入 AstrBot 核心 API（运行在 AstrBot 环境时会使用真实实现）
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message_components import Image, Plain
except Exception:
    # 最小回退占位，保证模块可导入用于语法检查/本地测试
    class _DummyFilter:
        def command(self, *args, **kwargs):
            def deco(f):
                return f
            return deco
    filter = _DummyFilter()

    class AstrMessageEvent:
        def __init__(self, message_str=""):
            self.message_str = message_str
        def plain_result(self, text):
            return text

    MessageEventResult = Any

    class Context:
        pass

    def register(*args, **kwargs):
        def deco(cls):
            return cls
        return deco

    class Star:
        pass

    class StarTools:
        pass

    logger = logging.getLogger("tmp-bot")
    # 简单 message components 占位
    class Image:
        @staticmethod
        def fromURL(url):
            return f"[Image:{url}]"

    class Plain:
        def __init__(self, text=""):
            self.text = text

# --- 辅助函数：格式化时间戳为北京时间（UTC+8） ---
def _format_timestamp_to_beijing(timestamp_str: Optional[str]) -> str:
    if not timestamp_str:
        return "未知"
    s = str(timestamp_str).strip()
    if s.lower().startswith('never'):
        return "永久"
    # 处理常见 ISO8601 或 时间戳（秒/毫秒）
    try:
        # 尝试作为整数时间戳（秒或毫秒）
        if s.isdigit():
            t = int(s)
            if t > 1e12:  # ms
                dt = datetime.utcfromtimestamp(t / 1000.0)
            else:
                dt = datetime.utcfromtimestamp(t)
        else:
            # 尝试解析常见 ISO 格式
            dt = datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(tz=None)
        # 转为 UTC then +8
        beijing = dt + timedelta(hours=8)
        return beijing.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return str(timestamp_str)
        except Exception:
            return "未知"

# --- 最小化 DLC/辅助实现（占位，避免 None 错误） ---
def _get_dlc_info(player_info: Dict) -> Dict[str, List[str]]:
    return {"owned": [], "missing": []}

# 自定义异常类（保留接口）
class TmpApiException(Exception):
    pass

class PlayerNotFoundException(TmpApiException):
    pass

class SteamIdNotFoundException(TmpApiException):
    pass

class NetworkException(Exception):
    pass

class ApiResponseException(TmpApiException):
    pass

# 确保版本与 metadata.yaml 保持一致
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.59", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self):
        # 会在真实环境中由框架注入 session/context 等
        self.session = None

    async def _safe_plain(self, event: AstrMessageEvent, text: str):
        # 兼容两种环境：框架期望 yield 组件或直接返回文本
        try:
            return event.plain_result(text)
        except Exception:
            return text

    # 示例：帮助命令
    @filter.command(r'^\s*帮助\s*$')
    async def tmphelp(self, event: AstrMessageEvent) -> MessageEventResult:
        msg = "TMP 插件帮助：支持查询、绑定、定位等。"
        return await self._safe_plain(event, msg)

    # 示例：查询命令（最小化实现，避免抛异常）
    @filter.command(r'^\s*查询\b.*$')
    async def tmpquery(self, event: AstrMessageEvent) -> MessageEventResult:
        # 简单解析 tmp id 或 steam id，真实实现请替换
        msg = f"收到查询请求：{getattr(event, 'message_str', '')}"
        return await self._safe_plain(event, msg)

    # 无前缀精确命令：把常见前缀剥离后调用原命令
    _PREFIX_RE = r'^\s*(?:[!\/\.\#\uFF01\uFF0F])\s*'

    @filter.command(_PREFIX_RE + r'查询\b.*$')
    async def _prefixed_query(self, event: AstrMessageEvent):
        orig = getattr(event, 'message_str', '')
        try:
            event.message_str = re.sub(self._PREFIX_RE, '', orig, count=1)
            return await self.tmpquery(event)
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass