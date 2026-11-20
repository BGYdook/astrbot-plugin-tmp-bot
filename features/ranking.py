"""Mileage rankings."""

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from .astrbot_compat import AstrMessageEvent, Image, logger
from .shared import read_json
from .shared import ApiResponseException, NetworkException
from ..render.templates import RANK_IMAGE_TEMPLATE


class RankingMixin:
    async def _get_rank_list(self, ranking_type: str = "total", limit: int = 10) -> Optional[List[Dict]]:
        """获取 TruckersMP 里程排行榜列表 (使用第三方 VTCM API)。

        ranking_type:
            - "total": 总里程排行
            - "today": 今日里程排行

        API 源取自 `_api_bases()`（用户自定义源优先，内置源兜底）。
        """
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        # 第三方接口使用数字枚举：1=总里程，2=今日里程
        type_code = 2 if str(ranking_type).lower() in ["today", "daily", "2"] else 1

        last_error: Optional[Exception] = None
        for base in self._api_bases():
            url = f"{base}/statistics/mileageRankingList?rankingType={type_code}&rankingCount={limit}"
            logger.info(f"尝试 API (排行榜): type={ranking_type}({type_code}), url={url}")
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await read_json(response)
                        if isinstance(data, list):
                            response_data = data
                        elif isinstance(data, dict):
                            code = data.get('code')
                            try:
                                code_ok = code is None or int(code) == 200
                            except (TypeError, ValueError):
                                code_ok = False
                            payload = data.get('data')
                            response_data = payload if code_ok else None
                        else:
                            response_data = None
                        if isinstance(response_data, list):
                            if response_data:
                                return response_data
                            last_error = ApiResponseException(f"排行榜 API 暂无数据: {base}")
                            logger.info(f"排行榜 API 源 {base} 返回空列表，尝试下一个源")
                            continue
                        raise ApiResponseException("排行榜 API 数据结构异常")

                    elif response.status == 404:
                        logger.info(f"排行榜 API 源 {base} 不存在该接口，尝试下一个源")
                        last_error = ApiResponseException(f"排行榜 API 源不支持: {base}")
                    else:
                        logger.info(f"排行榜 API 源 {base} 返回状态码 {response.status}，尝试下一个源")
                        last_error = ApiResponseException(f"排行榜 API 返回错误状态码: {response.status}")
            except aiohttp.ClientError as e:
                logger.error(f"排行榜 API 网络请求失败 ({base}, aiohttp.ClientError): {e}")
                last_error = NetworkException("排行榜 API 网络请求失败")
            except asyncio.TimeoutError:
                logger.error(f"请求排行榜 API 超时 ({base})")
                last_error = NetworkException("请求排行榜 API 超时")
            except ApiResponseException as e:
                last_error = e
            except Exception as e:
                logger.error(f"查询排行榜时发生未知错误 ({base}): {e}", exc_info=True)
                last_error = NetworkException("查询排行榜失败")

        if isinstance(last_error, NetworkException):
            raise last_error
        if isinstance(last_error, ApiResponseException):
            raise last_error
        raise NetworkException("排行榜 API 网络请求失败")

    async def tmprank_total(self, event: AstrMessageEvent):
        """查询总里程排行榜。"""
        async for result in self._show_rank(event, "total"):
            yield result

    async def tmprank_today(self, event: AstrMessageEvent):
        """查询今日里程排行榜。"""
        async for result in self._show_rank(event, "today"):
            yield result

    async def _show_rank(self, event: AstrMessageEvent, ranking_type: str):
        is_today = ranking_type == "today"
        if is_today:
            icon, title = "🏁", "今日里程排行榜"
            subtitle, scope = "TODAY · RESET 00:00", "每日 0 点重置"
            stats_prefix = "daily"
        else:
            icon, title = "🏆", "总里程排行榜"
            subtitle, scope = "ALL-TIME MILEAGE", "累计里程"
            stats_prefix = "total"

        try:
            rank_list = await self._get_rank_list(ranking_type=ranking_type, limit=10)
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

        message = f"{icon} TruckersMP 玩家{title} (前10名)\n"
        message += "=" * 35 + "\n"
        items: List[Dict[str, Any]] = []
        me_data: Optional[Dict[str, Any]] = None

        me_user_id = event.get_sender_id()
        me_tmp_id = None
        me_name = None
        me_km = None
        me_rank = None
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
                me_km = stats.get(f"{stats_prefix}_km")
                me_rank = stats.get(f"{stats_prefix}_rank")
                me_vtc_role = stats.get("vtcRole")
                if isinstance(me_km, (int, float)):
                    km_str = f"{float(me_km):,.2f}".replace(",", " ")
                    display_name = (str(me_name).strip() if me_name is not None else "") or "你"
                    message += f"🙋 个人信息: {display_name} (ID:{me_tmp_id})\n"
                    message += f"里程: {km_str} km"
                    if me_rank is not None:
                        message += f" | 排名: No.{me_rank}"
                    message += "\n"
                    if me_vtc_role:
                        message += f"车队职位: {str(me_vtc_role).strip()}\n"
                    message += "-" * 35 + "\n"
                    me_data = {
                        "name": display_name,
                        "tmp_id": me_tmp_id,
                        "rank": me_rank,
                        "km": float(me_km),
                        "km_text": km_str.removesuffix(".00"),
                        "vtc_role": (str(me_vtc_role).strip() if me_vtc_role else ""),
                    }
            except (NetworkException, ApiResponseException, TypeError, ValueError, AttributeError):
                logger.debug("排行榜个人信息不可用，仍显示榜单")

        for idx, player in enumerate(rank_list):
            try:
                rank = int(player.get('ranking', idx + 1))
            except (TypeError, ValueError):
                rank = idx + 1
            raw_name = (
                player.get('tmpName')
                or player.get('name')
                or player.get('tmp_name')
                or player.get('nickName')
                or player.get('nickname')
            )
            name = str(raw_name).strip() if raw_name is not None else ''
            if not name:
                name = '未知玩家'
            distance_raw = player.get('mileage') or player.get('distance') or 0
            try:
                distance_km = int(float(distance_raw) / 1000)
            except (TypeError, ValueError, OverflowError):
                distance_km = 0
            distance_str = f"{distance_km:,}".replace(',', ' ')
            tmp_id = player.get('tmpId', 'N/A')

            line = f"No.{rank:<2} | {name} (ID:{tmp_id})\n"
            line += f"       {distance_str} km\n"
            message += line

            items.append({
                'rank': rank,
                'name': name,
                'km': distance_km,
                'km_text': distance_str,
                'tmp_id': tmp_id,
            })

        message += "=" * 35 + "\n"

        rank_tmpl = RANK_IMAGE_TEMPLATE

        try:
            options = { 'type': 'jpeg', 'quality': 96, 'full_page': True, 'omit_background': False }
            url = await self.html_render(rank_tmpl, {
                'title': title,
                'subtitle': subtitle,
                'scope': scope,
                'is_today': is_today,
                'items': items,
                'me': me_data,
            }, options=options)
            if isinstance(url, str) and url:
                yield event.chain_result([Image.fromURL(url)])
                return
        except Exception as exc:
            logger.warning(f"排行榜图片渲染失败，回退为文本: {exc}")

        img = await self._render_text_to_image(message)
        if isinstance(img, (bytes, bytearray)):
            yield event.chain_result([Image.fromBytes(img)])
            return
        if isinstance(img, str) and img.startswith('http'):
            yield event.chain_result([Image.fromURL(img)])
            return
        yield event.plain_result(message)
