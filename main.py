#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
astrbot-plugin-tmp-bot
欧卡2TMP查询插件 (版本 1.7.4)
插件主入口与核心实现
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
from .templates import dlc_list_template, footprint_map_template, locate_map_template, rank_template
from .feature_handlers import FeatureHandlersMixin

# 引入 AstrBot 核心 API
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, StarTools, register
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

@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.7.4", "https://github.com/BGYdook/astrbot-plugin-tmp-bot")
class TmpBotPlugin(FeatureHandlersMixin, Star):
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
        s = (content or "").strip()
        if not s:
            return content
        if not self._cfg_bool('baidu_translate_enable', True):
            return content
        use_cache = self._cfg_bool('baidu_translate_cache_enable', False)
        cache_key = hashlib.md5(s.encode('utf-8')).hexdigest()
        if cache and use_cache:
            cached = self._translate_cache.get(cache_key)
            if cached:
                return cached
        app_id = self._cfg_str('baidu_translate_app_id', '').strip()
        app_key = self._cfg_str('baidu_translate_key', '').strip()
        if not app_id or not app_key or not self.session:
            return content
        try:
            salt = str(random.randint(1000, 9999))
            sign = hashlib.md5((app_id + s + salt + app_key).encode('utf-8')).hexdigest()
            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            params = {
                'q': s,
                'from': 'auto',
                'to': 'zh',
                'appid': app_id,
                'salt': salt,
                'sign': sign
            }
            async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict) and data.get('trans_result'):
                        dst = data['trans_result'][0].get('dst')
                        if isinstance(dst, str) and dst.strip():
                            translated = dst.strip()
                            if cache and use_cache:
                                self._translate_cache[cache_key] = translated
                            return translated
        except Exception:
            return content
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
            root = os.path.dirname(os.path.dirname(__file__))
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

        def _has_cjk(t: str) -> bool:
            return bool(_re_local.search(r"[\u4e00-\u9fff]", t or ""))

        def _clean_raw_text(raw: str) -> str:
            t = (raw or "").strip()
            if not t or _has_cjk(t):
                return t
            t = _re_local.sub(r"\s*\([^)]*\)\s*", " ", t)
            t = _re_local.sub(r"\s*（[^）]*）\s*", " ", t)
            t = _re_local.sub(r"\s*\[[^\]]*\]\s*", " ", t)
            t = _re_local.sub(r"[^A-Za-z\s\-]", " ", t)
            t = _re_local.sub(r"\s+", " ", t).strip()
            return t

        def _ensure_cn_text(text: Optional[str], en_fallback: str, is_city: bool) -> str:
            t = (text or "").strip()
            if _has_cjk(t):
                return t
            key = (en_fallback or "").strip().lower()
            mapped = self.CITY_MAP_EN_TO_CN.get(key) if is_city else self.COUNTRY_MAP_EN_TO_CN.get(key)
            if mapped and _has_cjk(mapped):
                return mapped
            fixed = self.LOCATION_FIX_MAP.get(key)
            if fixed and _has_cjk(fixed):
                return fixed
            return ""

        country_en = _clean_raw_text(country_en)
        city_en = _clean_raw_text(city_en)

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
        country_cn = _ensure_cn_text(country_cn, country_en, False)
        city_cn = _ensure_cn_text(city_cn, city_en, True)
        return country_cn, city_cn

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
                            formatted_location = f"{country_cn}-{city_cn}"
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
            logger.info(f"足迹历史: 请求 {url} params={params}")
            async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status != 200:
                    logger.info(f"足迹历史: 返回状态码 {resp.status}")
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
                logger.info(f"足迹接口: 请求 {url}")
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
        
    async def terminate(self):
        """插件卸载时的清理工作：关闭HTTP会话。"""
        self._fullmap_task = None
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")
