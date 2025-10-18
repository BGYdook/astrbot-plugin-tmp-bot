#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot (final version)
欧卡2TMP查询插件 - 修复 register_commands 参数错误
"""

import re
import asyncio
import aiohttp
import json
import os
from typing import Optional, List, Dict, Tuple, Any
from astrbot.api.event import AstrMessageEvent, MessageEventResult
# 确保 astrbot 库和 api 路径正确
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


# 重点：使用新的插件ID "tmp-bot-final" 来规避旧的缓存问题
@register("tmp-bot-final", "BGYdook", "欧卡2TMP查询插件", "1.0.6", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        """初始化插件，设置数据路径和HTTP会话。"""
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None 
        
        # 重点：修改数据目录名称以匹配新的插件ID
        self.data_dir = StarTools.get_data_dir("tmp-bot-final")
        
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        """初始化网络会话并注册命令"""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.6'},
            timeout=aiohttp.ClientTimeout(total=10)
        )
        
        # 🚨 最终修复：定义命令列表，包含 command_name, desc, handler
        commands_to_register = [
            # 顺序: command_name, desc, handler
            ("查询", "查询TMP玩家完整信息 (查询 ID)", self._handle_query),
            ("状态", "查询玩家在线状态和位置 (状态 ID)", self._handle_status),
            ("绑定", "绑定TMP账号 (绑定 ID)", self._handle_bind),
            ("解绑", "解绑TMP账号", self._handle_unbind),
            ("服务器", "查看TMP服务器状态", self._handle_server),
            ("帮助", "显示插件帮助信息", self._handle_help),
        ]
        
        # 循环注册每个命令，传入所有4个必要的位置参数 (command_name, desc, priority=0, awaitable=handler)
        # priority 设为 0 作为默认值
        for name, desc, handler in commands_to_register:
            self.context.register_commands(name, desc, 0, handler)
        
    
    # --- 数据持久化方法 (保持不变) ---
    def _load_bindings(self) -> Dict[str, Any]:
        """从文件加载用户绑定数据"""
        try:
            if os.path.exists(self.bind_file):
                with open(self.bind_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载绑定数据失败: {e}")
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        """将用户绑定数据保存到文件"""
        try:
            with open(self.bind_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}")
            return False

    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        """获取指定用户绑定的TMP ID"""
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id)
        if isinstance(user_binding, dict):
            return user_binding.get('tmp_id')
        return user_binding 

    def _bind_tmp_id(self, user_id: str, tmp_id: str, player_name: str) -> bool:
        """绑定用户ID和TMP ID"""
        bindings = self._load_bindings()
        bindings[user_id] = {
            'tmp_id': tmp_id,
            'player_name': player_name,
            'bind_time': asyncio.get_event_loop().time()
        }
        return self._save_bindings(bindings)

    def _unbind_tmp_id(self, user_id: str) -> bool:
        """解除用户绑定的TMP ID"""
        bindings = self._load_bindings()
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False

    # --- API请求方法 (保持不变) ---
    async def _get_player_info(self, tmp_id: str) -> Dict:
        """获取玩家基本信息 (v2/player/{tmp_id})"""
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with self.session.get(url) as response:
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
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            raise NetworkException("TruckersMP API 网络请求失败，请稍后重试")
        except asyncio.TimeoutError:
            logger.error(f"请求超时: {tmp_id}")
            raise NetworkException("请求TruckersMP API超时，请稍后重试")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        """获取玩家封禁信息 (v2/player/{tmp_id}/bans)"""
        if not self.session: return []

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
        """获取玩家在线状态 (使用 TruckyApp API)"""
        if not self.session: return {'online': False}
        
        try:
            # TruckyApp API 提供了更实时的在线和位置信息
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response', {})
                    if isinstance(response_data, list) and response_data:
                        return response_data[0]
                    return {'online': False}
                return {'online': False}
        except Exception as e:
            logger.error(f"获取在线状态失败 {tmp_id}: {e}")
            return {'online': False}

    # --- 格式化方法 (保持不变) ---
    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[bool, int, Optional[Dict], str]:
        """格式化封禁信息"""
        if not bans_info or not isinstance(bans_info, list):
            return False, 0, None, ""
        
        sorted_bans = sorted(bans_info, key=lambda x: x.get('created', ''), reverse=True)
        active_bans = [ban for ban in sorted_bans if not ban.get('expired', False)]
        ban_count = len(bans_info)
        is_banned = len(active_bans) > 0
        latest_active_ban = active_bans[0] if active_bans else None
        ban_reason = latest_active_ban.get('reason', '未知封禁原因') if latest_active_ban else ""
            
        return is_banned, ban_count, latest_active_ban, ban_reason

    def _format_player_info(self, player_info: Dict) -> str:
        """格式化玩家权限信息"""
        perms_str = "玩家"
        perms = player_info.get('permissions')

        if perms and isinstance(perms, dict):
            groups = []
            if perms.get('isStaff'): groups.append("Staff")
            if perms.get('isManagement'): groups.append("Management") 
            if perms.get('isGameAdmin'): groups.append("Game Admin")
            if groups: perms_str = ', '.join(groups)
        elif perms and isinstance(perms, list) and perms:
            perms_str = ', '.join(perms)
        return perms_str

    # --- 命令处理器 (保持不变) ---
    async def _handle_query(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理查询命令: 查询 TMP ID"""
        tmp_id = args[0] if args and args[0].isdigit() else self._get_bound_tmp_id(event.get_sender_id())
        
        if not tmp_id:
            return event.plain_result("请输入正确的玩家编号（纯数字），格式：查询 123456，或先使用 绑定 123456。")

        try:
            tasks = [self._get_player_info(tmp_id), self._get_player_bans(tmp_id), self._get_online_status(tmp_id)]
            player_info, bans_info, online_status = await asyncio.gather(*tasks, return_exceptions=True)
            
            if isinstance(player_info, Exception): raise player_info
            
        except PlayerNotFoundException as e:
            return event.plain_result(str(e))
        except Exception as e:
            return event.plain_result(f"查询失败: {type(e).__name__}: {str(e)}")
        
        is_banned, ban_count, latest_active_ban, ban_reason = self._format_ban_info(bans_info)
        perms_str = self._format_player_info(player_info)
        
        # 构建回复消息
        message = "🚛 **TMP玩家详细信息**\n"
        message += "=" * 20 + "\n"
        message += f"🆔TMP编号: **{tmp_id}**\n"
        message += f"😀玩家名称: **{player_info.get('name', '未知')}**\n"
        message += f"💼所属分组: {perms_str}\n"
        message += f"🚚所属车队: {player_info.get('vtc', {}).get('name', '无')}\n"
        
        message += f"🚫是否封禁: **{'是 🚨' if is_banned else '否 ✅'}**"
        if is_banned:
            message += f"\n🚫封禁原因: {ban_reason}\n🚫封禁截止: {latest_active_ban.get('expiration', 'N/A')}"
        elif ban_count > 0:
            message += f" (历史封禁: {ban_count}次)\n"
        else:
            message += "\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知')
            game_mode = "欧卡2" if online_status.get('game', 0) == 1 else "美卡2" if online_status.get('game', 0) == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知城市')
            message += f"📶**在线状态: 在线 🟢**\n"
            message += f"🖥️所在服务器: {server_name}\n"
            message += f"🗺️所在位置: {city} ({game_mode})\n"
        else:
            message += f"📶**在线状态: 离线 🔴**\n"
        
        return event.plain_result(message)

    async def _handle_bind(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理绑定命令"""
        if not args or not args[0].isdigit():
            return event.plain_result("请输入正确的玩家编号（纯数字），格式：绑定 123456")
        
        tmp_id = args[0]
        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            return event.plain_result("玩家不存在，请检查TMP ID是否正确")
        except Exception as e:
            return event.plain_result(f"查询失败: {type(e).__name__}: {str(e)}")

        player_name = player_info.get('name', '未知')
        if self._bind_tmp_id(event.get_sender_id(), tmp_id, player_name):
            return event.plain_result(f"✅ **绑定成功！**\n已将您的账号与TMP玩家 **{player_name}** (ID: {tmp_id}) 绑定")
        else:
            return event.plain_result("❌ 绑定失败，请稍后重试")

    async def _handle_unbind(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理解绑命令"""
        user_binding = self._load_bindings().get(event.get_sender_id(), {})
        
        if not user_binding or not user_binding.get('tmp_id'):
            return event.plain_result("❌ 您还没有绑定任何TMP账号")
        
        tmp_id = user_binding.get('tmp_id')
        player_name = user_binding.get('player_name', '未知玩家')
        
        if self._unbind_tmp_id(event.get_sender_id()):
            return event.plain_result(f"✅ **解绑成功！**\n已解除与TMP玩家 **{player_name}** (ID: {tmp_id}) 的绑定")
        else:
            return event.plain_result("❌ 解绑失败，请稍后重试")

    async def _handle_status(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理状态命令: 查询在线状态和位置"""
        tmp_id = args[0] if args and args[0].isdigit() else self._get_bound_tmp_id(event.get_sender_id())
        
        if not tmp_id:
            return event.plain_result("请输入正确的玩家编号，格式：状态 123456，或先使用 绑定 123456。")

        try:
            tasks = [self._get_online_status(tmp_id), self._get_player_info(tmp_id)]
            online_status, player_info = await asyncio.gather(*tasks, return_exceptions=True)
            
            player_name = player_info.get('name', '未知玩家 (查询失败)') if not isinstance(player_info, Exception) else "未知玩家"

        except Exception as e:
            return event.plain_result(f"查询失败: {type(e).__name__}: {str(e)}")
        
        message = f"🎮 **玩家状态查询**\n"
        message += "=" * 15 + "\n"
        message += f"😀玩家名称: **{player_name}**\n"
        message += f"🆔TMP编号: **{tmp_id}**\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知')
            game_mode = "欧卡2" if online_status.get('game', 0) == 1 else "美卡2" if online_status.get('game', 0) == 2 else "未知游戏"
            city = online_status.get('city', {}).get('name', '未知城市')
            message += f"📶**在线状态: 在线 🟢**\n"
            message += f"🖥️所在服务器: {server_name}\n"
            message += f"🗺️所在位置: {city} ({game_mode})\n"
        else:
            message += f"📶**在线状态: 离线 🔴**\n"
        
        return event.plain_result(message)

    async def _handle_server(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理服务器命令: 查看服务器状态"""
        if not self.session: return event.plain_result("插件初始化中，请稍后重试")

        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    servers = data.get('response', [])
                    
                    if servers and isinstance(servers, list):
                        message = "🖥️ **TMP服务器状态** (按在线人数排序)\n"
                        message += "=" * 25 + "\n"
                        online_servers = sorted(
                            [s for s in servers if s.get('online')],
                            key=lambda s: s.get('players', 0),
                            reverse=True
                        )[:6]
                        
                        for server in online_servers:
                            name = server.get('name', '未知')
                            players = server.get('players', 0)
                            max_players = server.get('maxplayers', 0)
                            queue = server.get('queue', 0)
                            status_icon = '🟢' if players > 0 else '🟡'
                            
                            message += f"{status_icon} **{name}**\n"
                            message += f"   👥 在线: {players}/{max_players}"
                            if queue > 0: message += f" (排队: {queue})"
                            message += "\n"
                        
                        if not online_servers: message += "暂无在线服务器"
                        return event.plain_result(message)
                    else:
                        return event.plain_result("查询服务器状态失败，API数据异常。")
                else:
                    return event.plain_result(f"查询服务器状态失败，HTTP状态码: {response.status}")
        except Exception as e:
            return event.plain_result("网络请求失败，请检查网络或稍后重试。")

    async def _handle_help(self, event: AstrMessageEvent, args: List[str]) -> MessageEventResult:
        """处理帮助命令"""
        help_text = """🚛 **欧卡2 TMP查询插件使用说明**

💡 **核心功能**：查询玩家信息、在线状态、服务器状态。

📋 **可用命令**:
1. **查询 [ID]** - 查询玩家的完整信息（封禁、车队、权限等）。
2. **状态 [ID]** - 查询玩家的实时在线状态、所在服务器和位置。 
3. **绑定 [ID]** - 绑定您的聊天账号与TMP ID。绑定后，可直接使用“查询”或“状态”。
4. **解绑** - 解除账号绑定。
5. **服务器** - 查看主要TMP服务器的实时状态和在线人数。
6. **帮助** - 显示此帮助信息。

**示例**: 
- `查询 123456`
- `绑定 654321` (绑定后可直接发送 `查询`)
"""
        return event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作。"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")