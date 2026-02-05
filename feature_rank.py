"""
里程排行功能
"""

from typing import Any, Dict, List, Optional


async def tmprank_total(self, event, Image, rank_template, NetworkException, ApiResponseException):
    try:
        rank_list = await self._get_rank_list(ranking_type="total", limit=10)
    except NetworkException as e:
        yield event.plain_result(f"查询排行榜失败: {str(e)}")
        return
    except ApiResponseException:
        yield event.plain_result("查询排行榜失败: API返回数据异常。")
        return
    except Exception:
        yield event.plain_result("查询排行榜时发生未知错误。")
        return

    if not rank_list:
        yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
        return

    message = "🏆 TruckersMP 玩家总里程排行榜 (前10名)\n"
    message += "=" * 35 + "\n"
    items: List[Dict[str, Any]] = []
    me_data: Optional[Dict[str, Any]] = None

    me_user_id = event.get_sender_id()
    me_tmp_id = None
    me_name = None
    me_total_km = None
    me_total_rank = None
    me_vtc_role = None
    try:
        bindings = self._load_bindings()
        b = bindings.get(me_user_id)
        if isinstance(b, dict):
            me_tmp_id = b.get("tmp_id")
            me_name = b.get("player_name")
        else:
            me_tmp_id = b
    except Exception:
        me_tmp_id = None

    if me_tmp_id:
        try:
            stats = await self._get_player_stats(str(me_tmp_id))
            me_total_km = stats.get("total_km")
            me_total_rank = stats.get("total_rank")
            me_vtc_role = stats.get("vtcRole")
            if isinstance(me_total_km, (int, float)):
                km_str = f"{float(me_total_km):,.2f}".replace(",", " ")
                display_name = (str(me_name).strip() if me_name is not None else "") or "你"
                message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                message += f"里程: {km_str} km"
                if me_total_rank is not None:
                    message += f" | 排名: No.{me_total_rank}"
                message += "\n"
                if me_vtc_role:
                    message += f"车队职位: {str(me_vtc_role).strip()}\n"
                message += "-" * 35 + "\n"
                me_data = {
                    "name": display_name,
                    "tmp_id": me_tmp_id,
                    "rank": me_total_rank,
                    "km": float(me_total_km),
                    "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                }
        except Exception:
            pass

    for idx, player in enumerate(rank_list):
        rank = player.get("ranking", idx + 1)
        raw_name = (
            player.get("tmpName")
            or player.get("name")
            or player.get("tmp_name")
            or player.get("nickName")
            or player.get("nickname")
        )
        name = str(raw_name).strip() if raw_name is not None else ""
        if not name:
            name = "未知玩家"
        distance_m = player.get("mileage") or player.get("distance") or 0

        distance_km = int(distance_m / 1000) if isinstance(distance_m, (int, float)) else 0
        distance_str = f"{distance_km:,}".replace(",", " ")
        tmp_id = player.get("tmpId", "N/A")

        line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
        line += f"       {distance_str} km\n"
        message += line

        items.append({"rank": rank, "name": name, "km": distance_km, "tmp_id": tmp_id})

    message += "=" * 35 + "\n"

    rank_tmpl = rank_template()

    try:
        options = {"type": "jpeg", "quality": 92, "full_page": True, "omit_background": False}
        url = await self.html_render(rank_tmpl, {"title": "- 总行驶里程排行榜 -", "items": items, "me": me_data}, options=options)
        if isinstance(url, str) and url:
            yield event.chain_result([Image.fromURL(url)])
            return
    except Exception:
        pass

    img = await self._render_text_to_image(message)
    if isinstance(img, (bytes, bytearray)):
        yield event.chain_result([Image.fromBytes(img)])
        return
    if isinstance(img, str) and img.startswith("http"):
        yield event.chain_result([Image.fromURL(img)])
        return
    yield event.plain_result(message)


async def tmprank_today(self, event, Image, rank_template, NetworkException, ApiResponseException):
    try:
        rank_list = await self._get_rank_list(ranking_type="today", limit=10)
    except NetworkException as e:
        yield event.plain_result(f"查询排行榜失败: {str(e)}")
        return
    except ApiResponseException:
        yield event.plain_result("查询排行榜失败: API返回数据异常。")
        return
    except Exception:
        yield event.plain_result("查询排行榜时发生未知错误。")
        return

    if not rank_list:
        yield event.plain_result("当前无法获取排行榜数据或排行榜为空。")
        return

    message = "🏁 TruckersMP 玩家今日里程排行榜 (前10名)\n"
    message += "=" * 35 + "\n"
    items: List[Dict[str, Any]] = []
    me_data: Optional[Dict[str, Any]] = None

    me_user_id = event.get_sender_id()
    me_tmp_id = None
    me_name = None
    me_daily_km = None
    me_daily_rank = None
    me_vtc_role = None
    try:
        bindings = self._load_bindings()
        b = bindings.get(me_user_id)
        if isinstance(b, dict):
            me_tmp_id = b.get("tmp_id")
            me_name = b.get("player_name")
        else:
            me_tmp_id = b
    except Exception:
        me_tmp_id = None

    if me_tmp_id:
        try:
            stats = await self._get_player_stats(str(me_tmp_id))
            me_daily_km = stats.get("daily_km")
            me_daily_rank = stats.get("daily_rank")
            me_vtc_role = stats.get("vtcRole")
            if isinstance(me_daily_km, (int, float)):
                km_str = f"{float(me_daily_km):,.2f}".replace(",", " ")
                display_name = (str(me_name).strip() if me_name is not None else "") or "你"
                message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                message += f"里程: {km_str} km"
                if me_daily_rank is not None:
                    message += f" | 排名: No.{me_daily_rank}"
                message += "\n"
                if me_vtc_role:
                    message += f"车队职位: {str(me_vtc_role).strip()}\n"
                message += "-" * 35 + "\n"
                me_data = {
                    "name": display_name,
                    "tmp_id": me_tmp_id,
                    "rank": me_daily_rank,
                    "km": float(me_daily_km),
                    "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                }
        except Exception:
            pass

    for idx, player in enumerate(rank_list):
        rank = player.get("ranking", idx + 1)
        raw_name = (
            player.get("tmpName")
            or player.get("name")
            or player.get("tmp_name")
            or player.get("nickName")
            or player.get("nickname")
        )
        name = str(raw_name).strip() if raw_name is not None else ""
        if not name:
            name = "未知玩家"
        distance_m = player.get("mileage") or player.get("distance") or 0

        distance_km = int(distance_m / 1000) if isinstance(distance_m, (int, float)) else 0
        distance_str = f"{distance_km:,}".replace(",", " ")
        tmp_id = player.get("tmpId", "N/A")

        line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
        line += f"       {distance_str} km\n"
        message += line

        items.append({"rank": rank, "name": name, "km": distance_km, "tmp_id": tmp_id})

    message += "=" * 35 + "\n"

    rank_tmpl = rank_template()

    try:
        options = {"type": "jpeg", "quality": 92, "full_page": True, "omit_background": False}
        url = await self.html_render(rank_tmpl, {"title": "- 今日行驶里程排行榜 -", "items": items, "me": me_data}, options=options)
        if isinstance(url, str) and url:
            yield event.chain_result([Image.fromURL(url)])
            return
    except Exception:
        pass

    img = await self._render_text_to_image(message)
    if isinstance(img, (bytes, bytearray)):
        yield event.chain_result([Image.fromBytes(img)])
        return
    if isinstance(img, str) and img.startswith("http"):
        yield event.chain_result([Image.fromURL(img)])
        return
    yield event.plain_result(message)
