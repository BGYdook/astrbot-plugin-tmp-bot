"""Player lookup, activity, and profile queries."""

import asyncio
import re
from typing import Optional, Dict, Tuple, Any

import aiohttp

from .astrbot_compat import AstrMessageEvent, Image, Plain, logger
from .shared import (
    read_json,
    command_text,
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
    _format_timestamp_to_beijing,
    _format_timestamp_to_readable,
    _is_hidden_ban_expiry,
    _is_hidden_ban_reason,
    _is_permanent_ban_expiry,
    _translate_user_groups,
)


class PlayerMixin:
    async def _get_tmp_id_from_steam_id(self, steam_id: str) -> str:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        try:
            # TruckersMP 官方 API - 直接通过 SteamID 查询玩家信息
            url = f"https://api.truckersmp.com/v2/player/{steam_id}"

            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await read_json(response)

                    if data.get('error') is False and data.get('response'):
                        player_data = data.get('response', {})
                        tmp_id = player_data.get('id')

                        if tmp_id:
                            logger.info(f"成功通过 SteamID {steam_id} 获取到 TMP ID: {tmp_id}")
                            return str(tmp_id)
                        else:
                            raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                    else:
                        error_msg = data.get('descriptor', '未知错误')
                        if 'not found' in error_msg.lower() or 'unable to find' in error_msg.lower():
                            raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                        else:
                            raise ApiResponseException(f"API 返回错误: {error_msg}")
                elif response.status == 404:
                    raise SteamIdNotFoundException(f"Steam ID {steam_id} 未在 TruckersMP 中注册。")
                else:
                    raise ApiResponseException(f"Steam ID查询API返回错误状态码: {response.status}")
        except SteamIdNotFoundException:
            raise
        except aiohttp.ClientError:
            raise SteamIdNotFoundException("Steam ID查询服务网络请求失败")
        except asyncio.TimeoutError:
            raise SteamIdNotFoundException("请求 Steam ID 查询服务超时")
        except Exception as e:
            logger.error(f"通过 SteamID 查询 TMP ID 失败: {e}")
            raise SteamIdNotFoundException(f"Steam ID {steam_id} 查询失败，请检查ID是否正确")

    def _get_steam_id_from_player_info(self, player_info: Dict) -> Optional[str]:
        steam_id = player_info.get('steamID64')
        return str(steam_id) if steam_id else None

    async def _get_player_info(self, tmp_id: str) -> Dict:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        try:
            # TMP 官方 V2 接口
            url = f"https://api.truckersmp.com/v2/player/{tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await read_json(response)
                    if not isinstance(data, dict):
                        raise ApiResponseException("玩家信息 API 返回格式异常")
                    if data.get('error'):
                        descriptor = str(data.get('descriptor') or data.get('message') or '').strip()
                        if 'not found' in descriptor.lower() or 'unable to find' in descriptor.lower():
                            raise PlayerNotFoundException("此TMPID不存在，请检查后重试")
                        raise ApiResponseException(descriptor or "TruckersMP 玩家信息查询失败")
                    response_data = data.get('response')
                    if response_data and isinstance(response_data, dict):
                        return response_data
                    raise PlayerNotFoundException("此TMPID不存在，请检查后重试")
                elif response.status == 404:
                    raise PlayerNotFoundException("此TMPID不存在，请检查后重试")
                else:
                    raise ApiResponseException(f"API返回错误状态码: {response.status}")
        except (PlayerNotFoundException, ApiResponseException, NetworkException):
            raise
        except aiohttp.ClientError:
            raise NetworkException("TruckersMP API 网络请求失败")
        except asyncio.TimeoutError:
            raise NetworkException("请求TruckersMP API超时")
        except Exception as e:
            logger.error(f"查询玩家信息失败: {e}")
            raise NetworkException(f"玩家信息查询失败: {e}") from e

    @staticmethod
    def _mentioned_user_id(event: AstrMessageEvent) -> Optional[str]:
        """Skip mentions of the bot, including QQ's synthetic adapter mention."""
        ignored = {'qq_official', 'all'}
        get_self_id = getattr(event, 'get_self_id', None)
        if callable(get_self_id):
            self_id = get_self_id()
            if self_id is not None:
                ignored.add(str(self_id).strip())

        message_obj = getattr(event, 'message_obj', None)
        for seg in getattr(message_obj, 'message', None) or []:
            if isinstance(seg, dict):
                fields = seg
            else:
                fields = {key: getattr(seg, key, None) for key in ('type', 'data', 'qq', 'user_id', 'id')}
            nested = fields.get('data')
            if not isinstance(nested, dict):
                nested = {}
            if str(fields.get('type') or '').lower() != 'at':
                # Older adapters may expose a bare qq attribute without a segment type.
                if fields.get('type') or not fields.get('qq'):
                    continue
            for source in (fields, nested):
                uid = source.get('qq') or source.get('user_id') or source.get('id')
                if uid is not None and (uid := str(uid).strip()):
                    if uid not in ignored:
                        return uid
                    break
        return None

    async def _resolve_tmp_id_for_user_command(
        self,
        event: AstrMessageEvent,
        command_name: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """解析用户命令中的 TMP ID、Steam ID、绑定账号或被 @ 用户。"""
        message_str = command_text(event)
        target_user_id = self._mentioned_user_id(event)

        match = re.search(rf"{re.escape(command_name)}\s*(\d+)?", message_str)
        input_id = match.group(1) if match else None
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    return await self._get_tmp_id_from_steam_id(input_id), None
                except SteamIdNotFoundException as exc:
                    return None, str(exc)
                except NetworkException as exc:
                    return None, f"SteamID查询失败: {exc}\n请稍后重试或使用TMP ID查询"
                except Exception as exc:
                    logger.error(f"违规查询解析 SteamID 失败: {exc}")
                    return None, "SteamID查询失败，请直接使用 TMP ID"
            return input_id, None

        bind_user_id = target_user_id or event.get_sender_id()
        tmp_id = self._get_bound_tmp_id(bind_user_id)
        if tmp_id:
            return str(tmp_id), None
        return None, f"请先绑定账号，或使用 {command_name} [TMP ID]"

    async def _get_player_stats(self, tmp_id: str) -> Dict[str, Any]:
        """通过 VTCM 里程 API 获取玩家的总里程、今日里程和头像。
        API 源取自 `_api_bases()`（用户自定义源优先，内置源兜底）。
        """
        if not self.session:
            return {'total_km': 0, 'daily_km': 0, 'avatar_url': '', 'debug_error': 'HTTP会话不可用。'}

        def _to_km_2f(val, default=0.0):
            try:
                if val is None:
                    return default
                if isinstance(val, (int, float)):
                    return round(float(val) / 1000.0, 2)
                s = str(val).strip()
                if s == "":
                    return default
                return round(float(s) / 1000.0, 2)
            except Exception:
                return default

        def _to_int_rank(val):
            try:
                if val is None:
                    return None
                if isinstance(val, int):
                    return val
                if isinstance(val, float):
                    return int(val)
                s = str(val).strip()
                if s == '':
                    return None
                return int(float(s))
            except Exception:
                return None

        for vtcm_base in self._api_bases():
            vtcm_stats_url = f"{vtcm_base}/player/info?tmpId={tmp_id}"
            logger.info(f"尝试 VTCM 里程 API: {vtcm_stats_url}")
            try:
                async with self.session.get(
                    vtcm_stats_url,
                    timeout=self._cfg_int('api_timeout_seconds', 10),
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        logger.info(f"VTCM 里程 API 返回非 200 状态: status={response.status}")
                        continue

                    data = await read_json(response)
                    response_data = data.get('data', {})
                    logger.info(f"VTCM 里程响应: status=200, code={data.get('code')}, has_data={bool(response_data)}")

                    total_raw = response_data.get('mileage')
                    daily_raw = response_data.get('todayMileage')
                    total_km = _to_km_2f(total_raw, 0.0)
                    daily_km = _to_km_2f(daily_raw, 0.0)
                    avatar_url = response_data.get('avatarUrl', '')
                    vtc_role = response_data.get('vtcRole') or response_data.get('vtc_role')

                    total_rank_raw = (
                        response_data.get('mileageRank')
                        or response_data.get('totalMileageRank')
                        or response_data.get('mileage_rank')
                        or response_data.get('total_rank')
                    )
                    daily_rank_raw = (
                        response_data.get('todayMileageRank')
                        or response_data.get('todayRank')
                        or response_data.get('today_mileage_rank')
                        or response_data.get('today_rank')
                    )
                    total_rank = _to_int_rank(total_rank_raw)
                    daily_rank = _to_int_rank(daily_rank_raw)
                    last_online = (
                        response_data.get('lastOnline')
                        or response_data.get('lastOnlineTime')
                        or response_data.get('last_login')
                        or response_data.get('lastLogin')
                        or None
                    )
                    logger.info(
                        f"VTCM 里程解析: total_km={total_km:.2f}, today_km={daily_km:.2f}, "
                        f"total_rank={total_rank}, daily_rank={daily_rank}, avatar={avatar_url}"
                    )

                    if data.get('code') != 200 or not response_data:
                        logger.info(f"VTCM 里程数据校验失败: code={data.get('code')}, has_data={bool(response_data)}")
                        raise ApiResponseException(f"VTCM 里程 API 返回非成功代码或空数据: {data.get('msg', 'N/A')}")

                    return {
                        'total_km': total_km,
                        'daily_km': daily_km,
                        'avatar_url': avatar_url,
                        'last_online': last_online,
                        'vtcRole': vtc_role,
                        'total_rank': total_rank,
                        'daily_rank': daily_rank,
                        'debug_error': 'VTCM 里程数据获取成功。',
                        'debug_source': vtcm_stats_url,
                    }
            except aiohttp.ClientError as e:
                logger.warning(f"VTCM 里程 API 网络异常({vtcm_stats_url}): {e}")
            except Exception as e:
                logger.warning(f"VTCM 里程 API 失败({vtcm_stats_url}): {e}")

        logger.warning(f"VTCM 里程 API 全部失败: tmpId={tmp_id}")
        return {
            'total_km': 0,
            'daily_km': 0,
            'avatar_url': '',
            'vtcRole': None,
            'total_rank': None,
            'daily_rank': None,
            'debug_source': None,
            'debug_error': '所有 VTCM 里程 API 备用源均失败。',
        }

    async def _get_online_status(self, tmp_id: str) -> Dict:
        """使用 TruckyApp V3 地图实时接口查询状态。"""
        if not self.session:
            return {'online': False, 'debug_error': 'HTTP会话不可用。'}

        trucky_url = f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}"
        logger.info(f"尝试 Trucky V3 API (地图实时状态): {trucky_url}")

        try:
            async with self.session.get(trucky_url, timeout=8) as response:

                status = response.status
                raw_data = await read_json(response)

                if status == 200:
                    online_data = raw_data.get('response') if 'response' in raw_data else raw_data

                    is_online = bool(
                        online_data and
                        online_data.get('online') is True and
                        online_data.get('server')
                    )

                    if is_online:
                        server_details = online_data.get('serverDetails', {})
                        server_name = server_details.get('name', f"未知服务器 ({online_data.get('server')})")

                        location_data = online_data.get('location')
                        if not isinstance(location_data, dict):
                            location_data = {}
                        poi = location_data.get('poi')
                        if not isinstance(poi, dict):
                            poi = {}
                        country = poi.get('country')
                        real_name = poi.get('realName')
                        location_type = poi.get('type') or ''

                        if not country:
                            country = location_data.get('country')
                        if not real_name:
                            real_name = location_data.get('realName')

                        country_cn, city_cn = await self._translate_country_city(country, real_name)

                        location_cn = city_cn or str(real_name or '').strip()
                        formatted_location = '未知位置'
                        if country_cn and location_cn:
                            formatted_location = f"{country_cn}-{location_cn}"
                        elif location_cn:
                            formatted_location = location_cn
                        elif country_cn:
                            formatted_location = country_cn

                        return {
                            'online': True,
                            'serverName': server_name,
                            'game': 1 if server_details.get('game') == 'ETS2' else 2 if server_details.get('game') == 'ATS' else 0,
                            'city': {'name': formatted_location},
                            'serverId': online_data.get('server'),
                            'serverDetailsId': server_details.get('id') or server_details.get('_id'),
                            'apiServerId': server_details.get('apiserverid') or server_details.get('apiServerId'),
                            'serverCode': server_details.get('code') or server_details.get('shortname'),
                            'x': online_data.get('x'),
                            'y': online_data.get('y'),
                            'country': country_cn or str(country or '').strip(),
                            'realName': location_cn,
                            'locationType': location_type,
                            'debug_error': 'Trucky V3 判断在线，并获取到实时数据。',
                            'raw_data': ''
                        }

                    return {
                        'online': False,
                        'debug_error': 'Trucky V3 API 响应判断为离线。',
                        'raw_data': ''
                    }

                else:
                    return {
                        'online': False,
                        'debug_error': f"Trucky V3 API 返回非 200 状态码: {status}",
                        'raw_data': ''
                    }

        except Exception as e:
            logger.error(f"Trucky V3 API 解析失败: {e.__class__.__name__}", exc_info=True)
            return {'online': False, 'debug_error': f'Trucky V3 API 发生意外错误: {e.__class__.__name__}。'}

    async def tmpquery(self, event: AstrMessageEvent):
        """[命令: 查询] 玩家完整信息查询。支持输入 TMP ID 或 Steam ID。"""
        message_str = command_text(event)
        user_id = event.get_sender_id()

        target_user_id = self._mentioned_user_id(event)

        match = re.search(r'(查询|查)\s*(\d+)', message_str)
        input_id = match.group(2) if match else None

        tmp_id = None

        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                # SteamID 格式检测
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

        try:
            # 并行查询：仅使用 V2 和相关接口（移除已失效的 V1）
            player_info_raw, bans_info, online_status, stats_info = await asyncio.gather(
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id),
                self._get_online_status(tmp_id),
                self._get_player_stats(tmp_id)
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
        banned_until_main = player_info.get('bannedUntil')

        ban_count, sorted_bans = self._format_ban_info(bans_info)
        bans_count_raw = player_info.get('bansCount')
        if bans_count_raw is not None:
            try:
                ban_count = int(str(bans_count_raw).strip())
            except (TypeError, ValueError):
                logger.debug("玩家 bansCount 不是有效整数，保留已解析的封禁数量")

        last_online_raw = (
            player_info.get('lastOnline')
            or stats_info.get('last_online')
            or stats_info.get('lastOnline')
            or stats_info.get('lastLogin')
            or stats_info.get('last_login')
            or None
        )
        if last_online_raw and last_online_raw != player_info.get('lastOnline'):
            logger.info(f"查询详情: 使用 VTCM 提供的上次在线字段，值={last_online_raw}")
        # 将“上次在线”统一显示为北京时间 (UTC+8)
        last_online_formatted = _format_timestamp_to_readable(last_online_raw)

        # 完整的回复消息正文构建
        body = ""
        body += f"🆔 TMP ID: {tmp_id}\n"
        if steam_id_to_display:
            body += f"🆔 Steam ID: {steam_id_to_display}\n"
        body += f"😀玩家名称: {player_info.get('name', '未知')}\n"
        # 📑注册日期：优先使用 joinDate，其次 fallback 到 created_at/registrationDate
        join_date_raw = (
            player_info.get('joinDate')
            or player_info.get('created_at')
            or player_info.get('registrationDate')
            or None
        )
        join_date_formatted = _format_timestamp_to_beijing(join_date_raw) if join_date_raw else '未知'
        body += f"📑注册日期: {join_date_formatted}\n"

        # 权限/分组信息
        perms_str = "玩家"
        if player_info.get('permissions'):
            perms = player_info['permissions']
            if isinstance(perms, dict):
                groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f'is{g.replace(" ", "")}')]
                if groups:
                    perms_str = ', '.join(_translate_user_groups(groups))
            elif isinstance(perms, list) and perms:
                perms_str = ', '.join(_translate_user_groups(perms))
        body += f"💼所属分组: {perms_str}\n"

        # 车队信息：优先使用 player_info.vtc（若为字典），若缺少 role 则调用 VTCM API 获取
        # 如检测到没有车队，则两个都不显示
        vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
        vtc_name = vtc.get('name')
        vtc_role = vtc.get('role') or vtc.get('position') or stats_info.get('vtcRole')

        # 只有当有车队时才显示车队信息
        if vtc_name:
            body += f"🚚所属车队: {vtc_name}\n"
            if not vtc_role:
                try:
                    vtc_role_remote = await self._get_vtc_member_role(tmp_id, vtc)
                    if vtc_role_remote:
                        vtc_role = vtc_role_remote
                        logger.info(f"查询详情: 从 VTC API 获取到车队角色: {vtc_role}")
                except Exception as e:
                    logger.info(f"查询详情: 获取 VTC 车队角色时发生异常: {e}", exc_info=False)
            if vtc_role:
                body += f"🚚车队职位: {vtc_role}\n"

        # --- 【核心逻辑】赞助信息 (基于 V2 player 接口字段) ---
        # 规则：
        # - isPatron: 是否赞助过（true 为赞助过，false 为未赞助过）
        # - 仅当 isPatron 为 true 时，才读取 active/currentPledge/lifetimePledge；否则 active=否，金额均为 0
        # - active: 当前赞助是否有效
        # - currentPledge: 当前赞助金额（需除以 100）；为 0 则视为“当前未赞助”
        # - lifetimePledge: 历史赞助金额（需除以 100）
        # 兼容字段位置：尝试从顶层、patron、donation 三处获取，避免结构差异导致解析失败。
        def _get_nested(d: Dict, *keys):
            cur = d
            for k in keys:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            return cur

        # 兼容 isPatron / isPatreon，兼容容器 patreon / patron
        is_patron = any([
            bool(player_info.get('isPatron')),
            bool(player_info.get('isPatreon')),
            bool(_get_nested(player_info, 'patreon', 'isPatron')),
            bool(_get_nested(player_info, 'patreon', 'isPatreon')),
            bool(_get_nested(player_info, 'patron', 'isPatron')),
            bool(_get_nested(player_info, 'patron', 'isPatreon')),
        ])

        def _to_int(val, default=0):
            try:
                if val is None:
                    return default
                if isinstance(val, (int,)):
                    return val
                if isinstance(val, float):
                    return int(val)
                s = str(val).strip()
                if s == "":
                    return default
                return int(float(s))
            except Exception:
                return default

        # 优先 patreon 容器，其次顶层，再次 patron/donation 容器
        current_pledge_raw = (
            _get_nested(player_info, 'patreon', 'currentPledge') or
            player_info.get('currentPledge') or
            _get_nested(player_info, 'patron', 'currentPledge') or
            _get_nested(player_info, 'donation', 'currentPledge') or 0
        )
        lifetime_pledge_raw = (
            _get_nested(player_info, 'patreon', 'lifetimePledge') or
            player_info.get('lifetimePledge') or
            _get_nested(player_info, 'patron', 'lifetimePledge') or
            _get_nested(player_info, 'donation', 'lifetimePledge') or 0
        )

        # 以“美元”为单位展示，去除小数（整美元）。API金额为分，使用整除 100。
        current_pledge = (_to_int(current_pledge_raw) // 100) if is_patron else 0
        lifetime_pledge = (_to_int(lifetime_pledge_raw) // 100) if is_patron else 0

        if is_patron and lifetime_pledge > 0:
            if current_pledge > 0:
                body += f"🎁当前赞助金额: {current_pledge}美元\n"
            body += f"🎁历史赞助金额: {lifetime_pledge}美元\n"
        # --- 赞助信息结束 ---

        # --- 里程信息输出 (不变) ---
        logger.info(f"查询详情: 里程字典 keys={list(stats_info.keys())}, debug={stats_info.get('debug_error')}")
        total_km = stats_info.get('total_km', 0.0)
        daily_km = stats_info.get('daily_km', 0.0)
        total_rank = stats_info.get('total_rank')
        daily_rank = stats_info.get('daily_rank')
        logger.info(f"查询详情: 里程输出值 total_km={total_km:.2f}, daily_km={daily_km:.2f}, total_rank={total_rank}, daily_rank={daily_rank}")

        try:
            total_val = float(total_km)
        except Exception:
            total_val = 0.0
        try:
            daily_val = float(daily_km)
        except Exception:
            daily_val = 0.0

        if total_val > 0:
            body += f"🚩历史里程: {total_val:.2f}公里/km\n"
        if daily_val > 0:
            body += f"🚩今日里程: {daily_val:.2f}公里/km\n"

        # --- 封禁信息 (不变) ---
        body += f"🚫是否封禁: {'是' if is_banned else '否'}\n"

        body += f"🚫历史封禁: {ban_count}次\n"

        if is_banned:

            current_ban = None
            if sorted_bans:
                current_ban = next((
                    ban for ban in sorted_bans
                    if ban.get('active') is True
                    or str(ban.get('active')).strip().lower() in {'1', 'true', 'yes'}
                ), None)
                if not current_ban:
                    current_ban = sorted_bans[0]

            if current_ban:
                ban_reason_raw = str(current_ban.get('reason') or '').strip()
                ban_reason = (
                    "该用户的封禁原因被隐藏"
                    if not ban_reason_raw or _is_hidden_ban_reason(ban_reason_raw)
                    else self._translate_ban_reason(ban_reason_raw)
                )
                ban_expiration = current_ban.get('expiration') or banned_until_main

                body += f"🚫封禁原因: {ban_reason}\n"

                if _is_permanent_ban_expiry(ban_expiration):
                    body += "🚫封禁截止: 永久封禁\n"
                elif _is_hidden_ban_expiry(ban_expiration):
                    body += "🚫封禁截止: 该用户的封禁截止被隐藏\n"
                else:
                    body += f"🚫封禁截止: {_format_timestamp_to_beijing(ban_expiration)}\n"

            else:
                body += "🚫封禁原因: 该用户的封禁原因被隐藏\n"
                if _is_permanent_ban_expiry(banned_until_main):
                    body += "🚫封禁截止: 永久封禁\n"
                elif _is_hidden_ban_expiry(banned_until_main):
                    body += "🚫封禁截止: 该用户的封禁截止被隐藏\n"
                else:
                    body += f"🚫封禁截止: {_format_timestamp_to_beijing(banned_until_main)}\n"


        if online_status and online_status.get('online'):
            server_name = online_status.get('serverName', '未知服务器')

            raw_city = online_status.get('city', {}).get('name', '未知位置')
            raw_country = online_status.get('country', '')

            # 使用更准确的翻译函数
            country_cn, city_cn = await self._translate_country_city(raw_country, raw_city)

            def _strip_paren_text_q(s: Optional[str]) -> str:
                t = (s or "").strip()
                if not t:
                    return t
                t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
                t = re.sub(r"\s*（[^）]*）\s*", "", t).strip()
                return t

            display_country = _strip_paren_text_q(country_cn or "")
            display_city = _strip_paren_text_q(city_cn or "")
            if display_country and display_city:
                dc = display_country.strip()
                dcity = display_city.strip()
                if dcity == dc or dcity.startswith(dc):
                    location_display = dcity
                else:
                    location_display = f"{dc}-{dcity}"
            else:
                location_display = display_city or display_country or "未知位置"

            body += "📶在线状态: 在线\n"
            body += f"📶所在服务器: {server_name}\n"
            body += f"📶所在位置: {location_display}"
        else:
            body += "📶在线状态: 离线\n"
            if last_online_formatted:
                body += f"📶上次在线: {last_online_formatted}"

        # 头像（强制按组件发送）
        show_avatar_cfg = self._cfg_bool('query_show_avatar_enable', True)
        logger.info(f"查询详情: 头像开关={'ON' if show_avatar_cfg else 'OFF'}，将组合 Image+Plain 统一发送。")
        avatar_url = self._normalize_avatar_url(player_info.get('avatar') or stats_info.get('avatar_url'))
        logger.info(f"查询详情: 规范化后URL={avatar_url}")
        components = []
        # 发送顺序控制：当头像关闭时，将标题与正文合并为一个文本组件以保证换行在同一组件内生效
        if not show_avatar_cfg:
            logger.info("查询详情: 头像开关为OFF，直接发送正文文本组件")
            components.append(Plain(body))
            yield event.chain_result(components)
            return
        else:
            # 头像开启：头像 -> 空行 -> 正文
            if avatar_url:
                try:
                    logger.info("查询详情: 组合消息链添加 Image(URL) 组件")
                    components.append(Image.fromURL(avatar_url))
                except Exception:
                    logger.error("查询详情: 生成 Image(URL) 组件失败，跳过头像", exc_info=True)
            else:
                logger.info("查询详情: 无可用头像URL，跳过头像组件")
            components.append(Plain(body))
            yield event.chain_result(components)
            return
