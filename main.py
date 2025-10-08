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
from typing import Optional
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
        super().__init__(context)
        self.session = None
        # 初始化数据存储路径
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def _get_session(self):
        """获取HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    def _load_bindings(self) -> dict:
        """加载绑定数据"""
        try:
            if os.path.exists(self.bind_file):
                with open(self.bind_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载绑定数据失败: {e}")
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        """保存绑定数据"""
        try:
            with open(self.bind_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存绑定数据失败: {e}")
            return False

    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        """获取用户绑定的TMP ID"""
        bindings = self._load_bindings()
        return bindings.get(user_id)

    def _bind_tmp_id(self, user_id: str, tmp_id: str) -> bool:
        """绑定用户和TMP ID"""
        bindings = self._load_bindings()
        bindings[user_id] = tmp_id
        return self._save_bindings(bindings)

    def _unbind_tmp_id(self, user_id: str) -> bool:
        """解除用户绑定"""
        bindings = self._load_bindings()
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False

    async def _query_player_info(self, tmp_id: str) -> dict:
        """查询玩家信息"""
        session = await self._get_session()
        try:
            # 查询玩家基本信息
            async with session.get(f"https://api.truckyapp.com/v3/player/{tmp_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('error'):
                        raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                    return data
                else:
                    raise ApiResponseException(f"API返回错误状态码: {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"查询玩家信息网络错误: {e}")
            raise NetworkException("网络请求失败")
        except Exception as e:
            logger.error(f"查询玩家信息失败: {e}")
            raise TmpApiException(f"查询失败: {str(e)}")

    async def _query_player_online(self, tmp_id: str) -> dict:
        """查询玩家在线状态"""
        session = await self._get_session()
        try:
            async with session.get(f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    raise ApiResponseException(f"在线状态查询失败，状态码: {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"查询在线状态网络错误: {e}")
            raise NetworkException("网络请求失败")
        except Exception as e:
            logger.error(f"查询在线状态失败: {e}")
            raise TmpApiException(f"查询失败: {str(e)}")

    def _extract_tmp_id(self, message: str, command: str) -> Optional[str]:
        """从消息中提取TMP ID，支持带空格和不带空格的格式"""
        # 匹配 "command 123456" 或 "command123456" 格式
        pattern = rf"^{command}\s*(\d+)$"
        match = re.match(pattern, message.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @filter.command("tmpquery")
    async def tmpquery(self, event: AstrMessageEvent):
        """TMP玩家查询指令"""
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "tmpquery")
        
        # 如果没有提供TMP ID，尝试使用绑定的ID
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：tmpquery 123456\n💡 提示：您也可以先使用 tmpbind 绑定您的TMP账号，之后直接使用 tmpquery 查询")
                return

        logger.info(f"查询TMP玩家: {tmp_id}")
        
        try:
            # 并发查询玩家信息和在线状态
            tasks = [
                self._query_player_info(tmp_id),
                self._query_player_online(tmp_id)
            ]
            results = await asyncio.gather(*tasks)
            player_info, online_info = results
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        # 构建回复消息
        data = player_info
        user_name = event.get_sender_name()
        
        message = f"🚛 TMP玩家查询结果\n"
        message += f"👤 玩家: {data.get('name', '未知')}\n"
        message += f"🆔 TMP ID: {tmp_id}\n"
        message += f"📅 注册时间: {data.get('joinDate', '未知')}\n"
        
        if data.get('vtc'):
            message += f"🚚 车队: {data['vtc'].get('name', '未知')}\n"
        
        # 在线状态
        if online_info.get('online'):
            server_name = online_info.get('serverDetails', {}).get('name', '未知服务器')
            message += f"📶 状态: 在线🟢 ({server_name})\n"
            
            location = online_info.get('location', {}).get('poi', {})
            if location:
                country = location.get('country', '')
                city = location.get('realName', '')
                if country and city:
                    message += f"🌍 位置: {country} - {city}\n"
        else:
            message += f"📶 状态: 离线⚫\n"
        
        # 封禁状态
        if data.get('banned'):
            message += f"⚠️ 状态: 已封禁\n"
        
        yield event.plain_result(message)

    @filter.command("tmpbind")
    async def tmpbind(self, event: AstrMessageEvent):
        """TMP账号绑定指令"""
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "tmpbind")
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号，格式：tmpbind 123456")
            return

        # 验证TMP ID是否存在
        try:
            player_info = await self._query_player_info(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result("玩家不存在，请检查TMP ID是否正确")
            return
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        # 获取用户ID并保存绑定信息
        user_id = event.get_sender_id()
        if self._bind_tmp_id(user_id, tmp_id):
            player_name = player_info.get('name', '未知')
            yield event.plain_result(f"✅ 绑定成功！\n已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定")
            logger.info(f"用户 {user_id} 绑定TMP ID: {tmp_id}")
        else:
            yield event.plain_result("❌ 绑定失败，请稍后重试")

    @filter.command("tmpunbind")
    async def tmpunbind(self, event: AstrMessageEvent):
        """解除TMP账号绑定指令"""
        user_id = event.get_sender_id()
        bound_tmp_id = self._get_bound_tmp_id(user_id)
        
        if not bound_tmp_id:
            yield event.plain_result("❌ 您还没有绑定任何TMP账号")
            return
        
        if self._unbind_tmp_id(user_id):
            yield event.plain_result(f"✅ 解绑成功！\n已解除与TMP ID {bound_tmp_id} 的绑定")
            logger.info(f"用户 {user_id} 解除TMP ID绑定: {bound_tmp_id}")
        else:
            yield event.plain_result("❌ 解绑失败，请稍后重试")

    @filter.command("tmpposition")
    async def tmpposition(self, event: AstrMessageEvent):
        """TMP玩家位置查询指令"""
        message_text = event.message_str.strip()
        tmp_id = self._extract_tmp_id(message_text, "tmpposition")
        
        # 如果没有提供TMP ID，尝试使用绑定的ID
        if not tmp_id:
            user_id = event.get_sender_id()
            tmp_id = self._get_bound_tmp_id(user_id)
            if not tmp_id:
                yield event.plain_result("请输入正确的玩家编号，格式：tmpposition 123456\n💡 提示：您也可以先使用 tmpbind 绑定您的TMP账号，之后直接使用 tmpposition 查询")
                return

        logger.info(f"查询TMP玩家位置: {tmp_id}")
        
        try:
            # 查询在线状态和位置
            online_info = await self._query_player_online(tmp_id)
        except (NetworkException, ApiResponseException, TmpApiException) as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
            
        if not online_info.get('online'):
            yield event.plain_result("该玩家当前不在线")
            return
            
        server_name = online_info.get('serverDetails', {}).get('name', '未知服务器')
        location = online_info.get('location', {}).get('poi', {})
        
        message = f"📍 TMP玩家位置\n"
        message += f"🆔 玩家ID: {tmp_id}\n"
        message += f"🖥️ 服务器: {server_name}\n"
        
        if location:
            country = location.get('country', '')
            city = location.get('realName', '')
            if country and city:
                message += f"🌍 位置: {country} - {city}\n"
            
            # 坐标信息
            coords = online_info.get('location', {})
            if coords.get('x') is not None and coords.get('y') is not None:
                message += f"📐 坐标: X:{coords['x']:.2f}, Y:{coords['y']:.2f}\n"
        
        yield event.plain_result(message)

    @filter.command("tmpserver")
    async def tmpserver(self, event: AstrMessageEvent):
        """TMP服务器状态查询指令"""
        logger.info("查询TMP服务器状态")
        
        session = await self._get_session()
        try:
            async with session.get("https://api.truckyapp.com/v3/servers") as resp:
                if resp.status == 200:
                    servers = await resp.json()
                    
                    message = "🖥️ TMP服务器状态\n\n"
                    for server in servers[:5]:  # 只显示前5个服务器
                        name = server.get('name', '未知')
                        players = server.get('players', 0)
                        max_players = server.get('maxplayers', 0)
                        queue = server.get('queue', 0)
                        
                        status = "🟢" if players > 0 else "🔴"
                        message += f"{status} {name}\n"
                        message += f"   👥 {players}/{max_players}"
                        if queue > 0:
                            message += f" (排队: {queue})"
                        message += "\n\n"
                    
                    yield event.plain_result(message.strip())
                else:
                    yield event.plain_result("查询服务器状态失败")
        except Exception as e:
            logger.error(f"查询服务器状态失败: {e}")
            yield event.plain_result("网络请求失败")

    @filter.command("tmpversion")
    async def tmpversion(self, event: AstrMessageEvent):
        """TMP版本信息查询指令"""
        yield event.plain_result("🚛 TMP Bot 插件\n版本: 1.0.0\n作者: BGYdook\n描述: 欧卡2TMP查询插件")

    async def terminate(self):
        """插件卸载时的清理工作"""
        if self.session:
            await self.session.close()
        logger.info("TMP Bot 插件已卸载")