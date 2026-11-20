"""Plugin configuration and HTTP session lifecycle."""

import asyncio
import os
import re
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp

from .astrbot_compat import StarTools, logger
from .shared import PLUGIN_ROOT, is_safe_http_url


class LifecycleMixin:
    DEFAULT_API_BASES = ("https://evmapi.cxnnn.cn", "https://evmapi.114512.xyz")

    VTC_HISTORY_API_BASES = DEFAULT_API_BASES

    def __init__(self, context, config=None):
        super().__init__(context)
        self.session: aiohttp.ClientSession | None = None
        self.config = config or {}
        self._translate_cache: Dict[str, str] = {}
        self._location_maps_loaded: bool = False
        self._fullmap_cache: Optional[Dict[str, Any]] = None
        self._fullmap_cache_ts: float = 0.0
        self._fullmap_next_fetch_ts: float = 0.0
        self._fullmap_fetch_lock = asyncio.Lock()
        self._footprint_request_semaphore = asyncio.Semaphore(6)

        self._load_location_maps()
        try:
            data_dir = StarTools.get_data_dir('astrbot_plugin_tmp_bot')
            os.makedirs(data_dir, exist_ok=True)
            bind_path = self.config.get('bind_file') or os.path.join(
                data_dir,
                'tmp_bindings.json',
            )
            data_dir = os.path.abspath(os.fspath(data_dir))
            configured_path = str(bind_path)
            candidate = (
                os.path.join(data_dir, configured_path)
                if not os.path.isabs(configured_path)
                else configured_path
            )
            candidate = os.path.abspath(candidate)
            try:
                common = os.path.commonpath((data_dir, candidate))
            except ValueError:
                common = ""
            if common != data_dir:
                logger.warning("绑定文件路径超出插件数据目录，已回退到默认路径")
                candidate = os.path.join(data_dir, "tmp_bindings.json")
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            self.bind_file = candidate
        except Exception:
            fallback_data_dir = os.path.join(
                PLUGIN_ROOT,
                'data',
                'plugin_data',
                'astrbot_plugin_tmp_bot',
            )
            os.makedirs(fallback_data_dir, exist_ok=True)
            self.bind_file = os.path.join(fallback_data_dir, 'tmp_bindings.json')

        self._tmp_update_state_file = os.path.join(
            os.path.dirname(os.path.abspath(self.bind_file)),
            'tmp_plugin_update_state.json',
        )
        self._tmp_update_state: Dict[str, Any] = {}
        self._tmp_update_groups: Dict[str, Dict[str, str]] = {}
        self._tmp_update_task: Optional[asyncio.Task] = None

    def _cfg_bool(self, key: str, default: bool) -> bool:
        v = self.config.get(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {'1', 'true', 'yes', 'on', '是', '开启', '启用'}:
                return True
            if normalized in {'0', 'false', 'no', 'off', '否', '关闭', '禁用', ''}:
                return False
        return default

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            v = self.config.get(key, default)
            return max(1, min(120, int(v)))
        except (TypeError, ValueError):
            return max(1, min(120, int(default)))

    def _cfg_str(self, key: str, default: str) -> str:
        v = self.config.get(key, default)
        if v is None:
            return default
        return str(v)

    @staticmethod
    def _merge_api_bases(raw, defaults) -> List[str]:
        """把用户填写的额外 API 源拼到内置源前面。

        支持逗号 / 空格 / 换行分隔，允许省略 `https://` 前缀；
        不含域名的条目会被忽略并打日志，重复项自动去重。
        """
        merged: List[str] = []
        for chunk in re.split(r"[,\s]+", str(raw or "")):
            item = chunk.strip().rstrip("/")
            if not item:
                continue
            if not item.lower().startswith(("http://", "https://")):
                item = "https://" + item
            if not is_safe_http_url(item, allow_local_http=True):
                logger.warning(f"忽略格式不安全的 API 源: {chunk.strip()}")
                continue
            host = (urlsplit(item).hostname or "").lower()
            if "." not in host and host.lower() not in {"localhost", "127.0.0.1", "::1"}:
                logger.warning(f"忽略无效的 API 源（缺少域名）: {chunk.strip()}")
                continue
            if host.lower() == "da.vtcm.link":
                logger.warning("忽略已移除的旧 API 源: da.vtcm.link")
                continue
            if item not in merged:
                merged.append(item)
        for d in defaults or ():
            d = str(d).rstrip("/")
            if d and d not in merged:
                merged.append(d)
        return merged

    def _api_bases(self, defaults=None) -> List[str]:
        """当前生效的 API 源列表：用户自定义的排在最前，内置源兜底。"""
        return self._merge_api_bases(
            self._cfg_str('extra_api_bases', ''),
            self.DEFAULT_API_BASES if defaults is None else defaults,
        )

    async def initialize(self):
        if self.session is not None and not self.session.closed:
            return
        timeout_sec = max(1, self._cfg_int('api_timeout_seconds', 10))
        # 使用 IPv4 优先的连接器，并允许读取环境代理设置（与浏览器/系统行为更一致）
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'astrBot-TMP-Plugin/v2.0.0'},
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
            connector=connector,
            trust_env=True
        )
        logger.info(f"TMP Bot 插件HTTP会话已创建，超时 {timeout_sec}s")
        logger.info(f"TMP Bot 插件 API 源（按优先级）: {' -> '.join(self._api_bases())}")
        self._load_tmp_update_state()
        self._start_tmp_update_task()

    async def terminate(self):
        """插件卸载时的清理工作：停止后台任务、保存状态并关闭HTTP会话。"""
        update_task = self._tmp_update_task
        self._tmp_update_task = None
        try:
            if update_task is not None:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
            if self._tmp_update_state or self._tmp_update_groups:
                self._save_tmp_update_state()
        finally:
            if self.session is not None:
                await self.session.close()
                self.session = None
        logger.info("TMP Bot 插件已卸载")
