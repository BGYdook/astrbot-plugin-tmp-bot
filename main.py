#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
astrbot-plugin-tmp-bot
欧卡2TMP查询插件 (版本 1.9.0)
"""

import re
import asyncio
import math
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
from datetime import datetime, timedelta, timezone

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

USER_GROUP_MAP = {
    'Player': '玩家',
    'Retired Legend': '退役',
    'Game Developer': '游戏开发者',
    'Retired Team Member': '退休团队成员',
    'Add-On Team': '附加组件团队',
    'Game Moderator': '游戏管理员'
}
PROMODS_SERVER_IDS = {50, 51}
BEIJING_TZ = timezone(timedelta(hours=8))
TMP_GAME_EPOCH = datetime(2015, 10, 25, 15, 48, 32)

RANK_IMAGE_TEMPLATE = """
<style>
  html, body {
    width: 760px;
    margin: 0;
    padding: 0;
    background: #070b12;
  }
  * { box-sizing: border-box; }
  .board {
    --accent: #55e0b0;
    --accent-soft: rgba(85, 224, 176, .16);
    --accent-line: rgba(85, 224, 176, .42);
    position: relative;
    width: 760px;
    overflow: hidden;
    padding: 28px 28px 24px;
    color: #f7f9fc;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    background:
      radial-gradient(circle at 90% 4%, rgba(65, 171, 255, .18), transparent 28%),
      radial-gradient(circle at 5% 48%, rgba(85, 224, 176, .12), transparent 30%),
      linear-gradient(150deg, #0d1523 0%, #09101b 48%, #070b12 100%);
  }
  .board.today {
    --accent: #ffbd63;
    --accent-soft: rgba(255, 189, 99, .16);
    --accent-line: rgba(255, 189, 99, .42);
  }
  .board::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: .34;
    background-image:
      linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
    background-size: 38px 38px;
    mask-image: linear-gradient(to bottom, black, transparent 78%);
  }
  .road-mark {
    position: absolute;
    right: -88px;
    top: 105px;
    width: 260px;
    height: 420px;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 50%;
    transform: rotate(24deg);
  }
  .road-mark::before,
  .road-mark::after {
    content: "";
    position: absolute;
    inset: 26px;
    border: 1px dashed rgba(255,255,255,.09);
    border-radius: 50%;
  }
  .road-mark::after { inset: 70px; }
  .hero {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 22px;
    padding-bottom: 22px;
    border-bottom: 1px solid rgba(255,255,255,.1);
  }
  .brand { display: flex; align-items: center; gap: 15px; min-width: 0; }
  .brand-mark {
    width: 54px;
    height: 54px;
    flex: 0 0 54px;
    display: grid;
    place-items: center;
    border-radius: 17px;
    color: #07121a;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: .5px;
    background: linear-gradient(145deg, var(--accent), #e9fff8);
    box-shadow: 0 10px 30px var(--accent-soft);
  }
  .eyebrow {
    margin-bottom: 5px;
    color: var(--accent);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2.6px;
    text-transform: uppercase;
  }
  h1 {
    margin: 0;
    font-size: 30px;
    line-height: 1.15;
    font-weight: 800;
    letter-spacing: -.8px;
  }
  .hero-meta {
    flex: 0 0 auto;
    text-align: right;
    padding-top: 3px;
  }
  .hero-meta strong {
    display: block;
    color: #fff;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 23px;
    line-height: 1;
    letter-spacing: -.5px;
  }
  .hero-meta span {
    display: block;
    margin-top: 6px;
    color: #8190a5;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.8px;
  }
  .section-label {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 9px;
    margin: 18px 2px 10px;
    color: #8592a5;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2.2px;
  }
  .section-label::after {
    content: "";
    height: 1px;
    flex: 1;
    background: linear-gradient(90deg, rgba(255,255,255,.13), transparent);
  }
  .champion,
  .runner-card,
  .row,
  .me-card {
    position: relative;
    z-index: 1;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(18, 28, 43, .88);
    box-shadow: 0 12px 34px rgba(0,0,0,.19);
  }
  .champion {
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr) auto;
    align-items: center;
    gap: 17px;
    padding: 19px 21px;
    border-radius: 18px;
    border-color: rgba(246, 196, 83, .42);
    background:
      linear-gradient(110deg, rgba(246,196,83,.17), rgba(246,196,83,.035) 46%, rgba(18,28,43,.92)),
      rgba(18,28,43,.95);
  }
  .champion::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: linear-gradient(#ffe49b, #f0a72f);
    box-shadow: 0 0 22px rgba(246,196,83,.7);
  }
  .champion::after {
    content: "01";
    position: absolute;
    right: 14px;
    bottom: -18px;
    color: rgba(255,255,255,.035);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 92px;
    font-weight: 900;
    letter-spacing: -8px;
  }
  .medal {
    width: 60px;
    height: 60px;
    display: grid;
    place-items: center;
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(255,255,255,.08);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 24px;
    font-weight: 900;
  }
  .champion .medal {
    color: #191204;
    border: 0;
    background: linear-gradient(145deg, #ffe7a2, #e7a531);
    box-shadow: 0 9px 24px rgba(240,167,47,.27);
  }
  .player { min-width: 0; }
  .player-name {
    overflow: hidden;
    color: #f8fafc;
    font-size: 18px;
    font-weight: 800;
    line-height: 1.25;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .player-id {
    margin-top: 4px;
    color: #8190a5;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 10px;
    letter-spacing: .7px;
  }
  .mileage {
    position: relative;
    z-index: 1;
    text-align: right;
    white-space: nowrap;
  }
  .mileage strong {
    display: block;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 22px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .mileage span {
    display: block;
    margin-top: 5px;
    color: #8290a3;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
  }
  .runner-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 10px;
  }
  .runner-card {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    padding: 14px;
    border-radius: 15px;
  }
  .runner-card.silver { border-color: rgba(194,207,222,.28); }
  .runner-card.bronze { border-color: rgba(226,153,91,.28); }
  .runner-card .medal { width: 44px; height: 44px; border-radius: 14px; font-size: 17px; }
  .runner-card.silver .medal { color: #17212d; background: linear-gradient(145deg, #edf3f9, #aab9ca); }
  .runner-card.bronze .medal { color: #24150a; background: linear-gradient(145deg, #f3bd8c, #c9783d); }
  .runner-card .player-name { font-size: 14px; }
  .runner-card .mileage { grid-column: 2; text-align: left; margin-top: -4px; }
  .runner-card .mileage strong { color: #dce5f0; font-size: 15px; }
  .runner-card .mileage span { display: none; }
  .rows { display: grid; gap: 7px; }
  .row {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    padding: 11px 14px;
    border-radius: 12px;
    background: rgba(17, 27, 41, .74);
  }
  .row-rank {
    color: #8c9aae;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 13px;
    font-weight: 800;
  }
  .row .player-name { font-size: 14px; font-weight: 700; }
  .row .player-id { margin-top: 2px; }
  .row .mileage strong { font-size: 14px; }
  .me-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 16px;
    margin-top: 18px;
    padding: 15px 17px;
    border-radius: 16px;
    border-color: var(--accent-line);
    background:
      linear-gradient(105deg, var(--accent-soft), rgba(16,26,40,.88) 72%),
      rgba(16,26,40,.95);
    box-shadow: inset 0 0 0 1px var(--accent-soft);
  }
  .me-label {
    margin-bottom: 6px;
    color: var(--accent);
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 2.2px;
  }
  .me-name { font-size: 15px; font-weight: 800; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .me-sub { margin-top: 5px; color: #8d9aad; font-size: 11px; }
  .me-values { text-align: right; white-space: nowrap; }
  .me-values strong {
    display: block;
    color: var(--accent);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 19px;
  }
  .me-values span {
    display: block;
    margin-top: 4px;
    color: #c3cedd;
    font-size: 11px;
    font-weight: 700;
  }
  .footer {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 15px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,.08);
    color: #59677a;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.1px;
  }
  .footer b { color: var(--accent); font-weight: 800; }
</style>
<div class="board {{ 'today' if is_today else 'total' }}">
  <div class="road-mark"></div>
  <header class="hero">
    <div class="brand">
      <div class="brand-mark">TMP</div>
      <div>
        <div class="eyebrow">TRUCKERSMP · ETS2</div>
        <h1>{{ title }}</h1>
      </div>
    </div>
    <div class="hero-meta">
      <strong>TOP 10</strong>
      <span>{{ subtitle }}</span>
    </div>
  </header>

  {% if items|length > 0 %}
  <div class="section-label">CHAMPION</div>
  <div class="champion">
    <div class="medal">01</div>
    <div class="player">
      <div class="player-name">{{ items[0].name }}</div>
      <div class="player-id">TMP ID · {{ items[0].tmp_id }}</div>
    </div>
    <div class="mileage">
      <strong>{{ items[0].km_text }}</strong>
      <span>KILOMETERS</span>
    </div>
  </div>
  {% endif %}

  {% if items|length > 1 %}
  <div class="runner-grid">
    <div class="runner-card silver">
      <div class="medal">02</div>
      <div>
        <div class="player-name">{{ items[1].name }}</div>
        <div class="player-id">TMP ID · {{ items[1].tmp_id }}</div>
      </div>
      <div class="mileage"><strong>{{ items[1].km_text }}</strong><span>KM</span></div>
    </div>
    {% if items|length > 2 %}
    <div class="runner-card bronze">
      <div class="medal">03</div>
      <div>
        <div class="player-name">{{ items[2].name }}</div>
        <div class="player-id">TMP ID · {{ items[2].tmp_id }}</div>
      </div>
      <div class="mileage"><strong>{{ items[2].km_text }}</strong><span>KM</span></div>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% set remaining = items|length - 3 %}
  {% if remaining > 0 %}
  <div class="section-label">LEADERBOARD · 04–{{ items|length }}</div>
  <div class="rows">
    {% for it in items if it.rank > 3 %}
    <div class="row">
      <div class="row-rank">{{ '%02d' % it.rank }}</div>
      <div>
        <div class="player-name">{{ it.name }}</div>
        <div class="player-id">TMP ID · {{ it.tmp_id }}</div>
      </div>
      <div class="mileage"><strong>{{ it.km_text }}</strong><span>KM</span></div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if me %}
  <div class="me-card">
    <div>
      <div class="me-label">MY POSITION</div>
      <div class="me-name">{{ me.name }}</div>
      <div class="me-sub">TMP ID · {{ me.tmp_id }}{% if me.vtc_role %} · {{ me.vtc_role }}{% endif %}</div>
    </div>
    <div class="me-values">
      <strong>{{ me.km_text }} KM</strong>
      <span>{% if me.rank is not none %}RANK #{{ me.rank }}{% else %}{{ scope }}{% endif %}</span>
    </div>
  </div>
  {% endif %}

  <footer class="footer">
    <span><b>LIVE DATA</b> · TRUCKERSMP MILEAGE</span>
    <span>{{ scope }} · TOP 10</span>
  </footer>
</div>
"""

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


def _is_unknown_display_value(value: Optional[str]) -> bool:
    """判断展示值是否应当被忽略。"""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    return s == "" or s.lower() in {"未知", "unknown", "null", "none"}
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
            dt_bj = (
                dt.astimezone(BEIJING_TZ)
                if dt.tzinfo is not None
                else dt.replace(tzinfo=BEIJING_TZ)
            )
            return dt_bj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return s

def _normalize_heading_to_direction(heading: Any) -> Optional[str]:
    """把角度值转换为方向字符串，如 0°≈北、90°≈东，并附带箭头符号。"""
    if heading is None:
        return None
    try:
        if isinstance(heading, dict):
            for key in ('heading', 'angle', 'yaw', 'rotation', 'bearing', 'direction'):
                if key in heading:
                    heading = heading.get(key)
                    break
            else:
                return None
        if isinstance(heading, str):
            heading = heading.strip()
            if not heading:
                return None
            heading = float(heading)
        angle = float(heading)
        if math.isnan(angle) or math.isinf(angle):
            return None
        normalized = ((angle % 360) + 360) % 360
        directions = [
            ("↑", "北"),
            ("↗", "东北"),
            ("→", "东"),
            ("↘", "东南"),
            ("↓", "南"),
            ("↙", "西南"),
            ("←", "西"),
            ("↖", "西北"),
        ]
        idx = int((normalized + 22.5) % 360 / 45)
        arrow, text = directions[idx]
        return f"{arrow} {text}"
    except Exception:
        return None


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

@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.9.0", "https://github.com/BGYdook/astrbot-plugin-tmp-bot")
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

        self._tmp_update_state_file = os.path.join(
            os.path.dirname(self.bind_file) or os.getcwd(),
            'tmp_plugin_update_state.json',
        )
        self._tmp_update_state: Dict[str, Any] = {}
        self._tmp_update_groups: Dict[str, Dict[str, str]] = {}
        self._tmp_update_task: Optional[asyncio.Task] = None

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

    # --- 自定义数据源 ---
    # 内置 API 源（按优先级排列）。用户可在插件配置里用 extra_api_bases 追加自己的源，
    # 追加的源会排在列表最前（优先尝试），内置源自动降级为兜底。
    DEFAULT_API_BASES = ("https://evmapi.cxnnn.cn", "https://evmapi.114512.xyz")
    # VTC 历史接口使用相同的源优先级
    VTC_HISTORY_API_BASES = DEFAULT_API_BASES

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
            host = item.split("://", 1)[-1].split("/", 1)[0]
            if "." not in host:
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

    def _tile_url(self, layer: str, default: str) -> str:
        """地图瓦片地址：用户自定义的优先，否则用传入的默认值。

        自定义地址必须带 `{z}` / `{x}` / `{y}` 占位符，否则忽略并回退默认值。
        """
        raw = self._cfg_str(f'extra_tile_{layer}_url', '').strip()
        if not raw:
            return default
        if not raw.lower().startswith(("http://", "https://")):
            raw = "https://" + raw
        missing = [k for k in ("{z}", "{x}", "{y}") if k not in raw]
        if missing:
            logger.warning(f"忽略无效的 {layer} 瓦片地址（缺少 {'/'.join(missing)} 占位符）: {raw}")
            return default
        return raw

    async def initialize(self):
        # 统一 User-Agent，并更新版本号
        timeout_sec = self._cfg_int('api_timeout_seconds', 10)
        # 使用 IPv4 优先的连接器，并允许读取环境代理设置（与浏览器/系统行为更一致）
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'astrBot-TMP-Plugin/1.9.0'}, 
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
            connector=connector,
            trust_env=True
        )
        logger.info(f"TMP Bot 插件HTTP会话已创建，超时 {timeout_sec}s")
        logger.info(f"TMP Bot 插件 API 源（按优先级）: {' -> '.join(self._api_bases())}")
        self._fullmap_task = None
        self._load_tmp_update_state()
        self._start_tmp_update_task()


    def _get_fullmap_interval(self) -> int:
        v = self._cfg_int('ets2map_fullmap_interval_seconds', 60)
        return 60 if v < 60 else v

    def _start_fullmap_task(self) -> None:
        if self._fullmap_task and not self._fullmap_task.done():
            return
        self._fullmap_task = asyncio.create_task(self._fullmap_loop())

    async def _fullmap_loop(self) -> None:
        try:
            await asyncio.sleep(self._get_fullmap_interval())
            while True:
                await self._fetch_fullmap()
                await asyncio.sleep(self._get_fullmap_interval())
        except Exception as e:
            logger.error(f"全局发送文件清单消息失败: {e}")

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

    TMP_VERSION_API = "https://api.truckersmp.com/v2/version"
    TMP_UPDATE_MAX_NOTIFY_ATTEMPTS = 10

    @staticmethod
    def _as_config_bool(value: Any, default: bool) -> bool:
        """更宽容地解析布尔配置（兼容 WebUI 传入的 "true"/"false" 字符串）。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("1", "true", "yes", "on", "是", "开启", "启用"):
                return True
            if s in ("0", "false", "no", "off", "否", "关闭", "禁用"):
                return False
        return default

    def _tmp_update_enabled(self) -> bool:
        return self._as_config_bool(self.config.get('tmp_update_check_enable', True), True)

    def _tmp_update_notify_first_run(self) -> bool:
        return self._as_config_bool(self.config.get('tmp_update_notify_first_run', False), False)

    def _tmp_update_interval_seconds(self) -> int:
        try:
            minutes = int(self.config.get('tmp_update_check_interval_minutes', 30))
        except Exception:
            minutes = 30
        if minutes < 5:
            minutes = 5
        return minutes * 60

    def _tmp_update_send_delay(self) -> float:
        try:
            delay = float(self.config.get('tmp_update_send_delay_seconds', 2))
        except Exception:
            delay = 2.0
        return min(max(delay, 0.0), 30.0)

    def _parse_tmp_update_excludes(self) -> set:
        """解析「不接收更新通知的群号」，支持中英文逗号、空格、换行分隔。"""
        raw = self._cfg_str('tmp_update_exclude_groups', '')
        raw = re.sub(r"#[^\n]*", "", raw)
        excludes = set()
        for chunk in re.split(r"[,，;；\s]+", raw):
            item = chunk.strip()
            if not item or item.startswith('#'):
                continue
            if item.startswith('群') and item[1:].isdigit():
                item = item[1:]
            excludes.add(item)
        return excludes

    @staticmethod
    def _tmp_update_origin_group_id(origin: str) -> str:
        try:
            parts = str(origin).split(':')
            if len(parts) >= 3:
                return parts[2].split('_')[-1]
        except Exception:
            pass
        return ''

    @staticmethod
    def _tmp_version_key(snapshot: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
        if not isinstance(snapshot, dict):
            return ("", "", "")
        return (
            str(snapshot.get('name') or ''),
            str(snapshot.get('ets2') or ''),
            str(snapshot.get('ats') or ''),
        )

    @staticmethod
    def _tmp_major_minor(version: str) -> str:
        """提取 1.61.3.18s 这类版本号的主次版本（1.61）。"""
        m = re.match(r"^\s*(\d+)\.(\d+)", str(version or ""))
        return f"{m.group(1)}.{m.group(2)}" if m else ""

    @classmethod
    def _format_tmp_update_message(cls, snapshot: Dict[str, Any]) -> str:
        version = str(snapshot.get('name') or '未知')
        official_raw = str(snapshot.get('official') or '').strip()
        official = official_raw or '未知'
        ets2 = str(snapshot.get('ets2') or '未知')
        ats = str(snapshot.get('ats') or '未知')

        if not official_raw or official_raw == '未知':
            ets2_ok = '未知'
            ats_ok = '未知'
        else:
            # 欧卡：官方 Steam 版本必须与 TMP 支持的版本完全一致
            ets2_ok = '✅' if ets2 != '未知' and official_raw == ets2 else '❌'
            # 美卡：接口没有单独提供美卡官方版本，按主次版本号（如 1.61）判断
            official_mm = cls._tmp_major_minor(official_raw)
            ats_mm = cls._tmp_major_minor(ats)
            ats_ok = '✅' if ats != '未知' and official_mm and official_mm == ats_mm else '❌'

        return (
            "检测到联机插件有更新!\n"
            f"联机插件版本: {version}\n"
            f"支持欧卡版本: {ets2}\n"
            f"支持美卡版本: {ats}\n"
            "-----------------------------\n"
            f"📊 官方Steam版本: {official}\n"
            f"🎮 欧卡兼容: {ets2_ok}\n"
            f"🎮 美卡兼容: {ats_ok}"
        )

    def _load_tmp_update_state(self) -> None:
        self._tmp_update_state = {}
        self._tmp_update_groups = {}
        try:
            if os.path.exists(self._tmp_update_state_file):
                with open(self._tmp_update_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._tmp_update_state = data
        except Exception as e:
            logger.error(f"读取联机插件更新状态失败: {e}")

        groups = self._tmp_update_state.get('groups')
        if isinstance(groups, dict):
            for origin, info in groups.items():
                if not isinstance(origin, str) or not isinstance(info, dict):
                    continue
                group_id = str(info.get('group_id') or self._tmp_update_origin_group_id(origin) or '')
                if not group_id:
                    continue
                self._tmp_update_groups[origin] = {
                    'platform_id': str(info.get('platform_id') or origin.split(':', 1)[0]),
                    'group_id': group_id,
                    'name': str(info.get('name') or ''),
                }

        last = self._tmp_update_state.get('last_snapshot')
        if isinstance(last, dict) and last.get('name'):
            logger.info(
                "联机插件版本基线: "
                f"{last.get('name')}（欧卡 {last.get('ets2') or '未知'} / 美卡 {last.get('ats') or '未知'}）"
            )

    def _save_tmp_update_state(self) -> None:
        try:
            self._tmp_update_state['schema'] = 1
            self._tmp_update_state['groups'] = self._tmp_update_groups
            directory = os.path.dirname(self._tmp_update_state_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp_path = self._tmp_update_state_file + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._tmp_update_state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._tmp_update_state_file)
        except Exception as e:
            logger.error(f"保存联机插件更新状态失败: {e}")

    # --- 群聊记录与发现 ---

    def _remember_tmp_update_group(self, event: Any) -> None:
        """从收到的群消息中记录群会话，作为 OneBot 群列表接口不可用时的兜底。"""
        try:
            get_group_id = getattr(event, 'get_group_id', None)
            group_id = get_group_id() if callable(get_group_id) else ''
            if not group_id:
                return
            origin = str(getattr(event, 'unified_msg_origin', '') or '')
            if not origin:
                session = getattr(event, 'session', None)
                if session is not None:
                    origin = str(session)
            if not origin:
                return
            platform_id = ''
            get_platform_id = getattr(event, 'get_platform_id', None)
            if callable(get_platform_id):
                platform_id = str(get_platform_id() or '')
            info = {
                'platform_id': platform_id or origin.split(':', 1)[0],
                'group_id': str(group_id),
                'name': str((self._tmp_update_groups.get(origin) or {}).get('name') or ''),
            }
            self._tmp_update_groups[origin] = info
        except Exception:
            pass

    async def _discover_tmp_update_groups(self) -> Dict[str, Dict[str, str]]:
        """获取需要推送的群会话。

        优先使用 aiocqhttp(OneBot) 的 get_group_list（能拿到机器人所在的全部群），
        同时合并从历史消息中记录到的群；如果某个平台能成功拉到群列表，则以实时列表为准，
        避免机器人退群后仍向旧群重试。
        """
        known: Dict[str, Dict[str, str]] = {}
        for origin, info in self._tmp_update_groups.items():
            if origin and info.get('group_id'):
                known[origin] = dict(info)

        live: Dict[str, Dict[str, str]] = {}
        confirmed_platforms = set()
        insts = []
        try:
            manager = getattr(self.context, 'platform_manager', None)
            if manager is not None:
                insts = manager.get_insts() or []
        except Exception as e:
            logger.warning(f"获取平台列表失败，将只使用已记录的群: {e}")

        for platform in insts:
            try:
                meta = platform.meta()
            except Exception:
                continue
            if getattr(meta, 'name', '') != 'aiocqhttp':
                continue
            platform_id = str(getattr(meta, 'id', '') or '')
            if not platform_id:
                continue
            bot = getattr(platform, 'bot', None)
            if bot is None or not hasattr(bot, 'call_action'):
                continue
            try:
                group_list = await asyncio.wait_for(
                    bot.call_action(action='get_group_list'), timeout=15
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"获取群列表失败（平台 {platform_id}），将使用已记录的群: {e}")
                continue
            if not isinstance(group_list, list):
                logger.warning(f"群列表接口返回格式异常（平台 {platform_id}），将使用已记录的群")
                continue
            confirmed_platforms.add(platform_id)
            for item in group_list:
                if not isinstance(item, dict):
                    continue
                group_id = item.get('group_id') or item.get('groupId')
                if group_id is None:
                    continue
                group_id = str(group_id)
                origin = f"{platform_id}:GroupMessage:{group_id}"
                live[origin] = {
                    'platform_id': platform_id,
                    'group_id': group_id,
                    'name': str(item.get('group_name') or item.get('groupName') or ''),
                }

        groups = {
            origin: info
            for origin, info in known.items()
            if info.get('platform_id') not in confirmed_platforms
        }
        groups.update(live)
        self._tmp_update_groups = dict(groups)
        return groups

    def _is_tmp_update_group_excluded(
        self,
        origin: str,
        info: Dict[str, str],
        excludes: set,
    ) -> bool:
        if not excludes:
            return False
        group_id = str(info.get('group_id') or '')
        platform_id = str(info.get('platform_id') or '')
        candidates = {origin, group_id}
        if platform_id and group_id:
            candidates.add(f"{platform_id}:GroupMessage:{group_id}")
            candidates.add(f"{platform_id}:{group_id}")
        if platform_id:
            candidates.add(f"{platform_id}:*")
        candidates.add('*')
        return bool(candidates & excludes)

    async def _fetch_tmp_plugin_version(self) -> Optional[Dict[str, Any]]:
        if not self.session:
            return None
        timeout = self._cfg_int('api_timeout_seconds', 10)
        try:
            async with self.session.get(self.TMP_VERSION_API, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.warning(f"检测联机插件版本失败: 错误代码 HTTP {resp.status}")
                    return None
                data = await resp.json(content_type=None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"检测联机插件版本请求异常: {e}")
            return None

        if not isinstance(data, dict):
            logger.warning("检测联机插件版本失败: 接口返回格式异常")
            return None
        name = data.get('name') or data.get('version')
        if not name:
            logger.warning(f"检测联机插件版本失败: 缺少版本号，返回内容 {str(data)[:200]}")
            return None
        return {
            'name': str(name),
            'ets2': str(data.get('supported_game_version') or '未知'),
            'ats': str(data.get('supported_ats_game_version') or '未知'),
            'numeric': str(data.get('numeric') or ''),
            'stage': str(data.get('stage') or ''),
            'api_time': str(data.get('time') or ''),
        }

    async def _fetch_tmp_official_game_version(self) -> str:
        """获取 Steam 官方游戏版本（欧卡）。

        数据来自插件内置/自定义 API 源的 /other/tmpVersion 接口；
        该值只用于展示「官方Steam版本」，不参与更新判断。
        接口不可用时返回空字符串，通知里显示为「未知」。
        """
        if not self.session:
            return ''
        timeout = self._cfg_int('api_timeout_seconds', 10)
        for base in self._api_bases():
            url = f"{base}/other/tmpVersion"
            try:
                async with self.session.get(url, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    payload = await resp.json(content_type=None)
            except asyncio.CancelledError:
                raise
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            code = payload.get('code')
            if code not in (None, 200, '200'):
                continue
            data = payload.get('data')
            official = None
            if isinstance(data, dict):
                official = data.get('officialGameVersion')
            if not official:
                official = payload.get('officialGameVersion')
            if official:
                return str(official)
        logger.warning("获取官方 Steam 版本失败，通知中将显示为未知")
        return ''

    def _start_tmp_update_task(self) -> None:
        if not self._tmp_update_enabled():
            logger.info("联机插件自动更新检测已关闭")
            return
        if self._tmp_update_task and not self._tmp_update_task.done():
            return
        self._tmp_update_task = asyncio.create_task(self._tmp_update_loop())
        logger.info(
            "联机插件自动更新检测已启动，"
            f"检测间隔 {self._tmp_update_interval_seconds() // 60} 分钟"
        )

    async def _tmp_update_loop(self) -> None:
        try:
            await asyncio.sleep(min(30, self._tmp_update_interval_seconds()))
            while True:
                try:
                    await self._check_tmp_plugin_update()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"联机插件自动更新检测异常: {e}", exc_info=True)
                await asyncio.sleep(self._tmp_update_interval_seconds())
        except asyncio.CancelledError:
            logger.info("联机插件自动更新检测任务已停止")
            raise

    async def _check_tmp_plugin_update(self) -> None:
        snapshot = await self._fetch_tmp_plugin_version()
        if not snapshot:
            return

        prev = self._tmp_update_state.get('last_snapshot')
        prev_key = self._tmp_version_key(prev)
        new_key = self._tmp_version_key(snapshot)
        now_ts = time.time()

        pending = self._tmp_update_state.get('pending')
        if not isinstance(pending, dict) or not isinstance(pending.get('snapshot'), dict):
            pending = None

        if not any(prev_key):
            logger.info(
                "已记录联机插件版本基线: "
                f"{new_key[0]}（欧卡 {new_key[1]} / 美卡 {new_key[2]}）"
            )
            pending = (
                {'snapshot': snapshot, 'notified': [], 'attempts': 0}
                if self._tmp_update_notify_first_run()
                else None
            )
            self._tmp_update_state['last_snapshot'] = snapshot
            self._tmp_update_state['last_check_ts'] = now_ts
            self._tmp_update_state['pending'] = pending
            self._save_tmp_update_state()
            if pending:
                await self._broadcast_pending_tmp_update(pending)
            return

        if new_key != prev_key:
            logger.info(
                "检测到联机插件更新: "
                f"{prev_key[0]} -> {new_key[0]}"
                f"（欧卡 {prev_key[1]} -> {new_key[1]}，"
                f"美卡 {prev_key[2]} -> {new_key[2]}）"
            )
            pending = {'snapshot': snapshot, 'notified': [], 'attempts': 0}
            self._tmp_update_state['last_snapshot'] = snapshot
        else:
            logger.info(
                "联机插件版本无变化: "
                f"{new_key[0]}（欧卡 {new_key[1]} / 美卡 {new_key[2]}）"
            )

        self._tmp_update_state['last_check_ts'] = now_ts
        self._tmp_update_state['pending'] = pending
        self._save_tmp_update_state()

        if pending:
            await self._broadcast_pending_tmp_update(pending)

    # --- 群推送 ---

    async def _broadcast_pending_tmp_update(self, pending: Dict[str, Any]) -> None:
        snapshot = pending.get('snapshot') or {}
        notified = pending.get('notified')
        if not isinstance(notified, list):
            notified = []
        notified_set = {str(x) for x in notified if x}
        pending['notified'] = sorted(notified_set)

        if not hasattr(self.context, 'send_message'):
            logger.warning("当前 AstrBot 版本不允许主动发送消息，无法推送联机插件更新通知")
            return

        all_groups = await self._discover_tmp_update_groups()
        excludes = self._parse_tmp_update_excludes()

        targets: List[Tuple[str, Dict[str, str]]] = []
        excluded_count = 0
        skipped_count = 0
        for origin, info in all_groups.items():
            if self._is_tmp_update_group_excluded(origin, info, excludes):
                excluded_count += 1
                continue
            if origin in notified_set:
                skipped_count += 1
                continue
            targets.append((origin, info))

        if not targets:
            if not all_groups:
                logger.warning("未发现可用群聊，联机插件更新通知将在下次检测时重试")
                return
            logger.info(
                "联机插件更新通知无需发送："
                f"已发送 {skipped_count} 个群，已排除 {excluded_count} 个群"
            )
            self._tmp_update_state['pending'] = None
            self._save_tmp_update_state()
            return

        # 官方 Steam 版本只在真正推送时查询，避免每次检测都多请求一次
        if not snapshot.get('official'):
            official = await self._fetch_tmp_official_game_version()
            if official:
                snapshot['official'] = official
                pending['snapshot'] = snapshot
                self._save_tmp_update_state()

        message = self._format_tmp_update_message(snapshot)
        delay = self._tmp_update_send_delay()
        sent = 0
        failed: List[str] = []

        logger.info(
            "开始推送联机插件更新通知："
            f"目标 {len(targets)} 个群，已排除 {excluded_count} 个群，"
            f"版本 {snapshot.get('name') or '未知'}"
        )

        for index, (origin, info) in enumerate(targets):
            label = info.get('name') or info.get('group_id') or origin
            try:
                ok = await asyncio.wait_for(
                    self.context.send_message(
                        origin,
                        MessageEventResult().message(message),
                    ),
                    timeout=30,
                )
                if ok is False:
                    raise RuntimeError("未找到匹配的平台适配器")
                notified_set.add(origin)
                pending['notified'] = sorted(notified_set)
                self._save_tmp_update_state()
                sent += 1
                logger.info(f"已推送联机插件更新通知到群 {label}（{origin}）")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed.append(origin)
                logger.error(f"推送联机插件更新通知到群 {label}（{origin}）失败: {e}")

            if delay > 0 and index < len(targets) - 1:
                await asyncio.sleep(delay)

        self._tmp_update_state['last_notify_ts'] = time.time()
        if failed:
            pending['attempts'] = int(pending.get('attempts') or 0) + 1
            attempts = pending['attempts']
            if attempts >= self.TMP_UPDATE_MAX_NOTIFY_ATTEMPTS:
                logger.error(
                    "联机插件更新通知连续发送失败 "
                    f"{attempts} 次，放弃剩余 {len(failed)} 个群："
                    + ", ".join(failed[:10])
                )
                self._tmp_update_state['pending'] = None
            else:
                self._tmp_update_state['pending'] = pending
                logger.warning(
                    "联机插件更新通知本轮发送完成："
                    f"成功 {sent} 个，失败 {len(failed)} 个，"
                    "失败的群将在下次检测时重试"
                )
        else:
            self._tmp_update_state['pending'] = None
            logger.info(f"联机插件更新通知已推送到 {sent} 个群")
        self._save_tmp_update_state()

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

    LANGUAGE_MAP_EN_TO_CN = {
        "english": "英语",
        "chinese (simplified)": "简体中文",
        "chinese (traditional)": "繁体中文",
        "french": "法语",
        "german": "德语",
        "russian": "俄语",
        "spanish": "西班牙语",
        "portuguese": "葡萄牙语",
        "italian": "意大利语",
        "polish": "波兰语",
        "czech": "捷克语",
        "slovak": "斯洛伐克语",
        "dutch": "荷兰语",
        "danish": "丹麦语",
        "swedish": "瑞典语",
        "norwegian": "挪威语",
        "finnish": "芬兰语",
        "estonian": "爱沙尼亚语",
        "latvian": "拉脱维亚语",
        "lithuanian": "立陶宛语",
        "romanian": "罗马尼亚语",
        "bulgarian": "保加利亚语",
        "greek": "希腊语",
        "hungarian": "匈牙利语",
        "turkish": "土耳其语",
        "ukrainian": "乌克兰语",
        "arabic": "阿拉伯语",
        "japanese": "日语",
        "korean": "韩语",
    }

    EVENT_TYPE_MAP_EN_TO_CN = {
        "convoy": "车队巡游",
        "truck_show_and_convoy": "卡车展与车队巡游",
        "truckfest and convoy": "卡车展与车队巡游",
        "truckfest": "卡车展",
        "truck show": "卡车展",
        "special event": "特别活动",
    }

    EVENT_LOCATION_MAP_EN_TO_CN = {
        "other": "其他",
        "city": "城市",
        "hotel": "酒店",
        "slots": "停车位",
        "booked slots": "预订停车位",
        "container port": "集装箱港口",
        "any city in the play area": "游戏区域内任意城市",
        "to be determined": "待定",
    }

    COMMON_TEXT_MAP_EN_TO_CN = {
        "truck show and convoy": "卡车展与车队巡游",
        "truckfest and convoy": "卡车展与车队巡游",
        "any city in the play area": "游戏区域内任意城市",
        "to be determined": "待定",
        "booked slots": "预订停车位",
        "container port": "集装箱港口",
        "join our rules": "加入规则",
        "join rules": "加入规则",
        "how to contact us": "联系方式",
        "truck show": "卡车展",
        "truckfest": "卡车展",
        "convoy": "车队巡游",
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
        "frankfurt am main": "法兰克福",
        "frankfurt": "法兰克福",
        "bremen": "不来梅",
        "hamburg": "汉堡",
        "munich": "慕尼黑",
        "nuremberg": "纽伦堡",
        "hanover": "汉诺威",
        "hannover": "汉诺威",
        "rostock": "罗斯托克",
        "athens": "雅典",
        "kavala": "卡瓦拉",
        "lamia": "拉米亚",
        "aarhus": "奥胡斯",
        "gävle": "耶夫勒",
        "gavle": "耶夫勒",
        "pärnu": "派尔努",
        "parnu": "派尔努",
        "vaasa": "瓦萨",
        "poznań": "波兹南",
        "poznan": "波兹南",
        "salzburg": "萨尔茨堡",
        "travemünde": "特拉弗明德",
        "travemunde": "特拉弗明德",
        "eindhoven": "埃因霍温",
        "bern": "伯尔尼",
        "innsbruck": "因斯布鲁克",
        "klagenfurt am wörthersee": "克拉根福",
        "klagenfurt": "克拉根福",
        "liepāja": "利耶帕亚",
        "liepaja": "利耶帕亚",
        "narva": "纳尔瓦",
        "rijeka": "里耶卡",
        "szeged": "塞格德",
        "tirana": "地拉那",
        "istanbul": "伊斯坦布尔",
        "i̇stanbul": "伊斯坦布尔",
        "omaha": "奥马哈",
        "nogales": "诺加莱斯",
        "scottsbluff": "斯科茨布拉夫",
        "show low": "肖洛",
        "wenatchee": "韦纳奇",
        "yakima": "亚基马",
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
            # TruckersMP 官方 API - 直接通过 SteamID 查询玩家信息
            url = f"https://api.truckersmp.com/v2/player/{steam_id}"
            
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('error') is False and data.get('response'):
                        player_data = data.get('response', {})
                        tmp_id = player_data.get('id')
                        
                        if tmp_id:
                            logger.info(f"成功通过 SteamID {steam_id} 获取到 TMP ID: {tmp_id}")
                            return str(tmp_id)
                        else:
                            raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                    else:
                        error_msg = data.get('descriptor', '未知错误')
                        if 'not found' in error_msg.lower() or 'unable to find' in error_msg.lower():
                            raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                        else:
                            raise ApiResponseException(f"API 返回错误: {error_msg}")
                elif response.status == 404:
                    raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                else:
                    raise ApiResponseException(f"Steam ID查询API返回错误状态码: {response.status}")
        except SteamIdNotFoundException:
            raise
        except aiohttp.ClientError:
            raise SteamIdNotFoundException("Steam ID查询服务网络请求失败")
        except asyncio.TimeoutError:
            raise SteamIdNotFoundException("请求 Steam ID 查询服务超时")
        except Exception as e:
            logger.error(f"通过 SteamID 查询 TMP ID 失败: {e}")
            raise SteamIdNotFoundException(f"Steam ID {steam_id} 查询失败，请检查ID是否正确")
            
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

    async def _resolve_tmp_id_for_user_command(
        self,
        event: AstrMessageEvent,
        command_name: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """解析用户命令中的 TMP ID、Steam ID、绑定账号或被 @ 用户。"""
        message_str = event.message_str.strip()
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
            except Exception:
                target_user_id = None

        match = re.search(rf"{re.escape(command_name)}\s*(\d+)?", message_str)
        input_id = match.group(1) if match else None
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    return await self._get_tmp_id_from_steam_id(input_id), None
                except SteamIdNotFoundException as exc:
                    return None, str(exc)
                except NetworkException as exc:
                    return None, f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询"
                except Exception as exc:
                    logger.error(f"违规查询解析 SteamID 失败: {exc}")
                    return None, "SteamID查询失败，请直接使用 TMP ID"
            return input_id, None

        bind_user_id = target_user_id or event.get_sender_id()
        tmp_id = self._get_bound_tmp_id(bind_user_id)
        if tmp_id:
            return str(tmp_id), None
        return None, f"请先绑定账号，或使用 {command_name} [TMP ID]"

    async def _get_game_time(self) -> Dict[str, Any]:
        if not self.session:
            raise NetworkException("插件初始化中，请稍后重试")
        url = "https://api.truckersmp.com/v2/game_time"
        async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as response:
            if response.status != 200:
                raise ApiResponseException(f"API返回错误状态码: {response.status}")
            data = await response.json()
        if not isinstance(data, dict):
            raise ApiResponseException("游戏时间 API 返回格式异常")
        if data.get('error'):
            raise ApiResponseException(str(data.get('error')))
        payload = data.get('response') if isinstance(data.get('response'), dict) else data
        game_time = payload.get('game_time')
        if game_time is None:
            raise ApiResponseException("游戏时间 API 未返回 game_time")
        try:
            game_minutes = float(game_time)
        except (TypeError, ValueError):
            raise ApiResponseException("游戏时间 API 返回值无效")
        return {
            'game_time': game_minutes,
            'game_datetime': TMP_GAME_EPOCH + timedelta(minutes=game_minutes),
        }

    async def _get_tmp_api_json(self, path: str, resource_name: str) -> Any:
        if not self.session:
            raise NetworkException("插件初始化中，请稍后重试")
        url = f"https://api.truckersmp.com/v2/{path.lstrip('/')}"
        async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as response:
            if response.status == 404:
                raise ApiResponseException(f"{resource_name}不存在")
            if response.status != 200:
                raise ApiResponseException(f"API返回错误状态码: {response.status}")
            data = await response.json()
        if not isinstance(data, dict):
            raise ApiResponseException(f"{resource_name} API 返回格式异常")
        if data.get('error'):
            detail = data.get('message') or data.get('error')
            raise ApiResponseException(f"{resource_name}查询失败: {detail}")
        return data

    async def _get_today_events(self) -> List[Dict[str, Any]]:
        data = await self._get_tmp_api_json('events', '活动')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("活动 API 返回格式异常")
        today_events = response.get('today') or []
        if not isinstance(today_events, list):
            return []
        unique_events = []
        seen_ids = set()
        for event in today_events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get('id') or '').strip()
            if not event_id or event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            unique_events.append(event)
        return unique_events

    async def _get_event_detail(self, event_id: str) -> Dict[str, Any]:
        data = await self._get_tmp_api_json(f"events/{event_id}", '活动')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("活动 API 返回格式异常")
        return response

    async def _get_vtc_detail(self, vtc_id: str) -> Dict[str, Any]:
        data = await self._get_tmp_api_json(f"vtc/{vtc_id}", 'VTC')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("VTC API 返回格式异常")
        return response

    async def _get_player_stats(self, tmp_id: str) -> Dict[str, Any]:
        """通过 VTCM 里程 API 获取玩家的总里程、今日里程和头像。
        API 源取自 `_api_bases()`（用户自定义源优先，内置源兜底）。
        """
        if not self.session:
            return {'total_km': 0, 'daily_km': 0, 'avatar_url': '', 'debug_error': 'HTTP会话不可用。'}

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

        def _to_int_rank(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return val
                if isinstance(val, float):
                    return int(val)
                s = str(val).strip()
                if s == '':
                    return None
                return int(float(s))
            except Exception:
                return None

        for vtcm_base in self._api_bases():
            vtcm_stats_url = f"{vtcm_base}/player/info?tmpId={tmp_id}"
            logger.info(f"尝试 VTCM 里程 API: {vtcm_stats_url}")
            try:
                async with self.session.get(
                    vtcm_stats_url,
                    timeout=self._cfg_int('api_timeout_seconds', 10),
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        logger.info(f"VTCM 里程 API 返回非 200 状态: status={response.status}")
                        continue

                    data = await response.json()
                    response_data = data.get('data', {})
                    logger.info(f"VTCM 里程响应: status=200, code={data.get('code')}, has_data={bool(response_data)}")

                    total_raw = response_data.get('mileage')
                    daily_raw = response_data.get('todayMileage')
                    total_km = _to_km_2f(total_raw, 0.0)
                    daily_km = _to_km_2f(daily_raw, 0.0)
                    avatar_url = response_data.get('avatarUrl', '')
                    vtc_role = response_data.get('vtcRole') or response_data.get('vtc_role')

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
                    last_online = (
                        response_data.get('lastOnline')
                        or response_data.get('lastOnlineTime')
                        or response_data.get('last_login')
                        or response_data.get('lastLogin')
                        or None
                    )
                    logger.info(
                        f"VTCM 里程解析: total_km={total_km:.2f}, today_km={daily_km:.2f}, "
                        f"total_rank={total_rank}, daily_rank={daily_rank}, avatar={avatar_url}"
                    )

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
                        'debug_error': 'VTCM 里程数据获取成功。',
                        'debug_source': vtcm_stats_url,
                    }
            except aiohttp.ClientError as e:
                logger.warning(f"VTCM 里程 API 网络异常({vtcm_stats_url}): {e}")
            except Exception as e:
                logger.warning(f"VTCM 里程 API 失败({vtcm_stats_url}): {e}")

        logger.warning(f"VTCM 里程 API 全部失败: tmpId={tmp_id}")
        return {
            'total_km': 0,
            'daily_km': 0,
            'avatar_url': '',
            'vtcRole': None,
            'total_rank': None,
            'daily_rank': None,
            'debug_source': None,
            'debug_error': '所有 VTCM 里程 API 备用源均失败。',
        }


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
        """获取 TruckersMP 里程排行榜列表 (使用第三方 VTCM API)。

        ranking_type:
            - "total": 总里程排行
            - "today": 今日里程排行

        API 源取自 `_api_bases()`（用户自定义源优先，内置源兜底）。
        """
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        # 第三方接口使用数字枚举：1=总里程，2=今日里程
        type_code = 2 if str(ranking_type).lower() in ["today", "daily", "2"] else 1

        last_error: Optional[Exception] = None
        for base in self._api_bases():
            url = f"{base}/statistics/mileageRankingList?rankingType={type_code}&rankingCount={limit}"
            logger.info(f"尝试 API (排行榜): type={ranking_type}({type_code}), url={url}")
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list):
                            response_data = data
                        elif isinstance(data, dict):
                            code = data.get('code')
                            try:
                                code_ok = code is None or int(code) == 200
                            except (TypeError, ValueError):
                                code_ok = False
                            payload = data.get('data')
                            response_data = payload if code_ok else None
                        else:
                            response_data = None
                        if isinstance(response_data, list):
                            if response_data:
                                return response_data
                            last_error = ApiResponseException(f"排行榜 API 暂无数据: {base}")
                            logger.info(f"排行榜 API 源 {base} 返回空列表，尝试下一个源")
                            continue
                        raise ApiResponseException("排行榜 API 数据结构异常")

                    elif response.status == 404:
                        logger.info(f"排行榜 API 源 {base} 不存在该接口，尝试下一个源")
                        last_error = ApiResponseException(f"排行榜 API 源不支持: {base}")
                    else:
                        logger.info(f"排行榜 API 源 {base} 返回状态码 {response.status}，尝试下一个源")
                        last_error = ApiResponseException(f"排行榜 API 返回错误状态码: {response.status}")
            except aiohttp.ClientError as e:
                logger.error(f"排行榜 API 网络请求失败 ({base}, aiohttp.ClientError): {e}")
                last_error = NetworkException("排行榜 API 网络请求失败")
            except asyncio.TimeoutError:
                logger.error(f"请求排行榜 API 超时 ({base})")
                last_error = NetworkException("请求排行榜 API 超时")
            except ApiResponseException as e:
                last_error = e
            except Exception as e:
                logger.error(f"查询排行榜时发生未知错误 ({base}): {e}", exc_info=True)
                last_error = NetworkException("查询排行榜失败")

        if isinstance(last_error, NetworkException):
            raise last_error
        if isinstance(last_error, ApiResponseException):
            raise last_error
        raise NetworkException("排行榜 API 网络请求失败")

    async def _get_dlc_market_list(self, dlc_type: int = 1) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        last_error: Optional[Exception] = None
        saw_valid_empty = False
        for base in self._api_bases():
            url = f"{base}/dlc/list?type={dlc_type}"
            logger.info(f"DLC列表: 请求 URL={url}")
            try:
                async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    logger.info(f"DLC列表: 响应 status={resp.status}, content-type={resp.headers.get('Content-Type')}")
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            code = data.get('code')
                            try:
                                code_ok = code is None or int(code) == 200
                            except (TypeError, ValueError):
                                code_ok = False
                            payload = data.get('data') or data.get('response') or data.get('result')
                            items = payload if isinstance(payload, list) else []
                            if not code_ok:
                                items = []
                        else:
                            items = []
                        logger.info(f"DLC列表: 解析到 items_count={len(items)}")
                        if items:
                            return items
                        if isinstance(data, (list, dict)):
                            saw_valid_empty = True
                        last_error = ApiResponseException(f"DLC列表 API 源无有效数据: {base}")
                        logger.info(f"DLC列表: 源 {base} 无有效数据，尝试下一个源")
                        continue
                    logger.info(f"DLC列表: 源 {base} 返回状态码 {resp.status}，尝试下一个源")
                    last_error = ApiResponseException(f"DLC列表 API 返回错误状态码: {resp.status}")
            except aiohttp.ClientError as e:
                logger.error(f"DLC列表 API 网络请求失败 ({base}, aiohttp.ClientError): {e}")
                last_error = NetworkException("DLC列表 API 网络请求失败")
            except asyncio.TimeoutError:
                logger.error(f"请求 DLC列表 API 超时 ({base})")
                last_error = NetworkException("请求 DLC列表 API 超时")
            except ApiResponseException as e:
                last_error = e
            except Exception as e:
                logger.error(f"查询 DLC列表 时发生未知错误 ({base}): {e}", exc_info=True)
                last_error = NetworkException("查询 DLC列表 失败")

        if saw_valid_empty:
            return []
        if isinstance(last_error, NetworkException):
            raise last_error
        if isinstance(last_error, ApiResponseException):
            raise last_error
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

    def _footprint_api_bases(self) -> List[str]:
        """返回足迹接口源；旧版单项配置仍可作为自定义源覆盖。"""
        legacy_base = self._cfg_str('footprint_api_base', '').strip()
        if legacy_base:
            return self._merge_api_bases(legacy_base, self._api_bases())
        return self._api_bases()

    async def _get_footprint_history(self, tmp_id: str, server_id: Optional[str], start_time: str, end_time: str) -> List[Dict[str, Any]]:
        if not self.session:
            return []
        sid = str(server_id or "").strip()
        params = {
            'tmpId': str(tmp_id).strip(),
            'startTime': str(start_time).strip(),
            'endTime': str(end_time).strip()
        }
        if sid:
            params['serverId'] = sid
        for base in self._footprint_api_bases():
            url = f"{base}/map/playerHistory"
            try:
                logger.debug(f"足迹历史: 请求 {url} params={params}")
                async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status != 200:
                        logger.debug(f"足迹历史: 源 {base} 返回状态码 {resp.status}，尝试下一个源")
                        continue
                    data = await resp.json()
            except Exception as e:
                logger.debug(f"足迹历史: 源 {base} 请求异常: {e}")
                continue
            if isinstance(data, list):
                if data:
                    return data
                continue
            if not isinstance(data, dict):
                continue
            code = data.get('code')
            try:
                code_ok = code is None or int(code) == 200
            except (TypeError, ValueError):
                code_ok = False
            if not code_ok:
                logger.info(f"足迹历史: 源 {base} 返回业务错误 code={code}")
                continue
            payload = data.get('data') or data.get('response') or data.get('result')
            if isinstance(payload, list) and payload:
                return payload
        return []

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
                    if s.endswith('Z') or re.search(r'[+-]\d{2}:\d{2}$', s):
                        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=BEIJING_TZ)
                    ts_val = int(dt.astimezone(BEIJING_TZ).timestamp())
                except Exception:
                    try:
                        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=BEIJING_TZ)
                        ts_val = int(dt.astimezone(BEIJING_TZ).timestamp())
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
        server_ids = server_ids or []
        server_ids = [str(s).strip() for s in server_ids if str(s).strip()]
        urls = []
        for base in self._footprint_api_bases():
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
                logger.debug(f"足迹接口: 请求 {url}")
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

    async def _get_vtc_history(self, tmp_id: str) -> List[Dict[str, Any]]:
        """查询玩家的历史VTC（车队）记录。
        主接口: TruckyApp v2/truckersmp/player（含 vtc + vtcHistory）
        备用: 用户自定义源 + 内置源 evmapi.cxnnn.cn / evmapi.114512.xyz
        最后回退: TruckersMP 官方 API
        """
        if not self.session:
            return []

        def _build_item(name: str, tag: str = '', role: str = '',
                        join_date: str = '', leave_date: str = '') -> Dict[str, Any]:
            return {'vtcName': name, 'vtcTag': tag, 'role': role,
                    'joinDate': join_date, 'leaveDate': leave_date}

        # 1) TruckyApp truckersmp/player — 双层包装 {response: {error: false, response: {vtc, vtcHistory}}}
        try:
            url = f"https://api.truckyapp.com/v2/truckersmp/player?playerID={tmp_id}"
            logger.info(f"VTC历史: TruckyApp -> {url}")
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    outer = data.get('response', data) if isinstance(data, dict) else {}
                    inner = outer.get('response') if isinstance(outer, dict) else None
                    if isinstance(inner, dict) and outer.get('error') is False:
                        # 检查是否开启了 VTC 历史显示
                        display_vtc_history = inner.get('displayVTCHistory')
                        if display_vtc_history is False:
                            logger.info("VTC历史: 用户设置了VTC历史为私密状态")
                            return None  # None 表示私密
                        result: List[Dict[str, Any]] = []
                        # 不包含当前车队，只返回历史车队
                        history = inner.get('vtcHistory')
                        if isinstance(history, list):
                            for h in history:
                                if isinstance(h, dict):
                                    result.append(_build_item(
                                        name=h.get('name', ''),
                                        tag=h.get('tag', ''),
                                        role=h.get('role', ''),
                                        join_date=h.get('joinDate', ''),
                                        leave_date=h.get('leftDate', ''),
                                    ))
                        if result:
                            logger.info(f"VTC历史: TruckyApp 获取到 {len(result)} 条记录")
                            return result
                        logger.info("VTC历史: TruckyApp 响应中无 VTC 数据")
                    else:
                        logger.info(f"VTC历史: TruckyApp error={outer.get('error')}")
                else:
                    logger.info(f"VTC历史: TruckyApp HTTP {resp.status}")
        except Exception as e:
            logger.error(f"VTC历史: TruckyApp 请求异常: {e}")

        # 2) 第三方 VTCM 源（用户自定义源优先，其后为内置源）
        for base in self._api_bases(self.VTC_HISTORY_API_BASES):
            try:
                url = f"{base}/vtc/history?tmpId={tmp_id}"
                logger.info(f"VTC历史: {base} -> {url}")
                async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get('data') or data.get('response') or []
                        if isinstance(items, list) and items:
                            logger.info(f"VTC历史: {base} 获取到 {len(items)} 条记录")
                            return items
            except Exception as e:
                logger.error(f"VTC历史: {base} 异常: {e}")

        # 不使用官方 API 回退 - 官方 API 只返回当前 VTC，不是历史记录
        return []

    async def _get_vtc_member_role(self, tmp_id: str, vtc_info: Optional[Dict] = None) -> Optional[str]:
        """查询玩家在车队内的角色。
        优先策略：
        1) 尝试使用官方 TruckersMP VTC 角色查询 API: https://api.truckersmp.com/v2/vtc/{vtc_id}/role/{role_id}
        2) 若官方API失败，回退到第三方 VTCM 源的 vtc/memberAll/role 接口
           （源列表取自 `_api_bases()`：用户自定义源优先，内置源兜底）
        3) 若传入 vtc_info 且包含 vtcId，则直接用 vtcId 查询成员列表并匹配 tmpId
        4) 若未传入或未包含 vtcId，则尝试从 TruckersMP player 接口获取 vtc.id
        5) 若仍无 vtcId，尝试直接用 memberAll/role?tmpId=tmp_id 回退查询（部分接口支持）
        6) 若有 vtc 名称但无 vtcId，先通过 /vtc/search?name= 搜索取得 vtcId，再查询成员列表
        返回值：匹配到的角色字符串或 None
        """
        if not self.session:
            return None

        # 0) 优先尝试官方 TruckersMP VTC 角色查询 API
        # 需要先获取 vtc_id 和 role_id
        try:
            # 获取玩家信息以获取 VTC ID
            player_info = await self._get_player_info(tmp_id)
            vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
            vtc_id = vtc.get('id')
            
            if vtc_id:
                # 获取 VTC 信息以获取角色 ID
                vtc_info_url = f"https://api.truckersmp.com/v2/vtc/{vtc_id}"
                logger.info(f"官方VTC查询: 获取VTC信息 {vtc_info_url}")
                async with self.session.get(vtc_info_url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                    if resp.status == 200:
                        vtc_data = await resp.json()
                        if vtc_data.get('error') is False:
                            vtc_response = vtc_data.get('response', {})
                            # 查找玩家在当前VTC中的角色
                            members = vtc_response.get('members', [])
                            for member in members:
                                if str(member.get('user_id', '')) == str(tmp_id):
                                    role_id = member.get('role_id')
                                    if role_id:
                                        # 获取角色详细信息
                                        role_url = f"https://api.truckersmp.com/v2/vtc/{vtc_id}/role/{role_id}"
                                        logger.info(f"官方VTC角色查询: {role_url}")
                                        async with self.session.get(role_url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as role_resp:
                                            if role_resp.status == 200:
                                                role_data = await role_resp.json()
                                                if role_data.get('error') is False:
                                                    role_info = role_data.get('response', {})
                                                    role_name = role_info.get('name')
                                                    if role_name:
                                                        logger.info(f"官方VTC角色查询成功: {role_name}")
                                                        return role_name
                                    break
        except Exception as e:
            logger.info(f"官方VTC角色查询异常: {e}")

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
            for base in self._api_bases():
                try:
                    url_vid = f"{base}/vtc/memberAll/role?vtcId={vtc_id}"
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
        for base in self._api_bases():
            try:
                url_tmp = f"{base}/vtc/memberAll/role?tmpId={tmp_id}"
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
            for base in self._api_bases():
                try:
                    from urllib.parse import quote_plus
                    qname = quote_plus(str(vtc_name))
                    search_url = f"{base}/vtc/search?name={qname}"
                    logger.info(f"VTC 车队搜索: {search_url}")
                    async with self.session.get(search_url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            items = data.get('data') or data.get('response') or []
                            if isinstance(items, list) and items:
                                it = items[0]
                                found_id = it.get('id') or it.get('vtcId') or it.get('vtc_id')
                                if found_id:
                                    vtc_id = found_id
                                    logger.info(f"VTC 搜索结果: name={vtc_name} -> vtcId={vtc_id}")
                                    break
                except Exception as e:
                    logger.info(f"VTC 车队搜索异常: {e}")

            # 如果通过搜索得到 vtc_id，再次用 vtcId 查询成员
            if vtc_id:
                for base in self._api_bases():
                    try:
                        url_vid2 = f"{base}/vtc/memberAll/role?vtcId={vtc_id}"
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
            for base in self._api_bases():
                try:
                    from urllib.parse import quote_plus
                    qname = quote_plus(str(vtc_name))
                    url_name = f"{base}/vtc/memberAll/role?vtcName={qname}"
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

        valid_bans = [ban for ban in bans_info if isinstance(ban, dict)]
        sorted_bans = sorted(valid_bans, key=lambda x: str(x.get('timeAdded') or ''), reverse=True)
        return len(valid_bans), sorted_bans

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

        self._remember_tmp_update_group(target_event)

        msg = (getattr(target_event, "message_str", "") or "").strip()
        if not msg:
            return

        message_obj = getattr(target_event, "message_obj", None)
        has_at = False
        at_user_id = None
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        has_at = True
                        # 提取被艾特用户的ID
                        uid = (
                            getattr(seg, "qq", None)
                            or getattr(seg, "user_id", None)
                            or getattr(seg, "id", None)
                        )
                        if isinstance(seg, dict):
                            uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                        if uid is not None:
                            at_user_id = str(uid)
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
                at_user_id = None

        if re.match(r'^(查询|查)(\s*\d+)?\s*$', msg) or (re.match(r'^(查询|查)(\s|$)', msg) and has_at):
            async for r in self.tmpquery(event):
                yield r
            return
        if msg.lower() in {"dlc", "dlc列表", "地图dlc"}:
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
        if re.match(r'^足迹(?:\s*\S+)?(?:\s*\d+)?\s*$', msg) or (msg.startswith("足迹") and has_at):
            async for r in self.tmptoday_footprint(event):
                yield r
            return
        if re.match(r'^服务器\s*$', msg):
            async for r in self.tmpserver(event, game_filter='ets'):
                yield r
            return
        if re.match(r'^美卡服务器\s*$', msg):
            async for r in self.tmpats_server(event):
                yield r
            return
        if re.match(r'^查违规(?:\s*\d+)?\s*$', msg) or (msg.startswith("查违规") and has_at):
            async for r in self.tmpviolations(event):
                yield r
            return
        if re.match(r'^时间\s*$', msg):
            async for r in self.tmpgametime(event):
                yield r
            return
        if re.match(r'^今日活动\s*$', msg):
            async for r in self.tmptoday_events(event):
                yield r
            return
        if re.match(r'^活动\s*\d+\s*$', msg):
            async for r in self.tmpevent_detail(event):
                yield r
            return
        if re.fullmatch(r'vtc\s*\d+', msg, flags=re.IGNORECASE):
            async for r in self.tmpvtc_info(event):
                yield r
            return
        if re.fullmatch(r'(活动|vtc)', msg, flags=re.IGNORECASE):
            yield event.plain_result("用法: 活动 [活动ID] 或 vtc [VTC ID]")
            return
        if re.match(r'^路况(?:\s*\S+)?\s*$', msg):
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
        
        if re.match(r'^历史车队(\s*\d+)?\s*$', msg) or (msg.startswith("历史车队") and has_at):
            async for r in self.tmpvtc_history(event):
                yield r
            return


    # 额外 AstrBot 正式指令包装（用于行为统计，保留无前缀用法）

    @filter.command("查询")
    async def cmd_tmp_query(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询玩家详细信息，支持绑定ID与@他人。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("查")
    async def cmd_tmp_query_alias(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询玩家详细信息（简写版）。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("定位")
    async def cmd_tmp_locate(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询并渲染玩家当前位置（底图+自动翻译位置）。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("路况")
    async def cmd_tmp_traffic(self, event: AstrMessageEvent, server: str | None = None):
        """查询指定服务器热门路段的实时路况信息。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("总里程排行")
    async def cmd_tmp_rank_total(self, event: AstrMessageEvent):
        """查看玩家总里程排行榜前若干名。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("今日里程排行")
    async def cmd_tmp_rank_today(self, event: AstrMessageEvent):
        """查看今日里程排行榜前若干名。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("足迹")
    async def cmd_tmp_today_footprint(self, event: AstrMessageEvent, server: str | None = None, tmp_id: str | None = None):
        """查询玩家今日足迹；未指定服务器时查询全部服务器。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("服务器")
    async def cmd_tmp_server(self, event: AstrMessageEvent):
        """查看 TruckersMP 欧卡服务器状态。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("美卡服务器")
    async def cmd_tmp_ats_server(self, event: AstrMessageEvent):
        """查看 TruckersMP 美卡服务器状态。"""
        return

    @filter.command("查违规")
    async def cmd_tmp_violations(self, event: AstrMessageEvent, tmp_id: str | None = None):
        """查询玩家公开的 TMP 违规记录。"""
        return

    @filter.command("时间")
    async def cmd_tmp_game_time(self, event: AstrMessageEvent):
        """查询 TruckersMP 当前游戏时间。"""
        return

    @filter.command("今日活动")
    async def cmd_tmp_today_events(self, event: AstrMessageEvent):
        """查看 TruckersMP 今日活动。"""
        return

    @filter.command("活动")
    async def cmd_tmp_event_detail(self, event: AstrMessageEvent, event_id: str | None = None):
        """按活动 ID 查询 TruckersMP 活动详情。"""
        return

    @filter.command("VTC")
    async def cmd_tmp_vtc_info(self, event: AstrMessageEvent, vtc_id: str | None = None):
        """按 VTC ID 查询 TruckersMP 车队资料。"""
        return

    @filter.command("插件版本")
    async def cmd_tmp_plugin_version(self, event: AstrMessageEvent):
        """查询当前TMP插件版本信息。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return

    @filter.command("DLC")
    async def cmd_tmp_dlc(self, event: AstrMessageEvent):
        """查询地图 DLC 列表。"""
        return

    @filter.command("DLC列表")
    async def cmd_tmp_dlc_list(self, event: AstrMessageEvent):
        """查询地图 DLC 列表。"""
        return

    @filter.command("地图DLC")
    async def cmd_tmp_dlc_alias(self, event: AstrMessageEvent):
        """查询地图 DLC 列表（别名）。"""
        return

    @filter.command("菜单")
    async def cmd_tmp_help(self, event: AstrMessageEvent):
        """显示本插件支持的指令与用法。"""
        # 此函数仅用于在 AstrBot 行为列表中显示功能
        # 实际处理通过事件监听器 _on_any_message_dispatch 完成
        # 不处理任何实际的命令逻辑
        return


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

        match = re.search(r'(查询|查)\s*(\d+)', message_str) 
        input_id = match.group(2) if match else None
        
        tmp_id = None
        
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                # SteamID 格式检测
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    # SteamID 未注册
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    # 网络错误，建议重试
                    yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                    return
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
        # 如检测到没有车队，则两个都不显示
        vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
        vtc_name = vtc.get('name')
        vtc_role = vtc.get('role') or vtc.get('position') or stats_info.get('vtcRole')
        
        # 只有当有车队时才显示车队信息
        if vtc_name:
            body += f"🚚所属车队: {vtc_name}\n"
            if not vtc_role:
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

            def _strip_paren_text_q(s: Optional[str]) -> str:
                t = (s or "").strip()
                if not t:
                    return t
                t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
                t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
                return t

            display_country = _strip_paren_text_q(country_cn or "")
            display_city = _strip_paren_text_q(city_cn or "")
            if display_country and display_city:
                dc = display_country.strip()
                dcity = display_city.strip()
                if dcity == dc or dcity.startswith(dc):
                    location_display = dcity
                else:
                    location_display = f"{dc}-{dcity}"
            else:
                location_display = display_city or display_country or "未知位置"

            body += f"📶在线状态: 在线\n"
            body += f"📶所在服务器: {server_name}\n"
            body += f"📶所在位置: {location_display}"
        else:
            body += f"📶在线状态: 离线\n"
            if last_online_formatted:
                body += f"📶上次在线: {last_online_formatted}"
        
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

    async def tmptoday_footprint(
        self,
        event: AstrMessageEvent,
        _server_override: Optional[str] = None,
        _tmp_id_override: Optional[str] = None,
        _identity_override: Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None,
        _silent_empty: bool = False,
    ):
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

        server_alias = {
            "s1": "sim1",
            "sim1": "sim1",
            "simulation1": "sim1",
            "s2": "sim2",
            "sim2": "sim2",
            "simulation2": "sim2",
            "p": "eupromods1",
            "promods": "eupromods1",
            "promods1": "eupromods1",
            "eupromods1": "eupromods1",
            "a": "arc1",
            "arc": "arc1",
            "arcade": "arc1",
            "arc1": "arc1",
        }
        all_server_keys = ["sim1", "sim2", "arc1", "eupromods1"]
        server_token = None
        input_id = None
        if not _server_override:
            rest = message_str[2:].strip() if message_str.startswith("足迹") else message_str.strip()
            compact = re.sub(r"\s+", "", rest)
            if compact.isdigit():
                input_id = compact
            elif compact:
                for alias in sorted(server_alias.keys(), key=len, reverse=True):
                    if not compact.lower().startswith(alias):
                        continue
                    suffix = compact[len(alias):]
                    if suffix == "" or suffix.isdigit():
                        server_token = alias
                        input_id = suffix or None
                        break
                if server_token is None:
                    tokens = rest.split()
                    if tokens:
                        server_token = tokens[0]
                        input_id = next((token for token in tokens[1:] if token.isdigit()), None)
        if _server_override:
            server_key = str(_server_override).strip().lower()
            if server_key not in all_server_keys:
                yield event.plain_result("服务器参数无效，请使用 s1、s2、a、p")
                return
        elif server_token:
            server_key_raw = str(server_token).strip().lower()
            server_key = server_alias.get(server_key_raw)
            if not server_key:
                yield event.plain_result("服务器参数无效，请使用 s1、s2、a、p")
                return
        else:
            server_key = None
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

        tmp_id = _tmp_id_override
        if not tmp_id:
            if input_id:
                if len(input_id) == 17 and input_id.startswith('7'):
                    try:
                        tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                    except SteamIdNotFoundException as e:
                        # SteamID 未注册
                        yield event.plain_result(str(e))
                        return
                    except NetworkException as e:
                        # 网络错误，建议重试
                        yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                        return
                else:
                    tmp_id = input_id
            else:
                bind_user_id = target_user_id or user_id
                tmp_id = self._get_bound_tmp_id(bind_user_id)

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        if _identity_override is not None:
            player_info, stats_info, online_status = _identity_override
        else:
            try:
                player_info, stats_info = await asyncio.gather(
                    self._get_player_info(tmp_id),
                    self._get_player_stats(tmp_id),
                )
                online_status = {}
            except PlayerNotFoundException as e:
                yield event.plain_result(str(e))
                return
            except Exception as e:
                yield event.plain_result(f"查询失败: {str(e)}")
                return

        if server_key is None:
            async def collect_server_footprint(target_server: str) -> List[Any]:
                results = []
                async for result in self.tmptoday_footprint(
                    event,
                    _server_override=target_server,
                    _tmp_id_override=tmp_id,
                    _identity_override=(player_info, stats_info, online_status),
                    _silent_empty=True,
                ):
                    results.append(result)
                return results

            server_results = await asyncio.gather(
                *(collect_server_footprint(target_server) for target_server in all_server_keys)
            )
            sent_count = 0
            for results in server_results:
                for result in results:
                    sent_count += 1
                    yield result
            if sent_count == 0:
                yield event.plain_result("所有服务器暂无可用的今日足迹数据")
            return

        server_label = server_label_map.get(server_key, server_key.upper())
        map_type = 'promods' if server_key == 'eupromods1' else 'ets'

        player_name = player_info.get('name', '未知')
        last_online_raw = stats_info.get('last_online') or player_info.get('lastOnline')
        last_online_formatted = _format_timestamp_to_readable(last_online_raw) if last_online_raw else None
        if _is_unknown_display_value(last_online_formatted):
            last_online_formatted = None

        try:
            server_ids = []
            if server_key == 'eupromods1':
                server_ids.extend(str(sid) for sid in sorted(PROMODS_SERVER_IDS))
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

            now_local = datetime.now(BEIJING_TZ)
            start_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now_local.replace(hour=23, minute=59, second=59, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            history_points = []
            history_candidates = []
            if server_ids:
                history_candidates.extend(server_ids)
            mapped_id = server_id_map.get(server_key)
            if mapped_id is not None:
                history_candidates.append(str(mapped_id))
            history_candidates.append("")
            seen_hist = set()
            hist_list = []
            for sid in history_candidates:
                s = str(sid or "").strip()
                if s in seen_hist:
                    continue
                seen_hist.add(s)
                hist_list.append(s)
            range_start = start_time
            range_end = end_time
            for sid in hist_list:
                history_points = await self._get_footprint_history(tmp_id, sid or None, start_time, end_time)
                if history_points:
                    break
            if history_points:
                has_server_id = any(
                    str(p.get('serverId') or p.get('server_id') or p.get('server') or "").strip()
                    for p in history_points
                    if isinstance(p, dict)
                )
                if has_server_id:
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
                meta = {'source': 'playerHistory', 'startTime': range_start, 'endTime': range_end}
            elif not _silent_empty:
                logger.info("足迹历史为空，开始回退足迹接口")
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
            else:
                # 全服务器批量查询时只使用历史接口，避免为空服务器发起整组备用请求。
                points = []
                meta = {}
        except ApiResponseException:
            logger.info(f"{server_label} 暂无今日足迹数据")
            if not _silent_empty:
                yield event.plain_result(f"{server_label} 暂无今日足迹数据")
            return
        except Exception as e:
            logger.warning(f"查询 {server_label} 足迹失败: {e}")
            if not _silent_empty:
                yield event.plain_result(f"查询今日足迹失败: {str(e)}")
            return

        if not points:
            if not _silent_empty:
                yield event.plain_result(f"{server_label} 暂无今日足迹数据")
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

        point_timestamps = []
        for point in points:
            try:
                point_ts = int(point.get('ts') or 0)
            except Exception:
                point_ts = 0
            if point_ts > 0:
                point_timestamps.append(point_ts)

        route_start_raw = min(point_timestamps) if point_timestamps else start_time
        route_end_raw = max(point_timestamps) if point_timestamps else end_time

        def _format_footprint_moment(value: Any) -> str:
            if value in (None, ''):
                return '暂无记录'
            parsed = None
            try:
                if isinstance(value, (int, float)):
                    parsed = datetime.fromtimestamp(float(value), BEIJING_TZ)
                else:
                    text = str(value).strip()
                    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=BEIJING_TZ)
                    else:
                        parsed = parsed.astimezone(BEIJING_TZ)
            except Exception:
                parsed = None
            if parsed is None:
                return str(value).replace(':00', '', 1) if str(value).count(':') >= 2 else str(value)
            date_prefix = '今天' if parsed.date() == now_local.date() else parsed.strftime('%m月%d日')
            return f"{date_prefix} {parsed:%H:%M}"

        route_start_label = _format_footprint_moment(route_start_raw)
        route_end_label = _format_footprint_moment(route_end_raw)
        track_duration_label = '未记录'
        if point_timestamps:
            duration_seconds = max(0, max(point_timestamps) - min(point_timestamps))
            if duration_seconds >= 86400:
                days, remainder = divmod(duration_seconds, 86400)
                hours = remainder // 3600
                track_duration_label = f"{days}天{hours}小时"
            elif duration_seconds >= 3600:
                hours, remainder = divmod(duration_seconds, 3600)
                track_duration_label = f"{hours}小时{remainder // 60}分"
            elif duration_seconds >= 60:
                track_duration_label = f"{duration_seconds // 60}分钟"
            else:
                track_duration_label = '少于1分钟'

        route_segments = 0
        previous_point = None
        for point in points:
            if previous_point is None:
                route_segments = 1
                previous_point = point
                continue
            try:
                coordinate_jump = math.hypot(
                    float(point.get('axisX') or 0) - float(previous_point.get('axisX') or 0),
                    float(point.get('axisY') or 0) - float(previous_point.get('axisY') or 0),
                ) * 19 > 30000
                previous_ts = int(previous_point.get('ts') or 0)
                current_ts = int(point.get('ts') or 0)
                time_jump = bool(previous_ts and current_ts and current_ts - previous_ts > 90)
                server_jump = point.get('serverId') != previous_point.get('serverId')
            except Exception:
                coordinate_jump = time_jump = server_jump = False
            if coordinate_jump or time_jump or server_jump:
                route_segments += 1
            previous_point = point

        tile_url_ets = "https://ets-map.oss-cn-beijing.aliyuncs.com/ets2/05102019/{z}/{x}/{y}.png"
        tile_url_promods = "https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png"
        fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
        fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
        if fullmap_ets:
            tile_url_ets = fullmap_ets
        if fullmap_promods:
            tile_url_promods = fullmap_promods
        # 用户在配置里填了自定义瓦片源时，优先级最高
        tile_url_ets = self._tile_url('ets', tile_url_ets)
        tile_url_promods = self._tile_url('promods', tile_url_promods)

        map_tmpl = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:1280px; height:720px; background:#244b63; overflow:hidden; }
  * { box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif; }
  .shell { position:relative; width:1280px; height:720px; overflow:hidden; color:#f5fbfa; background:#244b63; }
  .map-stage { position:relative; width:100%; height:100%; overflow:hidden; background:radial-gradient(circle at 52% 40%,#365f76 0,#294f66 52%,#1b3b51 100%); }
  #map { position:absolute; inset:0; background:transparent; }
  #map .leaflet-tile-pane {
    opacity:.82; filter:grayscale(1) brightness(1.75) contrast(1.12);
    mix-blend-mode:screen;
  }
  .leaflet-control-container { display:none; }
  .map-stage::after {
    content:""; position:absolute; inset:0; z-index:450; pointer-events:none;
    background:
      linear-gradient(180deg,rgba(7,29,45,.18) 0,rgba(7,29,45,0) 22%,rgba(7,29,45,0) 66%,rgba(7,29,45,.38) 100%),
      radial-gradient(circle at 52% 45%,transparent 50%,rgba(8,30,45,.24) 100%);
  }
  .route-tooltip {
    border:none!important; border-radius:9px!important; background:#f8f6ef!important; color:#172625!important;
    box-shadow:0 8px 22px rgba(0,0,0,.2)!important; font-size:11px!important; font-weight:700!important;
  }
  .route-tooltip::before { border-top-color:#f8f6ef!important; }
  .panel {
    position:absolute; z-index:900; left:28px; right:28px; bottom:24px; height:112px;
    padding:0 28px; display:grid; grid-template-columns:minmax(0,1fr) 280px;
    gap:18px; align-items:center; border:1px solid rgba(255,255,255,.16); border-radius:20px;
    background:linear-gradient(105deg,rgba(7,28,45,.94),rgba(8,36,55,.88));
    box-shadow:0 18px 45px rgba(6,25,39,.34); backdrop-filter:blur(14px);
  }
  .panel::before {
    content:""; position:absolute; left:22px; right:22px; top:0; height:1px;
    background:linear-gradient(90deg,transparent,rgba(121,213,255,.7),transparent);
  }
  .profile { min-width:0; display:flex; align-items:center; gap:15px; }
  .avatar-wrap {
    width:72px; height:72px; flex:0 0 72px; padding:4px; border-radius:50%;
    background:linear-gradient(145deg,#6bcfff,#267cad); box-shadow:0 8px 22px rgba(2,16,27,.38);
  }
  .avatar {
    width:64px; height:64px; display:block; border:3px solid #102f45; border-radius:50%;
    object-fit:cover; background:#d9e0dc;
  }
  .avatar-fallback {
    width:64px; height:64px; display:flex; align-items:center; justify-content:center;
    border:3px solid #102f45; border-radius:50%; color:#f8fffd;
    background:linear-gradient(145deg,#237ca8,#123d59); font-size:26px; font-weight:800;
  }
  .profile-copy { min-width:0; flex:1; }
  .profile-kicker { margin-bottom:5px; color:#8bb1c3; font-size:10px; font-weight:800; letter-spacing:1.35px; }
  .name-line { display:flex; align-items:baseline; min-width:0; max-width:100%; }
  .name {
    min-width:0; max-width:380px; overflow:hidden; color:#f7fbfc; font-size:24px; line-height:1.18;
    font-weight:800; letter-spacing:-.4px; text-overflow:ellipsis; white-space:nowrap;
  }
  .name-suffix { flex:0 0 auto; color:#afc8d4; font-size:17px; font-weight:600; letter-spacing:0; white-space:nowrap; }
  .chips { display:flex; align-items:center; gap:7px; margin-top:8px; }
  .chip {
    display:inline-flex; align-items:center; height:22px; padding:0 9px; border-radius:7px;
    color:#c1d8e3; background:rgba(255,255,255,.08); font-size:10px; font-weight:700; letter-spacing:.35px;
  }
  .chip.server { color:#78ddae; background:rgba(83,199,143,.13); }
  .mileage { display:flex; align-items:baseline; justify-content:flex-end; gap:16px; white-space:nowrap; }
  .mileage span { color:#9bb6c4; font-size:14px; font-weight:600; }
  .mileage strong { color:#8de4b0; font-size:29px; line-height:1; font-weight:800; letter-spacing:-.6px; }
  .mileage small { margin-left:5px; color:#a7c6b7; font-size:13px; font-weight:600; letter-spacing:0; }
</style>
<div class="shell">
  <div class="map-stage">
    <div id="map"></div>
  </div>
  <div class="panel">
    <div class="profile">
      <div class="avatar-wrap">
        {% if avatar %}
        <img class="avatar" src="{{ avatar }}" />
        {% else %}
        <div class="avatar-fallback">{{ avatar_initial }}</div>
        {% endif %}
      </div>
      <div class="profile-copy">
        <div class="profile-kicker">DRIVER JOURNEY</div>
        <div class="name-line">
          <div class="name">{{ player_name }}</div>
          <span class="name-suffix"> 的今日行驶足迹</span>
        </div>
        <div class="chips">
          <span class="chip server">{{ server_label }}</span>
          <span class="chip">TMP #{{ tmp_id }}</span>
        </div>
      </div>
    </div>
    <div class="mileage">
      <span>今日里程</span>
      <strong>
        {% if distance_km is not none %}{{ '%.1f' % distance_km }}<small>km</small>{% else %}暂无记录{% endif %}
      </strong>
    </div>
  </div>
</div>
<script>
  var mapType = "{{ map_type }}";
  var cfg = {
    ets: {
      tileUrl: '{{ tile_url_ets }}',
      fallbackUrl: 'https://ets_tiles.cnly.top/20260903/tmp-ets-yellow/Tiles/{z}/{x}/{y}.png',
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
  var points = [ {% for p in points %}{ axisX: {{ p.axisX }}, axisY: {{ p.axisY }}, serverId: {{ p.serverId }}, heading: {{ p.heading }}, ts: {{ p.ts }} }{% if not loop.last %}, {% endif %}{% endfor %} ];
  points = points.filter(function(p){ return !(p.axisX === 0 && p.axisY === 0 && p.heading === 0); });
  var lines = [];
  var currentLine = [];
  if (points.length > 0) {
    currentLine.push(points[0]);
    for (var i=1;i<points.length;i++){
      var prev = points[i-1];
      var curr = points[i];
      var dist = Math.hypot(curr.axisX - prev.axisX, curr.axisY - prev.axisY) * 19;
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
  var routeLines = [];
  var focusLatlngs = [];
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
    routeLines.push(latlngs);
    if (latlngs.length > focusLatlngs.length) {
      focusLatlngs = latlngs;
    }
    L.polyline(latlngs, {
      color:'#0c3653', weight:11, opacity:0.96, lineCap:'round', lineJoin:'round'
    }).addTo(map);
    L.polyline(latlngs, {
      color:'#50afe8', weight:6, opacity:1, lineCap:'round', lineJoin:'round'
    }).addTo(map);
    L.polyline(latlngs, {
      color:'#8bd8ff', weight:1.8, opacity:0.48, lineCap:'round', lineJoin:'round'
    }).addTo(map);
  }

  function addEndpoint(latlng, type) {
    var color = type === 'end' ? '#ef655e' : '#59c98d';
    L.circleMarker(latlng, {
      radius:11, color:color, weight:1.5, opacity:0.32, fillOpacity:0
    }).addTo(map);
    L.circleMarker(latlng, {
      radius:6.5, color:'#f8fffd', weight:2, opacity:1, fillColor:color, fillOpacity:1
    }).addTo(map);
  }

  if (focusLatlngs.length > 0) {
    addEndpoint(focusLatlngs[0], 'start');
    addEndpoint(focusLatlngs[focusLatlngs.length - 1], 'end');
  }

  if (focusLatlngs.length === 1) {
    map.setView(focusLatlngs[0], 7);
  } else if (focusLatlngs.length > 1) {
    map.fitBounds(L.latLngBounds(focusLatlngs), {
      paddingTopLeft: [48, 55],
      paddingBottomRight: [48, 165],
      maxZoom: 8
    });
  }
  setTimeout(function(){ map.invalidateSize(); }, 80);
</script>
"""
        data = {
            'player_name': player_name,
            'avatar': self._normalize_avatar_url(player_info.get('avatar')) or '',
            'avatar_initial': str(player_name or '?').strip()[:1].upper() or '?',
            'points': points,
            'points_count': len(points),
            'distance_km': distance_km,
            'start_time': start_time,
            'end_time': end_time,
            'route_start_label': route_start_label,
            'route_end_label': route_end_label,
            'track_duration_label': track_duration_label,
            'route_segments': route_segments,
            'tmp_id': tmp_id,
            'last_online': last_online_formatted if not _is_unknown_display_value(last_online_formatted) else None,
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
        if last_online_formatted:
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
                # 使用 TruckersMP 官方 API 直接查询
                tmp_id = await self._get_tmp_id_from_steam_id(input_id)
            except SteamIdNotFoundException as e:
                # SteamID 未注册
                yield event.plain_result(str(e))
                return
            except NetworkException as e:
                # 网络错误，建议重试
                yield event.plain_result(f"SteamID绑定失败: {str(e)}\n请稍后重试或使用TMP ID绑定")
                return
            except Exception:
                yield event.plain_result("Steam ID 查询服务请求失败，请直接使用TMP ID绑定。\n\n格式：绑定 [TMP ID]")
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
            message += f"已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定"         
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
    
    # --- 【定位命令】 ---
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
                    # SteamID 未注册
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    # 网络错误，建议重试
                    yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                    return
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
                'city': {'name': ''}
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
        def _strip_paren_text(s: Optional[str]) -> str:
            t = (s or "").strip()
            if not t:
                return t
            t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
            t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
            return t

        display_country = _strip_paren_text(country_cn or '未知国家')
        display_city = _strip_paren_text(city_cn or '未知位置')
        if display_country and display_city:
            dc = display_country.strip()
            dcity = display_city.strip()
            if dcity == dc or dcity.startswith(dc):
                location_line = dcity
            else:
                location_line = f"{dc}-{dcity}"
        else:
            location_line = display_city or display_country or "未知位置"

        heading_candidates = [
            online.get('heading'),
            online.get('direction'),
            online.get('yaw'),
            online.get('rotation'),
            online.get('bearing'),
            fullmap_player.get('Heading') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('heading') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('yaw') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('rotation') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('bearing') if isinstance(fullmap_player, dict) else None,
        ]
        direction_text = None
        for candidate in heading_candidates:
            direction_text = _normalize_heading_to_direction(candidate)
            if direction_text:
                break
        if direction_text:
            direction_text = f"正在向{direction_text}行驶"

        player_name = player_info.get('name') or '未知'

        avatar_url = self._normalize_avatar_url(player_info.get('avatar'))

        # 4) 周边玩家查询并绘制简易地图（第三方 VTCM 源，见 _api_bases()）
        try:
            server_id = online.get('serverId')
            cx = float(online.get('x') or 0)
            cy = float(online.get('y') or 0)
            ax, ay = cx - 4000, cy + 2500
            bx, by = cx + 4000, cy - 2500
            area_players = []
            if self.session and server_id:
                for api_base in self._api_bases():
                    area_url = f"{api_base}/map/playerList?aAxisX={ax}&aAxisY={ay}&bAxisX={bx}&bAxisY={by}&serverId={server_id}"
                    logger.info(f"定位: 使用底图查询周边玩家 serverId={server_id} center=({cx},{cy}) url={area_url}")
                    try:
                        async with self.session.get(area_url, timeout=self._cfg_int('api_timeout_seconds', 10), ssl=False) as resp:
                            if resp.status == 200:
                                j = await resp.json()
                                area_players = j.get('data') or []
                                logger.info(f"定位: 周边玩家数量={len(area_players)}")
                                break
                            logger.info(f"定位: 底图查询返回状态 {resp.status}，尝试备用源")
                    except Exception as e:
                        logger.info(f"定位: 底图查询异常: {e}")
            if not area_players and self._fullmap_cache:
                data = self._fullmap_cache or {}
                payload = data.get('Data') or data.get('data') or data.get('players')
                if isinstance(payload, list):
                    for p in payload:
                        if not isinstance(p, dict):
                            continue
                        sid = p.get('ServerId') or p.get('serverId') or p.get('server_id')
                        if sid is None or int(sid) != int(server_id or 0):
                            continue
                        px = p.get('X') or p.get('x') or p.get('axisX') or p.get('posX') or p.get('pos_x')
                        py = p.get('Y') or p.get('y') or p.get('axisY') or p.get('posY') or p.get('pos_y')
                        if px is None or py is None:
                            continue
                        try:
                            fx = float(px)
                            fy = float(py)
                        except Exception:
                            continue
                        if fx < min(ax, bx) or fx > max(ax, bx) or fy < min(by, ay) or fy > max(by, ay):
                            continue
                        pid = p.get('MpId') or p.get('mp_id') or p.get('tmpId') or p.get('tmp_id') or p.get('id')
                        area_players.append({'tmpId': str(pid) if pid is not None else '', 'axisX': fx, 'axisY': fy})
            normalized_players = []
            for p in area_players:
                if not isinstance(p, dict):
                    continue
                axis_x = p.get('axisX') or p.get('x') or p.get('posX') or p.get('pos_x')
                axis_y = p.get('axisY') or p.get('y') or p.get('posY') or p.get('pos_y')
                if axis_x is None or axis_y is None:
                    continue
                pid = p.get('tmpId') or p.get('mpId') or p.get('playerId') or p.get('id')
                normalized_players.append({
                    'tmpId': str(pid) if pid is not None else '',
                    'axisX': axis_x,
                    'axisY': axis_y
                })
            area_players = normalized_players
            area_players = [p for p in area_players if str(p.get('tmpId')) != str(tmp_id)]
            area_players.append({'tmpId': str(tmp_id), 'axisX': cx, 'axisY': cy})

            map_type = 'promods' if int(server_id or 0) in [50, 51] else 'ets'
            # 瓦片源：用户在配置里填了自定义源就用它，否则用内置默认源
            tile_url_ets = self._tile_url(
                'ets', "https://ets_tiles.cnly.top/20260903/tmp-ets-yellow/Tiles/{z}/{x}/{y}.png")
            tile_url_promods = self._tile_url(
                'promods', "https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png")
            logger.info(f"定位: tile_ets={tile_url_ets}")
            logger.info(f"定位: tile_promods={tile_url_promods}")

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
      {% if location_line %}<div>{{ location_line }}</div>{% endif %}
      {% if direction_text %}<div>{{ direction_text }}</div>{% endif %}
    </div>
  </div>
</div>
<script>
  var promodsIds = [50, 51];
  var serverId = {{ server_id }};
  var mapType = promodsIds.indexOf(serverId) !== -1 ? 'promods' : 'ets';
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
  map.setView(centerLL, 8);
  setTimeout(function(){}, 800); // 轻微延时确保瓦片加载
</script>
"""
            min_x, max_x = ax, bx
            min_y, max_y = by, ay  # 注意坐标系方向
            map_data = {
                'server_name': server_name,
                'location_name': location_line,
                'player_name': player_name,
                'me_id': str(tmp_id),
                'players': area_players,
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y,
                'avatar': avatar_url or '',
                'location_line': location_line,
                'direction_text': direction_text,
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
        msg = f"玩家实时定位\n玩家名称: {player_name}\nTMP编号: {tmp_id}\n服务器: {server_name}"
        if location_line:
            msg += f"\n位置: {location_line}"
        if direction_text:
            msg += f"\n状态: {direction_text}"
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
                        "km_text": km_str.removesuffix(".00"),
                        "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                    }
            except Exception:
                pass
        
        for idx, player in enumerate(rank_list):
            try:
                rank = int(player.get('ranking', idx + 1))
            except (TypeError, ValueError):
                rank = idx + 1
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
            distance_raw = player.get('mileage') or player.get('distance') or 0
            try:
                distance_km = int(float(distance_raw) / 1000)
            except (TypeError, ValueError):
                distance_km = 0
            distance_str = f"{distance_km:,}".replace(',', ' ')
            tmp_id = player.get('tmpId', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            message += line

            items.append({
                'rank': rank,
                'name': name,
                'km': distance_km,
                'km_text': distance_str,
                'tmp_id': tmp_id,
            })

        message += "=" * 35 + "\n"

        rank_tmpl = RANK_IMAGE_TEMPLATE

        try:
            options = { 'type': 'jpeg', 'quality': 96, 'full_page': True, 'omit_background': False }
            url = await self.html_render(rank_tmpl, {
                'title': '总里程排行榜',
                'subtitle': 'ALL-TIME MILEAGE',
                'scope': '累计里程',
                'is_today': False,
                'items': items,
                'me': me_data,
            }, options=options)
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
                        "km_text": km_str.removesuffix(".00"),
                        "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                    }
            except Exception:
                pass
        
        for idx, player in enumerate(rank_list):
            try:
                rank = int(player.get('ranking', idx + 1))
            except (TypeError, ValueError):
                rank = idx + 1
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
            distance_raw = player.get('mileage') or player.get('distance') or 0
            try:
                distance_km = int(float(distance_raw) / 1000)
            except (TypeError, ValueError):
                distance_km = 0
            distance_str = f"{distance_km:,}".replace(',', ' ')
            tmp_id = player.get('tmpId', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            message += line

            items.append({
                'rank': rank,
                'name': name,
                'km': distance_km,
                'km_text': distance_str,
                'tmp_id': tmp_id,
            })

        message += "=" * 35 + "\n"

        rank_tmpl = RANK_IMAGE_TEMPLATE

        try:
            options = { 'type': 'jpeg', 'quality': 96, 'full_page': True, 'omit_background': False }
            url = await self.html_render(rank_tmpl, {
                'title': '今日里程排行榜',
                'subtitle': 'TODAY · RESET 00:00',
                'scope': '每日 0 点重置',
                'is_today': True,
                'items': items,
                'me': me_data,
            }, options=options)
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


    async def tmpserver(self, event: AstrMessageEvent, game_filter: Optional[str] = None):
        """[命令: 服务器] 查询TruckersMP官方服务器的实时状态。"""
        if not self.session: 
            yield event.plain_result("插件初始化中，请稍后重试")
            return
            
        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    code = data.get('code') if isinstance(data, dict) else None
                    if code is not None and int(code) != 200:
                        yield event.plain_result("查询服务器失败，请稍后重试")
                        return
                    servers = data.get('data') or data.get('response') or data.get('result') or []
                    if not isinstance(servers, list):
                        yield event.plain_result("查询服务器失败，请稍后重试")
                        return
                    game_filter = str(game_filter or '').strip().lower()
                    heading = "美卡服务器状态" if game_filter == 'ats' else None
                    # 先收集每个服务器的文本块，避免循环内以条件追加换行导致出现多余空行
                    blocks = []
                    for server in servers:
                        game_name = str(
                            server.get('game')
                            or server.get('gameName')
                            or server.get('game_name')
                            or ''
                        ).strip().upper()
                        name_value = server.get('serverName') or server.get('name') or '未知服务器'
                        try:
                            name_trim = name_value.strip() if isinstance(name_value, str) else str(name_value)
                        except Exception:
                            name_trim = str(name_value)
                        if game_filter == 'ats':
                            if game_name:
                                if game_name != 'ATS':
                                    continue
                            elif not name_trim.upper().startswith('[US]'):
                                continue
                        elif game_filter == 'ets':
                            if game_name:
                                if game_name != 'ETS2':
                                    continue
                            elif name_trim.upper().startswith('[US]'):
                                continue

                        is_online = server.get('isOnline')
                        if is_online is None:
                            is_online = server.get('online')
                        online_flag = int(is_online) == 1 if isinstance(is_online, (int, float, str)) else bool(is_online)

                        # 兼容性：优先使用 serverName，再 fallback 到 name
                        name = name_value
                        # 忽略特定服务器（保持与 src/command/tmpServer.js 一致的精确匹配行为）
                        ignore_servers = ['Simulation', '[US] Simulation', '[US] Arcade']
                        if game_filter != 'ats' and name_trim in ignore_servers:
                            continue

                        status = "🟢" if online_flag else "⚫"
                        block = f"服务器: {status}{name}"

                        players = server.get('playerCount')
                        if players is None:
                            players = server.get('players', 0)
                        max_players = server.get('maxPlayer')
                        if max_players is None:
                            max_players = server.get('maxplayers', 0)
                        block += f"\n玩家人数: {players}/{max_players}"

                        queue_flag = server.get('queue', 0)
                        queue_count = server.get('queueCount', queue_flag)
                        if queue_flag:
                            block += f" (队列: {queue_count})"

                        characteristic_list = []
                        afk_enable = server.get('afkEnable')
                        if afk_enable is None:
                            afk_enable = server.get('afkEnabled')
                        if afk_enable is None:
                            afk_enable = server.get('afkenable')
                        if afk_enable is None:
                            afk_enable = server.get('afkenabled')
                        can_afk = False
                        if isinstance(afk_enable, bool):
                            can_afk = afk_enable
                        elif isinstance(afk_enable, (int, float)):
                            can_afk = int(afk_enable) == 1
                        elif isinstance(afk_enable, str):
                            can_afk = afk_enable.strip().lower() in ("1", "true", "yes", "y")
                        if not can_afk:
                            characteristic_list.append("⏱挂机")

                        collisions_enable = server.get('collisionsEnable')
                        if collisions_enable is None:
                            collisions_enable = server.get('collisions')
                        if isinstance(collisions_enable, bool):
                            if collisions_enable:
                                characteristic_list.append("💥碰撞")
                        elif isinstance(collisions_enable, (int, float)):
                            if int(collisions_enable) == 1:
                                characteristic_list.append("💥碰撞")

                        if characteristic_list:
                            block += "\n服务器特性: " + " ".join(characteristic_list)

                        blocks.append(block)

                    message = "\n\n".join(blocks)
                    if heading:
                        message = f"{heading}\n{'=' * 18}\n\n{message}" if message else "暂无美卡服务器数据"
                    yield event.plain_result(message or "暂无在线服务器")
                else:
                    yield event.plain_result(f"查询服务器状态失败，API返回错误状态码: {response.status}")
        except Exception:
            yield event.plain_result("网络请求失败，请检查网络或稍后重试。")

    async def tmpats_server(self, event: AstrMessageEvent):
        """[命令: 美卡服务器] 查询 TruckersMP 美卡服务器状态。"""
        async for result in self.tmpserver(event, game_filter='ats'):
            yield result

    async def tmpviolations(self, event: AstrMessageEvent):
        """[命令: 查违规] 查询玩家公开的 TMP 违规记录。"""
        tmp_id, id_error = await self._resolve_tmp_id_for_user_command(event, "查违规")
        if id_error:
            yield event.plain_result(id_error)
            return

        try:
            player_info, bans = await asyncio.gather(
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id),
            )
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"查询违规记录失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询玩家 {tmp_id} 违规记录失败: {exc}", exc_info=True)
            yield event.plain_result("查询违规记录失败，请稍后重试")
            return

        player_name = player_info.get('name') or '未知玩家'
        is_banned = bool(player_info.get('banned'))
        ban_count, sorted_bans = self._format_ban_info(bans)
        try:
            ban_count = int(str(player_info.get('bansCount')))
        except (TypeError, ValueError):
            pass

        message = "🚫 TMP 违规记录\n"
        message += "=" * 18 + "\n"
        message += f"玩家: {player_name} (ID: {tmp_id})\n"
        message += f"当前状态: {'封禁中' if is_banned else '正常'}\n"
        message += f"历史封禁: {ban_count} 次\n"

        if is_banned:
            banned_until = player_info.get('bannedUntil')
            if banned_until:
                expiry = (
                    "永久"
                    if str(banned_until).lower().startswith('never')
                    else _format_timestamp_to_beijing(str(banned_until))
                )
                message += f"当前封禁截止: {expiry}\n"

        if not sorted_bans:
            message += "\n未查询到公开的违规记录。\n"
            message += "注：如果玩家隐藏了封禁记录，这里也不会显示。"
            yield event.plain_result(message)
            return

        message += f"\n违规记录（共 {len(sorted_bans)} 条）"
        for index, ban in enumerate(sorted_bans, 1):
            active_raw = ban.get('active')
            active = active_raw is True or str(active_raw).strip().lower() in {'1', 'true', 'yes'}
            added = _format_timestamp_to_beijing(str(ban.get('timeAdded') or ''))
            reason_raw = str(ban.get('reason') or '未提供原因').strip()
            reason = self._translate_ban_reason(reason_raw) or reason_raw
            expiration_raw = str(ban.get('expiration') or '').strip()
            if not expiration_raw:
                expiration = "未知"
            elif expiration_raw.lower().startswith('never'):
                expiration = "永久"
            else:
                expiration = _format_timestamp_to_beijing(expiration_raw)
            admin_name = str(ban.get('adminName') or '').strip()
            admin_id = ban.get('adminID')

            message += f"\n\n{index}. {'🔴 生效中' if active else '⚪ 已结束'}"
            message += f"\n记录时间: {added}"
            message += f"\n违规原因: {reason}"
            message += f"\n封禁截止: {expiration}"
            if admin_name or admin_id:
                admin_display = admin_name or '未知GM'
                if admin_id is not None:
                    admin_display += f" (ID: {admin_id})"
                message += f"\n处理GM: {admin_display}"

        yield event.plain_result(message)

    async def tmpgametime(self, event: AstrMessageEvent):
        """[命令: 时间] 查询 TruckersMP 当前游戏时间。"""
        try:
            game_info = await self._get_game_time()
        except NetworkException as exc:
            yield event.plain_result(f"查询游戏时间失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询游戏时间失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询游戏时间失败: {exc}", exc_info=True)
            yield event.plain_result("查询游戏时间失败，请稍后重试")
            return

        game_datetime = game_info['game_datetime']
        message = f"当前游戏时间: {game_datetime:%H:%M}"
        yield event.plain_result(message)

    @classmethod
    def _clean_tmp_text(cls, value: Any, limit: int = 1000) -> str:
        text = str(value or '').strip()
        if not text:
            return ''
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'[#*_>`]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        for source, target in cls.COMMON_TEXT_MAP_EN_TO_CN.items():
            text = re.sub(
                r'(?<![A-Za-z])' + re.escape(source) + r'(?![A-Za-z])',
                target,
                text,
                flags=re.IGNORECASE,
            )
        if len(text) > limit:
            return text[:limit].rstrip() + '…'
        return text

    @classmethod
    def _translate_language(cls, value: Any) -> str:
        raw = str(value or '').strip()
        return cls.LANGUAGE_MAP_EN_TO_CN.get(raw.lower(), raw or '未知')

    @classmethod
    def _translate_event_type(cls, event_type: Dict[str, Any]) -> str:
        if not isinstance(event_type, dict):
            return '未知'
        for key in (event_type.get('name'), event_type.get('key')):
            raw = str(key or '').strip()
            if not raw:
                continue
            translated = cls.EVENT_TYPE_MAP_EN_TO_CN.get(raw.lower())
            if translated:
                return translated
        return str(event_type.get('name') or event_type.get('key') or '未知')

    @classmethod
    def _format_event_place(cls, place: Any) -> str:
        if not isinstance(place, dict):
            return ''
        city = str(place.get('city') or '').strip()
        location = str(place.get('location') or '').strip()
        if city:
            city_key = city.lower()
            city = (
                cls.CITY_MAP_EN_TO_CN.get(city_key)
                or cls.LOCATION_FIX_MAP.get(city_key)
                or cls.EVENT_LOCATION_MAP_EN_TO_CN.get(city_key)
                or city
            )
        if location:
            location_key = location.lower()
            location = (
                cls.EVENT_LOCATION_MAP_EN_TO_CN.get(location_key)
                or cls.LOCATION_FIX_MAP.get(location_key)
                or cls.CITY_MAP_EN_TO_CN.get(location_key)
                or location
            )
        if city and location and city.lower() != location.lower():
            return f"{city} · {location}"
        return city or location

    @classmethod
    def _format_event_route(cls, event_data: Dict[str, Any]) -> str:
        departure = cls._format_event_place(event_data.get('departure'))
        arrival = cls._format_event_place(event_data.get('arrive'))
        if departure and arrival:
            return f"{departure} → {arrival}"
        return departure or arrival or '未提供'

    async def tmptoday_events(self, event: AstrMessageEvent):
        """[命令: 今日活动] 查询 TruckersMP 今日活动。"""
        try:
            today_events = await self._get_today_events()
        except NetworkException as exc:
            yield event.plain_result(f"查询今日活动失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询今日活动失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询今日活动失败: {exc}", exc_info=True)
            yield event.plain_result("查询今日活动失败，请稍后重试")
            return

        if not today_events:
            yield event.plain_result("今日无活动")
            return

        today_events.sort(key=lambda item: str(item.get('start_at') or ''))
        message = f"📅 今日活动（{len(today_events)}）"
        for index, item in enumerate(today_events, 1):
            game_name = str(item.get('game') or '未知')
            game_label = '欧卡2' if game_name == 'ETS2' else '美卡' if game_name == 'ATS' else game_name
            start_at = _format_timestamp_to_beijing(str(item.get('start_at') or ''))
            attendances = item.get('attendances') if isinstance(item.get('attendances'), dict) else {}
            confirmed = attendances.get('confirmed', 0)
            message += (
                f"\n\n{index}. {item.get('name') or '未命名活动'}"
                f"\n活动ID: {item.get('id') or '未知'} | {game_label}"
                f"\n开始时间: {start_at}"
                f"\n路线: {self._format_event_route(item)}"
                f"\n已确认参加: {confirmed} 人"
            )
        yield event.plain_result(message)

    async def tmpevent_detail(self, event: AstrMessageEvent):
        """[命令: 活动] 按活动 ID 查询 TruckersMP 活动详情。"""
        match = re.search(r'活动\s*(\d+)', event.message_str.strip())
        if not match:
            yield event.plain_result("用法: 活动 [活动ID]")
            return
        event_id = match.group(1)
        try:
            detail = await self._get_event_detail(event_id)
        except NetworkException as exc:
            yield event.plain_result(f"查询活动失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询活动失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询活动 {event_id} 失败: {exc}", exc_info=True)
            yield event.plain_result("查询活动失败，请稍后重试")
            return

        event_type = detail.get('event_type') if isinstance(detail.get('event_type'), dict) else {}
        server = detail.get('server') if isinstance(detail.get('server'), dict) else {}
        user = detail.get('user') if isinstance(detail.get('user'), dict) else {}
        vtc = detail.get('vtc') if isinstance(detail.get('vtc'), dict) else {}
        attendances = detail.get('attendances') if isinstance(detail.get('attendances'), dict) else {}
        game_name = str(detail.get('game') or '未知')
        game_label = '欧卡2' if game_name == 'ETS2' else '美卡' if game_name == 'ATS' else game_name

        message = f"活动名称: {detail.get('name') or '未命名活动'}\n"
        message += f"活动 ID: {detail.get('id') or event_id}\n"
        message += f"活动类型: {self._translate_event_type(event_type)}\n"
        message += f"游戏: {game_label}\n"
        server_name = str(server.get('name') or '').strip()
        if server_name.lower() == 'to be determined':
            server_name = '待定'
        message += f"服务器: {server_name or '待定'}\n"
        message += f"语言: {self._translate_language(detail.get('language'))}\n"
        message += f"集合时间: {_format_timestamp_to_beijing(str(detail.get('meetup_at') or ''))}\n"
        message += f"开始时间: {_format_timestamp_to_beijing(str(detail.get('start_at') or ''))}\n"
        message += f"路线: {self._format_event_route(detail)}\n"
        if user.get('username'):
            message += f"主办玩家: {user.get('username')}"
            if user.get('id'):
                message += f" (ID: {user.get('id')})"
            message += "\n"
        if vtc.get('name'):
            message += f"主办车队: {vtc.get('name')}"
            if vtc.get('id'):
                message += f" (VTC ID: {vtc.get('id')})"
            message += "\n"
        message += (
            "参加情况: "
            f"已确认 {attendances.get('confirmed', 0)} 人"
            f" | 待定 {attendances.get('unsure', 0)} 人"
            f" | 车队 {attendances.get('vtcs', 0)} 个\n"
        )

        description = self._clean_tmp_text(detail.get('description'), limit=1200)
        rules = self._clean_tmp_text(detail.get('rule'), limit=1200)
        if description:
            message += f"\n活动简介:\n{description}\n"
        if rules:
            message += f"\n活动规则:\n{rules}\n"
        if detail.get('external_link'):
            message += f"\n活动链接: {detail.get('external_link')}"
        yield event.plain_result(message.rstrip())

    async def tmpvtc_info(self, event: AstrMessageEvent):
        """[命令: VTC] 按 VTC ID 查询 TruckersMP 车队资料。"""
        match = re.search(r'vtc\s*(\d+)', event.message_str.strip(), flags=re.IGNORECASE)
        if not match:
            yield event.plain_result("用法: vtc [VTC ID]")
            return
        vtc_id = match.group(1)
        try:
            detail = await self._get_vtc_detail(vtc_id)
        except NetworkException as exc:
            yield event.plain_result(f"查询 VTC 失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询 VTC 失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询 VTC {vtc_id} 失败: {exc}", exc_info=True)
            yield event.plain_result("查询 VTC 失败，请稍后重试")
            return

        games = detail.get('games') if isinstance(detail.get('games'), dict) else {}
        supported_games = []
        if games.get('ets'):
            supported_games.append('欧卡2')
        if games.get('ats'):
            supported_games.append('美卡')
        socials = detail.get('socials') if isinstance(detail.get('socials'), dict) else {}
        recruitment_raw = str(detail.get('recruitment') or '').strip().lower()
        recruitment = {
            'open': '开放招募',
            'closed': '停止招募',
        }.get(recruitment_raw, detail.get('recruitment') or '未知')

        message = f"车队名称: {detail.get('name') or '未命名车队'}\n"
        message += f"VTC ID: {detail.get('id') or vtc_id}\n"
        message += f"车队标签: {detail.get('tag') or '无'}\n"
        message += f"车主: {detail.get('owner_username') or '未知'}"
        if detail.get('owner_id'):
            message += f" (ID: {detail.get('owner_id')})"
        message += "\n"
        message += f"成员数量: {detail.get('members_count', 0)} 人\n"
        message += f"招募状态: {recruitment}\n"
        message += f"支持游戏: {'、'.join(supported_games) or '未知'}\n"
        message += f"主要语言: {self._translate_language(detail.get('language'))}\n"
        message += f"成立时间: {_format_timestamp_to_beijing(str(detail.get('created') or ''))}\n"
        if detail.get('slogan'):
            message += f"车队口号: {self._clean_tmp_text(detail.get('slogan'), limit=300)}\n"

        information = self._clean_tmp_text(detail.get('information'), limit=1000)
        rules = self._clean_tmp_text(detail.get('rules'), limit=800)
        requirements = self._clean_tmp_text(detail.get('requirements'), limit=800)
        if information:
            message += f"\n车队简介:\n{information}\n"
        if rules:
            message += f"\n车队规则:\n{rules}\n"
        if requirements:
            message += f"\n加入要求:\n{requirements}\n"
        if detail.get('website'):
            message += f"\n官方网站: {detail.get('website')}"
        social_links = []
        for platform in ('discord', 'twitter', 'youtube', 'twitch', 'facebook'):
            if socials.get(platform):
                social_links.append(f"{platform}: {socials.get(platform)}")
        if social_links:
            message += "\n社交链接:\n" + "\n".join(social_links)
        yield event.plain_result(message.rstrip())

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

    async def tmpvtc_history(self, event: AstrMessageEvent):
        """[命令: 历史车队] 查询玩家的历史VTC (车队) 记录。支持输入 TMP ID 或绑定查询。"""
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

        match = re.search(r'历史车队\s*(\d+)?', message_str)
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
                    yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID，或者先绑定账号")
            return

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')

        try:
            vtc_history = await self._get_vtc_history(tmp_id)
        except Exception as e:
            logger.error(f"历史车队查询异常: {e}")
            yield event.plain_result("查询历史车队失败，请稍后重试")
            return

        if vtc_history is None:
            yield event.plain_result("该用户的历史车队为私密状态")
            return
        if not vtc_history:
            yield event.plain_result("暂无历史车队记录")
            return

        lines = []
        for idx, vtc_item in enumerate(vtc_history, 1):
            vtc_name = vtc_item.get('vtcName') or vtc_item.get('name') or vtc_item.get('vtc_name') or '未知'
            vtc_tag = vtc_item.get('vtcTag') or vtc_item.get('tag') or vtc_item.get('vtc_tag', '')
            join_date = vtc_item.get('joinDate') or vtc_item.get('join_date') or vtc_item.get('joinedAt', '')
            leave_date = vtc_item.get('leaveDate') or vtc_item.get('leave_date') or vtc_item.get('leftAt', '')
            role = vtc_item.get('role') or vtc_item.get('position') or vtc_item.get('vtcRole', '')

            entry = f"{idx}. {vtc_name}"
            if vtc_tag:
                entry += f" [{vtc_tag}]"
            if role:
                entry += f"\n   职位: {role}"
            if join_date:
                entry += f"\n   加入时间: {join_date}"
            if leave_date:
                entry += f"\n   离开时间: {leave_date}"
            lines.append(entry)

        message = "\n".join(lines)
        if len(vtc_history) > 10:
            message += f"\n\n... 共 {len(vtc_history)} 条记录，仅显示前10条"

        yield event.plain_result(message)

    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: 菜单] 显示本插件的命令使用说明。"""
        main_help = """TMP查询姬指令菜单

可用命令:
1. 绑定 [TMP ID]
2. 查询 [TMP ID]
3. 定位 [TMP ID]
4. 路况[s1/s2/p/a]
5. 总里程排行
6. 今日里程排行
7. 足迹/ 足迹 [服务器简称] [TMP ID]
8. 服务器
9. 美卡服务器
10. 查违规 [TMP ID]
11. 时间(查询游戏时间)
12. 今日活动
13. 活动 [活动ID]
14. VTC [VTC ID]
15. 插件版本
16. 历史车队 [TMP ID]
使用提示: 绑定后可直接发送 查询/定位/足迹/查违规/历史车队，足迹可省略服务器
"""

        yield event.plain_result(main_help)
    
    
    
    @filter.command("历史车队")
    async def cmd_tmp_vtc_history(self, event: AstrMessageEvent):
        """查询玩家的历史VTC车队记录。"""
        return


    async def terminate(self):
        """插件卸载时的清理工作：停止后台任务、保存状态并关闭HTTP会话。"""
        update_task = self._tmp_update_task
        self._tmp_update_task = None
        if update_task and not update_task.done():
            update_task.cancel()
            try:
                await update_task
            except asyncio.CancelledError:
                pass
        if self._tmp_update_state or self._tmp_update_groups:
            self._save_tmp_update_state()

        self._fullmap_task = None
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")
