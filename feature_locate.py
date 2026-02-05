"""
定位功能
"""

import re
from typing import Optional


async def tmplocate(
    self,
    event,
    logger,
    Image,
    locate_map_template,
    PlayerNotFoundException,
    SteamIdNotFoundException,
    NetworkException,
):
    message_str = event.message_str.strip()
    user_id = event.get_sender_id()

    target_user_id = None
    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None:
        try:
            chain = getattr(message_obj, "message", None) or []
            for seg in chain:
                seg_type = getattr(seg, "type", None)
                if isinstance(seg, dict):
                    seg_type = seg.get("type") or seg_type
                if isinstance(seg_type, str) and seg_type.lower() == "at":
                    uid = (
                        getattr(seg, "qq", None)
                        or getattr(seg, "user_id", None)
                        or getattr(seg, "id", None)
                    )
                    if isinstance(seg, dict):
                        uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                    if uid:
                        target_user_id = str(uid)
                        break
                uid2 = getattr(seg, "qq", None)
                if isinstance(seg, dict):
                    uid2 = seg.get("qq") or uid2
                if uid2:
                    target_user_id = str(uid2)
                    break
        except Exception:
            target_user_id = None

    match = re.search(r"(定位)\s*(\d+)", message_str)
    input_id = match.group(2) if match else None

    tmp_id = None

    if input_id:
        if len(input_id) == 17 and input_id.startswith("7"):
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
        bind_user_id = target_user_id or user_id
        tmp_id = self._get_bound_tmp_id(bind_user_id)

    if not tmp_id:
        yield event.plain_result("请输入正确的玩家编号 TMP ID")
        return

    try:
        player_info = await self._get_player_info(tmp_id)
    except PlayerNotFoundException as e:
        yield event.plain_result(str(e))
        return
    except Exception as e:
        yield event.plain_result(f"查询失败: {str(e)}")
        return

    await self._fetch_fullmap()
    fullmap_player = self._get_fullmap_player(tmp_id)
    online = await self._get_online_status(tmp_id)
    if not online or not online.get("online"):
        if not fullmap_player:
            yield event.plain_result("玩家未在线")
            return
        online = {
            "online": True,
            "serverName": "未知服务器",
            "serverId": fullmap_player.get("ServerId"),
            "x": fullmap_player.get("X"),
            "y": fullmap_player.get("Y"),
            "country": None,
            "realName": None,
            "city": {"name": "未知位置"},
        }
    if fullmap_player:
        online["x"] = fullmap_player.get("X")
        online["y"] = fullmap_player.get("Y")
        online["serverId"] = fullmap_player.get("ServerId")

    server_name = online.get("serverName", "未知服务器")
    location_name = online.get("city", {}).get("name") or "未知位置"

    raw_country = online.get("country")
    raw_city = online.get("realName")

    if not raw_country and " " in location_name:
        parts = location_name.split(" ", 1)
        if len(parts) == 2:
            pass

    country_cn, city_cn = await self._translate_country_city(raw_country, location_name)

    def _strip_paren_text(s: Optional[str]) -> str:
        t = (s or "").strip()
        if not t:
            return t
        t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
        t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
        return t

    display_country = _strip_paren_text(country_cn or "未知国家")
    display_city = _strip_paren_text(city_cn or "未知位置")
    if display_country and display_city:
        dc = display_country.strip()
        dcity = display_city.strip()
        if dcity == dc or dcity.startswith(dc):
            location_line = dcity
        else:
            location_line = f"{dc}-{dcity}"
    else:
        location_line = display_city or display_country or "未知位置"

    player_name = player_info.get("name") or "未知"

    avatar_url = self._normalize_avatar_url(player_info.get("avatar"))

    try:
        server_id = online.get("serverId")
        try:
            server_id = int(server_id) if server_id is not None else None
        except Exception:
            server_id = None
        cx = float(online.get("x") or 0)
        cy = float(online.get("y") or 0)
        ax, ay = cx - 4000, cy + 2500
        bx, by = cx + 4000, cy - 2500
        area_players = []
        if self.session and server_id:
            area_url = f"https://da.vtcm.link/map/playerList?aAxisX={ax}&aAxisY={ay}&bAxisX={bx}&bAxisY={by}&serverId={server_id}"
            logger.info(f"定位: 使用底图查询周边玩家 serverId={server_id} center=({cx},{cy}) url={area_url}")
            async with self.session.get(area_url, timeout=self._cfg_int("api_timeout_seconds", 10)) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    area_players = j.get("data") or []
                    logger.info(f"定位: 周边玩家数量={len(area_players)}")
        if not area_players and self._fullmap_cache:
            data = self._fullmap_cache or {}
            payload = data.get("Data") or data.get("data") or data.get("players")
            if isinstance(payload, list):
                for p in payload:
                    if not isinstance(p, dict):
                        continue
                    if server_id:
                        sid = p.get("ServerId") or p.get("serverId") or p.get("server_id")
                        try:
                            sid = int(sid) if sid is not None else None
                        except Exception:
                            sid = None
                        if sid is None or sid != server_id:
                            continue
                    px = p.get("X") or p.get("x") or p.get("axisX") or p.get("posX") or p.get("pos_x")
                    py = p.get("Y") or p.get("y") or p.get("axisY") or p.get("posY") or p.get("pos_y")
                    if px is None or py is None:
                        continue
                    try:
                        fx = float(px)
                        fy = float(py)
                    except Exception:
                        continue
                    if fx < min(ax, bx) or fx > max(ax, bx) or fy < min(by, ay) or fy > max(by, ay):
                        continue
                    pid = p.get("MpId") or p.get("mp_id") or p.get("tmpId") or p.get("tmp_id") or p.get("id")
                    area_players.append({"tmpId": str(pid) if pid is not None else "", "axisX": fx, "axisY": fy})
        normalized_players = []
        for p in area_players:
            if not isinstance(p, dict):
                continue
            axis_x = p.get("axisX") or p.get("x") or p.get("posX") or p.get("pos_x")
            axis_y = p.get("axisY") or p.get("y") or p.get("posY") or p.get("pos_y")
            if axis_x is None or axis_y is None:
                continue
            pid = p.get("tmpId") or p.get("mpId") or p.get("playerId") or p.get("id")
            normalized_players.append({"tmpId": str(pid) if pid is not None else "", "axisX": axis_x, "axisY": axis_y})
        area_players = normalized_players
        area_players = [p for p in area_players if str(p.get("tmpId")) != str(tmp_id)]
        area_players.append({"tmpId": str(tmp_id), "axisX": cx, "axisY": cy})

        map_type = "promods" if int(server_id or 0) in [50, 51] else "ets"
        tile_url_ets = "https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png"
        tile_url_promods = "https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png"
        fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
        fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
        if fullmap_ets:
            tile_url_ets = fullmap_ets
        if fullmap_promods:
            tile_url_promods = fullmap_promods
        logger.info(f"定位: tile_ets={'fullmap' if fullmap_ets else 'ets2.online'}")
        logger.info(f"定位: tile_promods={'fullmap' if fullmap_promods else 'ets2.online'}")
        if map_type == "ets" and not tile_url_ets:
            raise RuntimeError("fullmap 缓存未包含 ETS 瓦片地址")
        if map_type == "promods" and not tile_url_promods:
            raise RuntimeError("fullmap 缓存未包含 ProMods 瓦片地址")

        map_tmpl = locate_map_template()
        min_x, max_x = ax, bx
        min_y, max_y = by, ay
        map_data = {
            "server_name": server_name,
            "location_name": location_line,
            "player_name": player_name,
            "me_id": str(tmp_id),
            "players": area_players,
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "avatar": avatar_url or "",
            "location_line": location_line,
            "server_id": int(online.get("serverId") or 0),
            "center_x": float(cx),
            "center_y": float(cy),
            "tile_url_ets": tile_url_ets,
            "tile_url_promods": tile_url_promods,
        }
        logger.info(
            f"定位: 渲染底图 mapType={'promods' if int(online.get('serverId') or 0) in [50,51] else 'ets'} players={len(area_players)}"
        )
        url2 = await self.html_render(
            map_tmpl,
            map_data,
            options={"type": "jpeg", "quality": 92, "full_page": True, "timeout": 8000, "animations": "disabled"},
        )
        if isinstance(url2, str) and url2:
            yield event.chain_result([Image.fromURL(url2)])
            return
    except Exception:
        pass

    msg = f"玩家实时定位\n玩家名称: {player_name}\nTMP编号: {tmp_id}\n服务器: {server_name}\n位置: {location_line}"
    yield event.plain_result(msg)
