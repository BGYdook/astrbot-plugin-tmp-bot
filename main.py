#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.2：Final - 修复并优化地图定位)
"""

import re
import asyncio
import aiohttp
import json
import os
import urllib.parse
import math 
from typing import Optional, List, Dict, Tuple, Any
import io 

# 引入图片处理库 Pillow
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    print("[ERROR] Pillow 库未安装。请运行 'pip install Pillow' 安装以启用图片生成功能。")
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None


# 引入 AstrBot 核心 API 
try:
    from astrbot.api.event import filter, AstrMessageEvent
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message import ImageMessage
except ImportError:
    # 兼容回退代码，确保不报错
    class _DummyFilter:
        def command(self, pattern, **kwargs): 
            def decorator(func):
                return func
            return decorator
    filter = _DummyFilter()
    # ... (此处省略兼容类定义，实际文件中需保留或使用你的环境兼容代码)

# 自定义异常类 
class TmpApiException(Exception):
    pass
class PlayerNotFoundException(TmpApiException):
    pass
class SteamIdNotFoundException(TmpApiException):
    pass
class NetworkException(Exception):
    pass
class ApiResponseException(TmpApiException):
    pass


# 版本号更新为 1.3.2
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.2", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
class TmpBotPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None 
        self.data_dir = StarTools.get_data_dir("tmp-bot")
        self.bind_file = os.path.join(self.data_dir, "tmp_bindings.json")
        self.font_path = os.path.join(self.data_dir, "font.ttf") 
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("TMP Bot 插件已加载")

    async def initialize(self):
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.3.2'},
            timeout=aiohttp.ClientTimeout(total=10)
        )
        logger.info("TMP Bot 插件HTTP会话已创建")
    
    # --- 内部工具方法 (数据绑定) ---
    def _load_bindings(self) -> Dict[str, Any]:
        # ... (数据绑定方法，与你之前的代码保持一致)
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


    # --- API 请求方法 ---
    # (此处省略 _get_tmp_id_from_steam_id, _get_player_info, _get_online_status 等 API 函数，请确保在你的实际文件中它们是完整的。)
    async def _get_tmp_id_from_steam_id(self, steam_id: str) -> str:
        if not self.session: raise NetworkException("插件未初始化，HTTP会话不可用")
        try:
            url = f"https://api.truckyapp.com/v2/truckersmp/player/get_by_steamid/{steam_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    tmp_id = data.get('response', {}).get('truckersmp_id')
                    if tmp_id: return str(tmp_id)
                    raise SteamIdNotFoundException(f"Steam ID {steam_id} 未绑定或Trucky API未找到对应的TMP账号。")
                elif response.status == 404:
                    raise SteamIdNotFoundException(f"Steam ID {steam_id} 未绑定或Trucky API未找到对应的TMP账号。")
                else:
                    raise ApiResponseException(f"Steam ID转换API返回错误状态码: {response.status}")
        except aiohttp.ClientError: raise NetworkException("Steam ID转换服务网络请求失败")
        except asyncio.TimeoutError: raise NetworkException("请求 Steam ID 转换服务超时")
        except SteamIdNotFoundException: raise 
        except Exception as e:
            logger.error(f"查询 TMP ID 失败: {e}")
            raise NetworkException("Steam ID 转换查询失败")
            
    def _get_steam_id_from_player_info(self, player_info: Dict) -> Optional[str]:
        steam_id = player_info.get('steamID64')
        return str(steam_id) if steam_id else None

    async def _get_player_info(self, tmp_id: str) -> Dict:
        if not self.session: raise NetworkException("插件未初始化，HTTP会话不可用")
        try:
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get('response')
                    if response_data and isinstance(response_data, dict): return response_data
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在") 
                elif response.status == 404:
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                else:
                    raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except aiohttp.ClientError: raise NetworkException("TruckersMP API 网络请求失败")
        except asyncio.TimeoutError: raise NetworkException("请求TruckersMP API超时")
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
        if not bans_info or not isinstance(bans_info, list): return 0, []
        sorted_bans = sorted(bans_info, key=lambda x: x.get('timeAdded', ''), reverse=True)
        return len(bans_info), sorted_bans

    
    # --- 地理编码和瓦片辅助函数 (定位功能依赖) ---
    
    def _lon_to_tile(self, lon: float, zoom: int) -> int:
        return int((lon + 180) / 360 * (2 ** zoom))

    def _lat_to_tile(self, lat: float, zoom: int) -> int:
        lat_rad = lat / 180 * math.pi 
        n = 2.0 ** zoom
        return int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)


    async def _get_map_tile(self, city_name: str, game_name: str, map_size: Tuple[int, int]) -> Optional[Image.Image]:
        if not self.session or not city_name: return None
        
        query = f"{city_name}, {game_name}" if city_name.lower() in ["london", "paris"] else f"{city_name} {game_name}"
        
        # 1. 地理编码：根据城市名称获取经纬度
        try:
            nominatim_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1&accept-language=zh"
            async with self.session.get(nominatim_url, timeout=5) as response:
                if response.status != 200: return None
                geo_data = await response.json()
                if not geo_data: return None
                lat = float(geo_data[0]['lat'])
                lon = float(geo_data[0]['lon'])

        except Exception as e:
            logger.error(f"地理编码失败: {e}")
            return None

        # 2. 获取静态地图瓦片
        try:
            ZOOM_LEVEL = 10 
            tile_x = self._lon_to_tile(lon, ZOOM_LEVEL)
            tile_y = self._lat_to_tile(lat, ZOOM_LEVEL)
            
            map_tile_url = f"https://tile.openstreetmap.org/{ZOOM_LEVEL}/{tile_x}/{tile_y}.png"
            
            async with self.session.get(map_tile_url, timeout=5) as response:
                if response.status != 200: return None
                
                tile_data = await response.read()
                tile_img = Image.open(io.BytesIO(tile_data)).convert("RGB")
                tile_img = ImageOps.fit(tile_img, map_size, method=Image.Resampling.LANCZOS)
                
                return tile_img
                
        except Exception as e:
            logger.error(f"地图瓦片处理失败: {e}")
            return None


    # --- 核心图片生成函数 ---
    async def _generate_player_location_image(self, 
                                               player_info: Dict, 
                                               online_status: Dict) -> Optional[bytes]:
        if Image is None or ImageDraw is None or ImageFont is None: return None

        img_width, img_height = 800, 450
        bg_color = (25, 25, 25) 
        
        player_name = player_info.get('name', '未知玩家')
        tmp_id = player_info.get('id', '未知TMPID')
        avatar_url = player_info.get('avatar')
        is_online = online_status and online_status.get('online', False)
        server_name = online_status.get('serverName', 'N/A')
        game_id = online_status.get('game', 0)
        game_name_long = "Euro Truck Simulator 2" if game_id == 1 else "American Truck Simulator" if game_id == 2 else "Unknown Game"
        game_name_short = "欧卡2" if game_id == 1 else "美卡" if game_id == 2 else "未知游戏"
        city_name = online_status.get('city', {}).get('name', '未知城市')

        # 1. 尝试获取地图图片
        map_area_width, map_area_height = 700, 200
        map_area_x, map_area_y = 50, 230
        map_img = None
        
        if is_online:
            map_img = await self._get_map_tile(city_name, game_name_long, (map_area_width, map_area_height))
        
        # 2. 创建基础图片 (背景)
        img = Image.new('RGB', (img_width, img_height), color = bg_color)
        draw = ImageDraw.Draw(img)

        # 字体加载
        try:
            font_title = ImageFont.truetype(self.font_path, 32)
            font_info = ImageFont.truetype(self.font_path, 24)
            font_map_label = ImageFont.truetype(self.font_path, 30)
        except Exception:
            logger.error("加载字体文件失败，请检查 'font.ttf' 是否存在。")
            return None

        # 3. 绘制地图/占位符
        if map_img:
            img.paste(map_img, (map_area_x, map_area_y))
            draw.rectangle([map_area_x, map_area_y, map_area_x + map_area_width, map_area_y + map_area_height], 
                           outline=(40, 40, 40), width=2)
            
            draw.text((map_area_x + 10, map_area_y + 10), 
                      f"➤ 玩家位于 {city_name} (近似位置)", 
                      fill=(255, 60, 60), 
                      font=font_map_label, 
                      stroke_width=1, 
                      stroke_fill=(0, 0, 0))
        else:
            # 离线或地图获取失败，使用占位符
            draw.rectangle([map_area_x, map_area_y, map_area_x + map_area_width, map_area_y + map_area_height], 
                           fill=(40, 40, 40), outline=(80, 80, 80), width=2)
            
            map_text = f"【地图不可用】玩家状态：{'离线' if not is_online else f'在线，位于 {city_name} (无法定位)'}"
            
            text_bbox = draw.textbbox((0, 0), map_text, font=font_map_label)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = map_area_x + (map_area_width - text_width) // 2
            text_y = map_area_y + (map_area_height - text_height) // 2
            draw.text((text_x, text_y), map_text, fill=(150, 150, 150), font=font_map_label)

        # 4. 绘制头像和文本信息
        text_color_online = (100, 255, 100)
        text_color_offline = (255, 100, 100)
        text_color_info = (255, 255, 255)
        
        avatar_size = 128
        avatar_pos_x, avatar_pos_y = 50, 50
        text_x_start = avatar_pos_x + avatar_size + 30
        current_y = avatar_pos_y + 10

        # 下载并放置头像
        try:
            if avatar_url and self.session:
                async with self.session.get(avatar_url, timeout=5) as response:
                    if response.status == 200:
                        avatar_data = await response.read()
                        avatar_img = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                        avatar_img = avatar_img.resize((avatar_size, avatar_size))
                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        img.paste(avatar_img, (avatar_pos_x, avatar_pos_y), mask)
        except Exception:
            logger.warning(f"下载或处理头像失败：{avatar_url}")
        
        # 绘制文本信息
        draw.text((text_x_start, current_y), f"玩家: {player_name}", fill=text_color_info, font=font_title)
        current_y += font_title.getbbox(f"玩家: {player_name}")[3] - font_title.getbbox(f"玩家: {player_name}")[1] + 10 
        
        draw.text((text_x_start, current_y), f"TMP ID: {tmp_id}", fill=text_color_info, font=font_info)
        current_y += font_info.getbbox(f"TMP ID: {tmp_id}")[3] - font_info.getbbox(f"TMP ID: {tmp_id}")[1] + 10

        online_status_text = "在线" if is_online else "离线"
        online_status_color = text_color_online if is_online else text_color_offline
        draw.text((text_x_start, current_y), f"状态: {online_status_text}", fill=online_status_color, font=font_info)
        current_y += font_info.getbbox(f"状态: {online_status_text}")[3] - font_info.getbbox(f"状态: {online_status_text}")[1] + 10

        if is_online:
            draw.text((text_x_start, current_y), f"服务器: {server_name}", fill=text_color_info, font=font_info)
            current_y += font_info.getbbox(f"服务器: {server_name}")[3] - font_info.getbbox(f"服务器: {server_name}")[1] + 10

            draw.text((text_x_start, current_y), f"游戏: {game_name_short}", fill=text_color_info, font=font_info)
            
        # 5. 返回图片字节流
        byte_arr = io.BytesIO()
        img.save(byte_arr, format='PNG')
        return byte_arr.getvalue()

    # --- 命令处理器 ---
    @filter.command("查询") 
    async def tmpquery(self, event: AstrMessageEvent):
        # ... (与你之前的查询代码一致)
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        match = re.search(r'查询\s*(\d+)', message_str) 
        input_id = match.group(1) if match else None
        
        tmp_id = None
        
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except Exception as e:
                    yield event.plain_result(str(e))
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
        
        message = "TMP玩家详细信息\n"
        message += "=" * 20 + "\n"
        message += f"ID TMP编号: {tmp_id}\n"
        if steam_id_to_display: message += f"ID Steam编号: {steam_id_to_display}\n" 
        message += f"玩家名称: {player_info.get('name', '未知')}\n"
        
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f'is{g.replace(" ", "")}')]
                if groups: perms_str = ', '.join(groups)
            elif isinstance(perms, list) and perms: perms_str = ', '.join(perms)
        message += f"所属分组: {perms_str}\n"

        vtc_name = player_info.get('vtc', {}).get('name')
        vtc_role = player_info.get('vtc', {}).get('role')
        message += f"所属车队: {vtc_name if vtc_name else '无'}\n"
        if vtc_role: message += f"车队角色: {vtc_role}\n"
        
        message += f"是否封禁: {'是' if is_banned else '否'}\n"
        
        if ban_count > 0: message += f"历史封禁: {ban_count}次\n"

        if is_banned:
            current_ban = None
            if sorted_bans:
                current_ban = next((ban for ban in sorted_bans if ban.get('active')), None)
                if not current_ban: current_ban = sorted_bans[0]
                    
            if current_ban:
                ban_reason = current_ban.get('reason', '未知封禁原因 (API V2)')
                ban_expiration = current_ban.get('expiration', banned_until_main) 
                
                message += f"当前封禁原因: {ban_reason}\n"
                if ban_expiration and ban_expiration.lower().startswith('never'):
                    message += f"封禁截止: 永久封禁\n"
                else:
                    message += f"封禁截止: {ban_expiration}\n"
            else:
                message += f"当前封禁原因: API详细记录缺失。\n"
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
                tmp_id = await self._get_tmp_id_from_steam_id(input_id)
            except Exception as e:
                yield event.plain_result(str(e))
                return

        try:
            player_info = await self._get_player_info(tmp_id)
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')
        steam_id_display = self._get_steam_id_from_player_info(player_info)
        
        if self._bind_tmp_id(user_id, tmp_id, player_name):
            message = f"绑定成功！\n"
            message += f"已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定\n"
            if steam_id_display: message += f"该玩家的 Steam ID: {steam_id_display}"
            yield event.plain_result(message)
        else:
            yield event.plain_result("绑定失败，请稍后重试")


    @filter.command("解绑")
    async def tmpunbind(self, event: AstrMessageEvent):
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

    @filter.command("定位")
    async def tmplocation_image(self, event: AstrMessageEvent): 
        """查询玩家的实时在线状态，并以图片形式显示位置和头像。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        match = re.search(r'定位\s*(\d+)', message_str) 
        input_id = match.group(1) if match else None
        
        tmp_id = None
        
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except Exception as e:
                    yield event.plain_result(str(e))
                    return
            else:
                tmp_id = input_id
        else:
            tmp_id = self._get_bound_tmp_id(user_id)
        
        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号，或先使用 绑定 [TMP ID] 绑定您的账号。")
            return

        try:
            player_info, online_status = await asyncio.gather(
                self._get_player_info(tmp_id), 
                self._get_online_status(tmp_id)
            )

        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return
        
        yield event.plain_result(f"正在生成 {player_info.get('name', tmp_id)} 的定位图片，请稍候...")

        image_bytes = await self._generate_player_location_image(player_info, online_status)

        if image_bytes:
            yield event.image_result(ImageMessage(image_bytes)) 
        else:
            yield event.plain_result("生成定位图片失败，请检查 Pillow 库和中文字体文件 `font.ttf` 是否正确安装和放置。")


    @filter.command("服务器")
    async def tmpserver(self, event: AstrMessageEvent):
        # ... (与你之前的服务器查询代码一致)
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
                        message = "TMP服务器状态 (显示前6个在线服务器)\n"
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

    @filter.command("帮助")
    async def tmphelp(self, event: AstrMessageEvent):
        help_text = """TMP查询插件使用说明 (无前缀命令)

可用命令:
1. 查询 [ID] - 查询玩家的完整信息（支持 TMP ID 或 Steam ID）。
2. 定位 [ID] - 查询玩家的实时在线状态，并以图片形式显示位置和头像。
3. 绑定 [ID] - 绑定您的聊天账号与 TMP ID（支持输入 Steam ID 转换）。
4. 解绑 - 解除账号绑定。
5. 服务器 - 查看主要TMP服务器的实时状态和在线人数。
6. 帮助 - 显示此帮助信息。

使用提示: 绑定后可直接发送 查询 或 定位 (无需ID参数)
"""
        yield event.plain_result(help_text)

    async def terminate(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")