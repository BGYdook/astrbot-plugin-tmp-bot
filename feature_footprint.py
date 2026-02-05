"""
足迹功能
"""

import asyncio
import re
from datetime import datetime, timedelta


async def tmptoday_footprint(
    self,
    event,
    logger,
    Image,
    footprint_map_template,
    _format_timestamp_to_readable,
    PROMODS_SERVER_IDS,
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

    tokens = message_str.split()
    server_token = None
    input_id = None
    if len(tokens) > 1:
        for t in tokens[1:]:
            if t.isdigit():
                input_id = t
            else:
                server_token = t
    if not server_token:
        yield event.plain_result("用法: 足迹 [服务器简称] [ID]或 足迹 [服务器简称]，例如: 足迹 s1 123 或足迹 s1")
        return
    server_key_raw = str(server_token).strip().lower()
    server_alias = {
        "s1": "sim1",
        "s2": "sim2",
        "p": "eupromods1",
        "a": "arc1",
        "promods": "eupromods1",
        "promods1": "eupromods1",
        "sim1": "sim1",
        "sim2": "sim2",
        "arc1": "arc1",
    }
    server_key = server_alias.get(server_key_raw, server_key_raw)
    server_id_map = {"sim1": 2, "sim2": 41, "eupromods1": 50, "arc1": 7}
    server_label_map = {"sim1": "SIM1", "sim2": "SIM2", "eupromods1": "ProMods", "arc1": "Arc"}
    server_label = server_label_map.get(server_key, server_key.upper())
    map_type = "promods" if server_key in ["eupromods1", "promods", "promods1"] else "ets"

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
        player_info, stats_info, online_status = await asyncio.gather(
            self._get_player_info(tmp_id),
            self._get_player_stats(tmp_id),
            self._get_online_status(tmp_id),
        )
    except PlayerNotFoundException as e:
        yield event.plain_result(str(e))
        return
    except Exception as e:
        yield event.plain_result(f"查询失败: {str(e)}")
        return

    player_name = player_info.get("name", "未知")
    last_online_raw = stats_info.get("last_online") or player_info.get("lastOnline")
    last_online_formatted = _format_timestamp_to_readable(last_online_raw) if last_online_raw else "未知"

    try:
        server_ids = await self._resolve_server_ids(server_key)
        for k in ["serverId", "serverDetailsId", "apiServerId"]:
            v = online_status.get(k)
            if v is not None:
                s = str(v).strip()
                if s:
                    server_ids.append(s)
        mapped_id = server_id_map.get(server_key)
        if mapped_id is not None:
            server_ids.append(str(mapped_id))
        seen = set()
        uniq = []
        for sid in server_ids:
            if sid in seen:
                continue
            seen.add(sid)
            uniq.append(sid)
        server_ids = uniq

        now_local = datetime.now()
        start_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        end_time = now_local.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        history_points = []
        history_candidates = []
        if server_ids:
            history_candidates.extend(server_ids)
        mapped_id = server_id_map.get(server_key)
        if mapped_id is not None:
            history_candidates.append(str(mapped_id))
        history_candidates.append("")
        seen_hist = set()
        hist_list = []
        for sid in history_candidates:
            s = str(sid or "").strip()
            if s in seen_hist:
                continue
            seen_hist.add(s)
            hist_list.append(s)
        range_start = start_time
        range_end = end_time
        for sid in hist_list:
            history_points = await self._get_footprint_history(tmp_id, sid or None, start_time, end_time)
            if history_points:
                break
        if not history_points:
            extended_start = (now_local - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            extended_end = now_local.strftime("%Y-%m-%d %H:%M:%S")
            for sid in hist_list:
                history_points = await self._get_footprint_history(tmp_id, sid or None, extended_start, extended_end)
                if history_points:
                    range_start = extended_start
                    range_end = extended_end
                    break
        if history_points:
            has_server_id = any(
                str(p.get("serverId") or p.get("server_id") or p.get("server") or "").strip()
                for p in history_points
                if isinstance(p, dict)
            )
            if has_server_id:
                if server_key in ["eupromods1", "promods", "promods1"]:
                    filtered = [
                        p
                        for p in history_points
                        if str(p.get("serverId") or p.get("server_id") or p.get("server")) in {str(i) for i in PROMODS_SERVER_IDS}
                    ]
                elif server_key in server_id_map:
                    target = str(server_id_map[server_key])
                    filtered = [p for p in history_points if str(p.get("serverId") or p.get("server_id") or p.get("server")) == target]
                elif server_ids:
                    target_set = {str(i) for i in server_ids}
                    filtered = [p for p in history_points if str(p.get("serverId") or p.get("server_id") or p.get("server")) in target_set]
                else:
                    filtered = history_points
                history_points = filtered

        if history_points:
            points = self._normalize_history_points(history_points)
            meta = {"source": "playerHistory", "startTime": range_start, "endTime": range_end}
        else:
            logger.info("足迹历史为空，开始回退足迹接口")
            footprint_resp = await self._get_footprint_data(server_key, tmp_id, server_ids)
            points, meta = self._extract_footprint_points(footprint_resp.get("data"), server_key, server_ids)
            fallback_points = []
            for p in points:
                x = p.get("x")
                y = p.get("y")
                if x is None or y is None:
                    continue
                fallback_points.append({"axisX": x, "axisY": y, "serverId": 0, "heading": 0, "ts": 0})
            points = fallback_points
    except Exception as e:
        yield event.plain_result(f"查询今日足迹失败: {str(e)}")
        return

    if not points:
        yield event.plain_result("今日/输入的对应服务器暂无足迹数据")
        return

    def _to_km(val):
        try:
            v = float(val)
            if v > 10000:
                v = v / 1000.0
            return round(v, 2)
        except Exception:
            return None

    distance_km = _to_km(meta.get("distance") or meta.get("mileage") or meta.get("totalDistance") or meta.get("totalMileage"))
    start_time = meta.get("startTime") or meta.get("start_time") or meta.get("beginTime") or meta.get("begin_time")
    end_time = meta.get("endTime") or meta.get("end_time") or meta.get("finishTime") or meta.get("finish_time")
    if distance_km is None:
        try:
            daily_km = float(stats_info.get("daily_km") or 0)
            if daily_km > 0:
                distance_km = round(daily_km, 2)
        except Exception:
            distance_km = None

    tile_url_ets = "https://ets-map.oss-cn-beijing.aliyuncs.com/ets2/05102019/{z}/{x}/{y}.png"
    tile_url_promods = "https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png"
    fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
    fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
    if fullmap_ets:
        tile_url_ets = fullmap_ets
    if fullmap_promods:
        tile_url_promods = fullmap_promods

    map_tmpl = footprint_map_template()
    data = {
        "player_name": player_name,
        "avatar": self._normalize_avatar_url(player_info.get("avatar")) or "",
        "points": points,
        "points_count": len(points),
        "distance_km": distance_km,
        "start_time": start_time,
        "end_time": end_time,
        "last_online": last_online_formatted,
        "map_type": map_type,
        "server_label": server_label,
        "tile_url_ets": tile_url_ets,
        "tile_url_promods": tile_url_promods,
    }
    try:
        url = await self.html_render(
            map_tmpl,
            data,
            options={"type": "jpeg", "quality": 92, "full_page": True, "timeout": 8000, "animations": "disabled"},
        )
        if isinstance(url, str) and url:
            yield event.chain_result([Image.fromURL(url)])
            return
    except Exception:
        pass

    message = "📍 足迹\n"
    message += f"玩家: {player_name} (ID:{tmp_id})\n"
    message += f"服务器: {server_label}\n"
    message += f"点位数: {len(points)}"
    if distance_km is not None:
        message += f" | 里程: {distance_km:.2f} km"
    message += f"\n上次在线: {last_online_formatted}"
    yield event.plain_result(message)
