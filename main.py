#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
astrbot-plugin-tmp-bot
欧卡2TMP查询插件 (版本 1.7.1)
"""

import re
import asyncio
import aiohttp
import json
import os
import re as _re_local
import base64
import socket
import hashlib
import random
import time
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta

# 引入 AstrBot 核心 API
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message_components import Image, Plain
    # 强制 INFO 级别，确保能看到 bans 日志
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
except ImportError:
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
        def __init__(self, message_str: str = "", sender_id: str = "0", match=None):
            self.message_str = message_str
            self._sender_id = sender_id
            self._match = match 
        def get_sender_id(self) -> str:
            return self._sender_id
        async def plain_result(self, msg):
            return msg
        async def chain_result(self, components):
            return components
    MessageEventResult = Any 
    class Context: pass
    class Star:
        def __init__(self, context: Context = None): pass
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
        def info(msg):
            print("[INFO]", msg)
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

USER_GROUP_MAP = {
    'Player': '玩家',
    'Retired Legend': '退役',
    'Game Developer': '游戏开发者',
    'Retired Team Member': '退休团队成员',
    'Add-On Team': '附加组件团队',
    'Game Moderator': '游戏管理员'
}
PROMODS_SERVER_IDS = {50, 51}

def _translate_user_groups(groups: List[Any]) -> List[str]:
    translated: List[str] = []
    for g in groups:
        if g is None:
            continue
        key = str(g)
        translated.append(USER_GROUP_MAP.get(key, key))
    return translated


# --- 辅助函数：格式化时间戳 ---
def _format_timestamp_to_readable(timestamp_str: Optional[str]) -> str:
    """将 TruckersMP API 返回的 UTC 时间戳转换为可读格式 (ISO 8601)。"""
    if not timestamp_str:
        return "未知"
    
    try:
        # TruckersMP V2 返回 ISO 8601 (e.g., "2024-05-28T14:30:00.000Z")
        clean_str = timestamp_str.replace('T', ' ').split('.')[0].replace('Z', '')
        dt_utc = datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
        # 直接显示 UTC 时间，并标注时区
        return dt_utc.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception:
        # 兼容性回退
        return timestamp_str.split('T')[0] if 'T' in timestamp_str else timestamp_str
# -----------------------------

def _format_timestamp_to_beijing(timestamp_str: Optional[str]) -> str:
    """将 UTC 时间戳转换为北京时间 (UTC+8)。兼容 ISO 8601 和简单格式。"""
    if not timestamp_str:
        return "未知"

    s = str(timestamp_str).strip()
    if s.lower().startswith('never'):
        return "永久封禁"

    try:
        clean_str = s.replace('T', ' ').split('.')[0].replace('Z', '')
        dt_utc = datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
        dt_bj = dt_utc + timedelta(hours=8)
        return dt_bj.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        try:
            # ISO 8601 with timezone offset, e.g. 2025-12-01T07:55:00+00:00
            iso = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(iso)
            dt_bj = dt + timedelta(hours=8)
            return dt_bj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return s

def _cleanup_cn_location_text(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return s
    try:
        s = _re_local.sub(r"\s+", " ", s).strip()
        s = _re_local.sub(r"^(?:[\[［][^\]］]+[\]］]\s*)+", "", s)
        s = _re_local.sub(r"^<[^>]+>\s*", "", s)
        s = _re_local.sub(r"^(?:&\s*)?(?:n|v|adj|adv|vt|vi|prep|pron|conj|abbr)[\.．]\s*", "", s, flags=_re_local.IGNORECASE)
        s = _re_local.sub(r"^(?:\s*(?:&\s*)?(?:n|v|adj|adv|vt|vi|prep|pron|conj|abbr)[\.．]\s*)+", "", s, flags=_re_local.IGNORECASE)
        s = _re_local.sub(r"^(?:\s*(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]\s*)+", "", s)
        s = _re_local.sub(r"（[^）]*）", "", s)
        s = _re_local.sub(r"\([^)]*\)", "", s)
        for sep in ["；", ";", "，"]:
            if sep in s:
                s = s.split(sep, 1)[0]
        s = s.strip(" 、，。.；;")
        if _re_local.search(r"\s", s):
            head = _re_local.split(r"\s+", s, 1)[0]
            if _re_local.search(r"[\u4e00-\u9fff]", head) and not _re_local.fullmatch(r"(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]?", head):
                s = head
        return s or text
    except Exception:
        return text

# -----------------------------


# 自定义异常类 
class TmpApiException(Exception):
    """TMP 相关异常的基类"""
    pass

class PlayerNotFoundException(TmpApiException):
    """玩家不存在异常"""
    pass

class SteamIdNotFoundException(TmpApiException):
    """Steam ID 未绑定 TMP 账号异常"""
    pass

class NetworkException(Exception):
    """网络请求异常"""
    pass

class ApiResponseException(TmpApiException):
    """API响应异常"""
    pass

# 版本号更新为 1.3.59
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.7.0", "https://github.com/BGYdook/astrbot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context, config=None):  # 接收 context 和 config
        super().__init__(context)              # 将 context 传给父类
        self.widget_list = []
        # 会在真实环境中由框架注入 session/context 等
        self.session = None
        self._ready = False
        self.config = config or {}
        self._translate_cache: Dict[str, str] = {}
        self._location_maps_loaded: bool = False
        self._fullmap_cache: Optional[Dict[str, Any]] = None
        self._fullmap_cache_ts: float = 0.0
        self._fullmap_last_fetch_ts: float = 0.0
        self._fullmap_next_fetch_ts: float = 0.0
        self._fullmap_task: Optional[asyncio.Task] = None
        self._fullmap_lock = asyncio.Lock()
        self._fullmap_fetch_lock = asyncio.Lock()
        self._load_location_maps()
        try:
            bind_path = self.config.get('bind_file')
            if not bind_path:
                root = os.getcwd()
                bind_path = os.path.join(root, 'data', 'tmp_bindings.json')
            d = os.path.dirname(bind_path)
            if d:
                os.makedirs(d, exist_ok=True)
            self.bind_file = bind_path
        except Exception:
            self.bind_file = os.path.join(os.getcwd(), 'tmp_bindings.json')
        try:
            logger.info("TMP Bot 插件初始化开始")
            # 仅做轻量初始化，避免在导入阶段执行网络/阻塞操作
            # 真实运行时框架会在 on_load/on_start 注入 session 等资源
            self._ready = True
            logger.info("TMP Bot 插件初始化完成（就绪）")
        except Exception as e:
            self._ready = False
            logger.exception("TMP Bot 插件初始化发生异常，标记为未就绪：%s", e)

    # --- 配置读取辅助 ---
    def _cfg_bool(self, key: str, default: bool) -> bool:
        v = self.config.get(key, default)
        return bool(v) if isinstance(v, (bool, int, str)) else default

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            v = self.config.get(key, default)
            return int(v)
        except Exception:
            return default

    def _cfg_str(self, key: str, default: str) -> str:
        v = self.config.get(key, default)
        if v is None:
            return default
        return str(v)

    async def initialize(self):
        # 统一 User-Agent，并更新版本号
        timeout_sec = self._cfg_int('api_timeout_seconds', 10)
        # 使用 IPv4 优先的连接器，并允许读取环境代理设置（与浏览器/系统行为更一致）
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'astrBot-TMP-Plugin/1.3.59'}, 
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
            connector=connector,
            trust_env=True
        )
        logger.info(f"TMP Bot 插件HTTP会话已创建，超时 {timeout_sec}s")
        self._fullmap_task = None

    def _get_fullmap_interval(self) -> int:
        v = self._cfg_int('ets2map_fullmap_interval_seconds', 60)
        return 60 if v < 60 else v

    def _start_fullmap_task(self) -> None:
        if self._fullmap_task and not self._fullmap_task.done():
            return
        self._fullmap_task = asyncio.create_task(self._fullmap_loop())

    async def _fullmap_loop(self) -> None:
        await asyncio.sleep(self._get_fullmap_interval())
        while True:
            await self._fetch_fullmap()
            await asyncio.sleep(self._get_fullmap_interval())

    async def _fetch_fullmap(self) -> None:
        if not self.session:
            return
        interval = self._get_fullmap_interval()
        async with self._fullmap_fetch_lock:
            now_wall = time.time()
            if now_wall - self._fullmap_last_fetch_ts < interval:
                if not self._fullmap_cache:
                    logger.info(f"fullmap 拉取跳过(限频): interval={interval}s")
                return
            now_mono = time.monotonic()
            if now_mono < self._fullmap_next_fetch_ts:
                if not self._fullmap_cache:
                    logger.info(f"fullmap 拉取跳过(限频): interval={interval}s")
                return
            self._fullmap_next_fetch_ts = now_mono + interval
            self._fullmap_last_fetch_ts = time.time()
        url = "https://tracker.ets2map.com/v3/fullmap"
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        async with self._fullmap_lock:
                            self._fullmap_cache = data
                            self._fullmap_cache_ts = time.time()
                        logger.info("fullmap 拉取成功")
                        return
                logger.info(f"fullmap 拉取失败 status={resp.status}")
        except Exception as e:
            logger.error(f"fullmap 拉取异常: {e}")

    def _get_fullmap_tile_url(self, map_type: str) -> Optional[str]:
        data = self._fullmap_cache or {}
        candidates: List[str] = []
        def walk(v: Any) -> None:
            if isinstance(v, dict):
                for val in v.values():
                    walk(val)
                return
            if isinstance(v, list):
                for val in v:
                    walk(val)
                return
            if isinstance(v, str):
                s = v.strip()
                if s.startswith("http") and "{z}" in s and "{x}" in s and "{y}" in s:
                    candidates.append(s)
        if isinstance(data, dict):
            if data.get('Data'):
                walk(data.get('Data'))
            if data.get('data'):
                walk(data.get('data'))
            walk(data)
        else:
            walk(data)
        if not candidates:
            return None
        seen = set()
        uniq = []
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)
        candidates = uniq
        if map_type == "promods":
            for c in candidates:
                if "promods" in c.lower():
                    return c
        for c in candidates:
            lc = c.lower()
            if "ets" in lc and "promods" not in lc:
                return c
        return candidates[0]

    # --- 工具：头像处理 ---
    def _normalize_avatar_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        # 去除日志可能引入的反引号、括号、引号，以及误传入的 CQ 片段前缀
        u = str(url).strip()
        # 清理包装字符
        for ch in ('`', '"', "'", '(', ')'):
            u = u.strip(ch)
        # 如果误传了完整片段，剥离前缀
        if u.startswith('[CQ:image,file='):
            u = u[len('[CQ:image,file='):]
        # 去掉结尾的右括号
        if u.endswith(']'):
            u = u[:-1]
        u = u.strip()
        return u or None

    async def _get_avatar_base64(self, url: str) -> Optional[str]:
        if not self.session:
            return None
        try:
            timeout_sec = self._cfg_int('api_timeout_seconds', 10)
            async with self.session.get(url, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if content:
                        return base64.b64encode(content).decode('ascii')
                return None
        except Exception:
            return None

    async def _get_avatar_bytes(self, url: str) -> Optional[bytes]:
        if not self.session:
            return None
        try:
            timeout_sec = self._cfg_int('api_timeout_seconds', 10)
            async with self.session.get(url, timeout=timeout_sec, allow_redirects=True) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if content:
                        return content
                    else:
                        logger.info(f"头像下载失败: 空内容 status=200 url={url}")
                        return None
                else:
                    logger.info(f"头像下载失败: status={resp.status} url={url}")
                    return None
        except Exception as e:
            logger.error(f"头像下载异常: url={url} err={e}", exc_info=False)
            return None

    async def _translate_text(self, content: str, cache: bool = True) -> str:
        return content

    async def _get_avatar_bytes_with_fallback(self, url: str, tmp_id: Optional[str]) -> Optional[bytes]:
        """尝试多种 TruckersMP 头像URL变体，尽可能获取头像字节。"""
        base = self._normalize_avatar_url(url)
        candidates: List[str] = []
        if base:
            candidates.append(base)
            # 切换 jpg/png
            if base.lower().endswith('.jpg'):
                candidates.append(base[:-4] + '.png')
            elif base.lower().endswith('.png'):
                candidates.append(base[:-4] + '.jpg')
            # 解析 avatarsN/{id}.{stamp}.{ext} -> 生成多种组合
            import re as _re
            m = _re.search(r"https?://static\.truckersmp\.com/(avatarsN|avatars)/(\d+)(?:\.\d+)?\.(jpg|png)", base, _re.IGNORECASE)
            if m:
                folder = m.group(1)
                pid = m.group(2)
                ext = m.group(3).lower()
                alt_ext = 'png' if ext == 'jpg' else 'jpg'
                # 去掉时间戳
                candidates.append(f"https://static.truckersmp.com/{folder}/{pid}.{ext}")
                candidates.append(f"https://static.truckersmp.com/{folder}/{pid}.{alt_ext}")
                # 切到另一个目录
                other_folder = 'avatars' if folder.lower() == 'avatarsn' else 'avatarsN'
                candidates.append(f"https://static.truckersmp.com/{other_folder}/{pid}.{ext}")
                candidates.append(f"https://static.truckersmp.com/{other_folder}/{pid}.{alt_ext}")

        # 根据 tmp_id 追加常见直连地址
        if tmp_id:
            for ext in ('jpg', 'png'):
                candidates.append(f"https://static.truckersmp.com/avatars/{tmp_id}.{ext}")
                candidates.append(f"https://static.truckersmp.com/avatarsN/{tmp_id}.{ext}")

        # 去重保持顺序
        seen = set()
        uniq: List[str] = []
        for c in candidates:
            if not c:
                continue
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)

        for c in uniq:
            b = await self._get_avatar_bytes(c)
            logger.info(f"头像下载尝试: url={c} -> {'成功' if b else '失败'}")
            if b:
                return b
        return None

    # --- 内部工具方法 (保持不变) ---
    def _load_bindings(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.bind_file):
                with open(self.bind_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载绑定数据失败: {e}")
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        try:
            with open(self.bind_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}")
            return False

    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id)
        if isinstance(user_binding, dict):
            return user_binding.get('tmp_id')
        return user_binding

    def _bind_tmp_id(self, user_id: str, tmp_id: str, player_name: str) -> bool:
        bindings = self._load_bindings()
        bindings[user_id] = {
            'tmp_id': tmp_id,
            'player_name': player_name,
            'bind_time': asyncio.get_event_loop().time()
        }
        return self._save_bindings(bindings)

    def _unbind_tmp_id(self, user_id: str) -> bool:
        bindings = self._load_bindings()
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False

    COUNTRY_MAP_EN_TO_CN = {
        "germany": "德国",
        "de": "德国",
        "france": "法国",
        "fr": "法国",
        "united kingdom": "英国",
        "uk": "英国",
        "gb": "英国",
        "netherlands": "荷兰",
        "nl": "荷兰",
        "belgium": "比利时",
        "be": "比利时",
        "poland": "波兰",
        "pl": "波兰",
        "czech republic": "捷克",
        "czechia": "捷克",
        "cz": "捷克",
        "slovakia": "斯洛伐克",
        "sk": "斯洛伐克",
        "italy": "意大利",
        "it": "意大利",
        "spain": "西班牙",
        "es": "西班牙",
        "portugal": "葡萄牙",
        "pt": "葡萄牙",
        "switzerland": "瑞士",
        "ch": "瑞士",
        "austria": "奥地利",
        "at": "奥地利",
        "hungary": "匈牙利",
        "hu": "匈牙利",
        "denmark": "丹麦",
        "dk": "丹麦",
        "sweden": "瑞典",
        "se": "瑞典",
        "norway": "挪威",
        "no": "挪威",
        "finland": "芬兰",
        "fi": "芬兰",
        "estonia": "爱沙尼亚",
        "ee": "爱沙尼亚",
        "latvia": "拉脱维亚",
        "lv": "拉脱维亚",
        "lithuania": "立陶宛",
        "lt": "立陶宛",
        "russia": "俄罗斯",
        "ru": "俄罗斯",
        "turkey": "土耳其",
        "tr": "土耳其",
        "romania": "罗马尼亚",
        "ro": "罗马尼亚",
        "bulgaria": "保加利亚",
        "bg": "保加利亚",
        "greece": "希腊",
        "gr": "希腊",
        "united states": "美国",
        "usa": "美国",
        "us": "美国",
        "iceland": "冰岛",
        "is": "冰岛",
        "svalbard": "斯瓦尔巴群岛",
    }

    CITY_MAP_EN_TO_CN = {
        "calais": "加来",
        "duisburg": "杜伊斯堡",
        "berlin": "柏林",
        "paris": "巴黎",
        "london": "伦敦",
        "cambridge": "剑桥",
        "milano": "米兰",
        "milan": "米兰",
        "rome": "罗马",
        "madrid": "马德里",
        "barcelona": "巴塞罗那",
        "lisbon": "里斯本",
        "rotterdam": "鹿特丹",
        "amsterdam": "阿姆斯特丹",
        "brussels": "布鲁塞尔",
        "prague": "布拉格",
        "vienna": "维也纳",
        "budapest": "布达佩斯",
        "warsaw": "华沙",
        "krakow": "克拉科夫",
        "akureyri": "阿克雷里",
        "burgos": "布尔戈斯",
        "praha": "布拉格",
        "steinkjer": "斯泰恩谢尔",
        "valmiera": "瓦尔米耶拉",
        "umeå": "于默奥",
        "umea": "于默奥",
        "longyearbyen": "朗伊尔城",
        "napoli": "那不勒斯",
        "sundsvall": "松兹瓦尔",
    }

    LOCATION_FIX_MAP = {
        "kirkenes": "希尔克内斯",
        "kirkenes quarry": "希尔克内斯 采石场",
        "c-d road": "加莱-杜伊斯堡",
        "cd road": "加莱-杜伊斯堡",
        "calais-duisburg road": "加莱-杜伊斯堡",
        "calais - duisburg": "加莱-杜伊斯堡",
        "calais–duisburg": "加莱-杜伊斯堡",
        "calais-duisburg": "加莱-杜伊斯堡",
        "calais intersection": "加来 交叉口",
        "dortmund": "多特蒙德",
        "hannover": "汉诺威",
        "hamburg": "汉堡",
        "strasbourg": "斯特拉斯堡",
        "dijon": "第戎",
        "reims": "兰斯",
        "brussel": "布鲁塞尔",
        "aalborg": "奥尔堡",
        "kiruna": "基律纳",
        "skellefteå": "谢莱夫特奥",
        "skelleftea": "谢莱夫特奥",
        "ljubjana": "卢布尔雅那",
        "ljubljana": "卢布尔雅那",
        "nikel": "尼克尔",
        "travemünde": "特拉弗明德",
        "travemunde": "特拉弗明德",
        "zürich": "苏黎世",
        "zurich": "苏黎世",
    }

    def _load_location_maps(self) -> None:
        if getattr(self, "_location_maps_loaded", False):
            return

        def _strip_cn_city_suffix(cn: str) -> str:
            t = (cn or "").strip()
            if t.endswith("（城市）"):
                t = t[:-4]
            return t.strip()

        def _parse_table(file_path: str) -> List[Tuple[str, str]]:
            try:
                if not os.path.exists(file_path):
                    return []
                rows: List[Tuple[str, str]] = []
                with open(file_path, "r", encoding="utf-8") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line.startswith("|"):
                            continue
                        if line.startswith("| English |"):
                            continue
                        if line.startswith("|---"):
                            continue
                        parts = [p.strip() for p in line.strip("|").split("|")]
                        if len(parts) < 2:
                            continue
                        en = parts[0].strip()
                        cn = parts[1].strip()
                        if not en or not cn:
                            continue
                        rows.append((en, cn))
                return rows
            except Exception:
                return []

        def _add_mapping(en: str, cn: str) -> None:
            en_raw = (en or "").strip()
            cn_raw = (cn or "").strip()
            if not en_raw or not cn_raw:
                return
            if cn_raw == en_raw:
                return

            en_key = en_raw.lower()
            cn_clean = _cleanup_cn_location_text(cn_raw)
            if not cn_clean:
                return

            status_m = _re_local.search(r"\s*-\s*(?P<status>[A-Za-z]+)\s*\((?P<num>\d+)\)\s*$", en_raw)
            en_base = en_raw
            if status_m:
                en_base = en_raw[: status_m.start()].strip()
            if cn_clean.lower() == en_base.lower():
                return

            city_m = _re_local.search(r"\s*\(City\)\s*$", en_base, flags=_re_local.IGNORECASE)
            if city_m:
                city_en_base = en_base[: city_m.start()].strip()
                city_cn_base = _strip_cn_city_suffix(cn_clean)
                if city_en_base and (city_cn_base or cn_clean).lower() == city_en_base.lower():
                    return
                if city_en_base:
                    self.CITY_MAP_EN_TO_CN[city_en_base.lower()] = city_cn_base or cn_clean
                    self.LOCATION_FIX_MAP[city_en_base.lower()] = city_cn_base or cn_clean
                self.LOCATION_FIX_MAP[en_base.lower()] = city_cn_base or cn_clean
                self.LOCATION_FIX_MAP[en_key] = city_cn_base or cn_clean
                return

            self.COUNTRY_MAP_EN_TO_CN[en_base.lower()] = cn_clean
            self.LOCATION_FIX_MAP[en_base.lower()] = cn_clean
            self.LOCATION_FIX_MAP[en_key] = cn_clean

        try:
            root = os.path.dirname(__file__)
        except Exception:
            root = os.getcwd()

        data_dir = os.path.join(root, "TruckersMP-citties-name")
        for name in ("s1-cities.md", "promods-cities.md"):
            path = os.path.join(data_dir, name)
            for en, cn in _parse_table(path):
                _add_mapping(en, cn)

        self._location_maps_loaded = True

    async def _translate_country_city(self, country: Optional[str], city: Optional[str]) -> Tuple[str, str]:
        country_en = (country or "").strip()
        city_en = (city or "").strip()

        def _normalize_city_input(raw_city: str, raw_country: str) -> str:
            s = (raw_city or "").strip()
            if not s:
                return s
            s = _re_local.sub(r"\s+", " ", s).strip()
            c = (raw_country or "").strip()
            if c:
                c_norm = _re_local.sub(r"\s+", " ", c).strip()
                if s.lower().startswith((c_norm + " - ").lower()):
                    s = s[len(c_norm) + 3 :].strip()
                elif s.lower().startswith((c_norm + " ").lower()):
                    s = s[len(c_norm) + 1 :].strip()
            if " - " in s:
                left, right = s.split(" - ", 1)
                left_k = left.strip().lower()
                if left_k in self.COUNTRY_MAP_EN_TO_CN:
                    s = right.strip()
            low = s.lower()
            for k in sorted(self.COUNTRY_MAP_EN_TO_CN.keys(), key=len, reverse=True):
                if not k:
                    continue
                if low.startswith(k + " - "):
                    s = s[len(k) + 3 :].strip()
                    break
                if low.startswith(k + " "):
                    s = s[len(k) + 1 :].strip()
                    break
            return s

        city_en = _normalize_city_input(city_en, country_en)
        country_key = country_en.lower()
        city_key = city_en.lower()
        country_cn = self.COUNTRY_MAP_EN_TO_CN.get(country_key)
        city_cn = self.CITY_MAP_EN_TO_CN.get(city_key)
        if country_en and not country_cn:
            translated_country = await self._translate_text(country_en, cache=True)
            if translated_country:
                country_cn = translated_country
        if city_en and not city_cn:
            translated_city = await self._translate_text(city_en, cache=True)
            if translated_city:
                city_cn = translated_city
        fix_country = self.LOCATION_FIX_MAP.get(country_key)
        fix_city = self.LOCATION_FIX_MAP.get(city_key)
        if fix_country:
            country_cn = fix_country
        if fix_city:
            city_cn = fix_city
        return country_cn or country_en, city_cn or city_en

    async def _translate_traffic_name(self, name: Optional[str]) -> str:
        s = (name or "").strip()
        if not s:
            return s
        s = _re_local.sub(r"\s+", " ", s).strip()
        key = s.lower()
        
        # 1. 查修正表
        fix = self.LOCATION_FIX_MAP.get(key)
        if fix:
            return fix
            
        # 2. 查城市表 (路况里的 name 经常是城市名)
        city_fix = self.CITY_MAP_EN_TO_CN.get(key)
        if city_fix:
            return city_fix

        m_suffix = _re_local.search(r"^(?P<base>.+?)\s+(?P<suffix>intersection|quarry)\s*$", s, flags=_re_local.IGNORECASE)
        if m_suffix:
            base = (m_suffix.group("base") or "").strip()
            suffix = (m_suffix.group("suffix") or "").strip().lower()
            base_cn = await self._translate_traffic_name(base)
            suffix_cn = "交叉口" if suffix == "intersection" else "采石场"
            merged_key = f"{base} {suffix}".strip().lower()
            merged_fix = self.LOCATION_FIX_MAP.get(merged_key)
            if merged_fix:
                return merged_fix
            if base_cn and base_cn != base:
                return f"{base_cn} {suffix_cn}".strip()

        for sep in (" - ", "–", "-", "/"):
            if sep in s:
                parts = [p.strip() for p in s.split(sep) if p.strip()]
                if len(parts) >= 2:
                    translated_parts: List[str] = []
                    for p in parts:
                        pk = p.lower()
                        translated_parts.append(
                            self.LOCATION_FIX_MAP.get(pk)
                            or self.CITY_MAP_EN_TO_CN.get(pk)
                            or p
                        )
                    joiner = " - " if sep.strip() in ("-", "–") else sep
                    return joiner.join(translated_parts)
            
        # 3. 百度翻译
        translated = await self._translate_text(s, cache=True)
        if translated:
            return translated
        return s

    # --- API请求方法 ---

    async def _get_tmp_id_from_steam_id(self, steam_id: str) -> str:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        
        try:
            # TruckyApp V2 Steam ID 转换接口
            url = f"https://api.truckyapp.com/v2/truckersmp/player/get_by_steamid/{steam_id}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tmp_id = data.get('response', {}).get('truckersmp_id')
                    
                    if tmp_id:
                        return str(tmp_id)
                    else:
                        raise SteamIdNotFoundException(f"Steam ID {steam_id} 未绑定或Trucky API未找到对应的TMP账号。")
                elif response.status == 404:
                    raise SteamIdNotFoundException(f"Steam ID {steam_id} 未绑定或Trucky API未找到对应的TMP账号。")
                else:
                    raise ApiResponseException(f"Steam ID转换API返回错误状态码: {response.status}")
        except aiohttp.ClientError:
            raise NetworkException("Steam ID转换服务网络请求失败")
        except asyncio.TimeoutError:
            raise NetworkException("请求 Steam ID 转换服务超时")
        except SteamIdNotFoundException:
            raise 
        except Exception as e:
            logger.error(f"查询 TMP ID 失败: {e}")
            raise NetworkException("查询失败")
            
    def _get_steam_id_from_player_info(self, player_info: Dict) -> Optional[str]:
        steam_id = player_info.get('steamID64')
        return str(steam_id) if steam_id else None

    async def _get_player_info(self, tmp_id: str) -> Dict:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        
        try:
            # TMP 官方 V2 接口
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response')
                    if response_data and isinstance(response_data, dict):
                        return response_data
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在") 
                elif response.status == 404:
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                else:
                    raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except aiohttp.ClientError:
            raise NetworkException("TruckersMP API 网络请求失败")
        except asyncio.TimeoutError:
            raise NetworkException("请求TruckersMP API超时")
        except Exception as e:
            logger.error(f"查询玩家信息失败: {e}")
            raise NetworkException("查询失败")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        if not self.session: return []

        try:
            url = f"https://api.truckersmp.com/v2/bans/{tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    # 兼容：优先取 response，其次直接取 data（防止结构变化）
                    bans = data.get('response') or data.get('data') or []
                    if not isinstance(bans, list):
                        bans = []
                    # 额外打印完整返回，方便一次性定位
                    logger.info(f"Bans API 原始返回: {data}")
                    logger.info(f"Bans API 提取后: keys={list(data.keys())}, count={len(bans)}")
                    return bans
                logger.warning(f"Bans API 非200状态: {response.status}")
                return []
        except Exception as e:
            logger.error(f"获取玩家封禁失败: {e}", exc_info=False)
            return []
            
    async def _get_player_stats(self, tmp_id: str) -> Dict[str, Any]:
        """通过 da.vtcm.link API 获取玩家的总里程、今日里程和头像。
        字段调整：历史里程使用 mileage，今日里程使用 todayMileage。
        输出调整：将从 API 获取的数值除以 1000（米→公里），保留两位小数。
        不再兼容旧字段 totalDistance/todayDistance，并对数值进行稳健转换。
        """
        if not self.session: 
            return {'total_km': 0, 'daily_km': 0, 'avatar_url': '', 'debug_error': 'HTTP会话不可用。'}

        vtcm_stats_url = f"https://da.vtcm.link/player/info?tmpId={tmp_id}"
        logger.info(f"尝试 VTCM 里程 API: {vtcm_stats_url}")
        
        try:
            # 指定 ssl=False（仅此请求）避免特定环境下证书或 TLS 握手导致的 ClientError，同时允许重定向
            async with self.session.get(
                vtcm_stats_url,
                timeout=self._cfg_int('api_timeout_seconds', 10),
                ssl=False,
                allow_redirects=True
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('data', {}) 
                    logger.info(f"VTCM 里程响应: status=200, code={data.get('code')}, has_data={bool(response_data)}")
                    
                    # 使用新字段：mileage / todayMileage（单位：米），转换为公里并保留两位小数
                    def _to_km_2f(val, default=0.0):
                        try:
                            if val is None:
                                return default
                            if isinstance(val, (int, float)):
                                return round(float(val) / 1000.0, 2)
                            s = str(val).strip()
                            if s == "":
                                return default
                            return round(float(s) / 1000.0, 2)
                        except Exception:
                            return default

                    total_raw = response_data.get('mileage')
                    daily_raw = response_data.get('todayMileage')

                    total_km = _to_km_2f(total_raw, 0.0)
                    daily_km = _to_km_2f(daily_raw, 0.0)
                    avatar_url = response_data.get('avatarUrl', '')
                    vtc_role = response_data.get('vtcRole') or response_data.get('vtc_role')
                    def _to_int_rank(val):
                        try:
                            if val is None:
                                return None
                            if isinstance(val, int):
                                return val
                            if isinstance(val, float):
                                return int(val)
                            s = str(val).strip()
                            if s == "":
                                return None
                            return int(float(s))
                        except Exception:
                            return None
                    total_rank_raw = (
                        response_data.get('mileageRank')
                        or response_data.get('totalMileageRank')
                        or response_data.get('mileage_rank')
                        or response_data.get('total_rank')
                    )
                    daily_rank_raw = (
                        response_data.get('todayMileageRank')
                        or response_data.get('todayRank')
                        or response_data.get('today_mileage_rank')
                        or response_data.get('today_rank')
                    )
                    total_rank = _to_int_rank(total_rank_raw)
                    daily_rank = _to_int_rank(daily_rank_raw)
                    # 尝试从 VTCM 响应中获取上次在线时间（兼容多个可能的字段名）
                    last_online = (
                        response_data.get('lastOnline')
                        or response_data.get('lastOnlineTime')
                        or response_data.get('last_login')
                        or response_data.get('lastLogin')
                        or None
                    )
                    logger.info(f"VTCM 里程解析: total_km={total_km:.2f}, today_km={daily_km:.2f}, total_rank={total_rank}, daily_rank={daily_rank}, avatar={avatar_url}")
                    
                    if data.get('code') != 200 or not response_data:
                        logger.info(f"VTCM 里程数据校验失败: code={data.get('code')}, has_data={bool(response_data)}")
                        raise ApiResponseException(f"VTCM 里程 API 返回非成功代码或空数据: {data.get('msg', 'N/A')}")

                    return {
                        'total_km': total_km,
                        'daily_km': daily_km,
                        'avatar_url': avatar_url,
                        'last_online': last_online,
                        'vtcRole': vtc_role,
                        'total_rank': total_rank,
                        'daily_rank': daily_rank,
                        'debug_error': 'VTCM 里程数据获取成功。'
                    }
                else:
                    logger.info(f"VTCM 里程 API 返回非 200 状态: status={response.status}")
                    return {'total_km': 0, 'daily_km': 0, 'avatar_url': '', 'debug_error': f'VTCM 里程 API 返回状态码: {response.status}'}

        except aiohttp.ClientError as e:
            logger.error(f"VTCM 里程 API 网络异常: {e.__class__.__name__}: {str(e)}")
            return {
                'total_km': 0, 
                'daily_km': 0, 
                'avatar_url': '', 
                'debug_error': f'VTCM 里程 API 请求失败（网络错误: {e.__class__.__name__}: {str(e)}）。'
            }
        except Exception as e:
            logger.error(f"VTCM 里程 API 异常: {e.__class__.__name__}")
            return {'total_km': 0, 'daily_km': 0, 'avatar_url': '', 'debug_error': f'VTCM 里程 API 异常: {e.__class__.__name__}'}



    async def _get_online_status(self, tmp_id: str) -> Dict:
        """使用 TruckyApp V3 地图实时接口查询状态。"""
        if not self.session: 
            return {'online': False, 'debug_error': 'HTTP会话不可用。'}

        trucky_url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
        logger.info(f"尝试 Trucky V3 API (地图实时状态): {trucky_url}")
        
        try:
            async with self.session.get(trucky_url, timeout=5) as response:
                
                status = response.status
                raw_data = await response.json()
                
                if status == 200:
                    online_data = raw_data.get('response') if 'response' in raw_data else raw_data
                    
                    is_online = bool(
                        online_data and 
                        online_data.get('online') is True and 
                        online_data.get('server') 
                    )
                    
                    if is_online:
                        server_details = online_data.get('serverDetails', {})
                        server_name = server_details.get('name', f"未知服务器 ({online_data.get('server')})")
                        
                        location_data = online_data.get('location', {})
                        country = location_data.get('poi', {}).get('country')
                        real_name = location_data.get('poi', {}).get('realName')

                        if not country:
                            country = location_data.get('country')
                        if not real_name:
                            real_name = location_data.get('realName')

                        country_cn, city_cn = await self._translate_country_city(country, real_name)

                        formatted_location = '未知位置'
                        if country_cn and city_cn:
                            formatted_location = f"{country_cn} {city_cn}"
                        elif city_cn:
                            formatted_location = city_cn
                        elif country_cn:
                            formatted_location = country_cn
                        
                        return {
                            'online': True,
                            'serverName': server_name,
                            'game': 1 if server_details.get('game') == 'ETS2' else 2 if server_details.get('game') == 'ATS' else 0,
                            'city': {'name': formatted_location}, 
                            'serverId': online_data.get('server'),
                            'serverDetailsId': server_details.get('id') or server_details.get('_id'),
                            'apiServerId': server_details.get('apiserverid') or server_details.get('apiServerId'),
                            'serverCode': server_details.get('code') or server_details.get('shortname'),
                            'x': online_data.get('x'),
                            'y': online_data.get('y'),
                            'country': country_cn,
                            'realName': city_cn,
                            'debug_error': 'Trucky V3 判断在线，并获取到实时数据。',
                            'raw_data': '' 
                        }
                    
                    return {
                        'online': False,
                        'debug_error': 'Trucky V3 API 响应判断为离线。',
                        'raw_data': '' 
                    }
                
                else:
                    return {
                        'online': False, 
                        'debug_error': f"Trucky V3 API 返回非 200 状态码: {status}",
                        'raw_data': '' 
                    }

        except Exception as e:
            logger.error(f"Trucky V3 API 解析失败: {e.__class__.__name__}", exc_info=True)
            return {'online': False, 'debug_error': f'Trucky V3 API 发生意外错误: {e.__class__.__name__}。'}

    def _get_fullmap_player(self, tmp_id: str) -> Optional[Dict[str, Any]]:
        data = self._fullmap_cache or {}
        payload = None
        if isinstance(data, dict):
            payload = data.get('Data') or data.get('data') or data.get('players')
        if not isinstance(payload, list):
            return None
        tid = str(tmp_id)
        for p in payload:
            if not isinstance(p, dict):
                continue
            mp_id = p.get('MpId') or p.get('mp_id') or p.get('tmpId') or p.get('tmp_id')
            if mp_id is None:
                continue
            if str(mp_id) == tid:
                return p
        return None
    
    async def _get_rank_list(self, ranking_type: str = "total", limit: int = 10) -> Optional[List[Dict]]:
        """获取 TruckersMP 里程排行榜列表 (使用 da.vtcm.link API)。

        ranking_type:
            - "total": 总里程排行
            - "today": 今日里程排行
        """
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        # 第三方接口使用数字枚举：1=总里程，2=今日里程
        type_code = 2 if str(ranking_type).lower() in ["today", "daily", "2"] else 1
        url = f"https://da.vtcm.link/statistics/mileageRankingList?rankingType={type_code}&rankingCount={limit}"
        logger.info(f"尝试 API (排行榜): type={ranking_type}({type_code}), url={url}")

        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('data', [])

                    if isinstance(response_data, list):
                        return response_data
                    else:
                        raise ApiResponseException("排行榜 API 数据结构异常")

                elif response.status == 404:
                    return []
                else:
                    raise ApiResponseException(f"排行榜 API 返回错误状态码: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"排行榜 API 网络请求失败 (aiohttp.ClientError): {e}")
            raise NetworkException("排行榜 API 网络请求失败")
        except asyncio.TimeoutError:
            logger.error("请求排行榜 API 超时")
            raise NetworkException("请求排行榜 API 超时")
        except Exception as e:
            logger.error(f"查询排行榜时发生未知错误: {e}", exc_info=True)
            raise NetworkException("查询排行榜失败")

    async def _get_dlc_market_list(self, dlc_type: int = 1) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        url = f"https://da.vtcm.link/dlc/list?type={dlc_type}"
        logger.info(f"DLC列表: 请求 URL={url}")
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                logger.info(f"DLC列表: 响应 status={resp.status}, content-type={resp.headers.get('Content-Type')}")
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('data') or []
                    logger.info(f"DLC列表: 解析到 items_count={len(items) if isinstance(items, list) else 0}")
                    return items if isinstance(items, list) else []
                else:
                    raise ApiResponseException(f"DLC列表 API 返回错误状态码: {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"DLC列表 API 网络请求失败 (aiohttp.ClientError): {e}")
            raise NetworkException("DLC列表 API 网络请求失败")
        except asyncio.TimeoutError:
            logger.error("请求 DLC列表 API 超时")
            raise NetworkException("请求 DLC列表 API 超时")
        except Exception as e:
            logger.error(f"查询 DLC列表 时发生未知错误: {e}", exc_info=True)
            raise NetworkException("查询 DLC列表 失败")

    async def _get_traffic_top(self, server_key: str) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        key = (server_key or "").strip().lower()
        alias = {
            "s1": "sim1",
            "s2": "sim2",
            "p": "eupromods1",
            "a": "arc1",
        }
        server = alias.get(key, key)
        if not server:
            raise ApiResponseException("无效的服务器标识")
        url = f"https://api.truckyapp.com/v2/traffic/top?game=ets2&server={server}"
        logger.info(f"路况: 请求 URL={url}")
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                status = resp.status
                if status == 200:
                    data = await resp.json()
                    items = data.get('response') if isinstance(data, dict) else data
                    if isinstance(items, list):
                        return items
                    raise ApiResponseException("路况 API 数据结构异常")
                if status == 404:
                    return []
                raise ApiResponseException(f"路况 API 返回错误状态码: {status}")
        except aiohttp.ClientError as e:
            logger.error(f"路况 API 网络请求失败 (aiohttp.ClientError): {e}")
            raise NetworkException("路况 API 网络请求失败")
        except asyncio.TimeoutError:
            logger.error("请求 路况 API 超时")
            raise NetworkException("请求 路况 API 超时")
        except Exception as e:
            logger.error(f"查询路况时发生未知错误: {e}", exc_info=True)
            raise NetworkException("查询路况失败")

    async def _resolve_server_ids(self, server_key: str) -> List[str]:
        if not self.session:
            return []
        key = str(server_key or "").strip().lower()
        if not key:
            return []
        if key.isdigit():
            return [key]
        patterns = []
        if key in ["sim1", "simulation1", "simulation_1"]:
            patterns = ["simulation 1", "sim 1", "sim1"]
        elif key in ["sim2", "simulation2", "simulation_2"]:
            patterns = ["simulation 2", "sim 2", "sim2"]
        elif key in ["arc1", "arc", "arcade"]:
            patterns = ["arcade", "arc 1", "arc1"]
        elif key in ["eupromods1", "promods", "promods1"]:
            patterns = ["promods", "pro mods"]
        else:
            patterns = [key]
        url = "https://api.truckersmp.com/v2/servers"
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        servers = data.get('response') if isinstance(data, dict) else None
        if not isinstance(servers, list):
            return []
        ids = []
        for s in servers:
            if not isinstance(s, dict):
                continue
            name = str(s.get('name') or "").lower()
            sid = s.get('id') or s.get('serverId') or s.get('server_id')
            if not sid:
                continue
            for p in patterns:
                if p and p in name:
                    ids.append(str(sid))
                    break
        seen = set()
        uniq = []
        for sid in ids:
            if sid in seen:
                continue
            seen.add(sid)
            uniq.append(sid)
        return uniq

    async def _get_footprint_history(self, tmp_id: str, server_id: Optional[str], start_time: str, end_time: str) -> List[Dict[str, Any]]:
        if not self.session:
            return []
        base = self._cfg_str('footprint_api_base', '').strip() or "https://da.vtcm.link"
        base = base[:-1] if base.endswith('/') else base
        sid = str(server_id or "").strip()
        params = {
            'tmpId': str(tmp_id).strip(),
            'startTime': str(start_time).strip(),
            'endTime': str(end_time).strip()
        }
        if sid:
            params['serverId'] = sid
        url = f"{base}/map/playerHistory"
        try:
            async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        code = data.get('code')
        if code is not None and int(code) != 200:
            return []
        payload = data.get('data') or data.get('response') or data.get('result')
        if not isinstance(payload, list):
            return []
        return payload

    def _normalize_history_points(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            x = it.get('axisX') or it.get('x') or it.get('posX') or it.get('pos_x')
            y = it.get('axisY') or it.get('y') or it.get('posY') or it.get('pos_y')
            if x is None or y is None:
                continue
            try:
                axis_x = float(x)
                axis_y = float(y)
            except Exception:
                continue
            server_id = it.get('serverId') or it.get('server_id') or it.get('server') or 0
            heading = it.get('heading') or 0
            ts_val = None
            update_time = it.get('updateTime') or it.get('time') or it.get('updatedAt') or it.get('update_time')
            if update_time:
                s = str(update_time).strip()
                try:
                    dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
                    ts_val = int(dt.timestamp())
                except Exception:
                    try:
                        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                        ts_val = int(dt.timestamp())
                    except Exception:
                        ts_val = None
            server_id_val = 0
            try:
                server_id_val = int(server_id)
            except Exception:
                server_id_val = 0
            points.append({
                'axisX': axis_x,
                'axisY': axis_y,
                'serverId': server_id_val,
                'heading': heading,
                'ts': ts_val or 0
            })
        return points

    async def _get_footprint_data(self, server_key: str, tmp_id: str, server_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        base = self._cfg_str('footprint_api_base', '').strip() or "https://da.vtcm.link"
        base = base[:-1] if base.endswith('/') else base
        urls = []
        server_ids = server_ids or []
        server_ids = [str(s).strip() for s in server_ids if str(s).strip()]
        urls.append(f"{base}/footprint/today?tmpId={tmp_id}&server={server_key}")
        urls.append(f"{base}/footprint/today?tmpId={tmp_id}&serverId={server_key}")
        urls.append(f"{base}/footprint/list?tmpId={tmp_id}&server={server_key}")
        urls.append(f"{base}/map/footprint?tmpId={tmp_id}&server={server_key}")
        urls.append(f"{base}/map/track?tmpId={tmp_id}&server={server_key}")
        for sid in server_ids:
            urls.append(f"{base}/footprint/today?tmpId={tmp_id}&serverId={sid}")
            urls.append(f"{base}/footprint/list?tmpId={tmp_id}&serverId={sid}")
            urls.append(f"{base}/map/footprint?tmpId={tmp_id}&serverId={sid}")
            urls.append(f"{base}/map/track?tmpId={tmp_id}&serverId={sid}")
        last_error = None
        for url in urls:
            try:
                async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict):
                            code = data.get('code')
                            if code is not None and int(code) != 200:
                                continue
                            success = data.get('success')
                            if success is not None and success is False:
                                continue
                        points, _ = self._extract_footprint_points(data, server_key, server_ids)
                        if not points:
                            continue
                        return { 'url': url, 'data': data }
                    if resp.status in (404, 204):
                        continue
            except Exception as e:
                last_error = e
        if last_error:
            raise NetworkException(f"足迹接口请求失败: {last_error}")
        raise ApiResponseException("足迹接口无可用数据")

    def _extract_footprint_points(self, payload: Any, server_key: str, server_ids: Optional[List[str]] = None) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
        ids = [str(s).lower() for s in (server_ids or []) if str(s).strip()]
        key = str(server_key or "").strip().lower()

        def _point_from_item(item: Any) -> Optional[Dict[str, float]]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                x, y = item[0], item[1]
            elif isinstance(item, dict):
                x = item.get('axisX') or item.get('x') or item.get('posX') or item.get('pos_x')
                y = item.get('axisY') or item.get('y') or item.get('posY') or item.get('pos_y')
            else:
                return None
            if x is None or y is None:
                return None
            try:
                return { 'x': float(x), 'y': float(y) }
            except Exception:
                return None

        def _collect_points_from_list(items: List[Any]) -> List[Dict[str, float]]:
            pts: List[Dict[str, float]] = []
            for it in items:
                p = _point_from_item(it)
                if p:
                    pts.append(p)
            return pts

        def _match_server(item: Dict[str, Any]) -> bool:
            sid = str(item.get('serverId') or item.get('server_id') or item.get('server') or '').strip().lower()
            if not sid:
                return False
            if sid == key:
                return True
            return sid in ids

        def _find_points(obj: Any, depth: int = 0) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
            if depth > 5:
                return [], {}
            if isinstance(obj, list):
                pts = _collect_points_from_list(obj)
                if pts:
                    return pts, {}
                for it in obj:
                    if isinstance(it, dict) and _match_server(it):
                        pts2, meta2 = _find_points(it, depth + 1)
                        if pts2:
                            return pts2, meta2 or it
                for it in obj:
                    pts2, meta2 = _find_points(it, depth + 1)
                    if pts2:
                        return pts2, meta2
                return [], {}
            if isinstance(obj, dict):
                for k in ['points', 'track', 'tracks', 'list', 'route', 'path', 'data', 'response', 'result', 'items']:
                    if k in obj:
                        pts2, meta2 = _find_points(obj.get(k), depth + 1)
                        if pts2:
                            return pts2, meta2 or obj
                for v in obj.values():
                    pts2, meta2 = _find_points(v, depth + 1)
                    if pts2:
                        return pts2, meta2
            return [], {}

        points, meta = _find_points(payload, 0)
        return points, meta

    async def _render_text_to_image(self, text: str) -> Optional[Any]:
        if not self.session:
            return None
        # 读取 AstrBot 系统配置 data/cmd_config.json 的 t2i_endpoint/t2i_strategy
        url = None
        try:
            root = os.getcwd()
            cfg = os.path.join(root, 'data', 'cmd_config.json')
            if os.path.exists(cfg):
                with open(cfg, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                strategy = str(j.get('t2i_strategy') or '').strip()
                endpoint = str(j.get('t2i_endpoint') or '').strip()
                if strategy == 'remote' and endpoint:
                    e = endpoint[:-1] if endpoint.endswith('/') else endpoint
                    url = e + "/text2img/generate"
                    logger.info(f"T2I: 使用系统配置 t2i_endpoint -> {url}")
        except Exception as e:
            logger.error(f"T2I: 读取系统配置失败: {e}")
        if not url:
            # 环境变量兜底
            endpoint = str(os.environ.get('ASTRBOT_T2I_ENDPOINT') or '').strip()
            if endpoint:
                e = endpoint[:-1] if endpoint.endswith('/') else endpoint
                url = e + "/text2img/generate"
                logger.info(f"T2I: 使用环境变量 -> {url}")
        if not url:
            logger.info("T2I: 未找到远程服务地址，跳过图片渲染")
            return None
        payload = {
            'text': text
        }
        try:
            async with self.session.post(url, json=payload, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                logger.info(f"T2I: POST {url} body_len={len(text)} status={resp.status} ct={resp.headers.get('Content-Type')}")
                ct = resp.headers.get('Content-Type', '')
                if 'application/json' in ct:
                    try:
                        data = await resp.json()
                    except Exception as je:
                        logger.error(f"T2I: JSON解析失败: {je}")
                        return None
                    img_b64 = (
                        data.get('image')
                        or (data.get('data') or {}).get('image')
                    )
                    img_url = (
                        data.get('url')
                        or (data.get('output')[0] if isinstance(data.get('output'), list) and data.get('output') else None)
                    )
                    if img_b64:
                        try:
                            import base64 as _b64
                            return _b64.b64decode(img_b64)
                        except Exception:
                            logger.error("T2I: Base64解码失败")
                            return None
                    if img_url:
                        return str(img_url)
                    return None
                else:
                    content = await resp.read()
                    if content:
                        return content
                    return None
        except Exception as e:
            logger.error(f"文本转图片渲染失败: {e}", exc_info=True)
            return None

    async def _get_vtc_member_role(self, tmp_id: str, vtc_info: Optional[Dict] = None) -> Optional[str]:
        """使用 da.vtcm.link 的 vtc/memberAll/role 接口查询玩家在车队内的角色。
        优先策略：
        1) 若传入 vtc_info 且包含 vtcId，则直接用 vtcId 查询成员列表并匹配 tmpId。
        2) 若未传入或未包含 vtcId，则尝试从 TruckersMP player 接口获取 vtc.id。
        3) 若仍无 vtcId，尝试直接用 memberAll/role?tmpId=tmp_id 回退查询（部分接口支持）。
        4) 若有 vtc 名称但无 vtcId，先通过 /vtc/search?name= 搜索取得 vtcId，再查询成员列表。
        返回值：匹配到的角色字符串或 None。
        """
        if not self.session:
            return None

        # Helper: 解析成员列表并匹配 tmp_id，返回 role 或 None
        def _find_role_in_members(members) -> Optional[str]:
            if not isinstance(members, list):
                return None
            for m in members:
                member_tmp = m.get('tmpId') or m.get('tmp_id') or m.get('tmpIdStr') or m.get('tmpid') or m.get('tmpID')
                if member_tmp and str(member_tmp) == str(tmp_id):
                    role = m.get('role') or m.get('roleName') or m.get('position') or m.get('name') or m.get('post')
                    if role:
                        return str(role)
            return None

        # 1) 尝试从传入的 vtc_info 获取 vtc_id
        vtc_id = None
        vtc_name = None
        if isinstance(vtc_info, dict):
            vtc_id = vtc_info.get('id') or vtc_info.get('vtcId') or vtc_info.get('vtc_id') or vtc_info.get('VTCId')
            vtc_name = vtc_info.get('name') or vtc_info.get('vtcName')

        # 2) 若仍无 vtc_id，尝试从 TruckersMP player 接口补充（如果调用方没有提前获取）
        if not vtc_id:
            try:
                player_info = await self._get_player_info(tmp_id)
                vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
                vtc_id = vtc.get('id') or vtc.get('vtcId') or vtc.get('vtc_id') or vtc.get('VTCId')
                if not vtc_name:
                    vtc_name = vtc.get('name') or vtc.get('vtcName')
            except Exception:
                # 忽略 player_info 获取失败，继续后续回退策略
                pass

        # 3) 如果有 vtc_id，直接用 vtcId 查询成员角色列表
        if vtc_id:
            try:
                url_vid = f"https://da.vtcm.link/vtc/memberAll/role?vtcId={vtc_id}"
                logger.info(f"VTC 角色查询: 使用 vtcId 查询 {url_vid}")
                async with self.session.get(url_vid, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('data') or data.get('response') or []
                        role = _find_role_in_members(members)
                        if role:
                            logger.info(f"VTC 角色: 通过 vtcId={vtc_id} 找到角色 {role}")
                            return role
                    else:
                        logger.info(f"VTC 角色查询(vtcId) 返回状态: {resp.status}")
            except Exception as e:
                logger.info(f"VTC 角色查询(vtcId) 异常: {e}")

        # 4) 回退：部分接口支持用 tmpId 直接查询
        try:
            url_tmp = f"https://da.vtcm.link/vtc/memberAll/role?tmpId={tmp_id}"
            logger.info(f"VTC 角色查询: 回退尝试 tmpId 查询 {url_tmp}")
            async with self.session.get(url_tmp, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    members = data.get('data') or data.get('response') or []
                    role = _find_role_in_members(members)
                    if role:
                        logger.info(f"VTC 角色: 通过 tmpId 回退查询到角色 {role}")
                        return role
                else:
                    logger.info(f"VTC 角色查询(tmpId) 返回状态: {resp.status}")
        except Exception as e:
            logger.info(f"VTC 角色查询(tmpId) 异常: {e}")

        # 5) 若没有 vtc_id 但有 vtc_name，则先搜索 vtcId 再查询
        if not vtc_id and vtc_name:
            try:
                from urllib.parse import quote_plus
                qname = quote_plus(str(vtc_name))
                search_url = f"https://da.vtcm.link/vtc/search?name={qname}"
                logger.info(f"VTC 车队搜索: {search_url}")
                async with self.session.get(search_url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get('data') or data.get('response') or []
                        if isinstance(items, list) and items:
                            # 取第一个匹配项的 id
                            it = items[0]
                            found_id = it.get('id') or it.get('vtcId') or it.get('vtc_id')
                            if found_id:
                                vtc_id = found_id
                                logger.info(f"VTC 搜索结果: name={vtc_name} -> vtcId={vtc_id}")
            except Exception as e:
                logger.info(f"VTC 车队搜索异常: {e}")

            # 如果通过搜索得到 vtc_id，再次用 vtcId 查询成员
            if vtc_id:
                try:
                    url_vid2 = f"https://da.vtcm.link/vtc/memberAll/role?vtcId={vtc_id}"
                    logger.info(f"VTC 角色查询: 通过搜索得到 vtcId 后查询 {url_vid2}")
                    async with self.session.get(url_vid2, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            members = data.get('data') or data.get('response') or []
                            role = _find_role_in_members(members)
                            if role:
                                logger.info(f"VTC 角色: 通过 vtcId={vtc_id}（搜索后）找到角色 {role}")
                                return role
                        else:
                            logger.info(f"VTC 角色查询(搜索后 vtcId) 返回状态: {resp.status}")
                except Exception as e:
                    logger.info(f"VTC 角色查询(搜索后 vtcId) 异常: {e}")

        # 6) 最后回退：尝试用 vtcName 参数直接查询 memberAll/role（部分实现支持）
        if vtc_name:
            try:
                from urllib.parse import quote_plus
                qname = quote_plus(str(vtc_name))
                url_name = f"https://da.vtcm.link/vtc/memberAll/role?vtcName={qname}"
                logger.info(f"VTC 最后回退: 通过 vtcName 查询 {url_name}")
                async with self.session.get(url_name, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('data') or data.get('response') or []
                        role = _find_role_in_members(members)
                        if role:
                            logger.info(f"VTC 角色: 通过 vtcName 找到角色 {role}")
                            return role
                    else:
                        logger.info(f"VTC 角色查询(vtcName) 返回状态: {resp.status}")
            except Exception as e:
                logger.info(f"VTC 角色查询(vtcName) 异常: {e}")

        logger.info(f"VTC 角色: 未能找到玩家 {tmp_id} 的车队角色信息")
        return None

    # --- 【核心逻辑】封禁信息处理 ---
    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[int, List[Dict]]:
        """只返回历史封禁次数和最新的封禁记录（按时间倒序）"""
        if not bans_info or not isinstance(bans_info, list):
            return 0, []
        
        sorted_bans = sorted(bans_info, key=lambda x: x.get('timeAdded', ''), reverse=True)
        return len(bans_info), sorted_bans

    def _translate_ban_reason(self, reason: Optional[str]) -> str:
        """将封禁原因中的所有片段（§X.X - 英文）翻译为中文，保留后续说明/链接。

        支持多段原因，例如：
        输入："§2.2 - Collisions, §2.5 - Reckless Driving - https://youtu.be/xxx // 30 days due to history (§2.8)"
        输出："§2.2 - 碰撞, §2.5 - 鲁莽驾驶 - https://youtu.be/xxx // 30天（§2.8历史）"（保留原样的链接与说明）
        """
        if not reason or not isinstance(reason, str):
            return reason or ""

        zh_map = {
            "1.1": "账号、设备与游戏设置责任",
            "1.2": "逃避封禁",
            "1.3": "个人信息与隐私",
            "1.4": "不当内容与交流",
            "1.5": "语言、头像和昵称违规",
            "1.6": "冒充官方或其他玩家",
            "1.7": "刷屏/滥用系统",
            "2.1": "黑客/漏洞/功能滥用",
            "2.2": "碰撞",
            "2.3": "堵塞",
            "2.4": "错误驾驶方式/不当超车",
            "2.5": "鲁莽驾驶",
            "2.6": "骚扰、侮辱或不当行为",
            "2.7": "特色区域和事件服务器规则",
            "2.8": "历史原因",
            "2.9": "保存修改",
            "3.1": "违规保存编辑",
            "3.2": "不兼容或缺失组件",        }
        keyword_map = {
            "collisions": "碰撞",
            "reckless driving": "鲁莽驾驶",
            "blocking": "堵塞",
            "trolling": "恶意捣乱",
            "inappropriate overtaking": "不当超车",
            "wrong way": "逆行",
            "ramming": "蓄意撞车",
            "chat abuse": "聊天滥用",
            "insulting": "辱骂他人",
        }

        matches = list(re.finditer(r"§\s*(?P<code>\d+\.\d+)\s*-\s*(?P<title>[^,\-]+)", reason))
        if matches:
            parts = []
            for m in matches:
                code = m.group("code").strip()
                title = m.group("title").strip()
                zh_title = zh_map.get(code)
                if zh_title:
                    parts.append(f"§{code} - {zh_title}")
                else:
                    parts.append(f"§{code} - {title}")
            remainder = reason[matches[-1].end():]
            result = ", ".join(parts) + remainder
        else:
            result = reason

        for en, zh in keyword_map.items():
            pattern = r"\b" + re.escape(en) + r"\b"
            result = re.sub(pattern, zh, result, flags=re.IGNORECASE)

        return result


    # ******************************************************
    # 命令处理与消息监听 
    # ******************************************************

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _on_any_message_dispatch(self, event: AstrMessageEvent, *args, **kwargs):
        target_event = event
        if not hasattr(target_event, "message_str"):
            if args:
                candidate = args[0]
                if hasattr(candidate, "message_str") or hasattr(candidate, "message_obj"):
                    target_event = candidate
            if target_event is event:
                kw_event = kwargs.get("event")
                if hasattr(kw_event, "message_str") or hasattr(kw_event, "message_obj"):
                    target_event = kw_event

        msg = (getattr(target_event, "message_str", "") or "").strip()
        if not msg:
            return

        message_obj = getattr(target_event, "message_obj", None)
        has_at = False
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        has_at = True
                        break
                    uid = (
                        getattr(seg, "qq", None)
                        or getattr(seg, "user_id", None)
                        or getattr(seg, "id", None)
                    )
                    if isinstance(seg, dict):
                        uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                    if uid is not None:
                        has_at = True
                        break
            except Exception:
                has_at = False

        if re.match(r'^(查询|查)(\s*\d+)?\s*$', msg) or (re.match(r'^(查询|查)(\s|$)', msg) and has_at):
            async for r in self.tmpquery(event):
                yield r
            return
        if msg == "地图dlc" or msg == "地图DLC":
            async for r in self.tmpdlc_list(event):
                yield r
            return
        if re.match(r'^绑定\s*\d+\s*$', msg):
            async for r in self.tmpbind(event):
                yield r
            return
        if re.match(r'^解绑\s*$', msg):
            async for r in self.tmpunbind(event):
                yield r
            return
        if re.match(r'^定位(\s*\d+)?\s*$', msg) or (msg.startswith("定位") and has_at):
            async for r in self.tmplocate(event):
                yield r
            return
        if re.match(r'^总里程排行\s*$', msg):
            async for r in self.tmprank_total(event):
                yield r
            return
        if re.match(r'^今日里程排行\s*$', msg):
            async for r in self.tmprank_today(event):
                yield r
            return
        if re.match(r'^足迹(\s+\S+)?(\s+\d+)?\s*$', msg) or (msg.startswith("足迹") and has_at):
            async for r in self.tmptoday_footprint(event):
                yield r
            return
        if re.match(r'^服务器\s*$', msg):
            async for r in self.tmpserver(event):
                yield r
            return
        if re.match(r'^路况(\s+\S+)?\s*$', msg):
            async for r in self.tmptraffic(event):
                yield r
            return
        if re.match(r'^插件版本\s*$', msg):
            async for r in self.tmpversion(event):
                yield r
            return
        if re.match(r'^菜单\s*$', msg):
            async for r in self.tmphelp(event):
                yield r
            return

    
    
    # 额外 AstrBot 正式指令包装（用于行为统计，保留无前缀用法）

    @filter.command("查询")
    async def cmd_tmp_query(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询玩家详细信息，支持绑定ID与@他人。"""
        orig = getattr(event, "message_str", "") or ""
        try:
            if tmp_id:
                event.message_str = f"查询 {tmp_id}"
            else:
                event.message_str = "查询"
            async for r in self.tmpquery(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("查")
    async def cmd_tmp_query_alias(self, event: AstrMessageEvent, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if tmp_id:
                event.message_str = f"查询 {tmp_id}"
            else:
                event.message_str = "查询"
            async for r in self.tmpquery(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("定位")
    async def cmd_tmp_locate(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询并渲染玩家当前位置（底图+自动翻译位置）。"""
        orig = getattr(event, "message_str", "") or ""
        try:
            if tmp_id:
                event.message_str = f"定位 {tmp_id}"
            else:
                event.message_str = "定位"
            async for r in self.tmplocate(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("路况")
    async def cmd_tmp_traffic(self, event: AstrMessageEvent, server: str | None = None):
        """查询指定服务器热门路段的实时路况信息。"""
        orig = getattr(event, "message_str", "") or ""
        try:
            if server:
                event.message_str = f"路况 {server}"
            else:
                event.message_str = "路况"
            async for r in self.tmptraffic(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("总里程排行")
    async def cmd_tmp_rank_total(self, event: AstrMessageEvent):
        """查看玩家总里程排行榜前若干名。"""
        async for r in self.tmprank_total(event):
            yield r

    @filter.command("今日里程排行")
    async def cmd_tmp_rank_today(self, event: AstrMessageEvent):
        """查看今日里程排行榜前若干名。"""
        async for r in self.tmprank_today(event):
            yield r

    @filter.command("足迹")
    async def cmd_tmp_today_footprint(self, event: AstrMessageEvent, server: str | None = None, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if server and tmp_id:
                event.message_str = f"足迹 {server} {tmp_id}"
            elif server:
                event.message_str = f"足迹 {server}"
            elif tmp_id:
                event.message_str = f"足迹 {tmp_id}"
            else:
                event.message_str = "足迹"
            async for r in self.tmptoday_footprint(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("服务器")
    async def cmd_tmp_server(self, event: AstrMessageEvent):
        """查看欧卡/美卡官方服务器的实时状态列表。"""
        async for r in self.tmpserver(event):
            yield r

    @filter.command("插件版本")
    async def cmd_tmp_plugin_version(self, event: AstrMessageEvent):
        """查询当前TMP插件版本信息。"""
        async for r in self.tmpversion(event):
            yield r

    @filter.command("菜单")
    async def cmd_tmp_help(self, event: AstrMessageEvent):
        """显示本插件支持的指令与用法。"""
        async for r in self.tmphelp(event):
            yield r


    # 具体功能实现

    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] 玩家完整信息查询。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()

        target_user_id = None
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        uid = (
                            getattr(seg, "qq", None)
                            or getattr(seg, "user_id", None)
                            or getattr(seg, "id", None)
                        )
                        if isinstance(seg, dict):
                            uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                        if uid:
                            target_user_id = str(uid)
                            break
                    uid2 = getattr(seg, "qq", None)
                    if isinstance(seg, dict):
                        uid2 = seg.get("qq") or uid2
                    if uid2:
                        target_user_id = str(uid2)
                        break
            except Exception:
                target_user_id = None

        match = re.search(r'查询\s*(\d+)', message_str) 
        input_id = match.group(1) if match else None
        
        tmp_id = None
        
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    yield event.plain_result(f"查询失败: {str(e)}")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return
        
        try:
            # 并行查询：仅使用 V2 和相关接口（移除已失效的 V1）
            player_info_raw, bans_info, online_status, stats_info = await asyncio.gather(
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id),
                self._get_online_status(tmp_id),
                self._get_player_stats(tmp_id)
            )
            player_info = player_info_raw
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
            
        steam_id_to_display = self._get_steam_id_from_player_info(player_info)
        is_banned = player_info.get('banned', False) 
        banned_until_main = player_info.get('bannedUntil', '永久/未知') 
        
        ban_count, sorted_bans = self._format_ban_info(bans_info)
        bans_count_raw = player_info.get('bansCount')
        if bans_count_raw is not None:
            try:
                ban_count = int(str(bans_count_raw).strip())
            except Exception:
                pass
        
        last_online_raw = (
            player_info.get('lastOnline')
            or stats_info.get('last_online')
            or stats_info.get('lastOnline')
            or stats_info.get('lastLogin')
            or stats_info.get('last_login')
            or None
        )
        if last_online_raw and last_online_raw != player_info.get('lastOnline'):
            logger.info(f"查询详情: 使用 VTCM 提供的上次在线字段，值={last_online_raw}")
        # 将“上次在线”统一显示为北京时间 (UTC+8)
        last_online_formatted = _format_timestamp_to_readable(last_online_raw)
        
        # 完整的回复消息正文构建
        body = ""
        body += f"🆔 TMP ID: {tmp_id}\n"
        if steam_id_to_display:
            body += f"🆔 Steam ID: {steam_id_to_display}\n"
        body += f"😀玩家名称: {player_info.get('name', '未知')}\n"
        # 📑注册日期：优先使用 joinDate，其次 fallback 到 created_at/registrationDate
        join_date_raw = (
            player_info.get('joinDate')
            or player_info.get('created_at')
            or player_info.get('registrationDate')
            or None
        )
        join_date_formatted = _format_timestamp_to_beijing(join_date_raw) if join_date_raw else '未知'
        body += f"📑注册日期: {join_date_formatted}\n"

        # 权限/分组信息
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f'is{g.replace(" ", "")}')]
                if groups:
                    perms_str = ', '.join(_translate_user_groups(groups))
            elif isinstance(perms, list) and perms:
                perms_str = ', '.join(_translate_user_groups(perms))
        body += f"💼所属分组: {perms_str}\n"

        # 车队信息：优先使用 player_info.vtc（若为字典），若缺少 role 则调用 VTCM API 获取
        vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
        vtc_name = vtc.get('name')
        vtc_role = vtc.get('role') or vtc.get('position') or stats_info.get('vtcRole')
        if vtc_name:
            body += f"🚚所属车队: {vtc_name}\n"
        if not vtc_role and vtc_name:
            try:
                vtc_role_remote = await self._get_vtc_member_role(tmp_id, vtc)
                if vtc_role_remote:
                    vtc_role = vtc_role_remote
                    logger.info(f"查询详情: 从 VTC API 获取到车队角色: {vtc_role}")
            except Exception as e:
                logger.info(f"查询详情: 获取 VTC 车队角色时发生异常: {e}", exc_info=False)
        if vtc_role:
            body += f"🚚车队职位: {vtc_role}\n"
        
        # --- 【核心逻辑】赞助信息 (基于 V2 player 接口字段) ---
        # 规则：
        # - isPatron: 是否赞助过（true 为赞助过，false 为未赞助过）
        # - 仅当 isPatron 为 true 时，才读取 active/currentPledge/lifetimePledge；否则 active=否，金额均为 0
        # - active: 当前赞助是否有效
        # - currentPledge: 当前赞助金额（需除以 100）；为 0 则视为“当前未赞助”
        # - lifetimePledge: 历史赞助金额（需除以 100）
        # 兼容字段位置：尝试从顶层、patron、donation 三处获取，避免结构差异导致解析失败。
        def _get_nested(d: Dict, *keys):
            cur = d
            for k in keys:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        # 兼容 isPatron / isPatreon，兼容容器 patreon / patron
        is_patron = any([
            bool(player_info.get('isPatron')),
            bool(player_info.get('isPatreon')),
            bool(_get_nested(player_info, 'patreon', 'isPatron')),
            bool(_get_nested(player_info, 'patreon', 'isPatreon')),
            bool(_get_nested(player_info, 'patron', 'isPatron')),
            bool(_get_nested(player_info, 'patron', 'isPatreon')),
        ])

        # 兼容 active 位于顶层 / patreon / patron / donation
        active = any([
            bool(player_info.get('active')),
            bool(_get_nested(player_info, 'patreon', 'active')),
            bool(_get_nested(player_info, 'patron', 'active')),
            bool(_get_nested(player_info, 'donation', 'active')),
        ]) if is_patron else False

        def _to_int(val, default=0):
            try:
                if val is None:
                    return default
                if isinstance(val, (int,)):
                    return val
                if isinstance(val, float):
                    return int(val)
                s = str(val).strip()
                if s == "":
                    return default
                return int(float(s))
            except Exception:
                return default

        # 优先 patreon 容器，其次顶层，再次 patron/donation 容器
        current_pledge_raw = (
            _get_nested(player_info, 'patreon', 'currentPledge') or 
            player_info.get('currentPledge') or 
            _get_nested(player_info, 'patron', 'currentPledge') or 
            _get_nested(player_info, 'donation', 'currentPledge') or 0
        )
        lifetime_pledge_raw = (
            _get_nested(player_info, 'patreon', 'lifetimePledge') or 
            player_info.get('lifetimePledge') or 
            _get_nested(player_info, 'patron', 'lifetimePledge') or 
            _get_nested(player_info, 'donation', 'lifetimePledge') or 0
        )

        # 以“美元”为单位展示，去除小数（整美元）。API金额为分，使用整除 100。
        current_pledge = (_to_int(current_pledge_raw) // 100) if is_patron else 0
        lifetime_pledge = (_to_int(lifetime_pledge_raw) // 100) if is_patron else 0

        if is_patron and lifetime_pledge > 0:
            if current_pledge > 0:
                body += f"🎁当前赞助金额: {current_pledge}美元\n"
            body += f"🎁历史赞助金额: {lifetime_pledge}美元\n"
        # --- 赞助信息结束 ---

        # --- 里程信息输出 (不变) ---
        logger.info(f"查询详情: 里程字典 keys={list(stats_info.keys())}, debug={stats_info.get('debug_error')}")
        total_km = stats_info.get('total_km', 0.0)
        daily_km = stats_info.get('daily_km', 0.0)
        total_rank = stats_info.get('total_rank')
        daily_rank = stats_info.get('daily_rank')
        logger.info(f"查询详情: 里程输出值 total_km={total_km:.2f}, daily_km={daily_km:.2f}, total_rank={total_rank}, daily_rank={daily_rank}")

        try:
            total_val = float(total_km)
        except Exception:
            total_val = 0.0
        try:
            daily_val = float(daily_km)
        except Exception:
            daily_val = 0.0

        if total_val > 0:
            body += f"🚩历史里程: {total_val:.2f}公里/km\n"
        if daily_val > 0:
            body += f"🚩今日里程: {daily_val:.2f}公里/km\n"
        
        # --- 封禁信息 (不变) ---
        body += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
        
        body += f"🚫历史封禁: {ban_count}次\n"

        if is_banned:
            
            current_ban = None
            if sorted_bans:
                current_ban = next((ban for ban in sorted_bans if ban.get('active')), None)
                if not current_ban:
                    current_ban = sorted_bans[0]
                    
            if current_ban:
                ban_reason_raw = current_ban.get('reason', '未知封禁原因 (API V2)')
                ban_reason = self._translate_ban_reason(ban_reason_raw)
                ban_expiration = current_ban.get('expiration', banned_until_main) 
                
                body += f"🚫封禁原因: {ban_reason}\n"
                
                if ban_expiration and isinstance(ban_expiration, str) and ban_expiration.lower().startswith('never'):
                    body += f"🚫封禁截止: 永久封禁\n"
                else:
                    body += f"🚫封禁截止: {_format_timestamp_to_beijing(ban_expiration)}\n"
                    
            else:
                body += f"🚫封禁原因: 隐藏\n"
                if banned_until_main and isinstance(banned_until_main, str) and banned_until_main.lower().startswith('never'):
                    body += f"🚫封禁截止: 永久封禁\n"
                else:
                    body += f"🚫封禁截止: {_format_timestamp_to_beijing(banned_until_main)}\n"
        
    
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            
            raw_city = online_status.get('city', {}).get('name', '未知位置')
            raw_country = online_status.get('country', '')
            
            # 使用更准确的翻译函数
            country_cn, city_cn = await self._translate_country_city(raw_country, raw_city)
            
            location_display = city_cn
            if country_cn and country_cn != city_cn:
                 location_display = f"{country_cn} {city_cn}"
            elif not location_display:
                 location_display = raw_city

            body += f"📶在线状态: 在线\n"
            body += f"📶所在服务器: {server_name}\n"
            body += f"📶所在位置: {location_display}\n"
        else:
            body += f"📶在线状态: 离线\n"
            body += f"📶上次在线: {last_online_formatted}\n"
        
        # 头像（强制按组件发送）
        show_avatar_cfg = self._cfg_bool('query_show_avatar_enable', True)
        logger.info(f"查询详情: 头像开关={'ON' if show_avatar_cfg else 'OFF'}，将组合 Image+Plain 统一发送。")
        avatar_url = self._normalize_avatar_url(player_info.get('avatar') or stats_info.get('avatar_url'))
        logger.info(f"查询详情: 规范化后URL={avatar_url}")
        components = []
        # 发送顺序控制：当头像关闭时，将标题与正文合并为一个文本组件以保证换行在同一组件内生效
        if not show_avatar_cfg:
            logger.info("查询详情: 头像开关为OFF，直接发送正文文本组件")
            components.append(Plain(body))
            yield event.chain_result(components)
            return
        else:
            # 头像开启：头像 -> 空行 -> 正文
            if avatar_url:
                try:
                    logger.info("查询详情: 组合消息链添加 Image(URL) 组件")
                    components.append(Image.fromURL(avatar_url))
                except Exception:
                    logger.error("查询详情: 生成 Image(URL) 组件失败，跳过头像", exc_info=True)
            else:
                logger.info("查询详情: 无可用头像URL，跳过头像组件")
            # 确保正文从新的一行开始（适配不同适配器的换行处理）
            components.append(Plain("\r\n"))
            components.append(Plain(body))
            yield event.chain_result(components)
            return

    async def tmpdlc_list(self, event: AstrMessageEvent):
        logger.info("DLC列表: 开始处理命令")
        try:
            items = await self._get_dlc_market_list(1)
        except Exception:
            yield event.plain_result("查询DLC列表失败")
            logger.error("DLC列表: 获取市场列表失败")
            return
        if not items:
            yield event.plain_result("暂无数据")
            logger.info("DLC列表: 无数据")
            return
        lines: List[str] = []
        for it in items:
            name = str(it.get('name') or '').strip()
            final_price = it.get('finalPrice')
            discount = it.get('discount') or 0
            price_str = ""
            try:
                if isinstance(final_price, (int, float)):
                    price_str = f"￥{int(final_price) // 100}"
            except Exception:
                price_str = ""
            if discount and isinstance(discount, (int, float)) and discount > 0:
                lines.append(f"{name} {price_str} (-{int(discount)}%)")
            else:
                lines.append(f"{name} {price_str}")
        text = "\n".join(lines)
        logger.info(f"DLC列表: 聚合文本长度={len(text)} 行数={len(lines)}")
        if self._cfg_bool('dlc_list_image', False):
            logger.info("DLC列表: 尝试进行图片渲染(html_render)")
            tmpl = """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
</style>
<div style=\"width:100vw;background:#222d33;color:#fff;font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;\">
  <div style=\"font-size:20px;font-weight:600;margin:0;padding:12px 0 8px 0;\">DLC 列表</div>
  {% for it in items %}
  <div style=\"display:flex;flex-direction:row;background:#24313a;margin:0 0 12px 0;padding:12px;\">
    <img src=\"{{ it.headerImageUrl }}\" style=\"width:210px;height:auto;object-fit:cover;\"/>
    <div style=\"flex:1;padding:0 12px;\">
      <div style=\"font-size:18px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;\">{{ it.name }}</div>
      <div style=\"font-size:14px;color:#e5e5e5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-overflow:ellipsis;\">{{ it.desc }}</div>
      <div style=\"margin-top:8px;\">
        <span style=\"display:inline-block;color:#BEEE11;font-size:16px;\">{{ it.price_str }}</span>
        {% if it.discount and it.discount > 0 %}
        <span style=\"display:inline-block;color:#cbcbcb;font-size:16px;text-decoration:line-through;margin-left:6px;\">{{ it.original_price_str }}</span>
        <span style=\"font-size:14px;color:#BEEE11;background:#4c6b22;padding:2px 6px;margin-left:4px;\">-{{ it.discount }}%</span>
        {% endif %}
      </div>
    </div>
  </div>
  {% endfor %}
</div>
"""
            mapped: List[Dict[str, Any]] = []
            for it in items:
                name = str(it.get('name') or '').strip()
                desc = str(it.get('desc') or '').strip()
                header = str(it.get('headerImageUrl') or '').strip()
                original = it.get('originalPrice')
                finalp = it.get('finalPrice')
                discount = it.get('discount') or 0
                def _p(v):
                    try:
                        return f"￥{int(v) // 100}" if isinstance(v, (int, float)) else ""
                    except Exception:
                        return ""
                mapped.append({
                    'name': name,
                    'desc': desc,
                    'headerImageUrl': header,
                    'price_str': _p(finalp),
                    'original_price_str': _p(original),
                    'discount': int(discount) if isinstance(discount, (int, float)) else 0
                })
            try:
                options = { 'type': 'jpeg', 'quality': 92, 'full_page': True, 'omit_background': False }
                url = await self.html_render(tmpl, { 'items': mapped }, options=options)
                if isinstance(url, str) and url:
                    logger.info(f"DLC列表: html_render 成功 -> {url}")
                    yield event.chain_result([Image.fromURL(url)])
                    return
                logger.error("DLC列表: html_render 返回空，尝试文本渲染")
            except Exception as e:
                logger.error(f"DLC列表: html_render 异常: {e}")
            img = await self._render_text_to_image(text)
            if isinstance(img, (bytes, bytearray)):
                logger.info("DLC列表: 文本渲染成功(字节)")
                yield event.chain_result([Image.fromBytes(img)])
                return
            if isinstance(img, str) and img.startswith('http'):
                logger.info(f"DLC列表: 文本渲染成功(URL={img})")
                yield event.chain_result([Image.fromURL(img)])
                return
            logger.error("DLC列表: 所有渲染失败，回退为文本")
        yield event.plain_result(text)

    async def tmpdlc_map_alias(self, event: AstrMessageEvent):
        async for r in self.tmpdlc_list(event):
            yield r
    # --- DLC 命令处理器结束 ---

    async def tmptoday_footprint(self, event: AstrMessageEvent):
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()

        target_user_id = None
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        uid = (
                            getattr(seg, "qq", None)
                            or getattr(seg, "user_id", None)
                            or getattr(seg, "id", None)
                        )
                        if isinstance(seg, dict):
                            uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                        if uid:
                            target_user_id = str(uid)
                            break
                    uid2 = getattr(seg, "qq", None)
                    if isinstance(seg, dict):
                        uid2 = seg.get("qq") or uid2
                    if uid2:
                        target_user_id = str(uid2)
                        break
            except Exception:
                target_user_id = None

        tokens = message_str.split()
        server_token = None
        input_id = None
        if len(tokens) > 1:
            for t in tokens[1:]:
                if t.isdigit():
                    input_id = t
                else:
                    server_token = t
        if not server_token:
            yield event.plain_result("用法: 足迹 [服务器简称] [ID]，例如: 足迹 s1 123")
            return
        server_key_raw = str(server_token).strip().lower()
        server_alias = {
            "s1": "sim1",
            "s2": "sim2",
            "p": "eupromods1",
            "a": "arc1",
            "promods": "eupromods1",
            "promods1": "eupromods1",
            "sim1": "sim1",
            "sim2": "sim2",
            "arc1": "arc1"
        }
        server_key = server_alias.get(server_key_raw, server_key_raw)
        server_id_map = {
            "sim1": 2,
            "sim2": 41,
            "eupromods1": 50,
            "arc1": 7
        }
        server_label_map = {
            "sim1": "SIM1",
            "sim2": "SIM2",
            "eupromods1": "ProMods",
            "arc1": "Arc"
        }
        server_label = server_label_map.get(server_key, server_key.upper())
        map_type = 'promods' if server_key in ['eupromods1', 'promods', 'promods1'] else 'ets'

        tmp_id = None
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    yield event.plain_result(f"查询失败: {str(e)}")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        try:
            player_info, stats_info, online_status = await asyncio.gather(
                self._get_player_info(tmp_id),
                self._get_player_stats(tmp_id),
                self._get_online_status(tmp_id)
            )
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')
        last_online_raw = stats_info.get('last_online') or player_info.get('lastOnline')
        last_online_formatted = _format_timestamp_to_readable(last_online_raw) if last_online_raw else '未知'

        try:
            server_ids = await self._resolve_server_ids(server_key)
            for k in ['serverId', 'serverDetailsId', 'apiServerId']:
                v = online_status.get(k)
                if v is not None:
                    s = str(v).strip()
                    if s:
                        server_ids.append(s)
            mapped_id = server_id_map.get(server_key)
            if mapped_id is not None:
                server_ids.append(str(mapped_id))
            seen = set()
            uniq = []
            for sid in server_ids:
                if sid in seen:
                    continue
                seen.add(sid)
                uniq.append(sid)
            server_ids = uniq

            now_local = datetime.now()
            start_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now_local.replace(hour=23, minute=59, second=59, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            history_points = await self._get_footprint_history(tmp_id, None, start_time, end_time)
            if history_points:
                if server_key in ['eupromods1', 'promods', 'promods1']:
                    filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) in {str(i) for i in PROMODS_SERVER_IDS}]
                elif server_key in server_id_map:
                    target = str(server_id_map[server_key])
                    filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) == target]
                elif server_ids:
                    target_set = {str(i) for i in server_ids}
                    filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) in target_set]
                else:
                    filtered = history_points
                history_points = filtered

            if history_points:
                points = self._normalize_history_points(history_points)
                meta = {'source': 'playerHistory'}
            else:
                footprint_resp = await self._get_footprint_data(server_key, tmp_id, server_ids)
                points, meta = self._extract_footprint_points(footprint_resp.get('data'), server_key, server_ids)
                fallback_points = []
                for p in points:
                    x = p.get('x')
                    y = p.get('y')
                    if x is None or y is None:
                        continue
                    fallback_points.append({'axisX': x, 'axisY': y, 'serverId': 0, 'heading': 0, 'ts': 0})
                points = fallback_points
        except Exception as e:
            yield event.plain_result(f"查询足迹失败: {str(e)}")
            return

        if not points:
            yield event.plain_result("暂无足迹数据")
            return

        def _to_km(val):
            try:
                v = float(val)
                if v > 10000:
                    v = v / 1000.0
                return round(v, 2)
            except Exception:
                return None

        distance_km = _to_km(meta.get('distance') or meta.get('mileage') or meta.get('totalDistance') or meta.get('totalMileage'))
        start_time = meta.get('startTime') or meta.get('start_time') or meta.get('beginTime') or meta.get('begin_time')
        end_time = meta.get('endTime') or meta.get('end_time') or meta.get('finishTime') or meta.get('finish_time')
        if distance_km is None:
            try:
                daily_km = float(stats_info.get('daily_km') or 0)
                if daily_km > 0:
                    distance_km = round(daily_km, 2)
            except Exception:
                distance_km = None

        tile_url_ets = "https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png"
        tile_url_promods = "https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png"
        fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
        fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
        if fullmap_ets:
            tile_url_ets = fullmap_ets
        if fullmap_promods:
            tile_url_promods = fullmap_promods

        map_tmpl = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:100vw; height:100vh; background:#111; overflow:hidden; }
  * { box-sizing: border-box; }
  .wrap { width: 100vw; color:#f2f4f8; font-family: system-ui, Segoe UI, Helvetica, Arial, sans-serif; }
  #map { width: 100vw; height: calc(100vh - 140px); background:#121417; }
  .panel { width:100vw; height:140px; background:rgba(10,10,10,.82); display:flex; align-items:center; padding:14px 20px; color:#eaeaea; backdrop-filter: blur(4px); }
  .avatar { width:64px; height:64px; border-radius:50%; background:#808080; object-fit:cover; margin-right:16px; }
  .col { flex:1; }
  .name { font-size:20px; font-weight:600; letter-spacing:.3px; color:#f0f3f5; }
  .sub { font-size:14px; color:#d8d8d8; margin-top:6px; line-height:1.5; }
  .right { width:260px; text-align:right; color:#f0f3f5; font-size:14px; }
</style>
<div class="wrap">
  <div id="map"></div>
  <div class="panel">
    <img class="avatar" src="{{ avatar }}" />
    <div class="col"> 
      <div class="name">{{ player_name }} · {{ server_label }}</div>
      <div class="sub">点位数: {{ points_count }}{% if distance_km is not none %} · 里程: {{ '%.2f' % distance_km }} km{% endif %}</div>
      <div class="sub">{% if start_time %}开始: {{ start_time }}{% endif %}{% if end_time %} · 结束: {{ end_time }}{% endif %}</div>
    </div>
    <div class="right">
      <div>上次在线: {{ last_online }}</div>
    </div>
  </div>
</div>
<script>
  var mapType = "{{ map_type }}";
  var cfg = {
    ets: {
      tileUrl: '{{ tile_url_ets }}',
      fallbackUrl: 'https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png',
      multipliers: { x: 70272, y: 76157 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 1.609055 + cfg.ets.multipliers.x, yy / 1.609055 + cfg.ets.multipliers.y ];
      }
    },
    promods: {
      tileUrl: '{{ tile_url_promods }}',
      fallbackUrl: 'https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png',
      multipliers: { x: 51953, y: 76024 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 2.598541 + cfg.promods.multipliers.x, yy / 2.598541 + cfg.promods.multipliers.y ];
      }
    }
  };

  var map = L.map('map', { attributionControl: false, crs: L.CRS.Simple, zoomControl: false, zoomSnap: 0.2, zoomDelta: 0.2 });
  var c = cfg[mapType];
  var b = L.latLngBounds(
    map.unproject([0, c.bounds.y], c.maxZoom),
    map.unproject([c.bounds.x, 0], c.maxZoom)
  );
  var tileLayer = L.tileLayer(c.tileUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  var switched = false;
  tileLayer.on('tileerror', function(){
    if (switched || !c.fallbackUrl) return;
    switched = true;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(c.fallbackUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  });
  map.setMaxBounds(b);
  function calculateDistance(p1, p2) {
    return Math.sqrt(Math.pow(p1.axisX - p2.axisX, 2) + Math.pow(p1.axisY - p2.axisY, 2));
  }
  var points = [ {% for p in points %}{ axisX: {{ p.axisX }}, axisY: {{ p.axisY }}, serverId: {{ p.serverId }}, heading: {{ p.heading }}, ts: {{ p.ts }} }{% if not loop.last %}, {% endif %}{% endfor %} ];
  points = points.filter(function(p){ return !(p.axisX === 0 && p.axisY === 0 && p.heading === 0); });
  var lines = [];
  var currentLine = [];
  if (points.length > 0) {
    currentLine.push(points[0]);
    for (var i=1;i<points.length;i++){
      var prev = points[i-1];
      var curr = points[i];
      var dist = calculateDistance(prev, curr) * 19;
      var isDistJump = dist > 30000;
      var timeDiff = 0;
      if (curr.ts && prev.ts) {
        timeDiff = curr.ts - prev.ts;
      }
      var isTimeJump = timeDiff > 90;
      var isServerJump = prev.serverId !== curr.serverId;
      if (isDistJump || isTimeJump || isServerJump) {
        if (currentLine.length > 0) lines.push(currentLine);
        currentLine = [];
      }
      currentLine.push(curr);
    }
    if (currentLine.length > 0) lines.push(currentLine);
  }
  var allLatlngs = [];
  for (var li=0; li<lines.length; li++){
    var linePts = lines[li];
    if (!linePts || linePts.length === 0) continue;
    var latlngs = [];
    for (var j=0;j<linePts.length;j++){
      var xy = c.calc(linePts[j].axisX, linePts[j].axisY);
      var ll = map.unproject(xy, c.maxZoom);
      latlngs.push(ll);
      allLatlngs.push(ll);
    }
    var line = L.polyline(latlngs, { color:'#3aa3ff', weight:4, opacity:0.9 }).addTo(map);
    if (latlngs.length > 0) {
      L.circleMarker(latlngs[0], { color:'#ffffff', weight:2, fillColor:'#21d07a', fillOpacity:1, radius:5 }).addTo(map);
      L.circleMarker(latlngs[latlngs.length-1], { color:'#ffffff', weight:2, fillColor:'#ff4d4f', fillOpacity:1, radius:5 }).addTo(map);
    }
  }
  if (allLatlngs.length > 0) {
    map.fitBounds(L.latLngBounds(allLatlngs), { padding: [30, 30] });
  }
</script>
"""
        data = {
            'player_name': player_name,
            'avatar': self._normalize_avatar_url(player_info.get('avatar')) or '',
            'points': points,
            'points_count': len(points),
            'distance_km': distance_km,
            'start_time': start_time,
            'end_time': end_time,
            'last_online': last_online_formatted,
            'map_type': map_type,
            'server_label': server_label,
            'tile_url_ets': tile_url_ets,
            'tile_url_promods': tile_url_promods
        }
        try:
            url = await self.html_render(map_tmpl, data, options={'type': 'jpeg', 'quality': 92, 'full_page': True, 'timeout': 8000, 'animations': 'disabled'})
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception:
            pass

        message = "📍 足迹\n"
        message += f"玩家: {player_name} (ID:{tmp_id})\n"
        message += f"服务器: {server_label}\n"
        message += f"点位数: {len(points)}"
        if distance_km is not None:
            message += f" | 里程: {distance_km:.2f} km"
        message += f"\n上次在线: {last_online_formatted}"
        yield event.plain_result(message)

    async def tmpbind(self, event: AstrMessageEvent):
        """[命令: 绑定] 绑定您的聊天账号与TMP ID。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'绑定\s*(\d+)', message_str)
        input_id = match.group(1) if match else None

        if not input_id:
            yield event.plain_result("请输入正确的玩家编号，格式：绑定 [TMP ID] 或 绑定 [Steam ID]")
            return

        tmp_id = input_id
        is_steam_id = (len(input_id) == 17 and input_id.startswith('7'))

        if is_steam_id:
            try:
                # 使用 TruckyApp 转换接口
                tmp_id = await self._get_tmp_id_from_steam_id(input_id)
            except SteamIdNotFoundException:
                yield event.plain_result(f"Steam ID {input_id} 未在 TruckersMP 中注册，无法绑定。")
                return
            except Exception:
                yield event.plain_result("Steam ID 转换服务请求失败，请稍后再试。")
                return

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result(f"玩家不存在，请检查ID是否正确")
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')
        
        steam_id_display = self._get_steam_id_from_player_info(player_info)
        
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            
            message = f"绑定成功！\n"
            message += f"已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定\n"         
            yield event.plain_result(message)
        else:
            yield event.plain_result("绑定失败，请稍后重试")

    async def tmpunbind(self, event: AstrMessageEvent):
        """[命令: 解绑] 解除当前用户的TruckersMP ID绑定。"""
        user_id = event.get_sender_id()
        user_binding = self._load_bindings().get(user_id, {})
        tmp_id = user_binding.get('tmp_id')
        
        if not tmp_id:
            yield event.plain_result("您还没有绑定任何TMP账号")
            return
        
        player_name = user_binding.get('player_name', '未知玩家')
        
        if self._unbind_tmp_id(user_id):
            yield event.plain_result(f"解绑成功！\n已解除与TMP玩家 {player_name}的绑定")
        else:
            yield event.plain_result("解绑失败，请稍后重试")

    # 状态命令已移除
    
    # --- 【新功能】定位命令 ---
    async def tmplocate(self, event: AstrMessageEvent):
        """[命令:定位] 查询玩家的实时位置，并返回图片。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        target_user_id = None
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        uid = (
                            getattr(seg, "qq", None)
                            or getattr(seg, "user_id", None)
                            or getattr(seg, "id", None)
                        )
                        if isinstance(seg, dict):
                            uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                        if uid:
                            target_user_id = str(uid)
                            break
                    uid2 = getattr(seg, "qq", None)
                    if isinstance(seg, dict):
                        uid2 = seg.get("qq") or uid2
                    if uid2:
                        target_user_id = str(uid2)
                        break
            except Exception:
                target_user_id = None

        match = re.search(r'(定位)\s*(\d+)', message_str) 
        input_id = match.group(2) if match else None
        
        tmp_id = None
        
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    yield event.plain_result(f"查询失败: {str(e)}")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        # 1) 玩家基本信息（昵称）
        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        # 2) 在线与坐标（fullmap + Trucky V3）
        await self._fetch_fullmap()
        fullmap_player = self._get_fullmap_player(tmp_id)
        online = await self._get_online_status(tmp_id)
        if not online or not online.get('online'):
            if not fullmap_player:
                yield event.plain_result("玩家未在线")
                return
            online = {
                'online': True,
                'serverName': '未知服务器',
                'serverId': fullmap_player.get('ServerId'),
                'x': fullmap_player.get('X'),
                'y': fullmap_player.get('Y'),
                'country': None,
                'realName': None,
                'city': {'name': '未知位置'}
            }
        if fullmap_player:
            online['x'] = fullmap_player.get('X')
            online['y'] = fullmap_player.get('Y')
            online['serverId'] = fullmap_player.get('ServerId')

        # 3) 构造 HTML 渲染数据（玩家 + 位置，周边玩家留作后续扩展）
        server_name = online.get('serverName', '未知服务器')
        location_name = online.get('city', {}).get('name') or '未知位置'
        
        # 增加翻译逻辑
        raw_country = online.get('country')
        raw_city = online.get('realName')
        
        # 如果 raw_country/raw_city 为空，尝试从 location_name 解析
        if not raw_country and ' ' in location_name:
             parts = location_name.split(' ', 1)
             if len(parts) == 2:
                 # 假设格式为 "Country City"
                 pass 

        country_cn, city_cn = await self._translate_country_city(raw_country, location_name)
        
        # 修正显示名称
        display_country = country_cn or raw_country or '未知国家'
        display_city = city_cn or location_name
        
        player_name = player_info.get('name') or '未知'

        avatar_url = self._normalize_avatar_url(player_info.get('avatar'))

        # 4) 周边玩家查询并绘制简易地图（基于 da.vtcm.link）
        try:
            server_id = online.get('serverId')
            cx = float(online.get('x') or 0)
            cy = float(online.get('y') or 0)
            ax, ay = cx - 4000, cy + 2500
            bx, by = cx + 4000, cy - 2500
            area_url = f"https://da.vtcm.link/map/playerList?aAxisX={ax}&aAxisY={ay}&bAxisX={bx}&bAxisY={by}&serverId={server_id}"
            logger.info(f"定位: 使用底图查询周边玩家 serverId={server_id} center=({cx},{cy}) url={area_url}")
            area_players = []
            if self.session and server_id:
                async with self.session.get(area_url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        area_players = j.get('data') or []
                        logger.info(f"定位: 周边玩家数量={len(area_players)}")
            # 将当前玩家追加
            area_players = [p for p in area_players if str(p.get('tmpId')) != str(tmp_id)]
            area_players.append({'tmpId': str(tmp_id), 'axisX': cx, 'axisY': cy})

            map_type = 'promods' if int(server_id or 0) in [50, 51] else 'ets'
            tile_url_ets = "https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png"
            tile_url_promods = "https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png"
            fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
            fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
            if fullmap_ets:
                tile_url_ets = fullmap_ets
            if fullmap_promods:
                tile_url_promods = fullmap_promods
            logger.info(f"定位: tile_ets={'fullmap' if fullmap_ets else 'ets2.online'}")
            logger.info(f"定位: tile_promods={'fullmap' if fullmap_promods else 'ets2.online'}")
            if map_type == 'ets' and not tile_url_ets:
                raise RuntimeError("fullmap 缓存未包含 ETS 瓦片地址")
            if map_type == 'promods' and not tile_url_promods:
                raise RuntimeError("fullmap 缓存未包含 ProMods 瓦片地址")

            map_tmpl = """
<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css\">
<script src=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js\"></script>
<style>
  html, body { margin:0; padding:0; width:100vw; height:100vh; background:#1f2328; overflow:hidden; }
  * { box-sizing: border-box; }
  .wrap { width: 100vw; color:#f2f4f8; font-family: system-ui, Segoe UI, Helvetica, Arial, sans-serif; }
  #map { width: 100vw; height: calc(100vh - 150px); background:#2a2f36; filter: contrast(1.08) saturate(1.15) brightness(1.18); }
  .panel { width:100vw; height:150px; background:rgba(28,28,28,.75); display:flex; align-items:center; padding:16px 20px; color:#eaeaea; backdrop-filter: blur(4px); }
  .avatar { width:64px; height:64px; border-radius:50%; background:#808080; object-fit:cover; margin-right:16px; }
  .col { flex:1; }
  .name { font-size:22px; font-weight:600; letter-spacing:.3px; color:#f0f3f5; }
  .sub { font-size:16px; color:#d8d8d8; margin-top:6px; }
  .right { width:240px; text-align:right; color:#f0f3f5; font-size:16px; }
</style>
<div class=\"wrap\">
  <div id=\"map\"></div>
  <div class=\"panel\">
    <img class=\"avatar\" src=\"{{ avatar }}\" />
    <div class=\"col\"> 
      <div class=\"name\">{{ player_name }}</div>
      <div class=\"sub\">{{ server_name }} 游戏中</div>
    </div>
    <div class=\"right\">
      <div>{{ country or '未知' }}</div>
      <div>{{ city }}</div>
    </div>
  </div>
</div>
<script>
  var promodsIds = [50, 51];
  var serverId = {{ server_id }};
  var mapType = promodsIds.indexOf(serverId) !== -1 ? 'promods' : 'ets';
  var cfg = {
    ets: {
      tileUrl: 'https://ets-map.oss-cn-beijing.aliyuncs.com/ets2/05102019/{z}/{x}/{y}.png',
      fallbackUrl: 'https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png',
      multipliers: { x: 70272, y: 76157 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 1.609055 + cfg.ets.multipliers.x, yy / 1.609055 + cfg.ets.multipliers.y ];
      }
    },
    promods: {
      tileUrl: 'https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png',
      fallbackUrl: 'https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png',
      multipliers: { x: 51953, y: 76024 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 2.598541 + cfg.promods.multipliers.x, yy / 2.598541 + cfg.promods.multipliers.y ];
      }
    }
  };

  var map = L.map('map', { attributionControl: false, crs: L.CRS.Simple, zoomControl: false, zoomSnap: 0.2, zoomDelta: 0.2 });
  var c = cfg[mapType];
  var b = L.latLngBounds(
    map.unproject([0, c.bounds.y], c.maxZoom),
    map.unproject([c.bounds.x, 0], c.maxZoom)
  );
  var tileLayer = L.tileLayer(c.tileUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  var switched = false;
  tileLayer.on('tileerror', function(){
    if (switched || !c.fallbackUrl) return;
    switched = true;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(c.fallbackUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  });
  map.setMaxBounds(b);
  var centerX = {{ center_x }};
  var centerY = {{ center_y }};
  var players = [ {% for p in players %}{ axisX: {{ p.axisX }}, axisY: {{ p.axisY }}, tmpId: "{{ p.tmpId }}" }{% if not loop.last %}, {% endif %}{% endfor %} ];
  for (var i=0;i<players.length;i++){
    var p = players[i];
    var xy = c.calc(p.axisX, p.axisY);
    var latlng = map.unproject(xy, c.maxZoom);
    L.circleMarker(latlng, { color:'#2f2f2f', weight:2, fillColor:(p.tmpId === '{{ me_id }}' ? '#57bd00' : '#3ca7ff'), fillOpacity:1, radius:(p.tmpId === '{{ me_id }}' ? 6 : 5) }).addTo(map);
  }
  var centerLL = map.unproject(c.calc(centerX, centerY+80), c.maxZoom);
  map.setView(centerLL, 7);
  setTimeout(function(){}, 800); // 轻微延时确保瓦片加载
</script>
"""
            min_x, max_x = ax, bx
            min_y, max_y = by, ay  # 注意坐标系方向
            map_data = {
                'server_name': server_name,
                'location_name': f"{display_country} {display_city}",
                'player_name': player_name,
                'me_id': str(tmp_id),
                'players': area_players,
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y,
                'avatar': avatar_url or '',
                'country': display_country,
                'city': display_city,
                'server_id': int(online.get('serverId') or 0),
                'center_x': float(cx),
                'center_y': float(cy),
                'tile_url_ets': tile_url_ets,
                'tile_url_promods': tile_url_promods
            }
            logger.info(f"定位: 渲染底图 mapType={'promods' if int(online.get('serverId') or 0) in [50,51] else 'ets'} players={len(area_players)}")
            url2 = await self.html_render(map_tmpl, map_data, options={'type': 'jpeg', 'quality': 92, 'full_page': True, 'timeout': 8000, 'animations': 'disabled'})
            if isinstance(url2, str) and url2:
                yield event.chain_result([Image.fromURL(url2)])
                return
        except Exception:
            pass

        # 最终回退文本
        msg = f"玩家实时定位\n玩家名称: {player_name}\nTMP编号: {tmp_id}\n服务器: {server_name}\n位置: {display_country} {display_city}"
        yield event.plain_result(msg)
    # --- 定位命令结束 ---
    

    # --- 里程排行榜命令处理器：总里程 ---
    async def tmprank_total(self, event: AstrMessageEvent):
        """[命令: 总里程排行] 查询 TruckersMP 玩家总里程排行榜前10名。"""
        
        try:
            rank_list = await self._get_rank_list(ranking_type="total", limit=10)
        except NetworkException as e:
            yield event.plain_result(f"查询排行榜失败: {str(e)}")
            return
        except ApiResponseException:
            yield event.plain_result("查询排行榜失败: API返回数据异常。")
            return
        except Exception:
            yield event.plain_result("查询排行榜时发生未知错误。")
            return

        if not rank_list:
            yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
            return
            
        message = "🏆 TruckersMP 玩家总里程排行榜 (前10名)\n"
        message += "=" * 35 + "\n"
        items: List[Dict[str, Any]] = []
        me_data: Optional[Dict[str, Any]] = None

        me_user_id = event.get_sender_id()
        me_tmp_id = None
        me_name = None
        me_total_km = None
        me_total_rank = None
        me_vtc_role = None
        try:
            bindings = self._load_bindings()
            b = bindings.get(me_user_id)
            if isinstance(b, dict):
                me_tmp_id = b.get("tmp_id")
                me_name = b.get("player_name")
            else:
                me_tmp_id = b
        except Exception:
            me_tmp_id = None

        if me_tmp_id:
            try:
                stats = await self._get_player_stats(str(me_tmp_id))
                me_total_km = stats.get("total_km")
                me_total_rank = stats.get("total_rank")
                me_vtc_role = stats.get("vtcRole")
                if isinstance(me_total_km, (int, float)):
                    km_str = f"{float(me_total_km):,.2f}".replace(",", " ")
                    display_name = (str(me_name).strip() if me_name is not None else "") or "你"
                    message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                    message += f"里程: {km_str} km"
                    if me_total_rank is not None:
                        message += f" | 排名: No.{me_total_rank}"
                    message += "\n"
                    if me_vtc_role:
                        message += f"车队职位: {str(me_vtc_role).strip()}\n"
                    message += "-" * 35 + "\n"
                    me_data = {
                        "name": display_name,
                        "tmp_id": me_tmp_id,
                        "rank": me_total_rank,
                        "km": float(me_total_km),
                        "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                    }
            except Exception:
                pass
        
        for idx, player in enumerate(rank_list):
            rank = player.get('ranking', idx + 1)
            raw_name = (
                player.get('tmpName')
                or player.get('name')
                or player.get('tmp_name')
                or player.get('nickName')
                or player.get('nickname')
            )
            name = str(raw_name).strip() if raw_name is not None else ''
            if not name:
                name = '未知玩家'
            distance_m = player.get('mileage') or player.get('distance') or 0
            
            distance_km = int(distance_m / 1000) if isinstance(distance_m, (int, float)) else 0
            distance_str = f"{distance_km:,}".replace(',', ' ')
            tmp_id = player.get('tmpId', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            message += line

            items.append({
                'rank': rank,
                'name': name,
                'km': distance_km,
                'tmp_id': tmp_id,
            })

        message += "=" * 35 + "\n"

        rank_tmpl = """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
  .wrap { width:600px; margin:0 auto; padding:14px; background:#222d33; color:#fff; font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif; }
  .header { font-size:20px; font-weight:600; margin:0 0 8px 0; text-align:center; }
  .me { background:#1f2a31; border:1px solid rgba(255,255,255,0.10); border-radius:8px; padding:10px 12px; margin:0 0 10px 0; }
  .me .t1 { font-size:14px; font-weight:700; margin:0 0 4px 0; }
  .me .t2 { font-size:13px; opacity:0.92; }
  .list { margin:0; padding:0; }
  .item { display:flex; align-items:center; background:#24313a; margin:0 0 8px 0; padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.08); }
  .item.top3 { background:linear-gradient(135deg,rgba(255,215,0,0.18),rgba(255,215,0,0.06)); border-color:rgba(255,215,0,0.35); }
  .rank { width:40px; font-size:15px; font-weight:bold; text-align:center; }
  .name { flex:1; padding:0 10px; min-width:0; font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .km { min-width:90px; font-size:14px; font-weight:700; text-align:right; white-space:nowrap; }
</style>
<div class="wrap">
  <div class="header">{{ title }}</div>
  {% if me %}
  <div class="me">
    <div class="t1">🙋 个人信息：{{ me.name }} (ID:{{ me.tmp_id }})</div>
    <div class="t2">里程：{{ '%.2f' % me.km }} km{% if me.rank is not none %} | 排名：No.{{ me.rank }}{% endif %}{% if me.vtc_role %} | 车队职位：{{ me.vtc_role }}{% endif %}</div>
  </div>
  {% endif %}
  <div class="list">
    {% for it in items %}
    <div class="item{% if it.rank <= 3 %} top3{% endif %}">
      <div class="rank">#{{ it.rank }}</div>
      <div class="name">{{ it.name }} (ID:{{ it.tmp_id }})</div>
      <div class="km">{{ it.km }} km</div>
    </div>
    {% endfor %}
  </div>
</div>
"""

        try:
            options = { 'type': 'jpeg', 'quality': 92, 'full_page': True, 'omit_background': False }
            url = await self.html_render(rank_tmpl, { 'title': '- 总行驶里程排行榜 -', 'items': items, 'me': me_data }, options=options)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception:
            pass

        img = await self._render_text_to_image(message)
        if isinstance(img, (bytes, bytearray)):
            yield event.chain_result([Image.fromBytes(img)])
            return
        if isinstance(img, str) and img.startswith('http'):
            yield event.chain_result([Image.fromURL(img)])
            return
        yield event.plain_result(message)
    # --- 里程排行榜命令处理器：总里程结束 ---

    # --- 里程排行榜命令处理器：今日里程 ---
    async def tmprank_today(self, event: AstrMessageEvent):
        """[命令: 今日里程排行] 查询 TruckersMP 玩家今日里程排行榜前10名。"""
        
        try:
            rank_list = await self._get_rank_list(ranking_type="today", limit=10)
        except NetworkException as e:
            yield event.plain_result(f"查询排行榜失败: {str(e)}")
            return
        except ApiResponseException:
            yield event.plain_result("查询排行榜失败: API返回数据异常。")
            return
        except Exception:
            yield event.plain_result("查询排行榜时发生未知错误。")
            return

        if not rank_list:
            yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
            return
            
        message = "🏁 TruckersMP 玩家今日里程排行榜 (前10名)\n"
        message += "=" * 35 + "\n"
        items: List[Dict[str, Any]] = []
        me_data: Optional[Dict[str, Any]] = None

        me_user_id = event.get_sender_id()
        me_tmp_id = None
        me_name = None
        me_daily_km = None
        me_daily_rank = None
        me_vtc_role = None
        try:
            bindings = self._load_bindings()
            b = bindings.get(me_user_id)
            if isinstance(b, dict):
                me_tmp_id = b.get("tmp_id")
                me_name = b.get("player_name")
            else:
                me_tmp_id = b
        except Exception:
            me_tmp_id = None

        if me_tmp_id:
            try:
                stats = await self._get_player_stats(str(me_tmp_id))
                me_daily_km = stats.get("daily_km")
                me_daily_rank = stats.get("daily_rank")
                me_vtc_role = stats.get("vtcRole")
                if isinstance(me_daily_km, (int, float)):
                    km_str = f"{float(me_daily_km):,.2f}".replace(",", " ")
                    display_name = (str(me_name).strip() if me_name is not None else "") or "你"
                    message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                    message += f"里程: {km_str} km"
                    if me_daily_rank is not None:
                        message += f" | 排名: No.{me_daily_rank}"
                    message += "\n"
                    if me_vtc_role:
                        message += f"车队职位: {str(me_vtc_role).strip()}\n"
                    message += "-" * 35 + "\n"
                    me_data = {
                        "name": display_name,
                        "tmp_id": me_tmp_id,
                        "rank": me_daily_rank,
                        "km": float(me_daily_km),
                        "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                    }
            except Exception:
                pass
        
        for idx, player in enumerate(rank_list):
            rank = player.get('ranking', idx + 1)
            raw_name = (
                player.get('tmpName')
                or player.get('name')
                or player.get('tmp_name')
                or player.get('nickName')
                or player.get('nickname')
            )
            name = str(raw_name).strip() if raw_name is not None else ''
            if not name:
                name = '未知玩家'
            distance_m = player.get('mileage') or player.get('distance') or 0
            
            distance_km = int(distance_m / 1000) if isinstance(distance_m, (int, float)) else 0
            distance_str = f"{distance_km:,}".replace(',', ' ')
            tmp_id = player.get('tmpId', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            message += line

            items.append({
                'rank': rank,
                'name': name,
                'km': distance_km,
                'tmp_id': tmp_id,
            })

        message += "=" * 35 + "\n"

        rank_tmpl = """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
  .wrap { width:600px; margin:0 auto; padding:14px; background:#222d33; color:#fff; font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif; }
  .header { font-size:20px; font-weight:600; margin:0 0 8px 0; text-align:center; }
  .me { background:#1f2a31; border:1px solid rgba(255,255,255,0.10); border-radius:8px; padding:10px 12px; margin:0 0 10px 0; }
  .me .t1 { font-size:14px; font-weight:700; margin:0 0 4px 0; }
  .me .t2 { font-size:13px; opacity:0.92; }
  .list { margin:0; padding:0; }
  .item { display:flex; align-items:center; background:#24313a; margin:0 0 8px 0; padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.08); }
  .item.top3 { background:linear-gradient(135deg,rgba(255,215,0,0.18),rgba(255,215,0,0.06)); border-color:rgba(255,215,0,0.35); }
  .rank { width:40px; font-size:15px; font-weight:bold; text-align:center; }
  .name { flex:1; padding:0 10px; min-width:0; font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .km { min-width:90px; font-size:14px; font-weight:700; text-align:right; white-space:nowrap; }
</style>
<div class="wrap">
  <div class="header">{{ title }}</div>
  {% if me %}
  <div class="me">
    <div class="t1">🙋 个人信息：{{ me.name }} (ID:{{ me.tmp_id }})</div>
    <div class="t2">里程：{{ '%.2f' % me.km }} km{% if me.rank is not none %} | 排名：No.{{ me.rank }}{% endif %}{% if me.vtc_role %} | 车队职位：{{ me.vtc_role }}{% endif %}</div>
  </div>
  {% endif %}
  <div class="list">
    {% for it in items %}
    <div class="item{% if it.rank <= 3 %} top3{% endif %}">
      <div class="rank">#{{ it.rank }}</div>
      <div class="name">{{ it.name }} (ID:{{ it.tmp_id }})</div>
      <div class="km">{{ it.km }} km</div>
    </div>
    {% endfor %}
  </div>
</div>
"""

        try:
            options = { 'type': 'jpeg', 'quality': 92, 'full_page': True, 'omit_background': False }
            url = await self.html_render(rank_tmpl, { 'title': '- 今日行驶里程排行榜 -', 'items': items, 'me': me_data }, options=options)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception:
            pass

        img = await self._render_text_to_image(message)
        if isinstance(img, (bytes, bytearray)):
            yield event.chain_result([Image.fromBytes(img)])
            return
        if isinstance(img, str) and img.startswith('http'):
            yield event.chain_result([Image.fromURL(img)])
            return
        yield event.plain_result(message)
    # --- 里程排行榜命令处理器：今日里程结束 ---

    async def tmptraffic(self, event: AstrMessageEvent):
        message_str = (event.message_str or "").strip()
        m = re.search(r"路况\s*(\S+)", message_str)
        server_token = m.group(1).strip().lower() if m else ""
        if not server_token:
            yield event.plain_result("用法: 路况 [服务器简称]，例如: 路况 s1")
            return
        try:
            items = await self._get_traffic_top(server_token)
        except NetworkException as e:
            yield event.plain_result(f"查询路况失败: {str(e)}")
            return
        except ApiResponseException:
            yield event.plain_result("查询路况失败: API 返回数据异常。")
            return
        except Exception:
            yield event.plain_result("查询路况时发生未知错误。")
            return
        if not items:
            yield event.plain_result("当前服务器暂无热门路段数据。")
            return
        severity_map = {
            "Fluid": "🟢畅通",
            "Moderate": "🟠正常",
            "Congested": "🔴缓慢",
            "Heavy": "🟣拥堵",
        }
        type_map = {
            "City": "城市",
            "Road": "公路",
            "Intersection": "十字路口",
        }
        lines: List[str] = []
        for t in items:
            country_raw = str(t.get("country") or "").strip()
            country_cn, _ = await self._translate_country_city(country_raw, None)
            country = country_cn or "未知区域"
            raw_name = str(t.get("name") or "").strip()
            name = raw_name
            place_type = ""
            idx1 = raw_name.rfind("(")
            idx2 = raw_name.rfind(")")
            if idx1 > 0 and idx2 > idx1:
                name = raw_name[:idx1].strip()
                place_type = raw_name[idx1 + 1:idx2].strip()
            translated_name = await self._translate_traffic_name(name)
            severity_key = str(t.get("newSeverity") or "").strip()
            severity_text = severity_map.get(severity_key) or severity_key or "未知"
            if severity_text and severity_text == severity_key:
                translated_severity = await self._translate_text(severity_text, cache=True)
                if translated_severity:
                    severity_text = translated_severity
            players = t.get("players")
            players_str = ""
            if isinstance(players, (int, float)):
                players_str = str(int(players))
            elif players is not None:
                players_str = str(players)
            line = f"{country} {translated_name}"
            if place_type:
                type_text = type_map.get(place_type, place_type)
                if type_text and type_text == place_type:
                    translated_type = await self._translate_text(type_text, cache=True)
                    if translated_type:
                        type_text = translated_type
                line += f" ({type_text})"
            line += f"\n路况: {severity_text}"
            if players_str:
                line += f" | 人数: {players_str}"
            lines.append(line)
        header = "🚦 服务器热门路况\n" + "=" * 20
        message = header + "\n" + "\n\n".join(lines)
        yield event.plain_result(message)


    async def tmpserver(self, event: AstrMessageEvent):
        """[命令: 服务器] 查询TruckersMP官方服务器的实时状态。"""
        if not self.session: 
            yield event.plain_result("插件初始化中，请稍后重试")
            return
            
        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    servers = data.get('response', [])
                    
                    if servers and isinstance(servers, list):
                        
                        ets2_servers = []
                        ats_servers = []
                        
                        # 优化服务器分组逻辑 (1.3.25/1.3.26)
                        for s in servers:
                            name = s.get('name', '').lower()
                            if s.get('online'):
                                # ATS 服务器的常见标记: [US] 或 American Truck Simulator/ATS
                                if '[us]' in name or 'american truck simulator' in name or 'ats' in name:
                                    ats_servers.append(s)
                                # ETS2 服务器的常见标记: 默认(Simulation 1/2, Arcade, ProMods等) 或包含[EU]/[Asia]
                                else:
                                    ets2_servers.append(s)

                        # ATS/ETS2总玩家数计算
                        total_players = sum(s.get('players', 0) for s in (ets2_servers + ats_servers))

                        message = f"TMP服务器状态 (总在线数: {len(ets2_servers) + len(ats_servers)}个)\n"
                        message += "=" * 30 + "\n"
                        message += f"**[当前总玩家数: {total_players:,}]**\n\n".replace(',', ' ')
                        
                        if ets2_servers or ats_servers:
                            
                            def _format_server_list(server_list: List[Dict], title: str, game_icon: str) -> str:
                                output = f"**{game_icon} {title} ({len(server_list)}个在线)**\n"
                                if not server_list:
                                    return output + "  (暂无)\n\n"
                                
                                # 保持 API 返回的顺序（即 Simulation 1/2 靠前）
                                for server in server_list:
                                    name = server.get('name', '未知')
                                    players = server.get('players', 0)
                                    max_players = server.get('maxplayers', 0)
                                    queue = server.get('queue', 0)
                                    
                                    status_str = '🟢' 
                                    
                                    # 服务器特性提示
                                    collision_str = "💥碰撞" if server.get('collisions') else "💥无碰撞"
                                    speed_str = "🚀无限速" if server.get('speedLimiter') is False else ""
                                    
                                    output += f"服务器: {status_str} {name}\n"
                                    
                                    players_str = f"  玩家人数: {players:,}/{max_players:,}".replace(',', ' ')
                                    
                                    if queue > 0: 
                                        output += f"{players_str} (排队: {queue})\n"
                                    else:
                                        output += f"{players_str}\n"
                                    
                                    output += f"  特性: {collision_str}"
                                    if speed_str:
                                        output += f" | {speed_str}"
                                    output += "\n"
                                    
                                    
                                return output + "\n"

                            message += _format_server_list(ets2_servers, "Euro Truck Simulator 2 服务器", "🚛")
                            message += _format_server_list(ats_servers, "American Truck Simulator 服务器", "🇺🇸")

                        else: 
                            message += "暂无在线服务器"
                        
                        message += "=" * 30 
                        yield event.plain_result(message)
                else:
                    yield event.plain_result(f"查询服务器状态失败，API返回错误状态码: {response.status}")
        except Exception:
            yield event.plain_result("网络请求失败，请检查网络或稍后重试。")

    async def tmpversion(self, event: AstrMessageEvent):
        """[命令: 插件版本] 实时查询 TMP 联机插件版本信息。"""
        if not self.session:
            yield event.plain_result("插件初始化中，请稍后重试")
            return

        try:
            url = "https://api.truckersmp.com/v2/version"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    plugin_ver = data.get("name") or data.get("version") or "未知"
                    ets2_ver = data.get("supported_game_version") or data.get("supported_ets2_version") or "未知"
                    ats_ver = data.get("supported_ats_game_version") or data.get("supported_ats_version") or "未知"
                    protocol = data.get("protocol") or "未知"

                    message = "TMP 插件版本信息\n" + "=" * 18 + "\n"
                    message += f"TMP 插件版本: {plugin_ver}\n"
                    message += f"欧卡支持版本: {ets2_ver}\n"
                    message += f"美卡支持版本: {ats_ver}"
                    yield event.plain_result(message)
                else:
                    yield event.plain_result(f"查询版本信息失败，API返回错误状态码: {response.status}")
        except Exception:
            yield event.plain_result("查询版本信息失败，请稍后重试。")

    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: 菜单] 显示本插件的命令使用说明。"""
        help_text = """TMP查询插件使用说明

可用命令:
1. 绑定 [ID]
2. 查询 [ID]
3. 定位 [ID]
4. 地图DLC
5. 总里程排行
6. 今日里程排行
7. 足迹 [服务器简称] [ID]
8. 路况
9. 解绑
10. 服务器
11. 插件版本
12. 菜单
使用提示: 绑定后可直接发送 查询/定位
"""
        yield event.plain_result(help_text)
        
    async def terminate(self):
        """插件卸载时的清理工作：关闭HTTP会话。"""
        self._fullmap_task = None
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")
