#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.27：新增排行榜和优化查询输出)
"""

import re
import asyncio
import aiohttp
import json
import os
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

# 引入 AstrBot 核心 API
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
except ImportError:
    # 最小化兼容回退 (用于本地测试或非 AstrBot 环境)
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
        @property
        def match(self):
             return self._match
        async def plain_result(self, msg):
            return msg # 在测试中直接返回消息字符串
    MessageEventResult = Any 
    class Context: pass
    class Star:
        def __init__(self, context: Context = None): pass
        async def initialize(self): pass
    def register(*args, **kwargs):
        def deco(cls):
            return cls
        return deco
    class StarTools:
        @staticmethod
        def get_data_dir(name: str):
            # 在测试环境中，使用 tmp 文件夹
            return os.path.join(os.getcwd(), f"tmp_{name}")
    class _Logger:
        @staticmethod
        def info(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')} INFO]", msg)
        @staticmethod
        def error(msg, exc_info=False):
            print(f"[{datetime.now().strftime('%H:%M:%S')} ERROR]", msg)
            if exc_info:
                import traceback
                traceback.print_exc()
    logger = _Logger()


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

# --- 辅助函数：获取 DLC 列表 (优化后) ---
def _get_dlc_info(player_info: Dict) -> Dict[str, List[str]]:
    """从玩家信息中提取并分组主要的地图 DLC 列表。"""
    dlc_list = player_info.get('dlc', [])
    
    ets2_dlc: List[str] = []
    ats_dlc: List[str] = []

    ETS2_MAP_PREFIX = "Euro Truck Simulator 2 - "
    ATS_MAP_PREFIX = "American Truck Simulator - "
    
    # 包含了几乎所有地图扩展包的关键词
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
        'ets2': sorted(list(set(ets2_dlc))), # 去重并排序
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

# 版本号更新为 1.3.27
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.27", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None 
        # 使用自定义的 StarTools.get_data_dir，确保插件数据隔离
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        # 统一 User-Agent，并更新版本号
        if not self.session or self.session.closed:
             self.session = aiohttp.ClientSession(
                headers={'User-Agent': 'AstrBot-TMP-Plugin/1.3.27'}, 
                timeout=aiohttp.ClientTimeout(total=10)
            )
             logger.info("TMP Bot 插件HTTP会话已创建")


    # --- 内部工具方法 ---
    def _is_steam_id_64(self, input_id: str) -> bool:
        """检查输入是否可能是 Steam ID 64"""
        return len(input_id) == 17 and input_id.startswith('7')

    def _load_bindings(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.bind_file):
                with open(self.bind_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载绑定数据失败: {e}", exc_info=True)
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        try:
            with open(self.bind_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}", exc_info=True)
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
            'bind_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
            logger.error(f"查询 TMP ID 失败: {e}", exc_info=True)
            raise NetworkException("查询失败")
            
    def _get_steam_id_from_player_info(self, player_info: Dict) -> Optional[str]:
        steam_id = player_info.get('steamID64')
        return str(steam_id) if steam_id else None

    async def _get_player_info(self, tmp_id: str) -> Dict:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        
        try:
            # TMP 官方 V2 接口 (用于基本信息、封禁、上次在线、DLC 查询)
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
            logger.error(f"查询玩家信息失败: {e}", exc_info=True)
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
            
    async def _get_player_stats(self, tmp_id: str) -> Dict[str, int]:
        """
        通过 da.vtcm.link API 获取玩家的总里程和今日里程 (推测 API 返回公里数)。
        返回: {'total_km': 0, 'daily_km': 0, 'debug_error': '...'}
        """
        if not self.session: 
            return {'total_km': 0, 'daily_km': 0, 'debug_error': 'HTTP会话不可用。'}

        # 优先使用 VTCM API
        vtcm_stats_url = f"https://da.vtcm.link/player/info?tmpId={tmp_id}"
        
        try:
            async with self.session.get(vtcm_stats_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('data', {})
                    
                    total_km = int(response_data.get('totalDistance', 0))
                    daily_km = int(response_data.get('todayDistance', 0))
                    
                    if data.get('code') != 200 or not response_data:
                        raise ApiResponseException("VTCM API返回非成功代码或空数据")

                    return {
                        'total_km': total_km, 
                        'daily_km': daily_km,
                        'debug_error': 'VTCM 里程数据获取成功。'
                    }
                else:
                    return await self._get_player_stats_fallback(tmp_id)

        except Exception as e:
            logger.error(f"获取玩家统计数据失败 (VTCM): {e.__class__.__name__}")
            # 如果 VTCM 失败，使用 Trucky App 作为备用 API
            return await self._get_player_stats_fallback(tmp_id)

    async def _get_player_stats_fallback(self, tmp_id: str) -> Dict[str, int]:
        """
        备用方案：使用 TruckyApp V3 API 获取玩家里程 (以米为单位)。
        """
        if not self.session: 
            return {'total_km': 0, 'daily_km': 0, 'debug_error': 'Fallback: HTTP会话不可用。'}

        trucky_stats_url = f"https://api.truckyapp.com/v3/player/{tmp_id}/stats"
        
        try:
            async with self.session.get(trucky_stats_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response', {})
                    
                    total_m = response_data.get('total', 0)
                    daily_m = response_data.get('daily', 0)
                    
                    total_km = int(total_m / 1000)
                    daily_km = int(daily_m / 1000)

                    return {
                        'total_km': total_km, 
                        'daily_km': daily_km,
                        'debug_error': 'Fallback: 里程数据获取成功 (Trucky)。'
                    }
                else:
                    return {'total_km': 0, 'daily_km': 0, 'debug_error': f'Fallback: 里程 API 返回状态码: {response.status}'}

        except Exception as e:
            logger.error(f"Fallback 获取玩家统计数据失败: {e.__class__.__name__}")
            return {'total_km': 0, 'daily_km': 0, 'debug_error': f'Fallback: 获取里程失败: {e.__class__.__name__}。'}


    async def _get_online_status(self, tmp_id: str) -> Dict:
        """
        使用 TruckyApp V3 地图实时接口查询状态。
        【版本 1.3.26 优化：修复即使 online:true 仍判断为离线的问题】
        """
        if not self.session: 
            return {'online': False, 'debug_error': 'HTTP会话不可用。', 'raw_data': '无'}

        # TruckyApp V3 Map Online API (实时状态)
        trucky_url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
        
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
                    
                    debug_msg = f"Trucky V3 原始数据:\n{json.dumps(raw_data, indent=2, ensure_ascii=False)}"

                    if is_online:
                        server_details = online_data.get('serverDetails', {})
                        server_name = server_details.get('name', f"未知服务器 ({online_data.get('server')})")
                        
                        location_data = online_data.get('location', {})
                        country = location_data.get('poi', {}).get('country') or location_data.get('country')
                        real_name = location_data.get('poi', {}).get('realName') or location_data.get('realName')
                        
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
                            'raw_data': debug_msg
                        }
                    
                    
                    return {
                        'online': False,
                        'debug_error': 'Trucky V3 API 响应判断为离线。',
                        'raw_data': debug_msg
                    }
                
                else:
                    return {
                        'online': False, 
                        'debug_error': f"Trucky V3 API 返回非 200 状态码: {status}",
                        'raw_data': f"Trucky V3 原始数据:\n{json.dumps(raw_data, indent=2, ensure_ascii=False)}"
                    }

        except Exception as e:
            logger.error(f"Trucky V3 API 解析失败: {e.__class__.__name__}", exc_info=True)
            return {'online': False, 'debug_error': f'Trucky V3 API 发生意外错误: {e.__class__.__name__}。', 'raw_data': '无'}
    # --- 在线状态查询方法结束 ---
    
    async def _get_rank_list(self, limit: int = 10) -> Optional[List[Dict]]:
        """
        获取 TruckersMP 里程排行榜列表 (使用 Trucky App V3 接口)。
        默认获取总里程排行榜前 N 名。
        """
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        # Trucky App V3 里程总榜 API
        url = f"https://api.truckyapp.com/v3/rankings/distance/total/1?limit={limit}"
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response', [])
                    
                    if isinstance(response_data, list):
                          return response_data
                    else:
                        raise ApiResponseException("排行榜 API 数据结构异常")

                elif response.status == 404:
                    return []
                else:
                    raise ApiResponseException(f"排行榜 API 返回错误状态码: {response.status}")
        except aiohttp.ClientError:
            raise NetworkException("排行榜 API 网络请求失败")
        except asyncio.TimeoutError:
            raise NetworkException("请求排行榜 API 超时")
        except Exception as e:
            logger.error(f"查询排行榜失败: {e}", exc_info=True)
            raise NetworkException("查询排行榜失败")


    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[int, List[Dict]]:
        """只返回历史封禁次数和最新的封禁记录（按时间倒序）"""
        if not bans_info or not isinstance(bans_info, list):
            return 0, []
        
        sorted_bans = sorted(bans_info, key=lambda x: x.get('timeAdded', ''), reverse=True)
        return len(bans_info), sorted_bans


    # ******************************************************
    # 命令处理器 
    # ******************************************************
    
    @filter.command("查询") 
    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] TMP玩家完整信息查询。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        # 检查是否要求显示 debug 信息
        is_debug_request = 'debug' in message_str.lower()
        
        match = re.search(r'查询\s*(\d+)', message_str) 
        input_id = match.group(1) if match else None
        
        tmp_id = None
        
        if input_id:
            if self._is_steam_id_64(input_id):
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
            # 玩家信息、封禁、在线状态和里程并行查询
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
        
        # --- 获取并格式化上次在线时间 ---
        last_online_raw = player_info.get('lastOnline')
        last_online_formatted = _format_timestamp_to_readable(last_online_raw)
        
        # --- 完整的回复消息构建 (优化格式) ---
        message = "🚚 TMP 玩家详细信息 🛠️\n"
        message += "=" * 25 + "\n"
        message += f"玩家名称: **{player_info.get('name', '未知')}**\n"
        message += f"TMP 编号: {tmp_id}\n"
        
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
        message += f"所属分组: {perms_str}\n"

        vtc_name = player_info.get('vtc', {}).get('name')
        vtc_role = player_info.get('vtc', {}).get('role')
        message += f"所属车队: {vtc_name if vtc_name else '无'}\n"
        if vtc_role:
             message += f"车队角色: {vtc_role}\n"
        
        message += "-" * 25 + "\n"

        # --- 里程信息输出 ---
        total_km = stats_info.get('total_km', 0)
        daily_km = stats_info.get('daily_km', 0)
        
        # 里程数格式化
        formatted_total_km = f"{total_km:,}".replace(',', ' ')
        formatted_daily_km = f"{daily_km:,}".replace(',', ' ')
        
        message += f"🚩 历史里程: **{formatted_total_km} km**\n"
        message += f"📅 今日里程: **{formatted_daily_km} km**\n"
        
        message += "-" * 25 + "\n"
        
        # --- 在线状态 ---
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知位置') 
            
            message += f"🚥 **在线状态: 在线**\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            message += f"🚦 **在线状态: 离线**\n"
            message += f"上次在线: {last_online_formatted}\n"
        
        # --- 封禁信息 ---
        message += f"🚫 是否封禁: {'**是**' if is_banned else '否'}\n"
        
        if ban_count > 0:
            message += f"历史封禁: {ban_count}次\n"

        if is_banned:
            current_ban = None
            if sorted_bans:
                current_ban = next((ban for ban in sorted_bans if ban.get('active')), None) or sorted_bans[0]
                    
            if current_ban:
                ban_reason = current_ban.get('reason', '未知封禁原因')
                ban_expiration = current_ban.get('expiration', banned_until_main) 
                
                message += f"❗ 当前封禁原因: {ban_reason}\n"
                
                if ban_expiration and ban_expiration.lower().startswith('never'):
                    message += f"❗ 封禁截止: **永久封禁**\n"
                else:
                    message += f"❗ 封禁截止: {ban_expiration}\n"
            else:
                message += f"❗ 封禁截止: {banned_until_main}\n"

        # --- 链接和调试信息（可选） ---
        message += "-" * 25 + "\n"
        if steam_id_to_display:
            message += f"🔗 Steam ID: {steam_id_to_display}\n"
            message += f"🔗 TMP 档案: https://truckersmp.com/user/{tmp_id}\n"
            
        if is_debug_request:
            message += "\n--- 🚨 调试信息 (DEBUG) 🚨 ---\n"
            message += f"里程 API: {stats_info.get('debug_error', '无')}\n"
            message += f"在线 API: {online_status.get('debug_error', '无')}\n"
            
            
        yield event.plain_result(message)
    
    @filter.command("DLC") 
    async def tmpdlc(self, event: AstrMessageEvent):
        """[命令: DLC] 查询玩家拥有的地图 DLC 列表。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'DLC\s*(\d+)', message_str) 
        input_id = match.group(1) if match else None
        
        tmp_id = None
        
        if input_id:
            if self._is_steam_id_64(input_id):
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
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
            
        player_name = player_info.get('name', '未知')
        dlc_data = _get_dlc_info(player_info)
        
        message = f"📦 玩家 **{player_name}** (ID: {tmp_id}) 的地图 DLC\n"
        message += "=" * 30 + "\n"
        
        ets2_dlc = dlc_data.get('ets2', [])
        ats_dlc = dlc_data.get('ats', [])

        message += f"🚛 Euro Truck Simulator 2 (数量: {len(ets2_dlc)}):\n"
        if ets2_dlc:
            # 每行 3 个 DLC
            chunks = [ets2_dlc[i:i + 3] for i in range(0, len(ets2_dlc), 3)]
            for chunk in chunks:
                 message += "  - " + " | ".join(chunk) + "\n"
        else:
            message += "  无 ETS2 地图 DLC 记录\n"
            
        message += f"\n🇺🇸 American Truck Simulator (数量: {len(ats_dlc)}):\n"
        if ats_dlc:
            # 每行 3 个 DLC
            chunks = [ats_dlc[i:i + 3] for i in range(0, len(ats_dlc), 3)]
            for chunk in chunks:
                 message += "  - " + " | ".join(chunk) + "\n"
        else:
            message += "  无 ATS 地图 DLC 记录\n"

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
        
        if self._is_steam_id_64(input_id):
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
            
            message = f"✅ 绑定成功！\n"
            message += f"已将您的账号与TMP玩家 **{player_name}** (ID: {tmp_id}) 绑定\n"
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
            yield event.plain_result(f"🗑️ 解绑成功！\n已解除与TMP玩家 {player_name} (ID: {tmp_id}) 的绑定")
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
            if self._is_steam_id_64(input_id):
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
            # 在线状态使用 TruckyApp V3，玩家基本信息使用 TMP 官方 V2
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
        message = f"🎮 玩家 **{player_name}** 实时状态\n"
        message += "=" * 25 + "\n"
        message += f"TMP 编号: {tmp_id}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡" if game_mode_code == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知位置') 
            
            message += f"🚥 **当前状态: 在线**\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            last_online_raw = player_info.get('lastOnline')
            last_online_formatted = _format_timestamp_to_readable(last_online_raw)
            message += f"🚦 **当前状态: 离线**\n"
            message += f"上次在线: {last_online_formatted}\n"
            
        yield event.plain_result(message)


    @filter.command("榜单")
    @filter.command("排行榜")
    async def tmprank(self, event: AstrMessageEvent):
        """[命令: 排行榜/榜单] 查询TruckersMP总里程排行榜前 N 名 (默认为 10)。"""
        
        message_str = event.message_str.strip()
        match = re.search(r'(榜单|排行榜)\s*(\d+)', message_str)
        limit = 10
        if match:
            try:
                # 限制查询数量在 1 到 50 之间，避免 API 负载过高
                limit = max(1, min(50, int(match.group(2))))
            except ValueError:
                pass

        try:
            rank_list = await self._get_rank_list(limit=limit) 
            
        except NetworkException as e:
            yield event.plain_result(f"查询排行榜失败：网络或API请求超时。({str(e)})")
            return
        except Exception:
            yield event.plain_result("查询排行榜失败：发生未知错误")
            return
            
        # --- 回复消息构造 ---
        message = f"🏆 TruckersMP 总里程排行榜 (Top {len(rank_list)})\n"
        message += "=" * 30 + "\n"
        
        if not rank_list:
            message += "当前无数据或 API 返回空列表。"
            yield event.plain_result(message)
            return

        for i, player in enumerate(rank_list):
            total_distance_m = player.get('total', 0)
            total_distance_km = int(total_distance_m / 1000)
            
            rank_icon = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, f"#{i+1}")
            
            name = player.get('name', '未知玩家')
            tmp_id = player.get('tmpid', 'N/A')
            
            formatted_km = f"{total_distance_km:,}".replace(',', ' ')
            
            message += f"{rank_icon} **{name}** (ID: {tmp_id})\n"
            message += f"   里程: **{formatted_km} km**\n"
            
        message += "=" * 30
        message += "\n数据来源于 Trucky App."
            
        yield event.plain_result(message)


# ******************************************************
# 插件结束
# ******************************************************


# --- 🧪 本地测试运行示例 (非 AstrBot 环境运行时使用) ---
async def run_test(command_str: str, user_id: str = "test_user"):
    """模拟 AstrBot 环境运行命令并输出结果"""
    print(f"\n>>> 模拟命令: {command_str} (User: {user_id})")
    
    # 初始化插件
    plugin = TmpBotPlugin(Context())
    await plugin.initialize()
    
    # 模拟事件匹配
    command_name = command_str.split(' ')[0].strip()
    match = re.search(rf'({command_name})\s*(.*)', command_str, re.IGNORECASE)
    
    if command_name == "查询":
        handler = plugin.tmpquery
    elif command_name == "DLC":
        handler = plugin.tmpdlc
    elif command_name == "绑定":
        handler = plugin.tmpbind
    elif command_name == "解绑":
        handler = plugin.tmpunbind
    elif command_name == "状态":
        handler = plugin.tmpstatus
    elif command_name in ["排行榜", "榜单"]:
        handler = plugin.tmprank
    else:
        print("未知的命令。")
        return

    # 创建模拟事件
    event = AstrMessageEvent(message_str=command_str, sender_id=user_id, match=match)
    
    # 运行处理器
    try:
        async for result in handler(event):
            print(f"\n--- 🤖 机器人回复 ---\n{result}\n----------------------")
            break # 只处理第一个结果
    except Exception as e:
        print(f"\n--- ❌ 命令执行错误 ---\n{e}\n----------------------")


if __name__ == '__main__':
    # 实际测试时，请将 ID 替换为有效的 TMP ID 或 Steam ID
    TEST_TMP_ID = "1545"      # 这是一个有效的 TMP ID
    TEST_STEAM_ID = "76561198075778848" # 这是一个有效的 Steam ID

    # --- 测试用例 ---
    async def main_tests():
        # 1. 绑定测试
        await run_test(f"绑定 {TEST_TMP_ID}")
        # 2. 查询绑定用户
        await run_test(f"查询")
        # 3. 查询 Steam ID (需要网络转换)
        await run_test(f"查询 {TEST_STEAM_ID}")
        # 4. 查询 DLC
        await run_test(f"DLC {TEST_TMP_ID}")
        # 5. 查询实时状态
        await run_test(f"状态 {TEST_TMP_ID}")
        # 6. 查询排行榜 (Top 5)
        await run_test(f"排行榜 5")
        # 7. 解绑测试
        await run_test("解绑")


    # 运行所有测试
    try:
        asyncio.run(main_tests())
    except Exception as e:
        print(f"异步主程序运行失败: {e}")