"""TruckersMP events and game time."""

import re
from datetime import timedelta
from typing import List, Dict, Any

from .astrbot_compat import AstrMessageEvent, logger
from .shared import (
    read_json,
    command_text,
    ApiResponseException,
    NetworkException,
    TMP_GAME_EPOCH,
    _format_timestamp_to_beijing,
)


class EventsMixin:
    async def _get_game_time(self) -> Dict[str, Any]:
        if not self.session:
            raise NetworkException("插件初始化中，请稍后重试")
        url = "https://api.truckersmp.com/v2/game_time"
        async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as response:
            if response.status != 200:
                raise ApiResponseException(f"API返回错误状态码: {response.status}")
            data = await read_json(response)
        if not isinstance(data, dict):
            raise ApiResponseException("游戏时间 API 返回格式异常")
        if data.get('error'):
            raise ApiResponseException(str(data.get('error')))
        payload = data.get('response') if isinstance(data.get('response'), dict) else data
        game_time = payload.get('game_time')
        if game_time is None:
            raise ApiResponseException("游戏时间 API 未返回 game_time")
        try:
            game_minutes = float(game_time)
        except (TypeError, ValueError):
            raise ApiResponseException("游戏时间 API 返回值无效")
        return {
            'game_time': game_minutes,
            'game_datetime': TMP_GAME_EPOCH + timedelta(minutes=game_minutes),
        }

    async def _get_tmp_api_json(self, path: str, resource_name: str) -> Any:
        if not self.session:
            raise NetworkException("插件初始化中，请稍后重试")
        url = f"https://api.truckersmp.com/v2/{path.lstrip('/')}"
        async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as response:
            if response.status == 404:
                raise ApiResponseException(f"{resource_name}不存在")
            if response.status != 200:
                raise ApiResponseException(f"API返回错误状态码: {response.status}")
            data = await read_json(response)
        if not isinstance(data, dict):
            raise ApiResponseException(f"{resource_name} API 返回格式异常")
        if data.get('error'):
            detail = data.get('message') or data.get('error')
            raise ApiResponseException(f"{resource_name}查询失败: {detail}")
        return data

    async def _get_today_events(self) -> List[Dict[str, Any]]:
        data = await self._get_tmp_api_json('events', '活动')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("活动 API 返回格式异常")
        today_events = response.get('today') or []
        if not isinstance(today_events, list):
            return []
        unique_events = []
        seen_ids = set()
        for event in today_events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get('id') or '').strip()
            if not event_id or event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            unique_events.append(event)
        return unique_events

    async def _get_event_detail(self, event_id: str) -> Dict[str, Any]:
        data = await self._get_tmp_api_json(f"events/{event_id}", '活动')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("活动 API 返回格式异常")
        return response

    async def tmpgametime(self, event: AstrMessageEvent):
        """[命令: 时间] 查询 TruckersMP 当前游戏时间。"""
        try:
            game_info = await self._get_game_time()
        except NetworkException as exc:
            yield event.plain_result(f"查询游戏时间失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询游戏时间失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询游戏时间失败: {exc}", exc_info=True)
            yield event.plain_result("查询游戏时间失败，请稍后重试")
            return

        game_datetime = game_info['game_datetime']
        message = f"当前游戏时间: {game_datetime:%H:%M}"
        yield event.plain_result(message)

    async def tmptoday_events(self, event: AstrMessageEvent):
        """[命令: 今日活动] 查询 TruckersMP 今日活动。"""
        try:
            today_events = await self._get_today_events()
        except NetworkException as exc:
            yield event.plain_result(f"查询今日活动失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询今日活动失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询今日活动失败: {exc}", exc_info=True)
            yield event.plain_result("查询今日活动失败，请稍后重试")
            return

        if not today_events:
            yield event.plain_result("今日无活动")
            return

        today_events.sort(key=lambda item: str(item.get('start_at') or ''))
        message = f"📅 今日活动（{len(today_events)}）"
        for index, item in enumerate(today_events, 1):
            game_name = str(item.get('game') or '未知')
            game_label = '欧卡2' if game_name == 'ETS2' else '美卡' if game_name == 'ATS' else game_name
            start_at = _format_timestamp_to_beijing(str(item.get('start_at') or ''))
            attendances = item.get('attendances') if isinstance(item.get('attendances'), dict) else {}
            confirmed = attendances.get('confirmed', 0)
            message += (
                f"\n\n{index}. {item.get('name') or '未命名活动'}"
                f"\n活动ID: {item.get('id') or '未知'} | {game_label}"
                f"\n开始时间: {start_at}"
                f"\n路线: {self._format_event_route(item)}"
                f"\n已确认参加: {confirmed} 人"
            )
        yield event.plain_result(message)

    async def tmpevent_detail(self, event: AstrMessageEvent):
        """[命令: 活动] 按活动 ID 查询 TruckersMP 活动详情。"""
        match = re.search(r'活动\s*(\d+)', command_text(event))
        if not match:
            yield event.plain_result("用法: 活动 [活动ID]")
            return
        event_id = match.group(1)
        try:
            detail = await self._get_event_detail(event_id)
        except NetworkException as exc:
            yield event.plain_result(f"查询活动失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询活动失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询活动 {event_id} 失败: {exc}", exc_info=True)
            yield event.plain_result("查询活动失败，请稍后重试")
            return

        event_type = detail.get('event_type') if isinstance(detail.get('event_type'), dict) else {}
        server = detail.get('server') if isinstance(detail.get('server'), dict) else {}
        user = detail.get('user') if isinstance(detail.get('user'), dict) else {}
        vtc = detail.get('vtc') if isinstance(detail.get('vtc'), dict) else {}
        attendances = detail.get('attendances') if isinstance(detail.get('attendances'), dict) else {}
        game_name = str(detail.get('game') or '未知')
        game_label = '欧卡2' if game_name == 'ETS2' else '美卡' if game_name == 'ATS' else game_name

        message = f"活动名称: {detail.get('name') or '未命名活动'}\n"
        message += f"活动 ID: {detail.get('id') or event_id}\n"
        message += f"活动类型: {self._translate_event_type(event_type)}\n"
        message += f"游戏: {game_label}\n"
        server_name = str(server.get('name') or '').strip()
        if server_name.lower() == 'to be determined':
            server_name = '待定'
        message += f"服务器: {server_name or '待定'}\n"
        message += f"语言: {self._translate_language(detail.get('language'))}\n"
        message += f"集合时间: {_format_timestamp_to_beijing(str(detail.get('meetup_at') or ''))}\n"
        message += f"开始时间: {_format_timestamp_to_beijing(str(detail.get('start_at') or ''))}\n"
        message += f"路线: {self._format_event_route(detail)}\n"
        if user.get('username'):
            message += f"主办玩家: {user.get('username')}"
            if user.get('id'):
                message += f" (ID: {user.get('id')})"
            message += "\n"
        if vtc.get('name'):
            message += f"主办车队: {vtc.get('name')}"
            if vtc.get('id'):
                message += f" (VTC ID: {vtc.get('id')})"
            message += "\n"
        message += (
            "参加情况: "
            f"已确认 {attendances.get('confirmed', 0)} 人"
            f" | 待定 {attendances.get('unsure', 0)} 人"
            f" | 车队 {attendances.get('vtcs', 0)} 个\n"
        )

        description = self._clean_tmp_text(detail.get('description'), limit=1200)
        rules = self._clean_tmp_text(detail.get('rule'), limit=1200)
        if description:
            message += f"\n活动简介:\n{description}\n"
        if rules:
            message += f"\n活动规则:\n{rules}\n"
        if detail.get('external_link'):
            message += f"\n活动链接: {detail.get('external_link')}"
        yield event.plain_result(message.rstrip())
