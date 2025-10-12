#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本
"""

import re
import asyncio
import aiohttp
import json
import os
from typing import Optional, List, Dict, Tuple
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger


# 自定义异常类
class TmpApiException(Exception):
    """TMP API相关异常的基类"""
    pass


class PlayerNotFoundException(TmpApiException):
    """玩家不存在异常"""
    pass


class NetworkException(TmpApiException):
    """网络请求异常"""
    pass


class ApiResponseException(TmpApiException):
    """API响应异常"""
    pass

@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.0.0", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        """
        初始化TMP查询插件。

        设置HTTP会话，初始化插件的数据目录和绑定文件路径，并确保目录存在。

        :param context: AstrBot的上下文对象。
        :type context: Context
        """
        super().__init__(context)
        self.session = None
        # 初始化数据存储路径
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        获取或创建异步HTTP会话 (aiohttp.ClientSession)。

        :returns: 配置了User-Agent的HTTP会话对象。
        :rtype: aiohttp.ClientSession
        """
        if self.session is None:
            headers = {
                'User-Agent': 'AstrBot-TMP-Plugin/1.0.0',
                'Accept': 'application/json',
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    def _load_bindings(self) -> Dict[str, any]:
        """
        从本地文件加载用户ID和TMP ID的绑定数据。

        如果文件不存在或加载失败，返回空字典。

        :returns: 包含绑定信息的字典。
        :rtype: Dict[str, any]
        """
        try:
            if os.path.exists(self.bind_file):
                with open(self.bind_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载绑定数据失败: {e}")
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        """
        将绑定数据保存到本地文件。

        :param bindings: 要保存的绑定信息字典。
        :type bindings: dict
        :returns: 保存是否成功。
        :rtype: bool
        """
        try:
            with open(self.bind_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}")
            return False

    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        """
        获取指定用户绑定的TMP ID。

        :param user_id: 用户的唯一ID。
        :type user_id: str
        :returns: 绑定的TMP ID字符串，如果没有绑定则返回None。
        :rtype: Optional[str]
        """
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id)
        if isinstance(user_binding, dict):
            return user_binding.get('tmp_id')
        # 兼容旧的绑定格式
        return user_binding

    def _bind_tmp_id(self, user_id: str, tmp_id: str, player_name: str) -> bool:
        """
        将用户ID与TMP ID、玩家昵称和绑定时间进行关联存储。

        :param user_id: 用户的唯一ID。
        :type user_id: str
        :param tmp_id: 要绑定的TruckersMP ID。
        :type tmp_id: str
        :param player_name: 玩家昵称。
        :type player_name: str
        :returns: 绑定并保存是否成功。
        :rtype: bool
        """
        bindings = self._load_bindings()
        bindings[user_id] = {
            'tmp_id': tmp_id,
            'player_name': player_name,
            'bind_time': asyncio.get_event_loop().time()
        }
        return self._save_bindings(bindings)

    def _unbind_tmp_id(self, user_id: str) -> bool:
        """
        解除用户的TMP ID绑定。

        :param user_id: 用户的唯一ID。
        :type user_id: str
        :returns: 解除绑定并保存是否成功（如果用户未绑定也会返回False）。
        :rtype: bool
        """
        bindings = self._load_bindings()
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False

    async def _get_player_info(self, tmp_id: str) -> Dict:
        """
        通过TruckersMP API获取玩家的完整档案信息。

        :param tmp_id: 要查询的TruckersMP ID。
        :type tmp_id: str
        :raises PlayerNotFoundException: 玩家不存在 (404)。
        :raises ApiResponseException: API访问被拒绝或返回错误状态码。
        :raises NetworkException: 网络请求失败。
        :returns: 玩家信息的字典数据。
        :rtype: Dict
        """
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            headers = {
                'User-Agent': 'AstrBot-TMP-Plugin/1.0.0',
                'Accept': 'application/json',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"🔍 玩家信息API返回: {data}")
                        
                        if data and isinstance(data, dict):
                            # 官方API返回在'response'字段中，部分第三方API可能直接返回数据
                            return data.get('response') or data
                        else:
                            # 如果JSON数据解析成功但内容为空或格式不正确
                            raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    elif response.status == 404:
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    elif response.status == 403:
                        raise ApiResponseException("TruckersMP API访问被拒绝")
                    else:
                        raise ApiResponseException(f"API返回错误状态码: {response.status}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"查询玩家信息网络错误: {e}")
            raise NetworkException("网络请求失败")
        except Exception as e:
            logger.error(f"查询玩家信息未知错误: {e}")
            raise NetworkException("查询失败")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        """
        通过TruckersMP API获取玩家的封禁历史信息。

        如果查询失败或没有封禁，返回空列表。

        :param tmp_id: 要查询的TruckersMP ID。
        :type tmp_id: str
        :returns: 封禁记录的列表，每项是一个字典。
        :rtype: List[Dict]
        """
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}/bans"
            headers = {
                'User-Agent': 'AstrBot-TMP-Plugin/1.0.0',
                'Accept': 'application/json',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"🔍 封禁信息API返回: {data}")
                        if data and isinstance(data, dict) and data.get('response'):
                            return data['response']
                        return []
                    else:
                        return []
        except Exception:
            # 任何异常（网络错误、解析错误等）都返回空列表，避免中断主查询流程
            return []

    async def _get_online_status(self, tmp_id: str) -> Dict:
        """
        通过TruckyApp API获取玩家的实时在线状态和位置信息。

        如果查询失败或玩家离线，返回包含 {'online': False} 的字典。

        :param tmp_id: 要查询的TruckersMP ID。
        :type tmp_id: str
        :returns: 包含在线状态、服务器、位置等信息的字典。
        :rtype: Dict
        """
        try:
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            headers = {
                'User-Agent': 'AstrBot-TMP-Plugin/1.0.0',
                'Accept': 'application/json',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('response'):
                            return data['response']
                        return {'online': False}
                    else:
                        return {'online': False}
        except Exception:
            # 任何异常都返回离线状态
            return {'online': False}

    def _extract_tmp_id(self, message: str, command: str) -> Optional[str]:
        """
        从用户消息中提取紧跟在命令后的TMP ID。

        支持带空格和不带空格的格式，例如："查询 123456" 或 "查询123456"。

        :param message: 原始消息字符串。
        :type message: str
        :param command: 命令的文本，例如 "查询" 或 "绑定"。
        :type command: str
        :returns: 提取到的TMP ID字符串，如果匹配失败则返回None。
        :rtype: Optional[str]
        """
        pattern = rf"^{command}\s*(\d+)$"
        match = re.match(pattern, message.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[bool, int, List[Dict], str]:
        """
        格式化和分析封禁信息列表。

        :param bans_info: 从API获取的封禁记录列表。
        :type bans_info: List[Dict]
        :returns: (是否活跃封禁, 总封禁次数, 活跃封禁记录列表, 最新活跃封禁原因)。
        :rtype: Tuple[bool, int, List[Dict], str]
        """
        if not bans_info or not isinstance(bans_info, list):
            return False, 0, [], ""
        
        # 获取活跃封禁（未过期的封禁）
        active_bans = [
            ban for ban in bans_info 
            if not ban.get('expired', False) # 检查API的'expired'字段
        ]
        
        ban_count = len(bans_info)
        is_banned = len(active_bans) > 0
        ban_reason = ""
        
        if active_bans:
            # 取最近的活跃封禁作为原因（通常API返回是按时间排序）
            latest_ban = active_bans[0]
            ban_reason = latest_ban.get('reason', '未知封禁原因')
            
        return is_banned, ban_count, active_bans, ban_reason

    @filter.command("查询")
    async def tmpquery(self, event: AstrMessageEvent):
        """
        [命令: /查询] TMP玩家完整信息查询。

        如果消息中包含TMP ID，则查询该ID；否则查询发送者绑定的ID。
        并发获取玩家基本信息、封禁记录和在线状态。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 包含玩家详细信息的回复消息。
        :rtype: MessageEventResult
        """
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "查询")
        
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：查询 123456")
                return

        logger.info(f"查询TMP玩家: {tmp_id}")
        
        try:
            # 并发获取玩家信息、封禁信息和在线状态
            tasks = [
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id),
                self._get_online_status(tmp_id)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            player_info, bans_info, online_status = results
            
            # 检查玩家信息是否获取失败（其他信息失败作为空值处理）
            if isinstance(player_info, Exception):
                raise player_info
            
            if isinstance(bans_info, Exception):
                bans_info = [] # 忽略封禁查询失败
            if isinstance(online_status, Exception):
                online_status = {'online': False} # 忽略在线状态查询失败
            
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        # 格式化封禁信息
        is_banned, ban_count, active_bans, ban_reason = self._format_ban_info(bans_info)
        
        # 根据官方API文档构建完整的回复消息
        message = "🚛 TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        
        # 🆔TMP编号
        message += f"🆔TMP编号: {tmp_id}\n"
        
        # 😀玩家名称
        message += f"😀玩家名称: {player_info.get('name', '未知')}\n"
        
        # 🎮SteamID (根据API文档)
        if player_info.get('steam_id'):
            message += f"🎮SteamID: {player_info.get('steam_id')}\n"
        elif player_info.get('steamID64'):
            message += f"🎮SteamID: {player_info.get('steamID64')}\n"
        
        # 📑注册日期 (根据API文档，created_at)
        if player_info.get('created_at'):
            message += f"📑注册日期: {player_info.get('created_at')}\n"
        elif player_info.get('joinDate'):
            message += f"📑注册日期: {player_info.get('joinDate')}\n"
        
        # 💼所属分组 (修复显示问题)
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                # 处理字典格式的权限
                groups = []
                if perms.get('isStaff'):
                    groups.append("Staff")
                if perms.get('isManagement'):
                    groups.append("Management")
                if perms.get('isGameAdmin'):
                    groups.append("Game Admin")
                if perms.get('showDetailedOnWebMaps'):
                    groups.append("Web Maps")
                
                if groups:
                    message += f"💼所属分组: {', '.join(groups)}\n"
                else:
                    message += f"💼所属分组: 玩家\n"
            elif isinstance(perms, list) and perms:
                message += f"💼所属分组: {', '.join(perms)}\n"
            elif perms:
                message += f"💼所属分组: {perms}\n"
        else:
            message += f"💼所属分组: 玩家\n"
        
        # 🚚所属车队 (删除车队ID显示)
        if player_info.get('vtc'):
            vtc = player_info['vtc']
            if vtc.get('name'):
                message += f"🚚所属车队: {vtc.get('name')}\n"
            if vtc.get('role'):
                message += f"🚚车队角色: {vtc.get('role')}\n"
        else:
            message += f"🚚所属车队: 无\n"
        
        # 🚫封禁信息 - 使用格式化后的封禁信息
        message += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
        
        if is_banned:
            message += f"🚫封禁次数: {ban_count}次\n"
            
            # 显示封禁原因
            if ban_reason:
                message += f"🚫封禁原因: {ban_reason}\n"
            else:
                message += f"🚫封禁原因: 未知原因\n"
            
            # 显示封禁截止时间（如果有）
            if active_bans:
                latest_ban = active_bans[0]
                expiration = latest_ban.get('expiration')
                if expiration:
                    message += f"🚫封禁截止: {expiration}\n"
                
                # 显示封禁管理员（如果有）
                admin = latest_ban.get('admin')
                if admin:
                    message += f"🚫封禁管理: {admin}\n"
        else:
            if ban_count > 0:
                message += f"🚫历史封禁: {ban_count}次\n"
        
        # 🚩里程信息 (需要额外API)
        message += f"🚩历史里程: 需要里程API\n"
        message += f"🚩今日里程: 需要里程API\n"
        
        # 📶在线状态
        if online_status and online_status.get('online'):
            message += f"📶在线状态: 在线 🟢\n"
            server_name = online_status.get('serverName', '未知服务器')
            message += f"🖥️所在服务器: {server_name}\n"
            
            # 位置信息
            if online_status.get('location'):
                location = online_status.get('location', {})
                country = location.get('country', '')
                city = location.get('city', '')
                if country or city:
                    message += f"🌍当前位置: {country} {city}\n"
            
            # 游戏信息
            if online_status.get('game'):
                message += f"🎯当前游戏: {online_status.get('game')}\n"
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        # 📶上次在线 (根据API文档，updated_at)
        if player_info.get('updated_at'):
            message += f"📶最后更新: {player_info.get('updated_at')}\n"
        else:
            message += f"📶上次在线: 未知\n"
        
        yield event.plain_result(message)

    @filter.command("绑定")
    async def tmpbind(self, event: AstrMessageEvent):
        """
        [命令: /绑定] 绑定QQ/群用户ID与TruckersMP ID。

        执行API查询验证ID的有效性，并存储用户-ID的映射关系。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 绑定成功或失败的回复消息。
        :rtype: MessageEventResult
        """
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "绑定")
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号，格式：绑定 123456")
            return

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result("玩家不存在，请检查TMP ID是否正确")
            return
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        user_id = event.get_sender_id()
        player_name = player_info.get('name', '未知')
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            yield event.plain_result(f"✅ 绑定成功！\n已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定")
            logger.info(f"用户 {user_id} 绑定TMP ID: {tmp_id}")
        else:
            yield event.plain_result("❌ 绑定失败，请稍后重试")

    @filter.command("解绑")
    async def tmpunbind(self, event: AstrMessageEvent):
        """
        [命令: /解绑] 解除当前用户的TruckersMP ID绑定。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 解绑成功或失败的回复消息。
        :rtype: MessageEventResult
        """
        user_id = event.get_sender_id()
        bound_info = self._get_bound_tmp_id(user_id)
        
        if not bound_info:
            yield event.plain_result("❌ 您还没有绑定任何TMP账号")
            return
        
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id, {})
        # 兼容处理旧的绑定格式
        tmp_id = user_binding.get('tmp_id') if isinstance(user_binding, dict) else bound_info
        player_name = user_binding.get('player_name', '未知玩家') if isinstance(user_binding, dict) else '未知玩家'
        
        if self._unbind_tmp_id(user_id):
            yield event.plain_result(f"✅ 解绑成功！\n已解除与TMP玩家 {player_name} (ID: {tmp_id}) 的绑定")
            logger.info(f"用户 {user_id} 解除TMP ID绑定: {tmp_id}")
        else:
            yield event.plain_result("❌ 解绑失败，请稍后重试")

    @filter.command("状态")
    async def tmpstatus(self, event: AstrMessageEvent):
        """
        [命令: /状态] 查询玩家的实时在线状态。

        如果消息中包含TMP ID，则查询该ID；否则查询发送者绑定的ID。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 包含玩家在线状态信息的回复消息。
        :rtype: MessageEventResult
        """
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "状态")
        
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：状态 123456")
                return

        logger.info(f"查询玩家状态: {tmp_id}")
        
        try:
            # 两个查询可以并发进行，虽然在线状态主要依赖TruckyApp
            tasks = [self._get_online_status(tmp_id), self._get_player_info(tmp_id)]
            online_status, player_info = await asyncio.gather(*tasks)

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        player_name = player_info.get('name', '未知')
        
        message = f"🎮 玩家状态查询\n"
        message += "=" * 15 + "\n"
        message += f"😀玩家名称: {player_name}\n"
        message += f"🆔TMP编号: {tmp_id}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            message += f"📶在线状态: 在线 🟢\n"
            message += f"🖥️所在服务器: {server_name}\n"
            
            # 位置信息
            if online_status.get('location'):
                location = online_status.get('location', {})
                country = location.get('country', '')
                city = location.get('city', '')
                if country or city:
                    message += f"🌍当前位置: {country} {city}\n"
            
            # 游戏信息
            if online_status.get('game'):
                message += f"🎯当前游戏: {online_status.get('game')}\n"
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        yield event.plain_result(message)

    @filter.command("服务器")
    async def tmpserver(self, event: AstrMessageEvent):
        """
        [命令: /服务器] 查询TruckersMP官方服务器的实时状态。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 包含服务器名称、在线人数和排队信息的回复消息。
        :rtype: MessageEventResult
        """
        logger.info("查询TMP服务器状态")
        
        try:
            url = "https://api.truckersmp.com/v2/servers"
            headers = {
                'User-Agent': 'AstrBot-TMP-Plugin/1.0.0',
                'Accept': 'application/json',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('response'):
                            servers = data['response']
                            message = "🖥️ TMP服务器状态\n\n"
                            
                            online_servers = [s for s in servers if s.get('online')]
                            # 仅显示前6个服务器以避免消息过长
                            for server in online_servers[:6]:
                                name = server.get('name', '未知')
                                players = server.get('players', 0)
                                max_players = server.get('maxplayers', 0)
                                queue = server.get('queue', 0)
                                
                                status = "🟢" if players > 0 else "🟡"
                                message += f"{status} {name}\n"
                                message += f"   👥 {players}/{max_players}"
                                if queue > 0:
                                    message += f" (排队: {queue})"
                                message += "\n"
                            
                            if not online_servers:
                                message += "暂无在线服务器"
                                
                            yield event.plain_result(message)
                        else:
                            yield event.plain_result("查询服务器状态失败")
                    else:
                        yield event.plain_result("查询服务器状态失败")
        except Exception as e:
            logger.error(f"查询服务器状态失败: {e}")
            yield event.plain_result("网络请求失败")

    @filter.command("帮助")
    async def tmphelp(self, event: AstrMessageEvent):
        """
        [命令: /帮助] 显示本插件的命令使用说明。

        :param event: AstrBot消息事件对象。
        :type event: AstrMessageEvent
        :yields: 插件帮助信息的回复消息。
        :rtype: MessageEventResult
        """
        help_text = """🚛 TMP查询插件使用说明

📋 可用命令:
/查询 123456    - 查询玩家完整信息
/状态 123456    - 查询玩家在线状态  
/绑定 123456    - 绑定TMP账号
/解绑          - 解除账号绑定
/服务器        - 查看服务器状态
/帮助          - 显示此帮助信息

💡 使用提示:
- 绑定后可直接使用 /查询 和 /状态 命令
- 支持格式: /查询123456 或 /查询 123456
- 数据来源: TruckersMP官方API
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """
        插件卸载时的清理工作。

        用于关闭所有活跃的HTTP会话，释放资源。
        """
        if self.session:
            await self.session.close()
        logger.info("TMP Bot 插件已卸载")