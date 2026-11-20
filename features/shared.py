"""Common formatting helpers, exceptions, and plugin paths."""

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlsplit
import ipaddress

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

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

FOOTPRINT_RENDER_REVISION = "2026-10-31-r5"

def _translate_user_groups(groups: List[Any]) -> List[str]:
    translated: List[str] = []
    for g in groups:
        if g is None:
            continue
        key = str(g)
        translated.append(USER_GROUP_MAP.get(key, key))
    return translated

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

def _format_timestamp_to_beijing(timestamp_str: Optional[str]) -> str:
    """将 UTC 时间戳转换为北京时间 (UTC+8)。兼容 ISO 8601 和简单格式。"""
    if not timestamp_str:
        return "未知"

    s = str(timestamp_str).strip()
    if s.lower().startswith('never'):
        return "永久封禁"

    try:
        iso = s.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
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
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"^(?:[\[［][^\]］]+[\]］]\s*)+", "", s)
        s = re.sub(r"^<[^>]+>\s*", "", s)
        s = re.sub(r"^(?:&\s*)?(?:n|v|adj|adv|vt|vi|prep|pron|conj|abbr)[\.．]\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(?:\s*(?:&\s*)?(?:n|v|adj|adv|vt|vi|prep|pron|conj|abbr)[\.．]\s*)+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(?:\s*(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]\s*)+", "", s)
        s = re.sub(r"（[^）]*）", "", s)
        s = re.sub(r"\([^)]*\)", "", s)
        for sep in ["；", ";", "，"]:
            if sep in s:
                s = s.split(sep, 1)[0]
        s = s.strip(" 、，。.；;")
        if re.search(r"\s", s):
            head = re.split(r"\s+", s, maxsplit=1)[0]
            if re.search(r"[\u4e00-\u9fff]", head) and not re.fullmatch(r"(?:名|动|形|副|介|代|连|数|量|叹|助|冠)(?:词)?[\.．:：]?", head):
                s = head
        return s or text
    except Exception:
        return text

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

def _is_permanent_ban_expiry(value: Any) -> bool:
    normalized = str(value or '').strip().lower()
    return normalized.startswith(('never', 'permanent', 'forever')) or normalized in {'永久', '永久封禁'}

def _is_hidden_ban_reason(value: Any) -> bool:
    normalized = str(value or '').strip().lower()
    return normalized in {
        'hidden', 'private', 'not public', 'hidden reason', 'reason hidden',
        'hidden by player', 'hidden by user',
    }

def _is_hidden_ban_expiry(value: Any) -> bool:
    normalized = str(value or '').strip().lower()
    return not normalized or normalized in {
        'hidden', 'private', 'not public', 'hidden expiry', 'expiry hidden',
        'hidden by player', 'hidden by user',
    }



def command_text(event, text: str | None = None) -> str:
    """Normalize the optional QQ mention and slash prefix in a command."""
    if text is None:
        text = getattr(event, 'message_str', '') or ''
    text = text.strip()
    platform_name = getattr(event, 'get_platform_name', None)
    if callable(platform_name) and platform_name() == 'qq_official':
        text = re.sub(
            r'^(?:<@!?[^<>\s]+>|<qqbot-at-user\s+id="[^"]+"\s*/>)\s*', '', text
        )
    return re.sub(r'^[/／]\s*', '', text).strip()



def is_safe_http_url(url: str, *, allow_local_http: bool = False) -> bool:
    """Check URL syntax and literal IPs. Hostnames are not resolved here."""
    try:
        raw = str(url).strip()
        if '\\' in raw or any(char.isspace() or ord(char) < 32 for char in raw):
            return False
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None or parsed.fragment or parsed.port == 0:
            return False

        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
            return allow_local_http and parsed.scheme == "http"

        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            # Avoid ambiguous numeric hostnames interpreted differently by HTTP clients.
            if not hostname or '%' in hostname or re.fullmatch(r'(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*', hostname):
                return False
            return parsed.scheme == "https" or allow_local_http

        if address.is_global and not address.is_multicast:
            return parsed.scheme == "https" or allow_local_http
        return allow_local_http and parsed.scheme == "http" and address.is_loopback
    except ValueError:
        return False


async def read_response_bytes(response: Any, limit: int) -> bytes:
    """Read an HTTP response with a hard memory limit."""
    content_length = getattr(response, "content_length", None)
    if content_length is not None and content_length > limit:
        raise ValueError("HTTP response exceeds the configured size limit")
    content = getattr(response, "content", None)
    if content is not None and hasattr(content, "iter_chunked"):
        chunks = []
        total = 0
        async for chunk in content.iter_chunked(65536):
            total += len(chunk)
            if total > limit:
                raise ValueError("HTTP response exceeds the configured size limit")
            chunks.append(chunk)
        return b"".join(chunks)
    reader = getattr(response, "read", None)
    if reader is None:
        reader = getattr(response, "json", None)
        if reader is None:
            raise ValueError("HTTP response has no readable body")
        data = json.dumps(await reader(), ensure_ascii=False).encode("utf-8")
        if len(data) > limit:
            raise ValueError("HTTP response exceeds the configured size limit")
        return data
    data = await reader()
    if len(data) > limit:
        raise ValueError("HTTP response exceeds the configured size limit")
    return data


async def read_json(response: Any, limit: int = 8 * 1024 * 1024) -> Any:
    """Decode a JSON response without allowing unbounded memory growth."""
    return json.loads((await read_response_bytes(response, limit)).decode("utf-8"))
