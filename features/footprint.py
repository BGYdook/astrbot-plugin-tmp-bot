"""Player footprint history and map output."""

import asyncio
import math
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any

from .astrbot_compat import AstrMessageEvent, Image, logger
from .shared import (
    read_json,
    ApiResponseException,
    BEIJING_TZ,
    FOOTPRINT_RENDER_REVISION,
    NetworkException,
    PROMODS_SERVER_IDS,
    PlayerNotFoundException,
    SteamIdNotFoundException,
    _format_timestamp_to_readable,
    _is_unknown_display_value,
    command_text,
)
from ..render.templates import COMBINED_FOOTPRINT_TEMPLATE, FOOTPRINT_TEMPLATE


class FootprintMixin:
    def _footprint_api_bases(self) -> List[str]:
        """返回足迹接口源；旧版单项配置仍可作为自定义源覆盖。"""
        legacy_base = self._cfg_str('footprint_api_base', '').strip()
        if legacy_base:
            return self._merge_api_bases(legacy_base, self._api_bases())
        return self._api_bases()

    async def _get_footprint_history(self, tmp_id: str, server_id: Optional[str], start_time: str, end_time: str) -> List[Dict[str, Any]]:
        if not self.session:
            return []
        sid = str(server_id or "").strip()
        params = {
            'tmpId': str(tmp_id).strip(),
            'startTime': str(start_time).strip(),
            'endTime': str(end_time).strip()
        }
        if sid:
            params['serverId'] = sid
        for base in self._footprint_api_bases():
            url = f"{base}/map/playerHistory"
            try:
                logger.debug(f"足迹历史: 请求 {url} params={params}")
                async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status != 200:
                        logger.debug(f"足迹历史: 源 {base} 返回状态码 {resp.status}，尝试下一个源")
                        continue
                    data = await read_json(resp)
            except Exception as e:
                logger.debug(f"足迹历史: 源 {base} 请求异常: {e}")
                continue
            if isinstance(data, list):
                if data:
                    return data
                continue
            if not isinstance(data, dict):
                continue
            code = data.get('code')
            try:
                code_ok = code is None or int(code) == 200
            except (TypeError, ValueError):
                code_ok = False
            if not code_ok:
                logger.info(f"足迹历史: 源 {base} 返回业务错误 code={code}")
                continue
            payload = data.get('data') or data.get('response') or data.get('result')
            if isinstance(payload, list) and payload:
                return payload
        return []

    def _normalize_history_points(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            coords = self._read_map_coordinates(it)
            if coords is None:
                continue
            axis_x, axis_y = coords
            server_id = it.get('serverId') or it.get('server_id') or it.get('server') or 0
            heading = self._finite_number(it.get('heading')) or 0
            ts_val = None
            update_time = it.get('updateTime') or it.get('time') or it.get('updatedAt') or it.get('update_time')
            if update_time:
                s = str(update_time).strip()
                try:
                    if s.endswith('Z') or re.search(r'[+-]\d{2}:\d{2}$', s):
                        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=BEIJING_TZ)
                    ts_val = int(dt.astimezone(BEIJING_TZ).timestamp())
                except Exception:
                    try:
                        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=BEIJING_TZ)
                        ts_val = int(dt.astimezone(BEIJING_TZ).timestamp())
                    except Exception:
                        ts_val = None
            server_id_val = 0
            try:
                server_id_val = int(server_id)
            except Exception:
                server_id_val = 0
            points.append({
                'axisX': axis_x,
                'axisY': axis_y,
                'serverId': server_id_val,
                'heading': heading,
                'ts': ts_val or 0
            })
        return points

    async def _get_footprint_data(self, server_key: str, tmp_id: str, server_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        server_ids = server_ids or []
        server_ids = [str(s).strip() for s in server_ids if str(s).strip()]
        urls = []
        for base in self._footprint_api_bases():
            urls.append(f"{base}/footprint/today?tmpId={tmp_id}&server={server_key}")
            urls.append(f"{base}/footprint/today?tmpId={tmp_id}&serverId={server_key}")
            urls.append(f"{base}/footprint/list?tmpId={tmp_id}&server={server_key}")
            urls.append(f"{base}/map/footprint?tmpId={tmp_id}&server={server_key}")
            urls.append(f"{base}/map/track?tmpId={tmp_id}&server={server_key}")
            for sid in server_ids:
                urls.append(f"{base}/footprint/today?tmpId={tmp_id}&serverId={sid}")
                urls.append(f"{base}/footprint/list?tmpId={tmp_id}&serverId={sid}")
                urls.append(f"{base}/map/footprint?tmpId={tmp_id}&serverId={sid}")
                urls.append(f"{base}/map/track?tmpId={tmp_id}&serverId={sid}")
        last_error = None
        request_limit = getattr(self, '_footprint_request_semaphore', None)
        if request_limit is None:
            request_limit = asyncio.Semaphore(6)
            self._footprint_request_semaphore = request_limit

        async def _request_footprint_url(url: str):
            nonlocal last_error
            try:
                async with request_limit:
                    logger.debug(f"足迹接口: 请求 {url}")
                    async with self.session.get(
                        url,
                        timeout=self._cfg_int('api_timeout_seconds', 10),
                    ) as resp:
                        if resp.status != 200:
                            return None
                        data = await read_json(resp)
                    if isinstance(data, dict):
                        code = data.get('code')
                        if code is not None and int(code) != 200:
                            return None
                        success = data.get('success')
                        if success is not None and success is False:
                            return None
                    points, _ = self._extract_footprint_points(data, server_key, server_ids)
                    return { 'url': url, 'data': data } if points else None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                return None

        tasks = [asyncio.create_task(_request_footprint_url(url)) for url in urls]
        try:
            for completed in asyncio.as_completed(tasks):
                result = await completed
                if result:
                    return result
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        if last_error:
            raise NetworkException(f"足迹接口请求失败: {last_error}")
        raise ApiResponseException("足迹接口无可用数据")

    def _extract_footprint_points(self, payload: Any, server_key: str, server_ids: Optional[List[str]] = None) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
        ids = [str(s).lower() for s in (server_ids or []) if str(s).strip()]
        key = str(server_key or "").strip().lower()

        def _point_from_item(item: Any) -> Optional[Dict[str, float]]:
            coords = self._read_map_coordinates(item)
            if coords is None:
                return None
            return {'x': coords[0], 'y': coords[1]}

        def _server_value(item: Any) -> Optional[str]:
            if not isinstance(item, dict):
                return None
            for field in ('serverId', 'server_id', 'server'):
                if field not in item or item.get(field) is None:
                    continue
                value = str(item.get(field)).strip().lower()
                if value:
                    return value
            return None

        def _match_server(item: Dict[str, Any]) -> bool:
            sid = _server_value(item)
            if not sid:
                return False
            return sid == key or sid in ids

        def _collect_points_from_list(items: List[Any]) -> List[Dict[str, float]]:
            """Collect direct points while excluding points from other servers.

            Some sources return a mixed flat list and others return a pure point
            list after the server has already been selected by the request. In
            the former case, the presence of a non-zero server id makes the
            filter authoritative; in the latter case all points are retained.
            """
            point_items = [(it, _point_from_item(it)) for it in items]
            point_items = [(it, point) for it, point in point_items if point]
            if not point_items:
                return []

            server_values = {
                sid for it, _ in point_items
                if (sid := _server_value(it)) and sid not in {'0', 'none', 'null'}
            }
            if server_values:
                return [
                    point for it, point in point_items
                    if _match_server(it)
                ]
            return [point for _, point in point_items]

        def _find_points(obj: Any, depth: int = 0) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
            if depth > 5:
                return [], {}
            if isinstance(obj, list):
                pts = _collect_points_from_list(obj)
                if pts:
                    return pts, {}
                for it in obj:
                    if isinstance(it, dict) and _match_server(it):
                        pts2, meta2 = _find_points(it, depth + 1)
                        if pts2:
                            return pts2, meta2 or it
                # A server-tagged group that does not match the requested
                # server must not be searched recursively, otherwise its
                # nested points would leak into the current route.
                for it in obj:
                    if isinstance(it, dict) and _server_value(it) and not _match_server(it):
                        continue
                    pts2, meta2 = _find_points(it, depth + 1)
                    if pts2:
                        return pts2, meta2
                return [], {}
            if isinstance(obj, dict):
                container_server = _server_value(obj)
                if (
                    container_server
                    and container_server not in {'0', 'none', 'null'}
                    and not _match_server(obj)
                ):
                    return [], {}
                for k in ['points', 'track', 'tracks', 'list', 'route', 'path', 'data', 'response', 'result', 'items']:
                    if k in obj:
                        pts2, meta2 = _find_points(obj.get(k), depth + 1)
                        if pts2:
                            return pts2, meta2 or obj
                for v in obj.values():
                    pts2, meta2 = _find_points(v, depth + 1)
                    if pts2:
                        return pts2, meta2
            return [], {}

        points, meta = _find_points(payload, 0)
        return points, meta

    async def _render_combined_footprint(self, server_data: List[Dict[str, Any]]) -> Optional[str]:
        """把同一天的多个服务器足迹合成为一张图片。ETS 与 ProMods 使用双地图面板。"""
        if not server_data:
            return None

        colors = {
            'SIM1': '#50afe8',
            'SIM2': '#72ddb0',
            'Arc': '#ffb45c',
            'ProMods': '#c58aff',
        }
        group_order = ('ets', 'promods')
        grouped: Dict[str, List[Dict[str, Any]]] = {key: [] for key in group_order}
        for item in server_data:
            map_type = item.get('map_type') if item.get('map_type') in grouped else 'ets'
            grouped[map_type].append({
                'label': item.get('server_label') or '未知服务器',
                'color': colors.get(item.get('server_label'), '#50afe8'),
                'points': item.get('points') or [],
            })

        map_groups = []
        for map_type in group_order:
            routes = grouped[map_type]
            if not routes:
                continue
            source = next(
                (item for item in server_data if item.get('map_type') == map_type),
                server_data[0],
            )
            map_groups.append({
                'map_type': map_type,
                'title': 'ETS2' if map_type == 'ets' else 'ProMods',
                'tile_url': (
                    source.get('tile_url_ets')
                    if map_type == 'ets'
                    else source.get('tile_url_promods')
                ),
                'routes': routes,
            })

        first = server_data[0]
        server_distances = []
        daily_total = None
        for item in server_data:
            distance = self._finite_number(item.get('distance_km'))
            if distance is None or distance < 0:
                continue
            if item.get('distance_scope') == 'daily_total':
                if daily_total is None:
                    daily_total = distance
            else:
                server_distances.append(distance)
        total_distance = daily_total
        if total_distance is None and server_distances:
            total_distance = sum(server_distances)
        if total_distance is not None:
            total_distance = round(total_distance, 1)

        combined_tmpl = COMBINED_FOOTPRINT_TEMPLATE
        server_chips = [
            {
                'label': item.get('server_label') or '未知服务器',
                'color': colors.get(item.get('server_label'), '#50afe8'),
            }
            for item in server_data
        ]
        data = {
            'map_groups': map_groups,
            'server_chips': server_chips,
            'player_name': first.get('player_name') or '未知',
            'avatar': first.get('avatar') or '',
            'avatar_initial': first.get('avatar_initial') or '?',
            'tmp_id': first.get('tmp_id') or '',
            'total_distance': total_distance,
        }
        try:
            return await self.html_render(
                combined_tmpl,
                data,
                options={
                    'type': 'jpeg',
                    'quality': 92,
                    'full_page': True,
                    'timeout': 8000,
                    'animations': 'disabled',
                },
            )
        except Exception as exc:
            logger.error(f"足迹合并渲染失败: {exc}", exc_info=True)
            return None

    async def tmptoday_footprint(
        self,
        event: AstrMessageEvent,
        _server_override: Optional[str] = None,
        _tmp_id_override: Optional[str] = None,
        _identity_override: Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None,
        _silent_empty: bool = False,
        _render_data_collector: Optional[List[Dict[str, Any]]] = None,
    ):
        message_str = command_text(event)
        user_id = event.get_sender_id()

        target_user_id = self._mentioned_user_id(event)
        message_text_parts = []
        message_obj = getattr(event, "message_obj", None)
        for seg in getattr(message_obj, "message", None) or []:
            if isinstance(seg, dict):
                seg_type = seg.get("type")
                seg_data = seg.get("data")
                text_value = seg.get("text")
            else:
                seg_type = getattr(seg, "type", None)
                seg_data = getattr(seg, "data", None)
                text_value = getattr(seg, "text", None)
            normalized_type = str(seg_type or "").lower()
            if normalized_type == "at":
                continue
            if isinstance(seg_data, dict):
                text_value = text_value or seg_data.get("text")
            if isinstance(text_value, str) and text_value:
                message_text_parts.append(text_value)
        if message_text_parts:
            reconstructed = command_text(event, " ".join(message_text_parts))
            if reconstructed.startswith("足迹"):
                message_str = reconstructed

        server_alias = {
            "s1": "sim1",
            "sim1": "sim1",
            "simulation1": "sim1",
            "s2": "sim2",
            "sim2": "sim2",
            "simulation2": "sim2",
            "p": "eupromods1",
            "promods": "eupromods1",
            "promods1": "eupromods1",
            "eupromods1": "eupromods1",
            "a": "arc1",
            "arc": "arc1",
            "arcade": "arc1",
            "arc1": "arc1",
        }
        all_server_keys = ["sim1", "sim2", "arc1", "eupromods1"]
        server_token = None
        input_id = None
        if not _server_override:
            rest = message_str[2:].strip() if message_str.startswith("足迹") else message_str.strip()
            compact = re.sub(r"\s+", "", rest)
            if compact.isdigit():
                input_id = compact
            elif compact:
                for alias in sorted(server_alias.keys(), key=len, reverse=True):
                    if not compact.lower().startswith(alias):
                        continue
                    suffix = compact[len(alias):]
                    if suffix == "" or suffix.isdigit():
                        server_token = alias
                        input_id = suffix or None
                        break
                if server_token is None:
                    tokens = rest.split()
                    if tokens:
                        server_token = tokens[0]
                        input_id = next((token for token in tokens[1:] if token.isdigit()), None)
        if _server_override:
            server_key = str(_server_override).strip().lower()
            if server_key not in all_server_keys:
                yield event.plain_result("服务器参数无效，请使用 s1、s2、a、p")
                return
        elif server_token:
            server_key_raw = str(server_token).strip().lower()
            server_key = server_alias.get(server_key_raw)
            if not server_key:
                yield event.plain_result("服务器参数无效，请使用 s1、s2、a、p")
                return
        else:
            server_key = None
        server_id_map = {
            "sim1": 2,
            "sim2": 41,
            "eupromods1": 50,
            "arc1": 7
        }
        server_label_map = {
            "sim1": "SIM1",
            "sim2": "SIM2",
            "eupromods1": "ProMods",
            "arc1": "Arc"
        }

        tmp_id = _tmp_id_override
        if not tmp_id:
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

        if _identity_override is not None:
            player_info, stats_info, online_status = _identity_override
        else:
            try:
                player_info, stats_info = await asyncio.gather(
                    self._get_player_info(tmp_id),
                    self._get_player_stats(tmp_id),
                )
                online_status = {}
            except PlayerNotFoundException as e:
                yield event.plain_result(str(e))
                return
            except Exception as e:
                yield event.plain_result(f"查询失败: {str(e)}")
                return

        if server_key is None:
            collected_server_data: List[Dict[str, Any]] = []

            async def collect_server_footprint(target_server: str) -> None:
                async for _ in self.tmptoday_footprint(
                    event,
                    _server_override=target_server,
                    _tmp_id_override=tmp_id,
                    _identity_override=(player_info, stats_info, online_status),
                    _silent_empty=True,
                    _render_data_collector=collected_server_data,
                ):
                    pass

            await asyncio.gather(
                *(collect_server_footprint(target_server) for target_server in all_server_keys)
            )
            if not collected_server_data:
                yield event.plain_result("所有服务器暂无可用的今日足迹数据")
                return

            label_order = {label: index for index, label in enumerate(("SIM1", "SIM2", "Arc", "ProMods"))}
            collected_server_data.sort(
                key=lambda item: label_order.get(item.get('server_label'), 99)
            )
            url = await self._render_combined_footprint(collected_server_data)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
            else:
                labels = "、".join(item['server_label'] for item in collected_server_data)
                yield event.plain_result(
                    f"足迹查询成功（{labels}），但图片渲染失败，请稍后重试"
                )
            return

        server_label = server_label_map.get(server_key, server_key.upper())
        map_type = 'promods' if server_key == 'eupromods1' else 'ets'

        player_name = player_info.get('name', '未知')
        last_online_raw = stats_info.get('last_online') or player_info.get('lastOnline')
        last_online_formatted = _format_timestamp_to_readable(last_online_raw) if last_online_raw else None
        if _is_unknown_display_value(last_online_formatted):
            last_online_formatted = None

        try:
            server_ids = []
            if server_key == 'eupromods1':
                server_ids.extend(str(sid) for sid in sorted(PROMODS_SERVER_IDS))
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

            now_local = datetime.now(BEIJING_TZ)
            start_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now_local.replace(hour=23, minute=59, second=59, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
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
            history_results = await asyncio.gather(
                *(
                    self._get_footprint_history(tmp_id, sid or None, start_time, end_time)
                    for sid in hist_list
                ),
                return_exceptions=True,
            )
            history_points = next(
                (
                    result for result in history_results
                    if isinstance(result, list) and result
                ),
                [],
            )
            if history_points:
                has_server_id = any(
                    str(p.get('serverId') or p.get('server_id') or p.get('server') or "").strip()
                    for p in history_points
                    if isinstance(p, dict)
                )
                if has_server_id:
                    if server_key in ['eupromods1', 'promods', 'promods1']:
                        filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) in {str(i) for i in PROMODS_SERVER_IDS}]
                    elif server_key in server_id_map:
                        target = str(server_id_map[server_key])
                        filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) == target]
                    elif server_ids:
                        target_set = {str(i) for i in server_ids}
                        filtered = [p for p in history_points if str(p.get('serverId') or p.get('server_id') or p.get('server')) in target_set]
                    else:
                        filtered = history_points
                    history_points = filtered

            if history_points:
                points = self._normalize_history_points(history_points)
                meta = {'source': 'playerHistory', 'startTime': range_start, 'endTime': range_end}
            else:
                logger.info("足迹历史为空，开始回退足迹接口")
                footprint_resp = await self._get_footprint_data(server_key, tmp_id, server_ids)
                points, meta = self._extract_footprint_points(footprint_resp.get('data'), server_key, server_ids)
                fallback_points = []
                for p in points:
                    x = p.get('x')
                    y = p.get('y')
                    if x is None or y is None:
                        continue
                    fallback_points.append({'axisX': x, 'axisY': y, 'serverId': 0, 'heading': 0, 'ts': 0})
                points = fallback_points
        except ApiResponseException:
            logger.info(f"{server_label} 暂无今日足迹数据")
            if not _silent_empty:
                yield event.plain_result(f"{server_label} 暂无今日足迹数据")
            return
        except Exception as e:
            logger.warning(f"查询 {server_label} 足迹失败: {e}")
            if not _silent_empty:
                yield event.plain_result(f"查询今日足迹失败: {str(e)}")
            return

        if not points:
            if not _silent_empty:
                yield event.plain_result(f"{server_label} 暂无今日足迹数据")
            return

        distance_km = None
        distance_scope = 'server'
        for field in ('distance', 'mileage', 'totalDistance', 'totalMileage'):
            value = self._finite_number(meta.get(field))
            if value is not None and value >= 0:
                distance_km = value / 1000.0 if value > 10000 else value
                break
        start_time = meta.get('startTime') or meta.get('start_time') or meta.get('beginTime') or meta.get('begin_time')
        end_time = meta.get('endTime') or meta.get('end_time') or meta.get('finishTime') or meta.get('finish_time')
        if distance_km is None:
            daily_km = self._finite_number(stats_info.get('daily_km'))
            if daily_km is not None and daily_km > 0:
                distance_km = daily_km
                distance_scope = 'daily_total'

        point_timestamps = []
        for point in points:
            try:
                point_ts = int(point.get('ts') or 0)
            except Exception:
                point_ts = 0
            if point_ts > 0:
                point_timestamps.append(point_ts)

        route_start_raw = min(point_timestamps) if point_timestamps else start_time
        route_end_raw = max(point_timestamps) if point_timestamps else end_time

        def _format_footprint_moment(value: Any) -> str:
            if value in (None, ''):
                return '暂无记录'
            parsed = None
            try:
                if isinstance(value, (int, float)):
                    parsed = datetime.fromtimestamp(float(value), BEIJING_TZ)
                else:
                    text = str(value).strip()
                    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=BEIJING_TZ)
                    else:
                        parsed = parsed.astimezone(BEIJING_TZ)
            except Exception:
                parsed = None
            if parsed is None:
                return str(value).replace(':00', '', 1) if str(value).count(':') >= 2 else str(value)
            date_prefix = '今天' if parsed.date() == now_local.date() else parsed.strftime('%m月%d日')
            return f"{date_prefix} {parsed:%H:%M}"

        route_start_label = _format_footprint_moment(route_start_raw)
        route_end_label = _format_footprint_moment(route_end_raw)
        track_duration_label = '未记录'
        if point_timestamps:
            duration_seconds = max(0, max(point_timestamps) - min(point_timestamps))
            if duration_seconds >= 86400:
                days, remainder = divmod(duration_seconds, 86400)
                hours = remainder // 3600
                track_duration_label = f"{days}天{hours}小时"
            elif duration_seconds >= 3600:
                hours, remainder = divmod(duration_seconds, 3600)
                track_duration_label = f"{hours}小时{remainder // 60}分"
            elif duration_seconds >= 60:
                track_duration_label = f"{duration_seconds // 60}分钟"
            else:
                track_duration_label = '少于1分钟'

        route_segments = 0
        previous_point = None
        for point in points:
            if previous_point is None:
                route_segments = 1
                previous_point = point
                continue
            try:
                coordinate_jump = math.hypot(
                    float(point.get('axisX') or 0) - float(previous_point.get('axisX') or 0),
                    float(point.get('axisY') or 0) - float(previous_point.get('axisY') or 0),
                ) * 19 > 30000
                previous_ts = int(previous_point.get('ts') or 0)
                current_ts = int(point.get('ts') or 0)
                time_jump = bool(previous_ts and current_ts and current_ts - previous_ts > 90)
            except Exception:
                coordinate_jump = time_jump = False
            if coordinate_jump or time_jump:
                route_segments += 1
            previous_point = point

        tile_url_ets = "https://ets-map.oss-cn-beijing.aliyuncs.com/ets2/05102019/{z}/{x}/{y}.png"
        tile_url_promods = "https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png"
        fullmap_ets = self._get_fullmap_tile_url("ets") if self._fullmap_cache else None
        fullmap_promods = self._get_fullmap_tile_url("promods") if self._fullmap_cache else None
        if fullmap_ets:
            tile_url_ets = fullmap_ets
        if fullmap_promods:
            tile_url_promods = fullmap_promods
        # 用户在配置里填了自定义瓦片源时，优先级最高
        tile_url_ets = self._tile_url('ets', tile_url_ets)
        tile_url_promods = self._tile_url('promods', tile_url_promods)

        map_tmpl = FOOTPRINT_TEMPLATE
        data = {
            'player_name': player_name,
            'avatar': self._normalize_avatar_url(player_info.get('avatar')) or '',
            'avatar_initial': str(player_name or '?').strip()[:1].upper() or '?',
            'points': points,
            'points_count': len(points),
            'distance_km': distance_km,
            'distance_scope': distance_scope,
            'start_time': start_time,
            'end_time': end_time,
            'route_start_label': route_start_label,
            'route_end_label': route_end_label,
            'track_duration_label': track_duration_label,
            'route_segments': route_segments,
            'tmp_id': tmp_id,
            'last_online': last_online_formatted if not _is_unknown_display_value(last_online_formatted) else None,
            'map_type': map_type,
            'server_label': server_label,
            'tile_url_ets': tile_url_ets,
            'tile_url_promods': tile_url_promods
        }
        if _render_data_collector is not None:
            _render_data_collector.append(data)
            return

        logger.info(
            f"足迹渲染: revision={FOOTPRINT_RENDER_REVISION}, "
            f"server={server_label}, points={len(points)}, distance_km={distance_km}"
        )
        try:
            url = await self.html_render(map_tmpl, data, options={'type': 'jpeg', 'quality': 92, 'full_page': True, 'timeout': 8000, 'animations': 'disabled'})
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception as exc:
            logger.warning(f"足迹图片渲染失败，回退为文本: {exc}")

        message = "📍 足迹\n"
        message += f"玩家: {player_name} (ID:{tmp_id})\n"
        message += f"服务器: {server_label}\n"
        message += f"点位数: {len(points)}"
        if distance_km is not None:
            message += f" | 里程: {distance_km:.2f} km"
        if last_online_formatted:
            message += f"\n上次在线: {last_online_formatted}"
        yield event.plain_result(message)
