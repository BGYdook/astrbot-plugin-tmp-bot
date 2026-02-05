import re
import sys

from . import feature_bind
from . import feature_dlc
from . import feature_footprint
from . import feature_help
from . import feature_locate
from . import feature_query
from . import feature_rank
from . import feature_server
from . import feature_traffic

try:
    from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
except ImportError:
    class _DummyFilter:
        class EventMessageType:
            ALL = "ALL"

        def command(self, pattern, **kwargs):
            def decorator(func):
                return func
            return decorator

        def event_message_type(self, _type, **kwargs):
            def decorator(func):
                return func
            return decorator

    filter = _DummyFilter()

    class AstrMessageEvent:
        def __init__(self, message_str: str = "", sender_id: str = "0", match=None):
            self.message_str = message_str
            self._sender_id = sender_id
            self._match = match

        def get_sender_id(self) -> str:
            return self._sender_id

        async def plain_result(self, msg):
            return msg

        async def chain_result(self, components):
            return components

    class MessageEventResult:
        pass


class FeatureHandlersMixin:
    def _mod(self):
        return sys.modules[self.__class__.__module__]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _on_any_message_dispatch(self, event: AstrMessageEvent, *args, **kwargs):
        target_event = event
        if not hasattr(target_event, "message_str"):
            if args:
                candidate = args[0]
                if hasattr(candidate, "message_str") or hasattr(candidate, "message_obj"):
                    target_event = candidate
            if target_event is event:
                kw_event = kwargs.get("event")
                if hasattr(kw_event, "message_str") or hasattr(kw_event, "message_obj"):
                    target_event = kw_event

        msg = (getattr(target_event, "message_str", "") or "").strip()
        if not msg:
            return

        message_obj = getattr(target_event, "message_obj", None)
        has_at = False
        if message_obj is not None:
            try:
                chain = getattr(message_obj, "message", None) or []
                for seg in chain:
                    seg_type = getattr(seg, "type", None)
                    if isinstance(seg, dict):
                        seg_type = seg.get("type") or seg_type
                    if isinstance(seg_type, str) and seg_type.lower() == "at":
                        has_at = True
                        break
                    uid = (
                        getattr(seg, "qq", None)
                        or getattr(seg, "user_id", None)
                        or getattr(seg, "id", None)
                    )
                    if isinstance(seg, dict):
                        uid = seg.get("qq") or seg.get("user_id") or seg.get("id") or uid
                    if uid is not None:
                        has_at = True
                        break
            except Exception:
                has_at = False

        if re.match(r"^(查询|查)(\s*\d+)?\s*$", msg) or (re.match(r"^(查询|查)(\s|$)", msg) and has_at):
            async for r in self.tmpquery(event):
                yield r
            return
        if msg == "地图dlc" or msg == "地图DLC":
            async for r in self.tmpdlc_list(event):
                yield r
            return
        if re.match(r"^绑定\s*\d+\s*$", msg):
            async for r in self.tmpbind(event):
                yield r
            return
        if re.match(r"^解绑\s*$", msg):
            async for r in self.tmpunbind(event):
                yield r
            return
        if re.match(r"^定位(\s*\d+)?\s*$", msg) or (msg.startswith("定位") and has_at):
            async for r in self.tmplocate(event):
                yield r
            return
        if re.match(r"^总里程排行\s*$", msg):
            async for r in self.tmprank_total(event):
                yield r
            return
        if re.match(r"^今日里程排行\s*$", msg):
            async for r in self.tmprank_today(event):
                yield r
            return
        if re.match(r"^足迹(\s+\S+)?(\s+\d+)?\s*$", msg) or (msg.startswith("足迹") and has_at):
            async for r in self.tmptoday_footprint(event):
                yield r
            return
        if re.match(r"^服务器\s*$", msg):
            async for r in self.tmpserver(event):
                yield r
            return
        if re.match(r"^路况(\s+\S+)?\s*$", msg):
            async for r in self.tmptraffic(event):
                yield r
            return
        if re.match(r"^插件版本\s*$", msg):
            async for r in self.tmpversion(event):
                yield r
            return
        if re.match(r"^菜单\s*$", msg):
            async for r in self.tmphelp(event):
                yield r
            return

    @filter.command("查询")
    async def cmd_tmp_query(self, event: AstrMessageEvent, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if tmp_id:
                event.message_str = f"查询 {tmp_id}"
            else:
                event.message_str = "查询"
            async for r in self.tmpquery(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("查")
    async def cmd_tmp_query_alias(self, event: AstrMessageEvent, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if not tmp_id and orig:
                m = re.match(r"^查\s*(\d+)\s*$", orig.strip())
                if m:
                    tmp_id = m.group(1)
            if tmp_id:
                event.message_str = f"查询 {tmp_id}"
            else:
                event.message_str = "查询"
            async for r in self.tmpquery(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("定位")
    async def cmd_tmp_locate(self, event: AstrMessageEvent, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if tmp_id:
                event.message_str = f"定位 {tmp_id}"
            else:
                event.message_str = "定位"
            async for r in self.tmplocate(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("路况")
    async def cmd_tmp_traffic(self, event: AstrMessageEvent, server: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if server:
                event.message_str = f"路况 {server}"
            else:
                event.message_str = "路况"
            async for r in self.tmptraffic(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("总里程排行")
    async def cmd_tmp_rank_total(self, event: AstrMessageEvent):
        async for r in self.tmprank_total(event):
            yield r

    @filter.command("今日里程排行")
    async def cmd_tmp_rank_today(self, event: AstrMessageEvent):
        async for r in self.tmprank_today(event):
            yield r

    @filter.command("足迹")
    async def cmd_tmp_today_footprint(self, event: AstrMessageEvent, server: str | None = None, tmp_id: str | None = None):
        orig = getattr(event, "message_str", "") or ""
        try:
            if server and tmp_id:
                event.message_str = f"足迹 {server} {tmp_id}"
            elif server:
                event.message_str = f"足迹 {server}"
            elif tmp_id:
                event.message_str = f"足迹 {tmp_id}"
            else:
                event.message_str = "足迹"
            async for r in self.tmptoday_footprint(event):
                yield r
        finally:
            try:
                event.message_str = orig
            except Exception:
                pass

    @filter.command("服务器")
    async def cmd_tmp_server(self, event: AstrMessageEvent):
        async for r in self.tmpserver(event):
            yield r

    @filter.command("插件版本")
    async def cmd_tmp_plugin_version(self, event: AstrMessageEvent):
        async for r in self.tmpversion(event):
            yield r

    @filter.command("菜单")
    async def cmd_tmp_help(self, event: AstrMessageEvent):
        async for r in self.tmphelp(event):
            yield r

    async def tmpquery(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_query.tmpquery(
            self,
            event,
            m.logger,
            m.Image,
            m.Plain,
            m._format_timestamp_to_readable,
            m._format_timestamp_to_beijing,
            m._translate_user_groups,
            m.PlayerNotFoundException,
            m.SteamIdNotFoundException,
            m.NetworkException,
        ):
            yield r

    async def tmpdlc_list(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_dlc.tmpdlc_list(self, event, m.logger, m.Image, m.dlc_list_template):
            yield r

    async def tmpdlc_map_alias(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_dlc.tmpdlc_map_alias(self, event, m.logger, m.Image, m.dlc_list_template):
            yield r

    async def tmptoday_footprint(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_footprint.tmptoday_footprint(
            self,
            event,
            m.logger,
            m.Image,
            m.footprint_map_template,
            m._format_timestamp_to_readable,
            m.PROMODS_SERVER_IDS,
            m.PlayerNotFoundException,
            m.SteamIdNotFoundException,
            m.NetworkException,
        ):
            yield r

    async def tmpbind(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_bind.tmpbind(self, event, m.PlayerNotFoundException, m.SteamIdNotFoundException):
            yield r

    async def tmpunbind(self, event: AstrMessageEvent):
        async for r in feature_bind.tmpunbind(self, event):
            yield r

    async def tmplocate(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_locate.tmplocate(
            self,
            event,
            m.logger,
            m.Image,
            m.locate_map_template,
            m.PlayerNotFoundException,
            m.SteamIdNotFoundException,
            m.NetworkException,
        ):
            yield r

    async def tmprank_total(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_rank.tmprank_total(self, event, m.Image, m.rank_template, m.NetworkException, m.ApiResponseException):
            yield r

    async def tmprank_today(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_rank.tmprank_today(self, event, m.Image, m.rank_template, m.NetworkException, m.ApiResponseException):
            yield r

    async def tmptraffic(self, event: AstrMessageEvent):
        m = self._mod()
        async for r in feature_traffic.tmptraffic(self, event, m.NetworkException, m.ApiResponseException):
            yield r

    async def tmpserver(self, event: AstrMessageEvent):
        async for r in feature_server.tmpserver(self, event):
            yield r

    async def tmpversion(self, event: AstrMessageEvent):
        async for r in feature_server.tmpversion(self, event):
            yield r

    async def tmphelp(self, event: AstrMessageEvent):
        async for r in feature_help.tmphelp(self, event):
            yield r
