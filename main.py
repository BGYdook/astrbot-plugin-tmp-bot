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
from typing import Optional, List, Dict, Tuple, Any
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger


# 自定义异常类
class TmpApiException(Exception):
    """TMP 相关异常的基类"""
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


@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.0.4", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        """初始化插件，设置数据路径和HTTP会话。"""
        super().__init__(context)
        self.session = None
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        """初始化网络会话"""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.4'},
            timeout=aiohttp.ClientTimeout(total=10)
        )
        # 注册消息处理器
        self.context.register_message_handler(self.handle_message)

    # --- 内部工具方法 ---
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

    async def _get_player_info(self, tmp_id: str) -> Dict:
        """获取玩家基本信息"""
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, dict):
                        return data.get('response', data)
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                elif response.status == 404:
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                else:
                    raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            raise NetworkException("网络请求失败，请稍后重试")
        except asyncio.TimeoutError:
            logger.error(f"请求超时: {tmp_id}")
            raise NetworkException("请求超时，请稍后重试")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        """获取玩家封禁信息"""
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}/bans"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('response', [])
                return []
        except Exception as e:
            logger.error(f"获取封禁信息失败 {tmp_id}: {e}")
            return []

    async def _get_online_status(self, tmp_id: str) -> Dict:
        """获取玩家在线状态"""
        try:
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # 处理可能的响应格式
                    response_data = data.get('response', {})
                    if isinstance(response_data, list) and response_data:
                        return response_data[0]
                    return response_data
                return {'online': False}
        except Exception as e:
            logger.error(f"获取在线状态失败 {tmp_id}: {e}")
            return {'online': False}

    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[bool, int, List[Dict], str]:
        """格式化封禁信息"""
        if not bans_info or not isinstance(bans_info, list):
            return False, 0, [], ""
        
        # 按时间排序，获取最新的封禁信息
        sorted_bans = sorted(bans_info, 
                           key=lambda x: x.get('created', ''), 
                           reverse=True)
        
        active_bans = [ban for ban in sorted_bans if not ban.get('expired', False)]
        ban_count = len(bans_info)
        is_banned = len(active_bans) > 0
        
        # 获取最新封禁的原因
        ban_reason = active_bans[0].get('reason', '未知封禁原因') if active_bans else ""
            
        return is_banned, ban_count, active_bans, ban_reason

    def _format_player_info(self, player_info: Dict) -> str:
        """格式化玩家权限信息"""
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = []
                if perms.get('isStaff'):
                    groups.append("Staff")
                if perms.get('isManagement'):
                    groups.append("Management") 
                if perms.get('isGameAdmin'):
                    groups.append("Game Admin")
                if groups:
                    perms_str = ', '.join(groups)
            elif isinstance(perms, list) and perms:
                perms_str = ', '.join(perms)
        return perms_str

    async def handle_message(self, event: AstrMessageEvent) -> Optional[MessageEventResult]:
        """处理消息事件"""
        message_str = event.message_str.strip()
        logger.info(f"TMP插件收到消息: {message_str}")
        
        # 检查是否是TMP相关命令
        if message_str in ["服务器", "帮助", "解绑"]:
            return await self._process_command(event, message_str)
        elif message_str.startswith("查询"):
            return await self._process_command(event, "查询", message_str)
        elif message_str.startswith("绑定"):
            return await self._process_command(event, "绑定", message_str)
        elif message_str.startswith("状态"):
            return await self._process_command(event, "状态", message_str)
        
        return None

    async def _process_command(self, event: AstrMessageEvent, command: str, full_message: str = None):
        """处理具体命令"""
        logger.info(f"处理TMP命令: {command}, 完整消息: {full_message or command}")
        
        if command == "服务器":
            return await self._handle_server(event)
        elif command == "帮助":
            return await self._handle_help(event)
        elif command == "解绑":
            return await self._handle_unbind(event)
        elif command == "查询":
            return await self._handle_query(event, full_message)
        elif command == "绑定":
            return await self._handle_bind(event, full_message)
        elif command == "状态":
            return await self._handle_status(event, full_message)
        
        return None

    async def _handle_query(self, event: AstrMessageEvent, message_str: str):
        """处理查询命令"""
        logger.info(f"处理查询命令: {message_str}")
        
        # 提取TMP ID
        tmp_id = None
        if message_str != "查询":
            match = re.search(r'查询\s*(\d+)', message_str)
            if match:
                tmp_id = match.group(1)

        # 如果没有提供ID，尝试使用绑定的ID
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                return event.plain_result("请输入正确的玩家编号，格式：查询 123456，或先使用 绑定 123456 绑定您的账号。")

        try:
            # 并发获取所有信息
            tasks = [
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id), 
                self._get_online_status(tmp_id)
            ]
            player_info, bans_info, online_status = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理可能的异常
            if isinstance(player_info, Exception):
                raise player_info
                
        except PlayerNotFoundException as e:
            return event.plain_result(str(e))
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return event.plain_result(f"查询失败: {str(e)}")
        
        # 格式化信息
        is_banned, ban_count, active_bans, ban_reason = self._format_ban_info(bans_info)
        perms_str = self._format_player_info(player_info)
        
        # 构建回复消息
        message = "🚛 TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        message += f"🆔TMP编号: {tmp_id}\n"
        message += f"😀玩家名称: {player_info.get('name', '未知')}\n"
        message += f"🎮SteamID: {player_info.get('steamID64', player_info.get('steam_id', 'N/A'))}\n"
        message += f"📑注册日期: {player_info.get('joinDate', player_info.get('created_at', 'N/A'))}\n"
        message += f"💼所属分组: {perms_str}\n"

        # 车队信息
        vtc = player_info.get('vtc', {})
        vtc_name = vtc.get('name')
        vtc_role = vtc.get('role')
        message += f"🚚所属车队: {vtc_name if vtc_name else '无'}\n"
        if vtc_role:
            message += f"🚚车队角色: {vtc_role}\n"
        
        # 封禁信息
        message += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
        if is_banned:
            message += f"🚫封禁次数: {ban_count}次\n"
            message += f"🚫封禁原因: {ban_reason}\n"
            if active_bans and active_bans[0].get('expiration'):
                message += f"🚫封禁截止: {active_bans[0]['expiration']}\n"
        elif ban_count > 0:
            message += f"🚫历史封禁: {ban_count}次\n"
        
        # 在线状态
        if online_status and online_status.get('online'):
            message += f"📶在线状态: 在线 🟢\n"
            server_name = online_status.get('serverName', '未知服务器')
            message += f"🖥️所在服务器: {server_name}\n"
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        # 最后更新
        if player_info.get('updated_at'):
            message += f"📶最后更新: {player_info.get('updated_at')}\n"
        
        logger.info(f"查询成功: {tmp_id}")
        return event.plain_result(message)

    async def _handle_bind(self, event: AstrMessageEvent, message_str: str):
        """处理绑定命令"""
        logger.info(f"处理绑定命令: {message_str}")
        
        # 提取TMP ID
        tmp_id = None
        if message_str != "绑定":
            match = re.search(r'绑定\s*(\d+)', message_str)
            if match:
                tmp_id = match.group(1)
        
        if not tmp_id:
            return event.plain_result("请输入正确的玩家编号，格式：绑定 123456")

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            return event.plain_result("玩家不存在，请检查TMP ID是否正确")
        except Exception as e:
            logger.error(f"绑定查询失败: {e}")
            return event.plain_result(f"查询失败: {str(e)}")

        user_id = event.get_sender_id()
        player_name = player_info.get('name', '未知')
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            logger.info(f"绑定成功: {user_id} -> {tmp_id}")
            return event.plain_result(f"✅ 绑定成功！\n已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定")
        else:
            return event.plain_result("❌ 绑定失败，请稍后重试")

    async def _handle_unbind(self, event: AstrMessageEvent):
        """处理解绑命令"""
        logger.info("处理解绑命令")
        
        user_id = event.get_sender_id()
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id, {})
        
        if not user_binding:
            return event.plain_result("❌ 您还没有绑定任何TMP账号")
        
        tmp_id = user_binding.get('tmp_id')
        player_name = user_binding.get('player_name', '未知玩家')
        
        if self._unbind_tmp_id(user_id):
            logger.info(f"解绑成功: {user_id}")
            return event.plain_result(f"✅ 解绑成功！\n已解除与TMP玩家 {player_name} (ID: {tmp_id}) 的绑定")
        else:
            return event.plain_result("❌ 解绑失败，请稍后重试")

    async def _handle_status(self, event: AstrMessageEvent, message_str: str):
        """处理状态命令"""
        logger.info(f"处理状态命令: {message_str}")
        
        # 提取TMP ID
        tmp_id = None
        if message_str != "状态":
            match = re.search(r'状态\s*(\d+)', message_str)
            if match:
                tmp_id = match.group(1)
        
        # 如果没有提供ID，尝试使用绑定的ID
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                return event.plain_result("请输入正确的玩家编号，格式：状态 123456，或先使用 绑定 123456 绑定您的账号。")

        try:
            tasks = [
                self._get_online_status(tmp_id),
                self._get_player_info(tmp_id)
            ]
            online_status, player_info = await asyncio.gather(*tasks, return_exceptions=True)
            
            if isinstance(player_info, Exception):
                raise player_info
                
        except PlayerNotFoundException as e:
            return event.plain_result(str(e))
        except Exception as e:
            logger.error(f"状态查询失败: {e}")
            return event.plain_result(f"查询失败: {str(e)}")
        
        player_name = player_info.get('name', '未知')
        
        message = f"🎮 玩家状态查询\n"
        message += "=" * 15 + "\n"
        message += f"😀玩家名称: {player_name}\n"
        message += f"🆔TMP编号: {tmp_id}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            message += f"📶在线状态: 在线 🟢\n"
            message += f"🖥️所在服务器: {server_name}\n"
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        logger.info(f"状态查询成功: {tmp_id}")
        return event.plain_result(message)

    async def _handle_server(self, event: AstrMessageEvent):
        """处理服务器命令"""
        logger.info("处理服务器命令")
        
        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('response'):
                        servers = data['response']
                        message = "🖥️ TMP服务器状态\n\n"
                        online_servers = [s for s in servers if s.get('online')][:6]
                        
                        for server in online_servers:
                            name = server.get('name', '未知')
                            players = server.get('players', 0)
                            max_players = server.get('maxplayers', 0)
                            queue = server.get('queue', 0)
                            
                            message += f"{'🟢' if players > 0 else '🟡'} {name}\n"
                            message += f"   👥 {players}/{max_players}"
                            if queue > 0:
                                message += f" (排队: {queue})"
                            message += "\n"
                        
                        if not online_servers:
                            message += "暂无在线服务器"
                        logger.info("服务器查询成功")
                        return event.plain_result(message)
                    else:
                        return event.plain_result("查询服务器状态失败")
                else:
                    return event.plain_result("查询服务器状态失败")
        except Exception as e:
            logger.error(f"查询服务器状态失败: {e}")
            return event.plain_result("网络请求失败")

    async def _handle_help(self, event: AstrMessageEvent):
        """处理帮助命令"""
        logger.info("处理帮助命令")
        
        help_text = """🚛 TMP查询插件使用说明 (无前缀命令)

📋 可用命令:
查询 123456    - 查询玩家完整信息
状态 123456    - 查询玩家在线状态  
绑定 123456    - 绑定TMP账号
解绑          - 解除账号绑定
服务器        - 查看服务器状态
帮助          - 显示此帮助信息

💡 使用提示: 绑定后可直接使用 查询 和 状态 (无需参数)
"""
        return event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作。"""
        if self.session:
            await self.session.close()
        logger.info("TMP Bot 插件已卸载")