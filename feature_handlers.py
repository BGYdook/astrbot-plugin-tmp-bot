import re


async def on_any_message_dispatch(self, event, *args, **kwargs):
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


async def cmd_tmp_query(self, event, tmp_id=None):
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


async def cmd_tmp_query_alias(self, event, tmp_id=None):
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


async def cmd_tmp_locate(self, event, tmp_id=None):
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


async def cmd_tmp_traffic(self, event, server=None):
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


async def cmd_tmp_rank_total(self, event):
    async for r in self.tmprank_total(event):
        yield r


async def cmd_tmp_rank_today(self, event):
    async for r in self.tmprank_today(event):
        yield r


async def cmd_tmp_today_footprint(self, event, server=None, tmp_id=None):
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


async def cmd_tmp_server(self, event):
    async for r in self.tmpserver(event):
        yield r


async def cmd_tmp_plugin_version(self, event):
    async for r in self.tmpversion(event):
        yield r


async def cmd_tmp_help(self, event):
    async for r in self.tmphelp(event):
        yield r
