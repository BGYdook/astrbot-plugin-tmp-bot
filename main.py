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
# 使用标准的 filter.command 装饰器，需要前缀 /
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


class NetworkException(Exception):
    """网络请求异常"""
    pass


class ApiResponseException(TmpApiException):
    """API响应异常"""
    pass

@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.0.0", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        """初始化插件，设置数据路径和HTTP会话。"""
        super().__init__(context)
        self.session = None
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    # --- 内部工具方法 ---
    def _load_bindings(self) -> Dict[str, any]:
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
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and isinstance(data, dict):
                            return data.get('response') or data
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    elif response.status == 404:
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    else:
                        raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except aiohttp.ClientError as e:
            raise NetworkException("网络请求失败")
        except Exception as e:
            raise NetworkException("查询失败")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}/bans"
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('response', [])
                    return []
        except Exception:
            return []

    async def _get_online_status(self, tmp_id: str) -> Dict:
        try:
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('response', {'online': False})
                    return {'online': False}
        except Exception:
            return {'online': False}

    def _extract_tmp_id(self, message: str) -> Optional[str]:
        """从消息中提取数字ID。"""
        parts = message.strip().split()
        if parts and parts[0].isdigit():
             return parts[0]
        return None
    
    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[bool, int, List[Dict], str]:
        if not bans_info or not isinstance(bans_info, list):
            return False, 0, [], ""
        
        active_bans = [ban for ban in bans_info if not ban.get('expired', False)]
        ban_count = len(bans_info)
        is_banned = len(active_bans) > 0
        ban_reason = active_bans[0].get('reason', '未知封禁原因') if active_bans else ""
            
        return is_banned, ban_count, active_bans, ban_reason

    # ******************************************************
    # 使用 filter.command 装饰器，需要前缀 / (例如：/查询 123456)
    # ******************************************************
    @filter.command("查询")
    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: /查询] TMP玩家完整信息查询。"""
        # 使用 event.message_str 手动解析参数
        message_str = event.message_str.strip()
        
        # 移除 "/查询" 部分，获取参数内容
        command_prefix = "/查询"
        if message_str.startswith(command_prefix):
            message_content = message_str[len(command_prefix):].strip()
        else:
            message_content = "" 

        tmp_id = self._extract_tmp_id(message_content)
        
        # *** 关键修复逻辑 ***
        if not tmp_id:
            # 如果没有输入 ID，则尝试使用绑定的 ID
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：/查询 123456，或先使用 /绑定 123456 绑定您的账号。")
                return
        # *** 修复结束 ***
        
        try:
            tasks = [self._get_player_info(tmp_id), self._get_player_bans(tmp_id), self._get_online_status(tmp_id)]
            player_info, bans_info, online_status = await asyncio.gather(*tasks)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        is_banned, ban_count, active_bans, ban_reason = self._format_ban_info(bans_info)
        
        # 完整的回复消息构建
        message = "🚛 TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        message += f"🆔TMP编号: {tmp_id}\n"
        message += f"😀玩家名称: {player_info.get('name', '未知')}\n"
        
        message += f"🎮SteamID: {player_info.get('steam_id', player_info.get('steamID64', 'N/A'))}\n"
        message += f"📑注册日期: {player_info.get('created_at', player_info.get('joinDate', 'N/A'))}\n"
        
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f'is{g.replace(" ", "")}')]
                if groups:
                    perms_str = ', '.join(groups)
            elif isinstance(perms, list) and perms:
                perms_str = ', '.join(perms)
        message += f"💼所属分组: {perms_str}\n"

        vtc_name = player_info.get('vtc', {}).get('name')
        vtc_role = player_info.get('vtc', {}).get('role')
        message += f"🚚所属车队: {vtc_name if vtc_name else '无'}\n"
        if vtc_role:
             message += f"🚚车队角色: {vtc_role}\n"
        
        message += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
        if is_banned:
            message += f"🚫封禁次数: {ban_count}次\n"
            message += f"🚫封禁原因: {ban_reason}\n"
            if active_bans and active_bans[0].get('expiration'):
                message += f"🚫封禁截止: {active_bans[0]['expiration']}\n"
        elif ban_count > 0:
            message += f"🚫历史封禁: {ban_count}次\n"
        
        if online_status and online_status.get('online'):
            message += f"📶在线状态: 在线 🟢\n"
            server_name = online_status.get('serverName', '未知服务器')
            message += f"🖥️所在服务器: {server_name}\n"
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        if player_info.get('updated_at'):
            message += f"📶最后更新: {player_info.get('updated_at')}\n"
        
        yield event.plain_result(message)

    @filter.command("绑定")
    async def tmpbind(self, event: AstrMessageEvent):
        """[命令: /绑定] 绑定QQ/群用户ID与TruckersMP ID。"""
        # 修复兼容性问题：使用 event.message_str 手动解析参数
        message_str = event.message_str.strip()
        
        command_prefix = "/绑定"
        if message_str.startswith(command_prefix):
            message_content = message_str[len(command_prefix):].strip()
        else:
            message_content = ""
            
        tmp_id = self._extract_tmp_id(message_content)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号，格式：/绑定 123456")
            return

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result("玩家不存在，请检查TMP ID是否正确")
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        user_id = event.get_sender_id()
        player_name = player_info.get('name', '未知')
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            yield event.plain_result(f"✅ 绑定成功！\n已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定")
        else:
            yield event.plain_result("❌ 绑定失败，请稍后重试")

    @filter.command("解绑")
    async def tmpunbind(self, event: AstrMessageEvent):
        """[命令: /解绑] 解除当前用户的TruckersMP ID绑定。"""
        user_id = event.get_sender_id()
        bound_info = self._get_bound_tmp_id(user_id)
        
        if not bound_info:
            yield event.plain_result("❌ 您还没有绑定任何TMP账号")
            return
        
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id, {})
        tmp_id = user_binding.get('tmp_id', bound_info)
        player_name = user_binding.get('player_name', '未知玩家')
        
        if self._unbind_tmp_id(user_id):
            yield event.plain_result(f"✅ 解绑成功！\n已解除与TMP玩家 {player_name} (ID: {tmp_id}) 的绑定")
        else:
            yield event.plain_result("❌ 解绑失败，请稍后重试")

    @filter.command("状态")
    async def tmpstatus(self, event: AstrMessageEvent):
        """[命令: /状态] 查询玩家的实时在线状态。"""
        # 使用 event.message_str 获取命令后的内容
        message_str = event.message_str.strip()
        command_prefix = "/状态"
        if message_str.startswith(command_prefix):
            message_content = message_str[len(command_prefix):].strip()
        else:
            message_content = ""
            
        tmp_id = self._extract_tmp_id(message_content)
        
        # *** 关键修复逻辑 ***
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：/状态 123456，或先使用 /绑定 123456 绑定您的账号。")
                return
        # *** 修复结束 ***

        try:
            tasks = [self._get_online_status(tmp_id), self._get_player_info(tmp_id)]
            online_status, player_info = await asyncio.gather(*tasks)

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
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
        else:
            message += f"📶在线状态: 离线 🔴\n"
        
        yield event.plain_result(message)

    @filter.command("服务器")
    async def tmpserver(self, event: AstrMessageEvent):
        """[命令: /服务器] 查询TruckersMP官方服务器的实时状态。"""
        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('response'):
                            servers = data['response']
                            message = "🖥️ TMP服务器状态\n\n"
                            online_servers = [s for s in servers if s.get('online')][:6]
                            
                            for server in online_servers:
                                name, players, max_players, queue = server.get('name', '未知'), server.get('players', 0), server.get('maxplayers', 0), server.get('queue', 0)
                                message += f"{'🟢' if players > 0 else '🟡'} {name}\n"
                                message += f"   👥 {players}/{max_players}"
                                if queue > 0: message += f" (排队: {queue})"
                                message += "\n"
                            
                            if not online_servers: message += "暂无在线服务器"
                            yield event.plain_result(message)
                        else:
                            yield event.plain_result("查询服务器状态失败")
                    else:
                        yield event.plain_result("查询服务器状态失败")
        except Exception as e:
            yield event.plain_result("网络请求失败")

    @filter.command("帮助")
    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: /帮助] 显示本插件的命令使用说明。"""
        help_text = """🚛 TMP查询插件使用说明 (需要斜杠前缀)

📋 可用命令:
/查询 123456    - 查询玩家完整信息
/状态 123456    - 查询玩家在线状态  
/绑定 123456    - 绑定TMP账号
/解绑          - 解除账号绑定
/服务器        - 查看服务器状态
/帮助          - 显示此帮助信息

💡 使用提示: 绑定后可直接使用 /查询 和 /状态 (无需参数)
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作。"""
        if self.session:
            await self.session.close()
        logger.info("TMP Bot 插件已卸载")