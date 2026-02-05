"""
查询功能
"""

import asyncio
import re
from typing import Any, Dict, List, Optional


async def tmpquery(
    self,
    event,
    logger,
    Image,
    Plain,
    _format_timestamp_to_readable,
    _format_timestamp_to_beijing,
    _translate_user_groups,
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

    match = re.search(r"查询\s*(\d+)", message_str)
    input_id = match.group(1) if match else None

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
        player_info_raw, bans_info, online_status, stats_info = await asyncio.gather(
            self._get_player_info(tmp_id),
            self._get_player_bans(tmp_id),
            self._get_online_status(tmp_id),
            self._get_player_stats(tmp_id),
        )
        player_info = player_info_raw
    except PlayerNotFoundException as e:
        yield event.plain_result(str(e))
        return
    except Exception as e:
        yield event.plain_result(f"查询失败: {str(e)}")
        return

    steam_id_to_display = self._get_steam_id_from_player_info(player_info)
    is_banned = player_info.get("banned", False)
    banned_until_main = player_info.get("bannedUntil", "永久/未知")

    ban_count, sorted_bans = self._format_ban_info(bans_info)
    bans_count_raw = player_info.get("bansCount")
    if bans_count_raw is not None:
        try:
            ban_count = int(str(bans_count_raw).strip())
        except Exception:
            pass

    last_online_raw = (
        player_info.get("lastOnline")
        or stats_info.get("last_online")
        or stats_info.get("lastOnline")
        or stats_info.get("lastLogin")
        or stats_info.get("last_login")
        or None
    )
    if last_online_raw and last_online_raw != player_info.get("lastOnline"):
        logger.info(f"查询详情: 使用 VTCM 提供的上次在线字段，值={last_online_raw}")
    last_online_formatted = _format_timestamp_to_readable(last_online_raw)

    body = ""
    body += f"🆔 TMP ID: {tmp_id}\n"
    if steam_id_to_display:
        body += f"🆔 Steam ID: {steam_id_to_display}\n"
    body += f"😀玩家名称: {player_info.get('name', '未知')}\n"
    join_date_raw = (
        player_info.get("joinDate")
        or player_info.get("created_at")
        or player_info.get("registrationDate")
        or None
    )
    join_date_formatted = _format_timestamp_to_beijing(join_date_raw) if join_date_raw else "未知"
    body += f"📑注册日期: {join_date_formatted}\n"

    perms_str = "玩家"
    if player_info.get("permissions"):
        perms = player_info["permissions"]
        if isinstance(perms, dict):
            groups = [g for g in ["Staff", "Management", "Game Admin"] if perms.get(f"is{g.replace(' ', '')}")]
            if groups:
                perms_str = ", ".join(_translate_user_groups(groups))
        elif isinstance(perms, list) and perms:
            perms_str = ", ".join(_translate_user_groups(perms))
    body += f"💼所属分组: {perms_str}\n"

    vtc = player_info.get("vtc") if isinstance(player_info.get("vtc"), dict) else {}
    vtc_name = vtc.get("name")
    vtc_role = vtc.get("role") or vtc.get("position") or stats_info.get("vtcRole")
    if vtc_name:
        body += f"🚚所属车队: {vtc_name}\n"
    if not vtc_role and vtc_name:
        try:
            vtc_role_remote = await self._get_vtc_member_role(tmp_id, vtc)
            if vtc_role_remote:
                vtc_role = vtc_role_remote
                logger.info(f"查询详情: 从 VTC API 获取到车队角色: {vtc_role}")
        except Exception as e:
            logger.info(f"查询详情: 获取 VTC 车队角色时发生异常: {e}", exc_info=False)
    if vtc_role:
        body += f"🚚车队职位: {vtc_role}\n"

    def _get_nested(d: Dict, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    is_patron = any(
        [
            bool(player_info.get("isPatron")),
            bool(player_info.get("isPatreon")),
            bool(_get_nested(player_info, "patreon", "isPatron")),
            bool(_get_nested(player_info, "patreon", "isPatreon")),
            bool(_get_nested(player_info, "patron", "isPatron")),
            bool(_get_nested(player_info, "patron", "isPatreon")),
        ]
    )

    active = (
        any(
            [
                bool(player_info.get("active")),
                bool(_get_nested(player_info, "patreon", "active")),
                bool(_get_nested(player_info, "patron", "active")),
                bool(_get_nested(player_info, "donation", "active")),
            ]
        )
        if is_patron
        else False
    )

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

    current_pledge_raw = (
        _get_nested(player_info, "patreon", "currentPledge")
        or player_info.get("currentPledge")
        or _get_nested(player_info, "patron", "currentPledge")
        or _get_nested(player_info, "donation", "currentPledge")
        or 0
    )
    lifetime_pledge_raw = (
        _get_nested(player_info, "patreon", "lifetimePledge")
        or player_info.get("lifetimePledge")
        or _get_nested(player_info, "patron", "lifetimePledge")
        or _get_nested(player_info, "donation", "lifetimePledge")
        or 0
    )

    current_pledge = (_to_int(current_pledge_raw) // 100) if is_patron else 0
    lifetime_pledge = (_to_int(lifetime_pledge_raw) // 100) if is_patron else 0

    if is_patron and lifetime_pledge > 0:
        if current_pledge > 0:
            body += f"🎁当前赞助金额: {current_pledge}美元\n"
        body += f"🎁历史赞助金额: {lifetime_pledge}美元\n"

    logger.info(
        f"查询详情: 里程字典 keys={list(stats_info.keys())}, debug={stats_info.get('debug_error')}"
    )
    total_km = stats_info.get("total_km", 0.0)
    daily_km = stats_info.get("daily_km", 0.0)
    total_rank = stats_info.get("total_rank")
    daily_rank = stats_info.get("daily_rank")
    logger.info(
        f"查询详情: 里程输出值 total_km={total_km:.2f}, daily_km={daily_km:.2f}, total_rank={total_rank}, daily_rank={daily_rank}"
    )

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

    body += f"🚫是否封禁: {'是' if is_banned else '否'}\n"
    body += f"🚫历史封禁: {ban_count}次\n"

    if is_banned:
        current_ban = None
        if sorted_bans:
            current_ban = next((ban for ban in sorted_bans if ban.get("active")), None)
            if not current_ban:
                current_ban = sorted_bans[0]

        if current_ban:
            ban_reason_raw = current_ban.get("reason", "未知封禁原因 (API V2)")
            ban_reason = self._translate_ban_reason(ban_reason_raw)
            ban_expiration = current_ban.get("expiration", banned_until_main)

            body += f"🚫封禁原因: {ban_reason}\n"

            if (
                ban_expiration
                and isinstance(ban_expiration, str)
                and ban_expiration.lower().startswith("never")
            ):
                body += "🚫封禁截止: 永久封禁\n"
            else:
                body += f"🚫封禁截止: {_format_timestamp_to_beijing(ban_expiration)}\n"
        else:
            body += "🚫封禁原因: 隐藏\n"
            if (
                banned_until_main
                and isinstance(banned_until_main, str)
                and banned_until_main.lower().startswith("never")
            ):
                body += "🚫封禁截止: 永久封禁\n"
            else:
                body += f"🚫封禁截止: {_format_timestamp_to_beijing(banned_until_main)}\n"

    if online_status and online_status.get("online"):
        server_name = online_status.get("serverName", "未知服务器")
        raw_city = online_status.get("city", {}).get("name", "未知位置")
        raw_country = online_status.get("country", "")
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
        body += f"📶所在位置: {location_display}\n"
    else:
        body += "📶在线状态: 离线\n"
        body += f"📶上次在线: {last_online_formatted}\n"

    show_avatar_cfg = self._cfg_bool("query_show_avatar_enable", True)
    logger.info(
        f"查询详情: 头像开关={'ON' if show_avatar_cfg else 'OFF'}，将组合 Image+Plain 统一发送。"
    )
    avatar_url = self._normalize_avatar_url(player_info.get("avatar") or stats_info.get("avatar_url"))
    logger.info(f"查询详情: 规范化后URL={avatar_url}")
    components = []
    if not show_avatar_cfg:
        logger.info("查询详情: 头像开关为OFF，直接发送正文文本组件")
        components.append(Plain(body))
        yield event.chain_result(components)
        return
    else:
        if avatar_url:
            try:
                logger.info("查询详情: 组合消息链添加 Image(URL) 组件")
                components.append(Image.fromURL(avatar_url))
            except Exception:
                logger.error("查询详情: 生成 Image(URL) 组件失败，跳过头像", exc_info=True)
        else:
            logger.info("查询详情: 无可用头像URL，跳过头像组件")
        components.append(Plain("\r\n"))
        components.append(Plain(body))
        yield event.chain_result(components)
        return
