#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.23：服务器列表按 API 原始顺序显示)
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
            self._match = match  # 使用内部变量避免冲突
        def get_sender_id(self) -> str:
            return self._sender_id
        async def plain_result(self, msg):
            return msg
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

# 版本号更新为 1.3.23
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.23", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None 
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        # 统一 User-Agent，并更新版本号
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.3.23'}, 
            timeout=aiohttp.ClientTimeout(total=10)
        )
        logger.info("TMP Bot 插件HTTP会话已创建")

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
            
    async def _get_player_stats(self, tmp_id: str) -> Dict[str, int]:
        """
        通过 da.vtcm.link API 获取玩家的总里程和今日里程 (推测 API 返回公里数)。
        返回: {'total_km': 0, 'daily_km': 0}
        """
        if not self.session: 
            return {'total_km': 0, 'daily_km': 0, 'debug_error': 'HTTP会话不可用。'}

        # 使用用户提供的 API 基础 URL
        vtcm_stats_url = f"https://da.vtcm.link/player/info?tmpId={tmp_id}"
        logger.info(f"尝试 VTCM 里程 API: {vtcm_stats_url}")
        
        try:
            async with self.session.get(vtcm_stats_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('data', {}) # 推测数据在 'data' 字段下
                    
                    # 关键字段推测（根据 API 命名约定和用户提供的 Apifox 文档）
                    total_km = int(response_data.get('totalDistance', 0))
                    daily_km = int(response_data.get('todayDistance', 0))
                    
                    # 检查API是否返回成功状态
                    if data.get('code') != 200 or not response_data:
                        raise ApiResponseException(f"VTCM 里程 API 返回非成功代码或空数据: {data.get('msg', 'N/A')}")


                    return {
                        'total_km': total_km, 
                        'daily_km': daily_km,
                        'debug_error': 'VTCM 里程数据获取成功。'
                    }
                else:
                    return {'total_km': 0, 'daily_km': 0, 'debug_error': f'VTCM 里程 API 返回状态码: {response.status}'}

        except aiohttp.ClientError:
             # 如果连接超时或失败，使用 Trucky App 作为备用 API
            return await self._get_player_stats_fallback(tmp_id)
        except Exception as e:
            logger.error(f"获取玩家统计数据失败 (VTCM): {e.__class__.__name__}")
            # 如果解析失败，使用 Trucky App 作为备用 API
            return await self._get_player_stats_fallback(tmp_id)

    async def _get_player_stats_fallback(self, tmp_id: str) -> Dict[str, int]:
        """
        作为 VTCM API 失败时的备用方案：使用 TruckyApp V3 API 获取玩家里程 (以米为单位)。
        """
        if not self.session: 
            return {'total_km': 0, 'daily_km': 0, 'debug_error': 'Fallback: HTTP会话不可用。'}

        trucky_stats_url = f"https://api.truckyapp.com/v3/player/{tmp_id}/stats"
        logger.info(f"尝试 Trucky V3 API (备用里程): {trucky_stats_url}")
        
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
        仅使用 TruckyApp V3 地图实时接口查询状态。
        """
        if not self.session: 
            return {'online': False, 'debug_error': 'HTTP会话不可用。'}

        # TruckyApp V3 Map Online API (实时状态)
        trucky_url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
        logger.info(f"尝试 Trucky V3 API (地图实时状态): {trucky_url}")
        
        try:
            async with self.session.get(trucky_url, timeout=5) as response:
                
                status = response.status
                
                if status == 200:
                    data = await response.json()
                    online_data = data.get('response') if 'response' in data else data
                    
                    is_online = bool(
                        online_data and 
                        online_data.get('online') is True and 
                        online_data.get('error') is not True
                    )
                    
                    if is_online:
                        server_details = online_data.get('serverDetails', {})
                        server_name = server_details.get('name', f"未知服务器 ({online_data.get('server')})")
                        
                        # --- 位置信息解析 ---
                        location_data = online_data.get('location', {})
                        country = location_data.get('poi', {}).get('country')
                        real_name = location_data.get('poi', {}).get('realName')
                        
                        if not country:
                            country = location_data.get('country')
                        if not real_name:
                            real_name = location_data.get('realName')

                        formatted_location = '未知位置'
                        if country and real_name:
                            formatted_location = f"{country} {real_name}"
                        elif real_name:
                            formatted_location = real_name
                        elif country:
                            formatted_location = country
                        # --- 位置信息解析结束 ---
                        
                        return {
                            'online': True,
                            'serverName': server_name,
                            'game': 1 if server_details.get('game') == 'ETS2' else 2 if server_details.get('game') == 'ATS' else 0,
                            'city': {'name': formatted_location}, 
                            'debug_error': 'Trucky V3 判断在线，并获取到实时数据。'
                        }
                    
                    debug_msg = 'Trucky V3 API 响应判断为离线。'
                    if online_data and online_data.get('error') is True:
                         debug_msg = 'Trucky V3 API 返回错误/延迟状态 (error: true)。'
                         
                    return {
                        'online': False,
                        'debug_error': debug_msg,
                    }
                
                else:
                    return {
                        'online': False, 
                        'debug_error': f"Trucky V3 API 返回非 200 状态码: {status}",
                    }

        except Exception as e:
            logger.error(f"Trucky V3 API 解析失败: {e.__class__.__name__}", exc_info=True)
            return {'online': False, 'debug_error': f'Trucky V3 API 发生意外错误: {e.__class__.__name__}。'}
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
        logger.info(f"尝试 Trucky V3 API (排行榜): {url}")
        
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
                    # 404 可能是由于没有数据或 API 路径改变，返回空列表
                    return []
                else:
                    raise ApiResponseException(f"排行榜 API 返回错误状态码: {response.status}")
        except aiohttp.ClientError:
            raise NetworkException("排行榜 API 网络请求失败")
        except asyncio.TimeoutError:
            raise NetworkException("请求排行榜 API 超时")
        except Exception as e:
            logger.error(f"查询排行榜失败: {e}")
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
        
        # 完整的回复消息构建 (纯文本输出)
        message = "TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        message += f"ID TMP编号: {tmp_id}\n"
        if steam_id_to_display:
            message += f"ID Steam编号: {steam_id_to_display}\n" 
            
        message += f"玩家名称: {player_info.get('name', '未知')}\n"
        
        # --- 上次在线时间 ---
        message += f"上次在线: {last_online_formatted}\n"
        
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
        
        # --- 里程信息输出 ---
        total_km = stats_info.get('total_km', 0)
        daily_km = stats_info.get('daily_km', 0)
        
        message += f"🚩历史里程: {total_km:,} km\n".replace(',', ' ')
        message += f"🚩今日里程: {daily_km:,} km\n".replace(',', ' ')
        
        # --- 封禁信息 ---
        message += f"是否封禁: {'是' if is_banned else '否'}\n"
        
        if ban_count > 0:
            message += f"历史封禁: {ban_count}次\n"

        if is_banned:
            
            current_ban = None
            if sorted_bans:
                current_ban = next((ban for ban in sorted_bans if ban.get('active')), None)
                if not current_ban:
                    current_ban = sorted_bans[0]
                    
            if current_ban:
                ban_reason = current_ban.get('reason', '未知封禁原因 (API V2)')
                ban_expiration = current_ban.get('expiration', banned_until_main) 
                
                message += f"当前封禁原因: {ban_reason}\n"
                
                if ban_expiration and ban_expiration.lower().startswith('never'):
                    message += f"封禁截止: 永久封禁\n"
                else:
                    message += f"封禁截止: {ban_expiration}\n"
                    
            else:
                message += f"当前封禁原因: API详细记录缺失。可能原因：封禁信息被隐藏或数据同步延迟。\n"
                if banned_until_main and banned_until_main.lower().startswith('never'):
                    message += f"封禁截止: 永久封禁\n"
                else:
                    message += f"封禁截止: {banned_until_main}\n"
        
        
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
        message = f"玩家状态查询\n"
        message += "=" * 15 + "\n"
        message += f"玩家名称: {player_name}\n"
        message += f"TMP编号: {tmp_id}\n"
        if steam_id_to_display:
            message += f"Steam编号: {steam_id_to_display}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode_code = online_status.get('game', 0)
            game_mode = "欧卡2" if game_mode_code == 1 else "美卡2" if game_mode_code == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知位置')
            
            message += f"在线状态: 在线\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            message += f"在线状态: 离线\n"

        yield event.plain_result(message)
    
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
            rank = player.get('rank', idx + 1)
            name = player.get('playerName', player.get('name', '未知玩家'))
            distance_m = player.get('totalDistance', player.get('distance', 0))
            
            # 转换为公里并格式化
            distance_km = int(distance_m / 1000)
            distance_str = f"{distance_km:,}".replace(',', ' ')
            
            # 格式化输出：[排名] 玩家名 (ID: TMP ID) - 里程
            tmp_id = player.get('id', 'N/A')
            
            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            
            message += line

        message += "=" * 35 + "\n"
        message += "数据来源: Trucky App V3 API"

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
                        
                        # 筛选所有在线服务器，不进行排序，保持 API 原始顺序
                        online_servers = [s for s in servers if s.get('online')]
                        
                        total_players = sum(s.get('players', 0) for s in online_servers)

                        message = f"TMP服务器状态 (总在线数: {len(online_servers)}个)\n"
                        message += "=" * 30 + "\n"
                        message += f"**[当前总玩家数: {total_players:,}]**\n\n".replace(',', ' ')
                        
                        if online_servers:
                            
                            for server in online_servers:
                                name = server.get('name', '未知')
                                players = server.get('players', 0)
                                max_players = server.get('maxplayers', 0)
                                queue = server.get('queue', 0)
                                
                                # 使用绿色圆点表示在线
                                status_str = '🟢' 
                                
                                # 服务器特性/游戏模式提示
                                feature_str = ""
                                if server.get('speedLimiter') is False:
                                    feature_str += " | 无限速"
                                if server.get('collisions') is False:
                                    feature_str += " | 无碰撞"

                                message += f"服务器: {status_str} {name}\n"
                                
                                players_str = f"玩家人数: {players:,}/{max_players:,}".replace(',', ' ')
                                
                                if queue > 0: 
                                    message += f"  {players_str} (排队: {queue})"
                                else:
                                    message += f"  {players_str}"
                                
                                # 如果有显著特性，则显示
                                if feature_str:
                                    # 提取 "碰撞" 关键字并使用💥符号
                                    if server.get('collisions') is False:
                                        message += "\n  特性: 💥无碰撞"
                                    else:
                                        message += "\n  特性: 💥碰撞"
                                    
                                message += "\n"
                        
                        if not online_servers: message += "暂无在线服务器"
                        
                        message += "=" * 30 
                        yield event.plain_result(message)
                    else:
                        yield event.plain_result("查询服务器状态失败，API数据异常。")
                else:
                    yield event.plain_result(f"查询服务器状态失败，HTTP状态码: {response.status}")
        except Exception:
            yield event.plain_result("网络请求失败，请检查网络或稍后重试。")

    @filter.command("help")
    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: help] 显示本插件的命令使用说明。"""
        help_text = """TMP查询插件使用说明 (无前缀命令)

可用命令:
1. 查询 [ID] - 查询玩家的完整信息（支持 TMP ID 或 Steam ID）。
2. 状态 [ID]- 查询玩家的实时在线状态（支持 TMP ID 或 Steam ID）。 
3. DLC [ID] - 查询玩家拥有的主要地图 DLC 列表（支持 TMP ID 或 Steam ID）。
4. 排行 - 查询 TruckersMP 总里程排行榜前10名。
5. 绑定 [ID] - 绑定您的聊天账号与 TMP ID（支持输入 Steam ID 转换）。
6. 解绑 - 解除账号绑定。
7. 服务器 - 查看所有在线的TMP服务器的实时状态和在线人数。
8. help - 显示此帮助信息。

使用提示: 绑定后可直接发送 查询/状态/DLC (无需ID参数)
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作：关闭HTTP会话。"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")