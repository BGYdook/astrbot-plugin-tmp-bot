"""AstrBot plugin entry point and command registration."""

from .features.astrbot_compat import AstrMessageEvent, Star, filter, register
from .features.avatars import AvatarMixin
from .features.bindings import BindingMixin
from .features.dispatcher import DispatcherMixin
from .features.dlc import DlcMixin
from .features.events import EventsMixin
from .features.footprint import FootprintMixin
from .features.lifecycle import LifecycleMixin
from .features.location import LocationMixin
from .features.maps import MapMixin
from .features.player import PlayerMixin
from .features.ranking import RankingMixin
from .features.rendering import RenderingMixin
from .features.servers import ServersMixin
from .features.traffic import TrafficMixin
from .features.translation import TranslationMixin
from .features.updates import UpdateMixin
from .features.violations import ViolationsMixin
from .features.vtc import VtcMixin


@register("tmp-bot", "BGYdook", "欧卡2TMP查询插件", "2.0.0", "https://github.com/BGYdook/astrbot-plugin-tmp-bot")
class TmpBotPlugin(
    LifecycleMixin,
    AvatarMixin,
    BindingMixin,
    DispatcherMixin,
    DlcMixin,
    EventsMixin,
    FootprintMixin,
    LocationMixin,
    MapMixin,
    PlayerMixin,
    RankingMixin,
    RenderingMixin,
    ServersMixin,
    TrafficMixin,
    TranslationMixin,
    UpdateMixin,
    ViolationsMixin,
    VtcMixin,
    Star,
):
    """TruckersMP commands for AstrBot."""

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _on_any_message_dispatch(self, event: AstrMessageEvent):
        self._remember_tmp_update_group(event)
        async for result in self._dispatch_message(event):
            yield result

    @filter.command("绑定")
    async def cmd_tmp_bind(self, event: AstrMessageEvent, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpbind(event)):
            yield result

    @filter.command("解绑")
    async def cmd_tmp_unbind(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpunbind(event)):
            yield result

    @filter.command("查询")
    async def cmd_tmp_query(self, event: AstrMessageEvent, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpquery(event)):
            yield result

    @filter.command("查")
    async def cmd_tmp_query_alias(self, event: AstrMessageEvent, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpquery(event)):
            yield result

    @filter.command("定位")
    async def cmd_tmp_locate(self, event: AstrMessageEvent, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmplocate(event)):
            yield result

    @filter.command("路况")
    async def cmd_tmp_traffic(self, event: AstrMessageEvent, server: str | None = None):
        async for result in self._run_command_once(event, self.tmptraffic(event)):
            yield result

    @filter.command("总里程排行")
    async def cmd_tmp_rank_total(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmprank_total(event)):
            yield result

    @filter.command("今日里程排行")
    async def cmd_tmp_rank_today(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmprank_today(event)):
            yield result

    @filter.command("足迹")
    async def cmd_tmp_today_footprint(self, event: AstrMessageEvent, server: str | None = None, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmptoday_footprint(event)):
            yield result

    @filter.command("服务器")
    async def cmd_tmp_server(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpserver(event, game_filter="ets")):
            yield result

    @filter.command("美卡服务器")
    async def cmd_tmp_ats_server(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpats_server(event)):
            yield result

    @filter.command("查违规")
    async def cmd_tmp_violations(self, event: AstrMessageEvent, tmp_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpviolations(event)):
            yield result

    @filter.command("时间")
    async def cmd_tmp_game_time(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpgametime(event)):
            yield result

    @filter.command("今日活动")
    async def cmd_tmp_today_events(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmptoday_events(event)):
            yield result

    @filter.command("活动")
    async def cmd_tmp_event_detail(self, event: AstrMessageEvent, event_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpevent_detail(event)):
            yield result

    @filter.command("VTC")
    async def cmd_tmp_vtc_info(self, event: AstrMessageEvent, vtc_id: str | None = None):
        async for result in self._run_command_once(event, self.tmpvtc_info(event)):
            yield result

    @filter.command("插件版本")
    async def cmd_tmp_plugin_version(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpversion(event)):
            yield result

    @filter.command("DLC")
    async def cmd_tmp_dlc(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpdlc_list(event)):
            yield result

    @filter.command("DLC列表")
    async def cmd_tmp_dlc_list(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpdlc_list(event)):
            yield result

    @filter.command("地图DLC")
    async def cmd_tmp_dlc_alias(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpdlc_list(event)):
            yield result

    @filter.command("菜单")
    async def cmd_tmp_help(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmphelp(event)):
            yield result

    @filter.command("历史车队")
    async def cmd_tmp_vtc_history(self, event: AstrMessageEvent):
        async for result in self._run_command_once(event, self.tmpvtc_history(event)):
            yield result
