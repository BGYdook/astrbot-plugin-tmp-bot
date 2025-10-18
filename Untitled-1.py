#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本
修复：正确查询不同玩家信息
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
        """获取玩家基本信息 - 修复版"""
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            logger.info(f"查询玩家信息: {url}")
            
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API返回数据: {json.dumps(data, ensure_ascii=False)}")
                        
                        if data and isinstance(data, dict):
                            # 检查API返回结构
                            if 'response' in data:
                                player_data = data['response']
                                if player_data and isinstance(player_data, dict):
                                    return player_data
                            elif data.get('id'):  # 直接包含玩家数据
                                return data
                            
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在或数据格式错误")
                    elif response.status == 404:
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    else:
                        raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            raise NetworkException("网络请求失败")
        except Exception as e:
            logger.error(f"查询失败: {e}")
            raise NetworkException(f"查询失败: {str(e)}")

    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        """获取玩家封禁信息 - 修复版"""
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}/bans"
            logger.info(f"查询玩家封禁: {url}")
            
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"封禁API返回: {json.dumps(data, ensure_ascii=False)}")
                        
                        if data and 'response' in data:
                            return data['response']
                        return []
                    elif response.status == 404:
                        return []  # 玩家存在但没有封禁记录
                    else:
                        logger.warning(f"封禁API返回状态码: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"获取封禁信息失败: {e}")
            return []

    async def _get_online_status(self, tmp_id: str) -> Dict:
        """获取玩家在线状态 - 修复版"""
        try:
            # 使用 TruckyApp API 获取在线状态
            url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
            logger.info(f"查询在线状态: {url}")
            
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"在线状态API返回: {json.dumps(data, ensure_ascii=False)}")
                        
                        # 解析 TruckyApp API 响应
                        if data and 'response' in data:
                            response_data = data['response']
                            if isinstance(response_data, list) and len(response_data) > 0:
                                player_data = response_data[0]
                                return {
                                    'online': True,
                                    'serverName': player_data.get('serverName', '未知服务器')
                                }
                        
                        return {'online': False, 'serverName': ''}
                    else:
                        return {'online': False, 'serverName': ''}
        except Exception as e:
            logger.error(f"获取在线状态失败: {e}")
            return {'online': False, 'serverName': ''}

    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[bool, int, List[Dict], str]:
        """格式化封禁信息 - 修复版"""
        if not bans_info or not isinstance(bans_info, list):
            return False, 0, [], ""
        
        # 过滤未过期的封禁
        active_bans = []
        for ban in bans_info:
            # 检查封禁是否过期
            expired = ban.get('expired', False)
            if not expired:
                active_bans.append(ban)
        
        ban_count = len(bans_info)
        is_banned = len(active_bans) > 0
        
        # 获取最新封禁的原因
        ban_reason = ""
        if active_bans:
            # 按时间排序，获取最新的封禁
            sorted_bans = sorted(active_bans, 
                               key=lambda x: x.get('created', ''), 
                               reverse=True)
            ban_reason = sorted_bans[0].get('reason', '未知封禁原因')
            
        return is_banned, ban_count, active_bans, ban_reason

    def _format_player_info(self, player_info: Dict, tmp_id: str) -> str:
        """格式化玩家信息显示 - 修复版"""
        # 基础信息
        message = "🚛 TMP玩家详细信息\n"
        message += "=" * 25 + "\n"
        message += f"🆔 TMP编号: {tmp_id}\n"
        message += f"😀 玩家名称: {player_info.get('name', '未知')}\n"
        
        # Steam ID
        steam_id = player_info.get('steamID64') or player_info.get('steam_id')
        message += f"🎮 SteamID: {steam_id or 'N/A'}\n"
        
        # 注册日期
        created_at = player_info.get('createdAt') or player_info.get('created_at')
        message += f"📑 注册日期: {created_at or 'N/A'}\n"
        
        # 权限/分组信息
        permissions = player_info.get('permissions', {})
        if isinstance(permissions, dict):
            groups = []
            if permissions.get('isStaff'):
                groups.append("Staff")
            if permissions.get('isGameAdmin'):
                groups.append("Game Admin")
            if permissions.get('isManagement'):
                groups.append("Management")
            
            perms_str = ', '.join(groups) if groups else "玩家"
        else:
            perms_str = "玩家"
        
        message += f"💼 所属分组: {perms_str}\n"
        
        # 车队信息
        vtc = player_info.get('vtc', {})
        if isinstance(vtc, dict):
            vtc_name = vtc.get('name', '')
            vtc_id = vtc.get('id')
            vtc_role = vtc.get('memberRole')
            
            if vtc_name:
                message += f"🚚 所属车队: {vtc_name}"
                if vtc_id:
                    message += f" (ID: {vtc_id})"
                message += "\n"
                
                if vtc_role:
                    message += f"🚚 车队角色: {vtc_role}\n"
            else:
                message += f"🚚 所属车队: 无\n"
        else:
            message += f"🚚 所属车队: 无\n"
        
        return message

    # ******************************************************
    # 使用 filter.message 适配无前缀命令，匹配 "查询" 或 "查询 123456"
    # ******************************************************
    @filter.message(r"^查询\s*(\d+)?$", regex=True)
    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] TMP玩家完整信息查询 - 修复版"""
        message_str = event.message_str.strip()
        
        # 提取 TMP ID
        match = re.search(r'查询\s*(\d+)', message_str)
        tmp_id = match.group(1) if match else None

        # 如果没有提供ID，尝试使用绑定的ID
        if not tmp_id:
            if message_str.strip().lower() == '查询':
                user_id = event.get_sender_id()
                tmp_id = self._get_bound_tmp_id(user_id)
            
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：查询 123456，或先使用 绑定 123456 绑定您的账号。")
                return
        
        logger.info(f"开始查询玩家: {tmp_id}")
        
        try:
            # 并行获取所有信息
            tasks = [
                self._get_player_info(tmp_id), 
                self._get_player_bans(tmp_id), 
                self._get_online_status(tmp_id)
            ]
            player_info, bans_info, online_status = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 检查异常
            if isinstance(player_info, Exception):
                raise player_info
            if isinstance(bans_info, Exception):
                bans_info = []
            if isinstance(online_status, Exception):
                online_status = {'online': False}
                
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            logger.error(f"查询过程中出错: {e}")
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        # 构建回复消息
        try:
            message = self._format_player_info(player_info, tmp_id)
            
            # 封禁信息
            is_banned, ban_count, active_bans, ban_reason = self._format_ban_info(bans_info)
            message += f"🚫 是否封禁: {'是' if is_banned else '否'}\n"
            
            if is_banned:
                message += f"🚫 封禁次数: {ban_count}次\n"
                message += f"🚫 封禁原因: {ban_reason}\n"
                if active_bans and active_bans[0].get('expiration'):
                    message += f"🚫 封禁截止: {active_bans[0]['expiration']}\n"
            elif ban_count > 0:
                message += f"🚫 历史封禁: {ban_count}次\n"
            
            # 在线状态
            if online_status and online_status.get('online'):
                message += f"📶 在线状态: 在线 🟢\n"
                server_name = online_status.get('serverName', '未知服务器')
                message += f"🖥️ 所在服务器: {server_name}\n"
            else:
                message += f"📶 在线状态: 离线 🔴\n"
            
            # 最后更新
            updated_at = player_info.get('updatedAt') or player_info.get('updated_at')
            if updated_at:
                message += f"🕒 最后更新: {updated_at}\n"
            
            yield event.plain_result(message)
            
        except Exception as e:
            logger.error(f"格式化消息失败: {e}")
            yield event.plain_result("处理玩家信息时出现错误")

    @filter.message(r"^绑定\s*(\d+)?$", regex=True)
    async def tmpbind(self, event: AstrMessageEvent):
        """[命令: 绑定] 绑定QQ/群用户ID与TruckersMP ID - 修复版"""
        message_str = event.message_str.strip()
        
        match = re.search(r'绑定\s*(\d+)', message_str)
        tmp_id = match.group(1) if match else None
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号，格式：绑定 123456")
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

    @filter.message(r"^解绑$", regex=True)
    async def tmpunbind(self, event: AstrMessageEvent):
        """[命令: 解绑] 解除当前用户的TruckersMP ID绑定。"""
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

    @filter.message(r"^状态\s*(\d+)?$", regex=True)
    async def tmpstatus(self, event: AstrMessageEvent):
        """[命令: 状态] 查询玩家的实时在线状态 - 修复版"""
        message_str = event.message_str.strip()
        match = re.search(r'状态\s*(\d+)', message_str)
        tmp_id = match.group(1) if match else None
        
        if not tmp_id:
            if message_str.strip().lower() == '状态':
                user_id = event.get_sender_id()
                tmp_id = self._get_bound_tmp_id(user_id)
            
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：状态 123456，或先使用 绑定 123456 绑定您的账号。")
                return

        try:
            tasks = [
                self._get_online_status(tmp_id), 
                self._get_player_info(tmp_id)
            ]
            online_status, player_info = await asyncio.gather(*tasks, return_exceptions=True)
            
            if isinstance(online_status, Exception):
                online_status = {'online': False}
            if isinstance(player_info, Exception):
                raise player_info

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        player_name = player_info.get('name', '未知')
        
        message = f"🎮 玩家状态查询\n"
        message += "=" * 20 + "\n"
        message += f"😀 玩家名称: {player_name}\n"
        message += f"🆔 TMP编号: {tmp_id}\n"
        
        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')
            message += f"📶 在线状态: 在线 🟢\n"
            message += f"🖥️ 所在服务器: {server_name}\n"
        else:
            message += f"📶 在线状态: 离线 🔴\n"
        
        yield event.plain_result(message)

    @filter.message(r"^服务器$", regex=True)
    async def tmpserver(self, event: AstrMessageEvent):
        """[命令: 服务器] 查询TruckersMP官方服务器的实时状态 - 修复版"""
        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with aiohttp.ClientSession(headers={'User-Agent': 'AstrBot-TMP-Plugin/1.0.0'}) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('response'):
                            servers = data['response']
                            message = "🖥️ TMP服务器状态\n\n"
                            online_servers = [s for s in servers if s.get('online')]
                            
                            # 限制显示数量，避免消息过长
                            for server in online_servers[:8]:
                                name = server.get('name', '未知服务器')
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
                                
                            yield event.plain_result(message)
                        else:
                            yield event.plain_result("查询服务器状态失败")
                    else:
                        yield event.plain_result(f"查询服务器状态失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"服务器状态查询失败: {e}")
            yield event.plain_result("网络请求失败")

    @filter.message(r"^帮助$", regex=True)
    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: 帮助] 显示本插件的命令使用说明。"""
        help_text = """🚛 TMP查询插件使用说明 (无前缀命令)

📋 可用命令:
查询 123456    - 查询玩家完整信息
状态 123456    - 查询玩家在线状态  
绑定 123456    - 绑定TMP账号
解绑          - 解除账号绑定
服务器        - 查看服务器状态
帮助          - 显示此帮助信息

💡 使用提示: 绑定后可直接使用 查询 和 状态 (无需参数)

🔧 修复内容:
• 修复了查询同一玩家的问题
• 改进了API错误处理
• 优化了信息显示格式
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件卸载时的清理工作。"""
        if self.session:
            await self.session.close()
        logger.info("TMP Bot 插件已卸载")