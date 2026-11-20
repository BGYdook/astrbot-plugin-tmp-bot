"""Message routing and the command menu."""

import re

from .astrbot_compat import AstrMessageEvent
from .shared import command_text


class DispatcherMixin:
    _EXACT_COMMANDS = {
        "解绑": "tmpunbind",
        "dlc": "tmpdlc_list",
        "dlc列表": "tmpdlc_list",
        "地图dlc": "tmpdlc_list",
        "总里程排行": "tmprank_total",
        "今日里程排行": "tmprank_today",
        "服务器": "tmpserver",
        "美卡服务器": "tmpats_server",
        "时间": "tmpgametime",
        "今日活动": "tmptoday_events",
        "插件版本": "tmpversion",
        "菜单": "tmphelp",
    }
    _ARGUMENT_COMMANDS = (
        (re.compile(r"绑定\s*[0-9]*"), "tmpbind"),
        (re.compile(r"(?:查询|查)(?:\s*\d+)?"), "tmpquery"),
        (re.compile(r"定位(?:\s*\d+)?"), "tmplocate"),
        (re.compile(r"足迹(?:\s*\S+)?(?:\s*\d+)?"), "tmptoday_footprint"),
        (re.compile(r"查违规(?:\s*\d+)?"), "tmpviolations"),
        (re.compile(r"活动\s*\d+"), "tmpevent_detail"),
        (re.compile(r"vtc\s*\d+"), "tmpvtc_info"),
        (re.compile(r"路况(?:\s*\S+)?"), "tmptraffic"),
        (re.compile(r"历史车队(?:\s*\d+)?"), "tmpvtc_history"),
    )
    _MENTION_COMMANDS = {
        "查询": "tmpquery", "查": "tmpquery", "定位": "tmplocate",
        "足迹": "tmptoday_footprint", "查违规": "tmpviolations", "历史车队": "tmpvtc_history",
    }

    def _match_command(self, msg: str, event: AstrMessageEvent) -> str | None:
        if name := self._EXACT_COMMANDS.get(msg):
            return name
        for pattern, name in self._ARGUMENT_COMMANDS:
            if pattern.fullmatch(msg):
                return name
        prefix = msg.split(maxsplit=1)[0]
        if prefix in self._MENTION_COMMANDS and self._mentioned_user_id(event):
            return self._MENTION_COMMANDS[prefix]
        return None

    async def _run_command_once(self, event: AstrMessageEvent, results):
        """Run a command handler once when both AstrBot and the raw event hook see it."""
        if getattr(event, "_tmp_bot_command_handled", False):
            return
        event._tmp_bot_command_handled = True
        async for result in results:
            yield result

    async def _dispatch_message(self, event: AstrMessageEvent):
        if getattr(event, "_tmp_bot_command_handled", False):
            return
        msg = command_text(event).lower()
        if not msg:
            return

        handler = self._match_command(msg, event)
        show_usage = msg in {"活动", "vtc"}
        if not handler and not show_usage:
            return

        # The general event listener and AstrBot's command handler can both receive it.
        event._tmp_bot_command_handled = True
        if show_usage:
            yield event.plain_result("用法: 活动 [活动ID] 或 vtc [VTC ID]")
        elif handler == "tmpserver":
            async for result in self.tmpserver(event, game_filter="ets"):
                yield result
        else:
            async for result in getattr(self, handler)(event):
                yield result

    async def tmphelp(self, event: AstrMessageEvent):
        """[命令: 菜单] 显示本插件的命令使用说明。"""
        main_help = """TMP查询姬指令菜单 v2

可用命令:
1. 绑定 [TMP ID]
2. 查询 [TMP ID]
3. 定位 [TMP ID]
4. 路况[s1/s2/p/a]
5. 总里程排行
6. 今日里程排行
7. 足迹/ 足迹 [服务器简称] [TMP ID]
8. 服务器
9. 美卡服务器
10. 查违规 [TMP ID]
11. 时间(查询游戏时间)
12. 今日活动
13. 活动 [活动ID]
14. VTC [VTC ID]
15. 插件版本
16. 历史车队 [TMP ID]
使用提示: 绑定后可直接发送 查询/定位/足迹/查违规/历史车队，足迹可省略服务器
"""

        yield event.plain_result(main_help)
