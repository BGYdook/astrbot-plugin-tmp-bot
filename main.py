#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AstrBot-plugin-tmp-bot
欧卡2TMP查询插件 - AstrBot版本 (版本 1.3.1：Beta - 尝试集成简易地图定位)
"""

import re
import asyncio
import aiohttp
import json
import os
import urllib.parse
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


# 引入 AstrBot 核心 API (保持不变)
try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context, Star, register, StarTools
    from astrbot.api import logger
    from astrbot.api.message import ImageMessage
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
            self.match = match
        def get_sender_id(self) -> str:
            return self._sender_id
        async def plain_result(self, msg):
            return msg
        async def image_result(self, image_bytes, **kwargs):
            print(f"[DEBUG] 模拟发送图片: {len(image_bytes)} 字节")
            return f"[图片消息: {len(image_bytes)} 字节]"

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
        @staticmethod
        def warning(msg):
            print("[WARNING]", msg)

    logger = _Logger()
    ImageMessage = lambda image: image 


# 自定义异常类 (保持不变)
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

# 版本号更新为 1.3.1
@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "1.3.1", "https://github.com/BGYdook/AstrBot-plugin-tmp-bot")
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
            headers={'User-Agent': 'AstrBot-TMP-Plugin/1.3.1'},
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

    # ... (其他绑定/解绑/API函数保持不变) ...
    # 为了精简代码，这里省略了未修改的函数，你在实际文件中要保留它们。
    
    async def _get_tmp_id_from_steam_id(self, steam_id: str) -> str:
        # ... (保持不变)
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
        # ... (保持不变)
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

    async def _get_online_status(self, tmp_id: str) -> Dict:
        # ... (保持不变)
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
    # ... (_get_player_bans, _format_ban_info 保持不变)

    
    # --- 新增：获取地图瓦片函数 ---
    async def _get_map_tile(self, city_name: str, map_size: Tuple[int, int]) -> Optional[bytes]:
        if not self.session or not city_name:
            return None
        
        # 1. 地理编码：根据城市名称获取经纬度
        try:
            nominatim_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(city_name)}&format=json&limit=1&accept-language=zh"
            async with self.session.get(nominatim_url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"Nominatim地理编码失败，状态码: {response.status}")
                    return None
                
                geo_data = await response.json()
                if not geo_data:
                    logger.warning(f"未找到城市 '{city_name}' 的地理编码信息。")
                    return None
                
                lat = float(geo_data[0]['lat'])
                lon = float(geo_data[0]['lon'])

        except Exception as e:
            logger.error(f"地理编码失败: {e}")
            return None

        # 2. 获取静态地图瓦片 (使用公共瓦片，放大级别 10 或 11 适合显示城市周边)
        try:
            # 这是一个公共的OpenStreetMap瓦片服务器
            map_tile_url = f"https://tile.openstreetmap.org/11/{self._lon_to_tile(lon, 11)}/{self._lat_to_tile(lat, 11)}.png"
            
            async with self.session.get(map_tile_url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"地图瓦片下载失败，状态码: {response.status}")
                    return None
                
                tile_data = await response.read()
                tile_img = Image.open(io.BytesIO(tile_data)).convert("RGB")
                
                # 由于只下载了一个瓦片，我们将其裁剪或缩放到所需大小
                # 标准瓦片大小是 256x256
                if tile_img.size != map_size:
                    tile_img = ImageOps.fit(tile_img, map_size, method=Image.Resampling.LANCZOS)
                
                byte_arr = io.BytesIO()
                tile_img.save(byte_arr, format='PNG')
                return byte_arr.getvalue()
                
        except Exception as e:
            logger.error(f"地图瓦片处理失败: {e}")
            return None

    def _lon_to_tile(self, lon: float, zoom: int) -> int:
        return int((lon + 180) / 360 * (2 ** zoom))

    def _lat_to_tile(self, lat: float, zoom: int) -> int:
        lat_rad = lat / 180 * 3.14159265359 # math.pi
        n = 2.0 ** zoom
        return int((1.0 - (lat_rad / 3.14159265359 + 1.0) * 0.5) * n)


    # --- 核心图片生成函数 (更新) ---
    async def _generate_player_location_image(self, 
                                               player_info: Dict, 
                                               online_status: Dict) -> Optional[bytes]:
        if Image is None or ImageDraw is None or ImageFont is None:
            logger.error("Pillow 库未安装，无法生成图片。")
            return None

        # 图片尺寸
        img_width, img_height = 800, 450
        bg_color = (25, 25, 25) # 深灰色背景
        
        # 玩家和在线状态信息
        player_name = player_info.get('name', '未知玩家')
        tmp_id = player_info.get('id', '未知TMPID')
        avatar_url = player_info.get('avatar')
        is_online = online_status and online_status.get('online', False)
        server_name = online_status.get('serverName', 'N/A')
        game_id = online_status.get('game', 0)
        game_name = "欧卡2" if game_id == 1 else "美卡" if game_id == 2 else "未知游戏"
        city_name = online_status.get('city', {}).get('name', '未知城市')

        # 1. 尝试获取地图图片 (如果玩家在线)
        map_area_width, map_area_height = 700, 200
        map_area_x, map_area_y = 50, 230
        map_img = None
        
        if is_online:
            logger.info(f"尝试获取城市 '{city_name}' 的地图瓦片...")
            map_bytes = await self._get_map_tile(city_name, (map_area_width, map_area_height))
            if map_bytes:
                map_img = Image.open(io.BytesIO(map_bytes)).convert("RGB")
        
        # 2. 创建基础图片 (背景是地图或纯色)
        if map_img:
             # 创建一个稍大的背景图，将地图粘贴到指定位置
            img = Image.new('RGB', (img_width, img_height), color = bg_color)
            img.paste(map_img, (map_area_x, map_area_y))
        else:
            # 离线或地图获取失败，使用纯色背景并绘制占位符
            img = Image.new('RGB', (img_width, img_height), color = bg_color)
            draw = ImageDraw.Draw(img)
            draw.rectangle([map_area_x, map_area_y, map_area_x + map_area_width, map_area_y + map_area_height], 
                           fill=(40, 40, 40), outline=(80, 80, 80), width=2)
            
        draw = ImageDraw.Draw(img)

        # 字体加载
        try:
            font_title = ImageFont.truetype(self.font_path, 32)
            font_info = ImageFont.truetype(self.font_path, 24)
            font_small = ImageFont.truetype(self.font_path, 20)
        except Exception as e:
            logger.error(f"加载字体文件失败: {e}。")
            return None

        # 3. 绘制信息和头像
        text_color_online = (100, 255, 100)
        text_color_offline = (255, 100, 100)
        text_color_info = (255, 255, 255)
        
        avatar_size = 128
        avatar_pos_x, avatar_pos_y = 50, 50
        text_x_start = avatar_pos_x + avatar_size + 30
        current_y = avatar_pos_y + 10

        # 下载并放置头像
        if avatar_url and self.session:
            try:
                async with self.session.get(avatar_url, timeout=5) as response:
                    if response.status == 200:
                        avatar_data = await response.read()
                        avatar_img = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                        avatar_img = avatar_img.resize((avatar_size, avatar_size))
                        
                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        
                        img.paste(avatar_img, (avatar_pos_x, avatar_pos_y), mask)
            except Exception as e:
                logger.warning(f"下载或处理头像失败: {e}")
        
        # 绘制文本信息 (左侧)
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

            draw.text((text_x_start, current_y), f"游戏: {game_name}", fill=text_color_info, font=font_info)
            
            # 在地图上叠加文字或标记
            if map_img:
                map_marker_text = f"➤ {city_name}"
                draw.text((map_area_x + 10, map_area_y + 10), map_marker_text, fill=(255, 0, 0), font=font_info)
            else:
                map_text = f"地图获取失败或离线，当前位置：{city_name}"
                text_bbox = draw.textbbox((0, 0), map_text, font=font_info)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                text_x = map_area_x + (map_area_width - text_width) // 2
                text_y = map_area_y + (map_area_height - text_height) // 2
                draw.text((text_x, text_y), map_text, fill=(180, 180, 180), font=font_info)


        # 将图片保存到字节流
        byte_arr = io.BytesIO()
        img.save(byte_arr, format='PNG')
        return byte_arr.getvalue()

    # ... (其他命令处理器保持不变) ...
    # 为了精简代码，这里省略了未修改的命令函数，你在实际文件中要保留它们。
    @filter.command("查询") 
    async def tmpquery(self, event: AstrMessageEvent):
        # ... (保持不变)
        pass # 实际代码请保留

    @filter.command("绑定")
    async def tmpbind(self, event: AstrMessageEvent):
        # ... (保持不变)
        pass # 实际代码请保留

    @filter.command("解绑")
    async def tmpunbind(self, event: AstrMessageEvent):
        # ... (保持不变)
        pass # 实际代码请保留

    @filter.command("定位")
    async def tmplocation_image(self, event: AstrMessageEvent): 
        """[命令: 定位] 查询玩家的实时在线状态，并以图片形式显示位置和头像。支持 TMP ID 或 Steam ID。"""
        message_str = event.message_str.strip()
        user_id = event.get_sender_id()
        
        match = re.search(r'定位\s*(\d+)', message_str) 
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
            yield event.plain_result("请输入正确的玩家编号（TMP ID 或 Steam ID），或先使用 绑定 [TMP ID] 绑定您的账号。")
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
        
        # 调用图片生成函数
        yield event.plain_result(f"正在尝试生成地图定位图片，玩家 {player_info.get('name', tmp_id)}...")

        image_bytes = await self._generate_player_location_image(player_info, online_status)

        if image_bytes:
            yield event.image_result(ImageMessage(image_bytes)) 
        else:
            yield event.plain_result("生成地图定位图片失败，请检查日志或网络连接。")


    @filter.command("服务器")
    async def tmpserver(self, event: AstrMessageEvent):
        # ... (保持不变)
        pass # 实际代码请保留

    @filter.command("帮助")
    async def tmphelp(self, event: AstrMessageEvent):
        # ... (保持不变)
        pass # 实际代码请保留

    async def terminate(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")