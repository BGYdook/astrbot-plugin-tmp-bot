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
import math # 引入 math 库用于三角函数
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
    # 最小化兼容回退代码，略...

    # 简化兼容回退代码
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
    
    # ... (此处省略所有未修改的绑定/API函数以保持简洁，请确保它们在你的实际文件内) ...
    
    # --- 地理编码和瓦片辅助函数 ---
    
    def _lon_to_tile(self, lon: float, zoom: int) -> int:
        return int((lon + 180) / 360 * (2 ** zoom))

    def _lat_to_tile(self, lat: float, zoom: int) -> int:
        # 使用 math.pi
        lat_rad = lat / 180 * math.pi 
        n = 2.0 ** zoom
        return int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)


    async def _get_map_tile(self, city_name: str, game_name: str, map_size: Tuple[int, int]) -> Optional[Image.Image]:
        if not self.session or not city_name:
            return None
        
        # 增加搜索范围，因为游戏地图城市可能和现实名称略有不同
        query = f"{city_name}, {game_name}" if city_name.lower() in ["london", "paris"] else f"{city_name} {game_name}"
        
        # 1. 地理编码：根据城市名称获取经纬度
        try:
            nominatim_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1&accept-language=zh"
            # 使用更宽容的User-Agent，并使用 HEADERS
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

        # 2. 获取静态地图瓦片 (使用公共瓦片，放大级别 10 适合显示城市周边)
        try:
            ZOOM_LEVEL = 10 
            tile_x = self._lon_to_tile(lon, ZOOM_LEVEL)
            tile_y = self._lat_to_tile(lat, ZOOM_LEVEL)
            
            # 使用标准的 OpenStreetMap 瓦片 URL
            map_tile_url = f"https://tile.openstreetmap.org/{ZOOM_LEVEL}/{tile_x}/{tile_y}.png"
            
            async with self.session.get(map_tile_url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"地图瓦片下载失败，状态码: {response.status}")
                    return None
                
                tile_data = await response.read()
                tile_img = Image.open(io.BytesIO(tile_data)).convert("RGB")
                
                # 裁剪或缩放瓦片以适应地图区域
                tile_img = ImageOps.fit(tile_img, map_size, method=Image.Resampling.LANCZOS)
                
                return tile_img
                
        except Exception as e:
            logger.error(f"地图瓦片处理失败: {e}")
            return None


    # --- 核心图片生成函数 (更新) ---
    async def _generate_player_location_image(self, 
                                               player_info: Dict, 
                                               online_status: Dict) -> Optional[bytes]:
        # 检查 Pillow 依赖
        if Image is None or ImageDraw is None or ImageFont is None:
            logger.error("Pillow 库未安装，无法生成图片。")
            return None

        # 图像参数
        img_width, img_height = 800, 450
        bg_color = (25, 25, 25) 
        
        # 玩家信息
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
        except Exception as e:
            logger.error(f"加载字体文件失败: {e}。请检查 '{self.font_path}' 是否存在。")
            # 即使字体失败，也尝试继续，但文本可能无法显示或乱码
            return None

        # 3. 绘制地图/占位符
        if map_img:
            img.paste(map_img, (map_area_x, map_area_y))
            # 绘制地图边框
            draw.rectangle([map_area_x, map_area_y, map_area_x + map_area_width, map_area_y + map_area_height], 
                           outline=(40, 40, 40), width=2)
            
            # 绘制城市标记
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
            
            map_text = f"【地图不可用】玩家状态：{'离线' if not is_online else '在线，但城市无法定位'}"
            if is_online:
                map_text = f"【地图不可用】玩家当前位于 {city_name}"
            
            text_bbox = draw.textbbox((0, 0), map_text, font=font_map_label)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = map_area_x + (map_area_width - text_width) // 2
            text_y = map_area_y + (map_area_height - text_height) // 2
            draw.text((text_x, text_y), map_text, fill=(150, 150, 150), font=font_map_label)

        # 4. 绘制头像和文本信息 (左上角)
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

    # ... (此处省略所有未修改的命令处理函数，请确保它们在你的实际文件内) ...

    @filter.command("定位")
    async def tmplocation_image(self, event: AstrMessageEvent): 
        """[命令: 定位] 查询玩家的实时在线状态，并以图片形式显示位置和头像。支持 TMP ID 或 Steam ID。"""
        # ... (命令参数解析部分保持不变) ...
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
        
        # 提示用户正在生成图片，因为地图获取可能需要时间
        yield event.plain_result(f"正在生成 {player_info.get('name', tmp_id)} 的定位图片，请稍候...")

        image_bytes = await self._generate_player_location_image(player_info, online_status)

        if image_bytes:
            yield event.image_result(ImageMessage(image_bytes)) 
        else:
            yield event.plain_result("生成定位图片失败，请检查 Pillow 库和中文字体文件 `font.ttf` 是否正确安装和放置。")

    # ... (terminate 函数保持不变) ...
    async def terminate(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("TMP Bot 插件已卸载")