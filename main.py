#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.2.9：恢复标准命令匹配模式，依赖框架处理群聊前缀)
"""

import re
import asyncio
import aiohttp
import json
import os
from typing import Optional, List, Dict, Tuple, Any

# 引入 AstrBot 核心 API
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
except ImportError:
    # 最小化兼容回退
    class _DummyFilter:
        # 移除 regex=True 确保匹配的是固定命令，而不是正则
        def command(self, pattern, **kwargs): 
            def decorator(func):
                return func
            return decorator
    filter = _DummyFilter()

    # 简化模拟类以确保代码块可执行
    class AstrMessageEvent:
        def __init__(self, message_str: str = "", sender_id: str = "0", match=None):
            self.message_str = message_str
            self._sender_id = sender_id
            self.match = match
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
        def error(msg):
            print("[ERROR]", msg)

    logger = _Logger()


# 自定义异常类 (保持不变)
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

# 版本号更新为 1.2.9
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.2.9", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        """初始化插件，设置数据路径和HTTP会话引用。"""
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None 
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        """在插件启动时，创建持久的HTTP会话。"""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.2.7'},
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

    # --- API请求方法 (保持不变) ---

    async def _get_tmp_id_from_steam_id(self, steam_id: str) -> str:
        """根据 Steam ID (17位) 查询对应的 TruckersMP ID"""
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        
        try:
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
            raise NetworkException("Steam ID 转换查询失败")
            
    def _get_steam_id_from_player_info(self, player_info: Dict) -> Optional[str]:
        """从 V2 Player API 响应中提取 Steam ID"""
        steam_id = player_info.get('steamID64')
        return str(steam_id) if steam_id else None

    async def _get_player_info(self, tmp_id: str) -> Dict:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        
        try:
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

    async def _get_online_status(self, tmp_id: str) -> Dict:
        if not self.session: return {'online': False}

        try:
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response', {})
                    if isinstance(response_data, list) and response_data:
                        return response_data[0]
                    return {'online': False}
                return {'online': False}
        except Exception:
            return {'online': False}

    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[int, List[Dict]]:
        """只返回历史封禁次数和最新的封禁记录（按时间倒序）"""
        if not bans_info or not isinstance(bans_info, list):
            return 0, []
        
        # 按创建时间降序排列，确保第一个是最新记录
        sorted_bans = sorted(bans_info, key=lambda x: x.get('timeAdded', ''), reverse=True)
        return len(bans_info), sorted_bans


    # ******************************************************
    # 命令处理器 (版本 1.2.9 - 恢复标准命令匹配)
    # ******************************************************
    
    # 恢复为标准命令匹配，不再使用正则表达式前缀匹配
    @filter.command("查询") 
    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] TMP玩家完整信息查询。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        # 匹配 '查询' 后面的空格和数字
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
            player_info_raw, bans_info, online_status = await asyncio.gather(
                self._get_player_info(tmp_id), 
                self._get_player_bans(tmp_id), 
                self._get_online_status(tmp_id)
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
        
        # 完整的回复消息构建 (纯文本输出)
        message = "TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        message += f"ID TMP编号: {tmp_id}\n"
        if steam_id_to_display:
            message += f"ID Steam编号: {steam_id_to_display}\n" 
            
        message += f"玩家名称: {player_info.get('name', '未知')}\n"
        
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
            game_mode = "欧卡2" if online_status.get('game', 0) == 1 else "美卡" if online_status.get('game', 0) == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知城市')
            message += f"在线状态: 在线\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            message += f"在线状态: 离线\n"
        
        yield event.plain_result(message)

    @filter.command("绑定")
    async def tmpbind(self, event: AstrMessageEvent):
        """[命令: 绑定] 绑定您的聊天账号与TMP ID。支持输入 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'绑定\s*(\d+)', message_str)
        input_id = match.group(1) if match else None

        if not input_id:
            yield event.plain_result("请输入正确的玩家编号，格式：绑定 [TMP ID]")
            return

        tmp_id = input_id
        is_steam_id = (len(input_id) == 17 and input_id.startswith('7'))

        if is_steam_id:
            try:
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
        
        # 匹配 '状态' 后面的空格和数字
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
        
        message = f"玩家状态查询\n"
        message += "=" * 15 + "\n"
        message += f"玩家名称: {player_name}\n"
        message += f"TMP编号: {tmp_id}\n"
        if steam_id_to_display:
            message += f"Steam编号: {steam_id_to_display}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            game_mode = "欧卡2" if online_status.get('game', 0) == 1 else "美卡2" if online_status.get('game', 0) == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知城市')
            message += f"在线状态: 在线\n"
            message += f"所在服务器: {server_name}\n"
            message += f"所在位置: {city} ({game_mode})\n"
        else:
            message += f"在线状态: 离线\n"
        
        yield event.plain_result(message)

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
                        message = "TMP服务器状态\n"
                        message += "=" * 25 + "\n"
                        
                        online_servers = sorted(
                            [s for s in servers if s.get('online')],
                            key=lambda s: s.get('players', 0),
                            reverse=True
                        )[:6]
                        
                        for server in online_servers:
                            name, players, max_players, queue = server.get('name', '未知'), server.get('players', 0), server.get('maxplayers', 0), server.get('queue', 0)
                            status_str = '[在线]' if players > 0 else '[空闲]'
                            
                            message += f"{status_str} {name}\n"
                            message += f"  在线人数: {players}/{max_players}"
                            if queue > 0: message += f" (排队: {queue})"
                            message += "\n"
                        
                        if not online_servers: message += "暂无在线服务器"
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
3. 绑定 [ID] - 绑定您的聊天账号与 TMP ID（支持输入 Steam ID 转换）。
4. 解绑 - 解除账号绑定。
5. 服务器 - 查看主要TMP服务器的实时状态和在线人数。
6. help - 显示此帮助信息。

使用提示: 绑定后可直接发送 查询 或 定位 (无需ID参数)
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作：关闭HTTP会话。"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")