"""Player location queries and map output."""

import asyncio
import math
import re
from typing import Optional

import aiohttp

from .astrbot_compat import AstrMessageEvent, Image, logger
from .shared import (
    read_json,
    command_text,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
    _normalize_heading_to_direction,
)
from ..render.templates import LOCATION_TEMPLATE


class LocationMixin:
    async def tmplocate(self, event: AstrMessageEvent):
        """[命令:定位] 查询玩家的实时位置，并返回图片。支持输入 TMP ID 或 Steam ID。"""
        message_str = command_text(event)
        user_id = event.get_sender_id()

        target_user_id = self._mentioned_user_id(event)

        match = re.search(r'(定位)\s*(\d+)', message_str)
        input_id = match.group(2) if match else None

        tmp_id = None

        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    # SteamID 未注册
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    # 网络错误，建议重试
                    yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID")
            return

        # 1) 玩家基本信息（昵称）
        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        # 2) 在线与坐标（fullmap + Trucky V3）
        await self._fetch_fullmap()
        fullmap_player = self._get_fullmap_player(tmp_id)
        online = await self._get_online_status(tmp_id)
        if not online or not online.get('online'):
            if not fullmap_player:
                yield event.plain_result("玩家未在线")
                return
            fullmap_server_id = fullmap_player.get('ServerId')
            fullmap_server_names = {
                2: 'Simulation 1',
                41: 'Simulation 2',
                7: 'Arcade',
                50: 'ProMods',
                51: 'ProMods Arcade',
                15: '[US] Simulation',
                38: '[US] Arcade',
            }
            online = {
                'online': True,
                'serverName': fullmap_server_names.get(
                    int(fullmap_server_id or 0),
                    f'服务器 {fullmap_server_id or "未知"}',
                ),
                'game': 2 if int(fullmap_server_id or 0) in {9, 11, 38} else 1,
                'serverId': fullmap_server_id,
                'x': fullmap_player.get('X'),
                'y': fullmap_player.get('Y'),
                'country': None,
                'realName': None,
                'city': {'name': ''}
            }
        try:
            live_coordinates_valid = all(
                math.isfinite(float(online.get(key))) for key in ('x', 'y')
            )
        except (TypeError, ValueError, OverflowError):
            live_coordinates_valid = False
        if (
            fullmap_player and not live_coordinates_valid
            and str(fullmap_player.get('ServerId')) == str(online.get('serverId'))
        ):
            online['x'] = fullmap_player.get('X')
            online['y'] = fullmap_player.get('Y')
        try:
            if not all(math.isfinite(float(online.get(key))) for key in ('x', 'y')):
                raise ValueError("non-finite coordinates")
        except (TypeError, ValueError, OverflowError):
            yield event.plain_result("玩家在线，但暂未获取到有效的位置坐标，请稍后重试")
            return

        # 3) 构造 HTML 渲染数据（玩家 + 位置，周边玩家留作后续扩展）
        server_name = online.get('serverName', '未知服务器')
        location_name = online.get('city', {}).get('name') or '未知位置'

        # 增加翻译逻辑
        raw_country = online.get('country')

        # 如果 raw_country 为空，尝试从 location_name 解析
        if not raw_country and ' ' in location_name:
             parts = location_name.split(' ', 1)
             if len(parts) == 2:
                 # 假设格式为 "Country City"
                 pass

        country_cn, city_cn = await self._translate_country_city(raw_country, location_name)

        # 修正显示名称
        def _strip_paren_text(s: Optional[str]) -> str:
            t = (s or "").strip()
            if not t:
                return t
            t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
            t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
            return t

        display_country = _strip_paren_text(country_cn or '未知国家')
        display_city = _strip_paren_text(city_cn or '未知位置')
        if display_country and display_city:
            dc = display_country.strip()
            dcity = display_city.strip()
            if dcity == dc or dcity.startswith(dc):
                location_line = dcity
            else:
                location_line = f"{dc}-{dcity}"
        else:
            location_line = display_city or display_country or "未知位置"

        heading_candidates = [
            online.get('heading'),
            online.get('direction'),
            online.get('yaw'),
            online.get('rotation'),
            online.get('bearing'),
            fullmap_player.get('Heading') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('heading') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('yaw') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('rotation') if isinstance(fullmap_player, dict) else None,
            fullmap_player.get('bearing') if isinstance(fullmap_player, dict) else None,
        ]
        direction_text = None
        for candidate in heading_candidates:
            direction_text = _normalize_heading_to_direction(candidate)
            if direction_text:
                break
        if direction_text:
            direction_text = f"正在向{direction_text}行驶"

        player_name = player_info.get('name') or '未知'

        avatar_url = self._normalize_avatar_url(player_info.get('avatar'))

        # 4) 周边玩家查询并绘制简易地图（第三方 VTCM 源，见 _api_bases()）
        try:
            server_id = online.get('serverId')
            cx = float(online.get('x') or 0)
            cy = float(online.get('y') or 0)
            ax, ay = cx - 4000, cy + 2500
            bx, by = cx + 4000, cy - 2500
            area_players = []
            if self.session and server_id:
                for api_base in self._api_bases():
                    area_url = f"{api_base}/map/playerList?aAxisX={ax}&aAxisY={ay}&bAxisX={bx}&bAxisY={by}&serverId={server_id}"
                    logger.info(f"定位: 使用底图查询周边玩家 serverId={server_id} center=({cx},{cy}) url={area_url}")
                    try:
                        async with self.session.get(area_url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                            if resp.status == 200:
                                j = await read_json(resp)
                                area_players = j.get('data') or []
                                logger.info(f"定位: 周边玩家数量={len(area_players)}")
                                break
                            logger.info(f"定位: 底图查询返回状态 {resp.status}，尝试备用源")
                    except Exception as e:
                        logger.info(f"定位: 底图查询异常: {e}")
            if not area_players:
                for p in self._fresh_fullmap_players():
                    if not isinstance(p, dict):
                        continue
                    sid = p.get('ServerId') or p.get('serverId') or p.get('server_id')
                    if str(sid) != str(server_id or 0):
                        continue
                    coords = self._read_map_coordinates(p)
                    if coords is None:
                        continue
                    fx, fy = coords
                    if not (min(ax, bx) <= fx <= max(ax, bx) and min(by, ay) <= fy <= max(by, ay)):
                        continue
                    pid = p.get('MpId') or p.get('mp_id') or p.get('tmpId') or p.get('tmp_id') or p.get('id')
                    area_players.append({'tmpId': str(pid) if pid is not None else '', 'axisX': fx, 'axisY': fy})
            normalized_players = []
            for p in area_players:
                if not isinstance(p, dict):
                    continue
                coords = self._read_map_coordinates(p)
                if coords is None:
                    continue
                axis_x, axis_y = coords
                pid = p.get('tmpId') or p.get('mpId') or p.get('playerId') or p.get('id')
                normalized_players.append({
                    'tmpId': str(pid) if pid is not None else '',
                    'axisX': axis_x,
                    'axisY': axis_y
                })
            area_players = normalized_players
            area_players = [p for p in area_players if str(p.get('tmpId')) != str(tmp_id)]
            area_players.append({'tmpId': str(tmp_id), 'axisX': cx, 'axisY': cy})

            map_type = 'promods' if int(server_id or 0) in [50, 51] else 'ets'
            default_tile_ets = "https://ets2.online/map/ets2map_161/{z}/{x}/{y}.png"
            default_tile_promods = "https://ets2.online/map/ets2mappromods_158/{z}/{x}/{y}.png"
            custom_tile_urls = {layer: self._tile_url(layer, '') for layer in ('ets', 'promods')}
            tile_url_ets = custom_tile_urls['ets'] or default_tile_ets
            tile_url_promods = custom_tile_urls['promods'] or default_tile_promods
            map_profiles = {
                'ets': self._location_map_profile('ets', tile_url_ets),
                'promods': self._location_map_profile('promods', tile_url_promods),
            }
            for layer, default_url in (
                ('ets', default_tile_ets), ('promods', default_tile_promods),
            ):
                if map_profiles[layer]['tileUrl'] != default_url:
                    map_profiles[layer]['fallback'] = self._location_map_profile(layer, default_url)
            logger.info(f"定位: tile_ets={tile_url_ets}")
            logger.info(f"定位: tile_promods={tile_url_promods}")
            if not custom_tile_urls[map_type]:
                try:
                    tracker_profile = await self._prepare_location_basemap(map_type, float(cx), float(cy))
                except (aiohttp.ClientError, asyncio.TimeoutError, NetworkException, ValueError) as exc:
                    logger.warning(f"定位: 追踪地图不可用，使用默认底图 ({type(exc).__name__})")
                else:
                    tracker_profile['fallback'] = map_profiles[map_type]
                    map_profiles[map_type] = tracker_profile

            map_tmpl = LOCATION_TEMPLATE
            min_x, max_x = ax, bx
            min_y, max_y = by, ay  # 注意坐标系方向
            map_data = {
                'server_name': server_name,
                'location_name': location_line,
                'player_name': player_name,
                'me_id': str(tmp_id),
                'players': area_players,
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y,
                'avatar': avatar_url or '',
                'avatar_initial': str(player_name or '?').strip()[:1].upper() or '?',
                'nearby_count': max(0, len(area_players) - 1),
                'location_line': location_line,
                'direction_text': direction_text,
                'server_id': int(online.get('serverId') or 0),
                'center_x': float(cx),
                'center_y': float(cy),
                'tile_url_ets': tile_url_ets,
                'tile_url_promods': tile_url_promods,
                'map_profiles': map_profiles,
            }
            logger.info(f"定位: 渲染底图 mapType={'promods' if int(online.get('serverId') or 0) in [50,51] else 'ets'} players={len(area_players)}")
            url2 = await self.html_render(map_tmpl, map_data, options={'type': 'jpeg', 'quality': 92, 'full_page': True, 'timeout': 8000, 'animations': 'disabled'})
            if isinstance(url2, str) and url2:
                yield event.chain_result([Image.fromURL(url2)])
                return
        except Exception as exc:
            logger.warning(f"定位图片生成失败，回退文字: {exc}", exc_info=True)

        # 最终回退文本
        msg = f"玩家实时定位\n玩家名称: {player_name}\nTMP编号: {tmp_id}\n服务器: {server_name}"
        if location_line:
            msg += f"\n位置: {location_line}"
        if direction_text:
            msg += f"\n状态: {direction_text}"
        yield event.plain_result(msg)
