"""AstrBot API imports with lightweight stubs for standalone tests."""

import os
from typing import Any

try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message_components import Image, Plain
except ModuleNotFoundError as exc:
    if exc.name != "astrbot":
        raise

    # 最小化兼容回退
    class _DummyFilter:
        class EventMessageType:
            ALL = "ALL"

        def command(self, pattern, **kwargs):
            def decorator(func):
                return func
            return decorator

        def event_message_type(self, _type, **kwargs):
            def decorator(func):
                return func
            return decorator
    filter = _DummyFilter()
    class AstrMessageEvent:
        def __init__(self, message_str: str = "", sender_id: str = "0", match=None, group_id: str = None):
            self.message_str = message_str
            self._sender_id = sender_id
            self._match = match
            self._group_id = group_id
        def get_sender_id(self) -> str:
            return self._sender_id
        def get_group_id(self) -> str:
            return self._group_id or ""
        def is_group_message(self) -> bool:
            return bool(self._group_id)
        def is_private_message(self) -> bool:
            return not self._group_id
        def plain_result(self, msg):
            return msg
        def chain_result(self, components):
            return components
    MessageEventResult = Any
    class Context: pass
    class Star:
        def __init__(self, context: Context = None):
            self.context = context
    def register(*args, **kwargs):
        def deco(cls):
            return cls
        return deco
    class StarTools:
        @staticmethod
        def get_data_dir(name: str):
            return os.path.join(os.getcwd(), name)
    class _Logger:
        @staticmethod
        def debug(msg):
            pass
        @staticmethod
        def info(msg):
            print("[INFO]", msg)
        @staticmethod
        def warning(msg):
            print("[WARN]", msg)
        @staticmethod
        def error(msg, exc_info=False):
            print("[ERROR]", msg)
            if exc_info:
                import traceback
                traceback.print_exc()
    logger = _Logger()
    # 兼容运行环境缺失时的占位 Image 类
    class Image:
        @staticmethod
        def fromBytes(b: bytes):
            return b
        @staticmethod
        def fromURL(url: str):
            return url
    class Plain:
        def __init__(self, text: str):
            self.text = text
