#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.51)
"""

import re
import asyncio
import aiohttp
import json
import os
import base64
import socket
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta

# 引入 AstrBot 核心 API
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message_components import Image, Plain
except ImportError:
    # 最小化兼容回退 
    class _DummyFilter:
        def command(self, pattern, **kwargs): 
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
        return dt_utc.strftime('%Y-%m-%d %H:%M:%S') + " (UTC)"
        
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
        return dt_bj.strftime('%Y-%m-%d %H:%M:%S') + " (UTC+8)"
    except Exception:
        try:
            # ISO 8601 with timezone offset, e.g. 2025-12-01T07:55:00+00:00
            iso = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(iso)
            dt_bj = dt + timedelta(hours=8)
            return dt_bj.strftime('%Y-%m-%d %H:%M:%S') + " (UTC+8)"
        except Exception:
            return s

# --- 辅助函数：获取 DLC 列表 (优化后) ---
def _get_dlc_info(player_info: Dict) -> Dict[str, List[str]]:
    """从玩家信息中提取并分组主要的地图 DLC 列表。"""
    dlc_list = player_info.get('dlc', [])
    
    ets2_dlc: List[str] = []
    ats_dlc: List[str] = []

    ETS2_MAP_PREFIX = "Euro Truck Simulator 2 - "
    ATS_MAP_PREFIX = "American Truck Simulator - "
    
    MAP_KEYWORDS = [
        "Going East!", "Scandinavia", "Vive la France !", "Italia", "Beyond the Baltic Sea", 
        "Road to the Black Sea", "Iberia", "West Balkans", "Heart of Russia", 
        "New Mexico", "Oregon", "Washington", "Utah", "Idaho", "Colorado", 
        "Wyoming", "Montana", "Texas", "Oklahoma", "Kansas", "Nebraska"
    ]

    if isinstance(dlc_list, list):
        for dlc in dlc_list:
            dlc_name_full = dlc.get('name', '').strip()
            
            # 1. ETS2 DLC
            if dlc_name_full.startswith(ETS2_MAP_PREFIX):
                name = dlc_name_full[len(ETS2_MAP_PREFIX):].strip()
                if name in MAP_KEYWORDS:
                    ets2_dlc.append(name)
                elif "Germany Rework" in name:
                    ets2_dlc.append("Germany Rework")
                        
            # 2. ATS DLC
            elif dlc_name_full.startswith(ATS_MAP_PREFIX):
                name = dlc_name_full[len(ATS_MAP_PREFIX):].strip()
                if name not in ["Arizona", "Nevada"] and name in MAP_KEYWORDS: 
                    ats_dlc.append(name)
                elif name in ["Arizona", "Nevada"]: 
                    ats_dlc.append(f"{name} (基础地图)")

    return {
        'ets2': sorted(list(set(ets2_dlc))), 
        'ats': sorted(list(set(ats_dlc)))
    }
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

# 版本号更新为 1.3.32
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.32", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context, config: Optional[Dict[str, Any]] = None):
        super().__init__(context)
        self.config: Dict[str, Any] = config or {}
        self.session: Optional[aiohttp.ClientSession] = None 
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

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

    async def initialize(self):
        # 统一 User-Agent，并更新版本号
        timeout_sec = self._cfg_int('api_timeout_seconds', 10)
        # 使用 IPv4 优先的连接器，并允许读取环境代理设置（与浏览器/系统行为更一致）
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.3.32'}, 
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
            connector=connector,
            trust_env=True
        )
        logger.info(f"TMP Bot 插件HTTP会话已创建，超时 {timeout_sec}s")

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
                    return data.get('response', [])
                return []
        except Exception:
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
                    # 尝试从 VTCM 响应中获取上次在线时间（兼容多个可能的字段名）
                    last_online = (
                        response_data.get('lastOnline')
                        or response_data.get('lastOnlineTime')
                        or response_data.get('last_login')
                        or response_data.get('lastLogin')
                        or None
                    )
                    logger.info(f"VTCM 里程解析: total_km={total_km:.2f}, today_km={daily_km:.2f}, avatar={avatar_url}")
                    
                    if data.get('code') != 200 or not response_data:
                        logger.info(f"VTCM 里程数据校验失败: code={data.get('code')}, has_data={bool(response_data)}")
                        raise ApiResponseException(f"VTCM 里程 API 返回非成功代码或空数据: {data.get('msg', 'N/A')}")

                    return {
                        'total_km': total_km, 
                        'daily_km': daily_km,
                        'avatar_url': avatar_url,
                        # 将上次在线时间传回供上层使用（可能为 ISO 字符串或其他格式）
                        'last_online': last_online,
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
                        
                        if not country: country = location_data.get('country')
                        if not real_name: real_name = location_data.get('realName')

                        formatted_location = '未知位置'
                        if country and real_name:
                            formatted_location = f"{country} {real_name}"
                        elif real_name:
                            formatted_location = real_name
                        elif country:
                            formatted_location = country
                        
                        return {
                            'online': True,
                            'serverName': server_name,
                            'game': 1 if server_details.get('game') == 'ETS2' else 2 if server_details.get('game') == 'ATS' else 0,
                            'city': {'name': formatted_location}, 
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
    
    async def _get_rank_list(self, limit: int = 10) -> Optional[List[Dict]]:
        """获取 TruckersMP 里程排行榜列表 (使用 da.vtcm.link API)。"""
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        # 正确的排行榜接口（总里程），支持数量参数
        url = f"https://da.vtcm.link/statistics/mileageRankingList?rankingType=total&rankingCount={limit}"
        logger.info(f"尝试 API (排行榜): {url}")

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
            "2.1": "黑客攻击/错误/功能滥用",
            "2.2": "碰撞",
            "2.3": "堵塞",
            "2.4": "不正确的方式/不适当的超车",
            "2.5": "鲁莽驾驶",
            "2.6": "不适当的车队管理/滥用汽车",
            "2.7": "特色区域和事件服务器",
        }

        # 找出所有 "§x.x - title" 片段（title 截止到逗号或连字符）
        matches = list(re.finditer(r"§\s*(?P<code>\d+\.\d+)\s*-\s*(?P<title>[^,\-]+)", reason))
        if not matches:
            return reason

        parts = []
        for m in matches:
            code = m.group("code").strip()
            title = m.group("title").strip()
            zh_title = zh_map.get(code)
            if zh_title:
                parts.append(f"§{code} - {zh_title}")
            else:
                parts.append(f"§{code} - {title}")

        # 保留最后一个匹配之后的所有内容（通常包含链接与说明）
        remainder = reason[matches[-1].end():]
        return ", ".join(parts) + remainder


    # ******************************************************
    # 命令处理器 
    # ******************************************************
    
    @filter.command("查询") 
    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] TMP玩家完整信息查询。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
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
            tmp_id = self._get_bound_tmp_id(user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号（TMP ID 或 Steam ID）")
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
        last_online_formatted = _format_timestamp_to_readable(last_online_raw)
        
        # 完整的回复消息构建：标题与正文分离，便于控制发送顺序
        header = "TMP玩家详细信息\r\n" + "=" * 20 + "\r\n"
        body = ""
        body += f"ID TMP编号: {tmp_id}\n"
        if steam_id_to_display:
            body += f"ID Steam编号: {steam_id_to_display}\n"
        body += f"玩家名称: {player_info.get('name', '未知')}\n"
        body += f"上次在线: {last_online_formatted}\n"

        # 权限/分组信息
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f'is{g.replace(" ", "")}')]
                if groups:
                    perms_str = ', '.join(groups)
            elif isinstance(perms, list) and perms:
                perms_str = ', '.join(perms)
        body += f"所属分组: {perms_str}\n"

        vtc_name = player_info.get('vtc', {}).get('name')
        vtc_role = player_info.get('vtc', {}).get('role')
        body += f"所属车队: {vtc_name if vtc_name else '无'}\n"
        if vtc_role:
            body += f"车队角色: {vtc_role}\n"
        
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

        body += f"是否赞助: {'是' if is_patron else '否'}\n"
        body += f"赞助是否有效: {'是' if active else '否'}\n"
        if is_patron:
            if current_pledge > 0:
                body += f"当前赞助金额: {current_pledge}美元\n"
            else:
                body += f"当前赞助金额: 0美元（当前未赞助）\n"
            body += f"历史赞助金额: {lifetime_pledge}美元\n"
        else:
            body += f"当前赞助金额: 0美元\n"
            body += f"历史赞助金额: 0美元\n"
        # --- 赞助信息结束 ---

        # --- 里程信息输出 (不变) ---
        logger.info(f"查询详情: 里程字典 keys={list(stats_info.keys())}, debug={stats_info.get('debug_error')}")
        total_km = stats_info.get('total_km', 0.0)
        daily_km = stats_info.get('daily_km', 0.0)
        logger.info(f"查询详情: 里程输出值 total_km={total_km:.2f}, daily_km={daily_km:.2f}")
        
        body += f"🚩历史里程: {total_km:.2f}公里/km\n"
        body += f"🚩今日里程: {daily_km:.2f}公里/km\n"
        
        # --- 封禁信息 (不变) ---
        body += f"是否封禁: {'是' if is_banned else '否'}\n"
        
        if ban_count > 0:
            body += f"历史封禁: {ban_count}次\n"

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
                
                body += f"当前封禁原因: {ban_reason}\n"
                
                if ban_expiration and isinstance(ban_expiration, str) and ban_expiration.lower().startswith('never'):
                    body += f"封禁截止: 永久封禁\n"
                else:
                    body += f"封禁截止: {_format_timestamp_to_beijing(ban_expiration)}\n"
                    
            else:
                body += f"当前封禁原因: API详细记录缺失。可能原因：封禁信息被隐藏或数据同步延迟。\n"
                if banned_until_main and isinstance(banned_until_main, str) and banned_until_main.lower().startswith('never'):
                    body += f"封禁截止: 永久封禁\n"
                else:
                    body += f"封禁截止: {_format_timestamp_to_beijing(banned_until_main)}\n"
        
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知位置') 
            
            body += f"在线状态: 在线\n"
            body += f"所在服务器: {server_name}\n"
            body += f"所在位置: {city} ({game_mode})\n"
        else:
            body += f"在线状态: 离线\n"
        
        # 头像（强制按组件发送）
        show_avatar_cfg = self._cfg_bool('query_show_avatar_enable', True)
        logger.info(f"查询详情: 头像开关={'ON' if show_avatar_cfg else 'OFF'}，将组合 Image+Plain 统一发送。")
        avatar_url = self._normalize_avatar_url(player_info.get('avatar') or stats_info.get('avatar_url'))
        logger.info(f"查询详情: 规范化后URL={avatar_url}")
        components = []
        # 发送顺序控制：当头像关闭时，将标题与正文合并为一个文本组件以保证换行在同一组件内生效
        if not show_avatar_cfg:
            logger.info("查询详情: 头像开关为OFF，合并标题与正文为单个文本组件")
            components.append(Plain(header + "\r\n" + body))
            yield event.chain_result(components)
            return
        else:
            # 头像开启：标题 -> 头像 -> 空行 -> 正文
            components.append(Plain(header))
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
    
    @filter.command("DLC") 
    async def tmpdlc(self, event: AstrMessageEvent):
        """[命令: DLC] 查询玩家拥有的地图 DLC 列表。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'DLC\s*(\d+)', message_str) 
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
            tmp_id = self._get_bound_tmp_id(user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号（TMP ID 或 Steam ID）")
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
        dlc_data = _get_dlc_info(player_info)
        
        message = f"📦 玩家 {player_name} (ID: {tmp_id}) 的主要地图 DLC 列表\n"
        message += "=" * 30 + "\n"
        
        ets2_dlc = dlc_data.get('ets2', [])
        ats_dlc = dlc_data.get('ats', [])

        message += f"🚛 Euro Truck Simulator 2 (数量: {len(ets2_dlc)}):\n"
        if ets2_dlc:
            chunks = [ets2_dlc[i:i + 3] for i in range(0, len(ets2_dlc), 3)]
            for chunk in chunks:
                message += "  " + " | ".join(chunk) + "\n"
        else:
            message += "  无 ETS2 地图 DLC 记录\n"
            
        message += f"\n🇺🇸 American Truck Simulator (数量: {len(ats_dlc)}):\n"
        if ats_dlc:
            chunks = [ats_dlc[i:i + 3] for i in range(0, len(ats_dlc), 3)]
            for chunk in chunks:
                message += "  " + " | ".join(chunk) + "\n"
        else:
            message += "  无 ATS 地图 DLC 记录\n"

        message += "\n(此列表仅展示主要地图扩展包)"

        yield event.plain_result(message)
    # --- DLC 命令处理器结束 ---

    @filter.command("绑定")
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
            yield event.plain_result(f"玩家 TMP ID {tmp_id} 不存在，请检查ID是否正确")
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')
        
        steam_id_display = self._get_steam_id_from_player_info(player_info)
        
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            
            message = f"绑定成功！\n"
            message += f"已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定\n"
            if steam_id_display:
                message += f"该玩家的 Steam ID: {steam_id_display}"
            
            yield event.plain_result(message)
        else:
            yield event.plain_result("绑定失败，请稍后重试")

    @filter.command("解绑")
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
            yield event.plain_result(f"解绑成功！\n已解除与TMP玩家 {player_name} (ID: {tmp_id}) 的绑定")
        else:
            yield event.plain_result("解绑失败，请稍后重试")

    @filter.command("状态")
    async def tmpstatus(self, event: AstrMessageEvent):
        """[命令:状态] 查询玩家的实时在线状态。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'(状态)\s*(\d+)', message_str) 
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
            tmp_id = self._get_bound_tmp_id(user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号（TMP ID 或 Steam ID），或先使用 绑定 [TMP ID] 绑定您的账号。")
            return

        try:
            # 并行查询：仅使用 V2 接口（移除已失效的 V1）
            online_status, player_info = await asyncio.gather(
                self._get_online_status(tmp_id),
                self._get_player_info(tmp_id)
            )

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        player_name = player_info.get('name', '未知')
        steam_id_to_display = self._get_steam_id_from_player_info(player_info)
        
        
        # --- 核心回复构造 ---
        message = f"玩家状态查询\n"
        message += "=" * 15 + "\n"
        message += f"玩家名称: {player_name}\n"
        message += f"TMP编号: {tmp_id}\n"

        if steam_id_to_display:
            message += f"Steam编号: {steam_id_to_display}\n"
        
        # --- 【核心逻辑】赞助信息 (仅基于 V2 player 接口字段) ---
        def _get_nested(d: Dict, *keys):
            cur = d
            for k in keys:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        def _to_int(val, default=0):
            try:
                if val is None:
                    return default
                if isinstance(val, int):
                    return val
                if isinstance(val, float):
                    return int(round(val))
                s = str(val).strip()
                if s == "":
                    return default
                # 允许像 "123.0" 的字符串
                return int(float(s))
            except Exception:
                return default

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

        tier = '赞助者'
        currency = 'USD'
        amount = 0
        donation_info = player_info.get('donation', {}) if isinstance(player_info.get('donation'), dict) else {}
        tier = donation_info.get('tier', tier)
        currency = donation_info.get('currency', currency)
        if is_patron:
            amount = _to_int(donation_info.get('amount'), 0)
            if amount <= 0:
                # 兼容 currentPledge 以分为单位，需要除以 100
                cp = _to_int(
                    _get_nested(player_info, 'currentPledge')
                    or _get_nested(player_info, 'donation', 'currentPledge')
                    or _get_nested(player_info, 'patron', 'currentPledge')
                    or _get_nested(player_info, 'patreon', 'currentPledge'),
                    0
                )
                if cp > 0:
                    amount = cp // 100

        message += f"是否赞助: {'是' if is_patron else '否'}\n"
        if is_patron:
            if amount > 0:
                message += f"赞助金额: {tier} ({amount}{currency})\n"
            else:
                message += f"赞助等级: {tier}\n"
        # -------------------

        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            
            city = online_status.get('city', {}).get('name', '未知位置')
            
            message += f"在线状态: 在线\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            message += f"在线状态: 离线\n"

        # 头像（强制按组件发送，组合链）
        show_avatar_cfg = self._cfg_bool('query_show_avatar_enable', True)
        logger.info(f"玩家状态: 头像开关={'ON' if show_avatar_cfg else 'OFF'}，将组合 Image+Plain 统一发送。")
        # 优先使用 TruckersMP V2 的头像字段，其次 VTCM 查询
        avatar_url = self._normalize_avatar_url(player_info.get('avatar'))
        if not avatar_url:
            try:
                stats_info = await self._get_player_stats(tmp_id)
                avatar_url = self._normalize_avatar_url(stats_info.get('avatar_url'))
            except Exception:
                avatar_url = None
        logger.info(f"玩家状态: 规范化后URL={avatar_url}")
        components = []
        if show_avatar_cfg and avatar_url:
            try:
                logger.info("玩家状态: 组合消息链添加 Image(URL) 组件")
                components.append(Image.fromURL(avatar_url))
            except Exception:
                logger.error("玩家状态: 生成 Image(URL) 组件失败，跳过头像", exc_info=True)
        else:
            if not show_avatar_cfg:
                logger.info("玩家状态: 头像开关为OFF，跳过头像组件")
            elif not avatar_url:
                logger.info("玩家状态: 无可用头像URL，跳过头像组件")
        components.append(Plain(message))
        yield event.chain_result(components)
    
    # --- 【新功能】定位命令 ---
    @filter.command("定位")
    async def tmplocate(self, event: AstrMessageEvent):
        """[命令:定位] 查询玩家的实时位置。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'(定位)\s*(\d+)', message_str) 
        input_id = match.group(2) if match else None
        
        tmp_id = None
        
        # --- ID 解析逻辑 ---
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
            tmp_id = self._get_bound_tmp_id(user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号（TMP ID 或 Steam ID），或先使用 绑定 [TMP ID] 绑定您的账号。")
            return

        try:
            # 只需要在线状态 (位置) 和 玩家信息 (名字)
            online_status, player_info = await asyncio.gather(
                self._get_online_status(tmp_id), 
                self._get_player_info(tmp_id)
            )

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        player_name = player_info.get('name', '未知')
        
        # --- 定位回复构造 ---
        message = f"📍 玩家实时定位\n"
        message += "=" * 15 + "\n"
        message += f"玩家名称: {player_name}\n"
        message += f"TMP编号: {tmp_id}\n"

        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知位置')
            
            message += f"🚦 在线状态: 在线\n"
            message += f"🌐 所在服务器: {server_name}\n"
            message += f"🗺️ 所在位置: {city} ({game_mode})\n"
        else:
            # 如果离线
            last_online_formatted = _format_timestamp_to_readable(player_info.get('lastOnline'))
            message += f"🚦 在线状态: 离线\n"
            message += f"⌚ 上次在线: {last_online_formatted}\n"

        yield event.plain_result(message)
    # --- 定位命令结束 ---
    

    # --- 里程排行榜命令处理器 ---
    @filter.command("排行") 
    async def tmprank(self, event: AstrMessageEvent):
        """[命令: 排行] 查询 TruckersMP 玩家总里程排行榜前10名。"""
        
        try:
            # 获取排行榜数据，默认为前10名
            rank_list = await self._get_rank_list(limit=10)
        except NetworkException as e:
            yield event.plain_result(f"查询排行榜失败: {str(e)}")
            return
        except ApiResponseException as e:
            yield event.plain_result(f"查询排行榜失败: API返回数据异常。")
            return
        except Exception:
            yield event.plain_result("查询排行榜时发生未知错误。")
            return

        if not rank_list:
            yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
            return
            
        message = "🏆 TruckersMP 玩家总里程排行榜 (前10名)\n"
        message += "=" * 35 + "\n"
        
        for idx, player in enumerate(rank_list):
            rank = player.get('ranking', idx + 1)
            name = player.get('name', '未知玩家')
            distance_m = player.get('mileage', 0)
            
            # 转换为公里并格式化
            distance_km = int(distance_m / 1000)
            distance_str = f"{distance_km:,}".replace(',', ' ')
            
            # 格式化输出：[排名] 玩家名 (ID: TMP ID) - 里程
            tmp_id = player.get('tmpId', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            
            message += line

        message += "=" * 35 + "\n"
        message += "数据来源: da.vtcm.link API"

        yield event.plain_result(message)
    # --- 里程排行榜命令处理器结束 ---


    @filter.command("服务器")
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

    @filter.command("菜单")
    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: 菜单] 显示本插件的命令使用说明。"""
        help_text = """TMP查询插件使用说明

可用命令:
1. 查询 [ID] - 查询玩家的完整信息（支持 TMP ID 或 Steam ID）。
2. 状态 [ID]- 查询玩家的实时在线状态（支持 TMP ID 或 Steam ID）。 
3. 定位 [ID] - 【新】查询玩家的实时服务器和位置。
4. DLC [ID] - 查询玩家拥有的主要地图 DLC 列表（支持 TMP ID 或 Steam ID）。
5. 排行 - 查询 TruckersMP 总里程排行榜前10名。
6. 绑定 [ID] - 绑定您的聊天账号与 TMP ID（支持输入 Steam ID 转换）。
7. 解绑 - 解除账号绑定。
8. 服务器 - 查看所有在线的TMP服务器的实时状态和在线人数。
9. 菜单 - 显示此帮助信息。

使用提示: 绑定后可直接发送 查询/状态/DLC/定位 (无需ID参数)
"""
        yield event.plain_result(help_text)
        
    async def terminate(self):
        """插件卸载时的清理工作：关闭HTTP会话。"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")